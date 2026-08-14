"""Upload/storage failure tests — mock fault injection, zero production changes.

存储 OSError 按 P2-02 与依赖故障区分：exception_handler 统一映射 503
「存储服务异常」（非 500 编程错误）。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app as fastapi_app
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.documents.content_hash import sha256_hex
from app.services.ingestion.pipeline import process_document_ingestion
from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_upload_storage_write_fails(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upload write_bytes OSError -> HTTP 503 + no doc stored."""
    headers, user = await register_and_login(prefix="upload-storage-fail")
    kb = await _create_kb(client, headers, user, name="Write Fail KB")

    monkeypatch.setattr(
        "app.services.documents.upload.Path.write_bytes",
        lambda self, content: (_ for _ in ()).throw(OSError("disk full")),
    )

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("fail.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 503
    assert "存储服务异常" in resp.text

    import sqlalchemy as sa
    async with SessionLocal() as db:
        rows = (await db.execute(
            sa.select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )).scalars().all()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_preview_storage_unreadable(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """Preview after file deleted -> graceful error, no crash."""
    headers, user = await register_and_login(prefix="preview-unreadable")
    kb = await _create_kb(client, headers, user, name="Preview Fail KB")

    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("preview.md", b"# Hello\n\nWorld.", "text/markdown"))],
    )
    assert upload.status_code == 201
    doc_id = upload.json()["documents"][0]["id"]

    await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )

    preview = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/preview",
        headers=headers,
    )
    assert preview.status_code in (200, 404, 410, 503)


@pytest.mark.asyncio
async def test_ingestion_file_read_fails(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion pipeline: file open/read fails -> doc status=failed + Chinese error."""
    headers, user = await register_and_login(prefix="ingest-read-fail")
    kb = await _create_kb(client, headers, user, name="Read Fail KB")

    pdf_bytes = (
        Path(__file__).resolve().parent / "fixtures" / "golden_handbook.pdf"
    ).read_bytes()

    async def _skip_auto_enqueue(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "app.services.documents.upload.enqueue_document_ingestion",
        _skip_auto_enqueue,
    )

    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("data.pdf", pdf_bytes, "application/pdf"))],
    )
    assert upload.status_code == 201
    doc_id = uuid.UUID(upload.json()["documents"][0]["id"])

    monkeypatch.setattr(
        "app.services.ingestion.parser.Path.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("storage unavailable")),
    )

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message is not None
        assert "文档处理失败" in doc.error_message


def test_parse_document_magic_reads_only_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I1：魔数校验只读文件头 4 字节，不整读文件；错误口径不变。"""
    from app.services.ingestion import parser as parser_mod

    bad_pdf = tmp_path / "fake.pdf"
    bad_pdf.write_bytes(b"NOTPDF" * 1000)

    read_sizes: list[int] = []
    original_open = Path.open

    class _TrackingReader:
        def __init__(self, f):
            self._f = f

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            if size == -1 or size > 4:
                raise AssertionError(f"魔数校验不应整读文件: read({size})")
            return self._f.read(size)

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            self._f.close()
            return False

    def tracked_open(self, *args, **kwargs):
        return _TrackingReader(original_open(self, *args, **kwargs))

    monkeypatch.setattr(parser_mod.Path, "open", tracked_open)

    with pytest.raises(ValueError, match="文件格式不匹配：扩展名为 .pdf 但内容格式不符"):
        parser_mod.parse_document(bad_pdf, "pdf")

    assert read_sizes == [4]


def test_parse_document_magic_accepts_valid_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I1：合法 PK 文件头仍通过魔数校验，解析入口语义不变。"""
    from app.services.ingestion import parser as parser_mod

    docx = tmp_path / "ok.docx"
    docx.write_bytes(b"PK\x03\x04" + b"\x00" * 64)

    calls: list[Path] = []
    monkeypatch.setattr(parser_mod, "parse_docx", lambda path: calls.append(path) or [])

    assert parser_mod.parse_document(docx, "docx") == []
    assert calls == [docx]


@pytest.mark.asyncio
async def test_batch_upload_quota_failure_cleans_orphan_files(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I2：批量上传第二批超配额时，第一批已落盘文件不留孤儿。"""
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 6)
    headers, user = await register_and_login(prefix="upload-orphan-quota")
    kb = await _create_kb(client, headers, user, name="Orphan Quota KB")

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            ("files", ("first.txt", b"aaaa", "text/plain")),
            ("files", ("second.txt", b"bbbb", "text/plain")),
        ],
    )
    assert resp.status_code == 422
    assert "容量已达上限" in resp.text

    assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    import sqlalchemy as sa
    async with SessionLocal() as db:
        rows = (await db.execute(
            sa.select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )).scalars().all()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_upload_commit_failure_cleans_orphan_files(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I2：DB commit 失败时，已落盘文件被清理、不建文档行。"""
    headers, user = await register_and_login(prefix="upload-orphan-commit")
    kb = await _create_kb(client, headers, user, name="Orphan Commit KB")

    async def _fail_commit(self: AsyncSession) -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(AsyncSession, "commit", _fail_commit)

    transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/knowledge-bases/{kb['id']}/documents",
            headers=headers,
            files=[("files", ("only.txt", b"hello", "text/plain"))],
        )
    assert resp.status_code == 500

    assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    import sqlalchemy as sa
    async with SessionLocal() as db:
        rows = (await db.execute(
            sa.select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )).scalars().all()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_upload_overwrite_commit_failure_keeps_old_file(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I2：覆盖上传 commit 失败 → 清理新文件、旧版本文件与 DB 行保留。"""
    headers, user = await register_and_login(prefix="upload-orphan-overwrite")
    kb = await _create_kb(client, headers, user, name="Orphan Overwrite KB")

    first = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("same.txt", b"aaaa", "text/plain"))],
    )
    assert first.status_code == 201
    doc_id = first.json()["documents"][0]["id"]

    async with SessionLocal() as db:
        old_doc = await db.get(Document, uuid.UUID(doc_id))
        assert old_doc is not None
        old_path = Path(old_doc.storage_path)
    assert old_path.is_file()

    async def _fail_commit(self: AsyncSession) -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(AsyncSession, "commit", _fail_commit)

    transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/knowledge-bases/{kb['id']}/documents",
            headers=headers,
            files=[("files", ("same.txt", b"bbbb", "text/plain"))],
        )
    assert resp.status_code == 500

    assert old_path.is_file()
    assert [p for p in upload_dir.rglob("*") if p.is_file()] == [old_path]

    async with SessionLocal() as db:
        doc = await db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        assert Path(doc.storage_path) == old_path
        assert doc.content_sha256 == sha256_hex(b"aaaa")

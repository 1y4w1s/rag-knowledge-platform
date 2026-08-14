"""M8-I3 · OOXML zip 压缩炸弹防护（P1-I3）：守卫 + 上传审计 + parse 兜底。"""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ValidationError
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.services.documents.magic import (
    ZIP_BOMB_ERROR_CODE,
    assert_content_matches_extension,
    assert_zip_archive_safe,
)
from app.services.ingestion.parser import parse_document
from tests.conftest import create_test_kb as _create_kb

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_OOXML_OK = b"PK\x03\x04" + b"\x00" * 20  # 最小 PK 头，非合法 zip（NW-45 兼容）


def _minimal_docx_bytes(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types/>',
        )
        zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships/>')
        zf.writestr("word/document.xml", payload)
    return buf.getvalue()


def _bomb_docx_bytes() -> bytes:
    return _minimal_docx_bytes(b"A" * (5 * 1024 * 1024))


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def skip_ingestion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.documents.upload.enqueue_document_ingestion",
        AsyncMock(return_value=None),
    )


def test_default_zip_limits_are_positive() -> None:
    assert settings.zip_max_uncompressed_bytes > 0
    assert settings.zip_max_compression_ratio > 0


def test_valid_docx_bytes_pass_guard() -> None:
    content = _minimal_docx_bytes(b"hello ruige")
    assert_zip_archive_safe(content)
    assert_content_matches_extension("docx", content)


def test_valid_ooox_fixtures_pass_guard() -> None:
    for name in (
        _FIXTURES / "golden_handbook.docx",
        _FIXTURES / "m13_format" / "m13_ledger.xlsx",
        _FIXTURES / "m13_format" / "m13_deck.pptx",
    ):
        assert_zip_archive_safe(name)


def test_uncompressed_size_limit_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "zip_max_uncompressed_bytes", 1024)
    monkeypatch.setattr(settings, "zip_max_compression_ratio", 0.0)

    with pytest.raises(ValidationError) as ei:
        assert_zip_archive_safe(_minimal_docx_bytes(b"B" * 2048))

    extra = ei.value.extra or {}
    assert extra["error_code"] == ZIP_BOMB_ERROR_CODE
    assert extra["reason"] == "uncompressed_size"
    assert "安全上限" in ei.value.detail


def test_compression_ratio_limit_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "zip_max_compression_ratio", 10.0)

    with pytest.raises(ValidationError) as ei:
        assert_zip_archive_safe(_bomb_docx_bytes())

    extra = ei.value.extra or {}
    assert extra["error_code"] == ZIP_BOMB_ERROR_CODE
    assert extra["reason"] == "compression_ratio"
    assert "压缩比异常" in ei.value.detail


def test_bad_zip_still_passes_guard() -> None:
    assert_zip_archive_safe(_OOXML_OK)
    assert_content_matches_extension("docx", _OOXML_OK)


def test_empty_zip_passes_guard() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    assert_zip_archive_safe(buf.getvalue())


def test_guard_disabled_when_limits_non_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "zip_max_uncompressed_bytes", 0)
    monkeypatch.setattr(settings, "zip_max_compression_ratio", 0)
    assert_zip_archive_safe(_bomb_docx_bytes())


def test_guard_source_never_extracts_zip_content() -> None:
    magic_source = Path(assert_zip_archive_safe.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    parser_source = Path(parse_document.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    assert "zipfile.ZipFile" in magic_source
    assert "zf.infolist()" in magic_source
    # parser.py 既有魔数头读取含 f.read(4)，哨兵只盯 zip 解压 API
    for source in (magic_source, parser_source):
        assert "extractall(" not in source
        assert "extract(" not in source
    assert ".read(" not in magic_source


@pytest.mark.asyncio
async def test_upload_bomb_docx_rejected_with_audit(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="zip-bomb-upload")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            (
                "files",
                ("bomb.docx", _bomb_docx_bytes(), "application/octet-stream"),
            )
        ],
    )
    assert resp.status_code == 422, resp.text
    assert "压缩比异常" in resp.text

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
            )
        ).all()
        assert rows == []

        entry = await db.scalar(
            select(AuditLog)
            .where(
                AuditLog.kb_id == uuid.UUID(kb["id"]),
                AuditLog.action == "document.zip_bomb_rejected",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        assert entry is not None
        details = entry.details or {}
        assert details["error_code"] == ZIP_BOMB_ERROR_CODE
        assert details["reason"] == "compression_ratio"
        assert details["filename"] == "bomb.docx"

    assert [p for p in upload_dir.rglob("*") if p.is_file()] == []


@pytest.mark.asyncio
async def test_upload_valid_docx_still_201(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    skip_ingestion: None,
) -> None:
    headers, user = await register_and_login(prefix="zip-bomb-ok")
    kb = await _create_kb(client, headers, user)
    content = (_FIXTURES / "golden_handbook.docx").read_bytes()

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[
            (
                "files",
                ("handbook.docx", content, "application/octet-stream"),
            )
        ],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["documents"][0]["filename"] == "handbook.docx"


def test_parse_document_rejects_bomb_accepts_fixture(tmp_path: Path) -> None:
    bomb_path = tmp_path / "bomb.docx"
    bomb_path.write_bytes(_bomb_docx_bytes())

    with pytest.raises(ValueError) as ei:
        parse_document(bomb_path, "docx")
    assert "压缩比异常" in str(ei.value)

    blocks = parse_document(_FIXTURES / "golden_handbook.docx", "docx")
    assert blocks

"""同名上传覆盖语义与并发竞态（P2-I3）测试。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.services.documents.content_hash import sha256_hex
from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_upload_duplicate_filename_in_kb_overwrites(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """同名上传改为覆盖：复用同一文档行并递增版本，而不是 409。"""
    headers, user = await register_and_login(prefix="upload-dup-file")
    kb = await _create_kb(client, headers, user)

    first = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("handbook.txt", b"v1", "text/plain"))],
    )
    assert first.status_code == 201
    first_doc = first.json()["documents"][0]

    dup = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("handbook.txt", b"v2", "text/plain"))],
    )
    assert dup.status_code == 201
    dup_doc = dup.json()["documents"][0]
    assert dup_doc["id"] == first_doc["id"]

    case_dup = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("Handbook.TXT", b"v3", "text/plain"))],
    )
    assert case_dup.status_code == 201
    assert case_dup.json()["documents"][0]["id"] == first_doc["id"]

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.current_version == 3
        assert row.content_sha256 == sha256_hex(b"v3")
        versions = (
            await db.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == row.id)
            )
        ).scalars().all()
        assert len(versions) == 2


@pytest.mark.asyncio
async def test_concurrent_same_name_uploads_keep_single_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-I3：两个并发同名上传只保留一条文档，后到者走覆盖而非再插一条。"""
    from app.services.documents import upload as upload_mod

    headers, user = await register_and_login(prefix="upload-race")
    kb = await _create_kb(client, headers, user, name="并发同名库")

    # 拉宽“查已有文件名”之前的窗口，确保两个请求同时越过初查再竞争。
    barrier = asyncio.Barrier(2)
    original_lock = upload_mod._lock_filename

    async def _gated_lock(*args, **kwargs) -> None:
        await barrier.wait()
        await original_lock(*args, **kwargs)

    async def _noop_enqueue(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(upload_mod, "_lock_filename", _gated_lock)
    monkeypatch.setattr(upload_mod, "enqueue_document_ingestion", _noop_enqueue)

    async def _upload(content: bytes):
        return await client.post(
            f"/api/v1/knowledge-bases/{kb['id']}/documents",
            headers=headers,
            files=[("files", ("race.txt", content, "text/plain"))],
        )

    resp_a, resp_b = await asyncio.gather(
        _upload(b"race content a"),
        _upload(b"race content b"),
    )
    assert resp_a.status_code == 201, resp_a.text
    assert resp_b.status_code == 201, resp_b.text

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
            )
        ).scalars().all()
        assert len(rows) == 1
        doc = rows[0]
        assert doc.current_version == 2
        versions = (
            await db.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
            )
        ).scalars().all()
        assert len(versions) == 1
        hashes = {doc.content_sha256, versions[0].content_sha256}
        assert hashes == {
            sha256_hex(b"race content a"),
            sha256_hex(b"race content b"),
        }

"""Upload/storage failure tests — mock fault injection, zero production changes.

With OSError → 500 exception_handler now registered.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
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
    """Upload write_bytes OSError -> HTTP 500 + no doc stored."""
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
    assert resp.status_code == 500
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
    """Ingestion pipeline: read_bytes fails -> doc status=failed + Chinese error."""
    headers, user = await register_and_login(prefix="ingest-read-fail")
    kb = await _create_kb(client, headers, user, name="Read Fail KB")

    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("data.txt", b"sensitive content", "text/plain"))],
    )
    assert upload.status_code == 201
    doc_id = uuid.UUID(upload.json()["documents"][0]["id"])

    monkeypatch.setattr(
        "app.services.ingestion.parser.Path.read_bytes",
        lambda self: (_ for _ in ()).throw(OSError("storage unavailable")),
    )
    import os
    monkeypatch.setattr(
        "app.services.ingestion.parser.Path.stat",
        lambda self: os.stat_result((0o644, 0, 0, 1, 0, 0, 100, 0, 0, 0)),
    )

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message is not None

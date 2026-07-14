"""Embedding service 5xx tests — mock fault injection, zero production changes."""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from tests.conftest import create_test_kb as _create_kb


@pytest.mark.asyncio
async def test_embed_texts_5xx_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embed_texts raises HTTPStatusError on 5xx."""
    from app.services.ingestion import embedder as mod

    monkeypatch.setattr(settings, "embedding_provider", "tongyi")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-fake-5xx")

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a, **kw): pass
        async def post(self, *a, **kw):
            resp = httpx.Response(503, request=httpx.Request("POST", "http://test"))
            resp.raise_for_status()
            return resp  # unreachable

    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    with pytest.raises(httpx.HTTPStatusError):
        await mod.embed_texts(["test text"])


@pytest.mark.asyncio
async def test_ingestion_embedding_5xx_document_failed(
    client: AsyncClient,
    register_and_login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion: embedding 5xx -> doc status=failed."""
    from app.services.ingestion import embedder as mod

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "embedding_provider", "tongyi")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-fake-5xx")

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a, **kw): pass
        async def post(self, *a, **kw):
            resp = httpx.Response(503, request=httpx.Request("POST", "http://test"))
            resp.raise_for_status()
            return resp  # unreachable

    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    headers, user = await register_and_login(prefix="embed-5xx-ingest")
    kb = await _create_kb(client, headers, user, name="Embed 5xx KB")
    kb_id = kb["id"]

    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", ("hello.txt", b"Annual leave 10 days.", "text/plain"))],
    )
    assert upload.status_code == 201
    doc_id = upload.json()["documents"][0]["id"]

    import asyncio
    await asyncio.sleep(2)

    async with SessionLocal() as db:
        doc = await db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message is not None
        assert "500" not in doc.error_message

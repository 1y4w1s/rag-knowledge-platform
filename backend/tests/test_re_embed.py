"""Plan-RAG R2-4：全库重嵌入 stale chunk 检测与批量更新。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD = FIXTURES / "golden_handbook.md"


async def _ingest_golden_md(*, kb_id: uuid.UUID, user_id: uuid.UUID, upload_dir: Path) -> uuid.UUID:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.md"
    storage_path.write_bytes(GOLDEN_MD.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=GOLDEN_MD.name,
            file_type="md",
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)
    return doc_id


async def _load_searchable_chunks(document_id: uuid.UUID) -> list[DocumentChunk]:
    async with SessionLocal() as db:
        result = await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.chunk_kind != "parent")
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.all())


@pytest.mark.asyncio
async def test_ingestion_tags_embedding_model(
    register_and_login,
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-v2")

    headers, user = await register_and_login(prefix="reembed-tag")
    from tests.conftest import create_test_kb

    kb = await create_test_kb(client, headers, user, name="重嵌标签库")
    doc_id = await _ingest_golden_md(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        upload_dir=tmp_path,
    )
    chunks = await _load_searchable_chunks(doc_id)
    assert chunks
    assert all(c.embedding_model == "text-embedding-v2" for c in chunks)


@pytest.mark.asyncio
async def test_re_embed_updates_stale_chunks_only(
    register_and_login,
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-v2")

    headers, user = await register_and_login(prefix="reembed-stale")
    from tests.conftest import create_test_kb

    kb = await create_test_kb(client, headers, user, name="重嵌库")
    kb_id = uuid.UUID(kb["id"])
    doc_id = await _ingest_golden_md(kb_id=kb_id, user_id=uuid.UUID(user["id"]), upload_dir=tmp_path)

    async with SessionLocal() as db:
        parent = await db.scalar(
            select(DocumentChunk).where(
                DocumentChunk.document_id == doc_id,
                DocumentChunk.chunk_kind == "parent",
            )
        )
        searchable = await _load_searchable_chunks(doc_id)

        for chunk in searchable:
            chunk.embedding_model = "legacy-model"
        if parent is not None:
            parent.embedding_model = "legacy-model"
        await db.commit()

    monkeypatch.setattr(settings, "embedding_model", "text-embedding-v3")

    assert await count_stale_chunks(kb_id=kb_id) == len(searchable)

    result = await re_embed_all_chunks(kb_id=kb_id)
    assert result["status"] == "completed"
    assert result["updated"] == len(searchable)
    assert result["embedding_model"] == "text-embedding-v3"

    chunks_after = await _load_searchable_chunks(doc_id)
    assert all(c.embedding_model == "text-embedding-v3" for c in chunks_after)
    assert all(c.embedding is not None for c in chunks_after)

    if parent is not None:
        async with SessionLocal() as db:
            parent_row = await db.get(DocumentChunk, parent.id)
            assert parent_row is not None
            assert parent_row.embedding_model == "legacy-model"

    assert await count_stale_chunks(kb_id=kb_id) == 0

    # 向量应已重写（mock 下同文同向量，但流程须跑通）
    for chunk in chunks_after:
        assert chunk.embedding is not None


@pytest.mark.asyncio
async def test_internal_re_embed_api_requires_token(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "re_embed_token", "")

    resp = await client.post(
        "/api/v1/internal/re-embed",
        headers={"X-Re-Embed-Token": "anything"},
    )
    assert resp.status_code == 404

    monkeypatch.setattr(settings, "re_embed_token", "secret-token")

    bad = await client.post(
        "/api/v1/internal/re-embed",
        headers={"X-Re-Embed-Token": "wrong"},
    )
    assert bad.status_code == 403

    ok = await client.post(
        "/api/v1/internal/re-embed",
        headers={"X-Re-Embed-Token": "secret-token"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "started"
    assert "stale_chunks" in body

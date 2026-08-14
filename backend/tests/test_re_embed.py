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
from app.services.ingestion.embedder import (
    current_bge_en_model,
    current_embedding_model,
    embed_texts,
)
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks
from tests.fixtures.audit_events import _register_org_admin

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


async def _seed_reembed_chunk(
    db,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    content: str,
    embedding: list[float] | None = None,
    embedding_en: list[float] | None = None,
    embedding_model: str | None = None,
    embedding_en_model: str | None = None,
    chunk_kind: str = "text",
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename="reembed-en.txt",
            file_type="txt",
            file_size=len(content),
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=1,
            uploaded_by=uploaded_by,
        )
    )
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=0,
            content=content,
            embedding=embedding,
            embedding_en=embedding_en,
            embedding_model=embedding_model,
            embedding_en_model=embedding_en_model,
            chunk_kind=chunk_kind,
        )
    )
    await db.flush()
    return chunk_id


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
async def test_re_embed_rebuilds_stale_en_vectors_within_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    """旧 EN 模型 chunk 计入 stale；重建只更新 stale 列并保留 kb 范围。"""
    from tests.conftest import create_test_kb

    headers, user = await register_and_login(prefix="reembed-en-m2b")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="重嵌 EN 库",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    content = "Annual leave policy after one year"
    vec = (await embed_texts([content]))[0]
    en_vec = (await embed_texts([content], provider="bge_en"))[0]
    current_main = current_embedding_model()
    current_en = current_bge_en_model()

    async with SessionLocal() as db:
        en_only = await _seed_reembed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=content,
            embedding=vec,
            embedding_en=en_vec,
            embedding_model=current_main,
            embedding_en_model="legacy-en-model",
        )
        both_stale = await _seed_reembed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=content + " renewal",
            embedding=vec,
            embedding_en=en_vec,
            embedding_model="legacy-main-model",
            embedding_en_model="legacy-en-model",
        )
        fresh = await _seed_reembed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=content + " carryover",
            embedding=vec,
            embedding_en=en_vec,
            embedding_model=current_main,
            embedding_en_model=current_en,
        )
        parent = await _seed_reembed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=content + " parent",
            embedding=None,
            embedding_en=en_vec,
            embedding_model="legacy-main-model",
            embedding_en_model="legacy-en-model",
            chunk_kind="parent",
        )
        await db.commit()

    assert await count_stale_chunks(kb_id=kb_id) == 2

    result = await re_embed_all_chunks(kb_id=kb_id)
    assert result["status"] == "completed"
    assert result["updated"] == 2

    async with SessionLocal() as db:
        rows = {
            row.id: row
            for row in await db.scalars(
                select(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
            )
        }

    assert rows[en_only].embedding_model == current_main
    assert rows[en_only].embedding_en is not None
    assert rows[en_only].embedding_en_model == current_en

    assert rows[both_stale].embedding_model == current_main
    assert rows[both_stale].embedding is not None
    assert rows[both_stale].embedding_en is not None
    assert rows[both_stale].embedding_en_model == current_en

    assert rows[fresh].embedding_en_model == current_en
    assert rows[parent].embedding_model == "legacy-main-model"
    assert rows[parent].embedding_en_model == "legacy-en-model"

    assert await count_stale_chunks(kb_id=kb_id) == 0


@pytest.mark.asyncio
async def test_internal_re_embed_api_requires_token(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # F2：内部端点须 JWT + 静态令牌双因子
    headers, _ = await _register_org_admin(client, prefix="re-embed-int")

    monkeypatch.setattr(settings, "re_embed_token", "")

    resp = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "anything"},
    )
    assert resp.status_code == 404

    monkeypatch.setattr(settings, "re_embed_token", "secret-token")

    bad = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "wrong"},
    )
    assert bad.status_code == 403

    ok = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "started"
    assert "stale_chunks" in body
    assert "operator" in body

"""P1-11 EN 覆盖度补嵌：count_en_gap_chunks / re_embed_en_gap_chunks / API mode=en_gap。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion import re_embed as re_embed_mod
from app.services.ingestion.embedder import current_bge_en_model, embed_texts
from app.services.ingestion.re_embed import count_en_gap_chunks, re_embed_en_gap_chunks
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _latest_audit_log

EN_CONTENT = "What is the annual leave policy after one full year?"
ZH_CONTENT = "员工年假满一年可休十天"
MAIN_MODEL = "text-embedding-v2"


async def _seed_chunk(
    db: AsyncSession,
    *,
    doc_id: UUID,
    kb_id: UUID,
    content: str,
    chunk_index: int,
    embedding_en: list[float] | None = None,
    embedding_en_model: str | None = None,
    chunk_kind: str = "text",
) -> UUID:
    chunk_id = uuid.uuid4()
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=chunk_index,
            content=content,
            embedding=[0.1] * 512,
            embedding_en=embedding_en,
            embedding_model=MAIN_MODEL,
            embedding_en_model=embedding_en_model,
            chunk_kind=chunk_kind,
        )
    )
    if chunk_kind != "parent":
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
                "WHERE id = :chunk_id"
            ),
            {"src": content, "chunk_id": chunk_id},
        )
    await db.flush()
    return chunk_id


async def _seed_document(
    db: AsyncSession,
    *,
    kb_id: UUID,
    uploaded_by: UUID,
    contents: list[str],
    embedding_en: list[float] | None = None,
    embedding_en_model: str | None = None,
    chunk_kind: str = "text",
    deleted_at: datetime | None = None,
) -> UUID:
    doc_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename="en-gap.txt",
            file_type="txt",
            file_size=sum(len(c) for c in contents),
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=len(contents),
            uploaded_by=uploaded_by,
            deleted_at=deleted_at,
        )
    )
    if embedding_en is not None and embedding_en_model is None:
        embedding_en_model = current_bge_en_model()
    for idx, content in enumerate(contents):
        await _seed_chunk(
            db,
            doc_id=doc_id,
            kb_id=kb_id,
            content=content,
            chunk_index=idx,
            embedding_en=embedding_en,
            embedding_en_model=embedding_en_model,
            chunk_kind=chunk_kind,
        )
    return doc_id


async def _chunk_tsv_texts(kb_id: UUID) -> dict[UUID, str]:
    async with SessionLocal() as db:
        rows = await db.execute(
            text(
                "SELECT id::text, content_tsv::text FROM document_chunks "
                "WHERE kb_id = :kb_id"
            ),
            {"kb_id": str(kb_id)},
        )
        return {UUID(row[0]): row[1] for row in rows.all()}


@pytest.mark.asyncio
async def test_count_en_gap_chunks_scopes_english_docs_only(
    client: AsyncClient,
    register_and_login,
) -> None:
    """口径：只统计偏英文档内可检索 chunk 的 EN 空缺口。"""
    headers, user = await register_and_login(prefix="en-gap-count")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-gap-count",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    en_vec = (await embed_texts([EN_CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        english_doc = await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT, EN_CONTENT + " carryover", EN_CONTENT + " renewal"],
        )
        await _seed_chunk(
            db,
            doc_id=english_doc,
            kb_id=kb_id,
            content=EN_CONTENT + " parent",
            chunk_index=99,
            chunk_kind="parent",
        )
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT + " covered"],
            embedding_en=en_vec,
        )
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[ZH_CONTENT, ZH_CONTENT + " 二"],
        )
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT + " deleted"],
            deleted_at=datetime.now(timezone.utc),
        )
        await db.commit()

    assert await count_en_gap_chunks(kb_id=kb_id) == 3


@pytest.mark.asyncio
async def test_re_embed_en_gap_writes_en_only_and_is_idempotent(
    client: AsyncClient,
    register_and_login,
) -> None:
    """补嵌只写 EN 列与模型列；主列/模型列/content_tsv 不变；重跑 updated=0。"""
    headers, user = await register_and_login(prefix="en-gap-write")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-gap-write",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    en_vec = (await embed_texts([EN_CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        english_doc = await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT, EN_CONTENT + " renewal"],
        )
        await _seed_chunk(
            db,
            doc_id=english_doc,
            kb_id=kb_id,
            content=EN_CONTENT + " covered",
            chunk_index=2,
            embedding_en=en_vec,
        )
        await _seed_chunk(
            db,
            doc_id=english_doc,
            kb_id=kb_id,
            content=EN_CONTENT + " parent",
            chunk_index=99,
            chunk_kind="parent",
        )
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[ZH_CONTENT],
        )
        await db.commit()

    tsv_before = await _chunk_tsv_texts(kb_id)
    result = await re_embed_en_gap_chunks(kb_id=kb_id)
    assert result["status"] == "completed"
    assert result["updated"] == 2
    assert result["errors"] == 0
    assert result["en_model"] == current_bge_en_model()
    assert result["kb_id"] == str(kb_id)

    async with SessionLocal() as db:
        rows = list(
            await db.scalars(
                select(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
            )
        )
        by_index = {row.chunk_index: row for row in rows}

    assert by_index[0].embedding_en is not None
    assert by_index[0].embedding_en_model == current_bge_en_model()
    assert by_index[1].embedding_en is not None
    assert by_index[1].embedding_en_model == current_bge_en_model()
    assert list(by_index[2].embedding_en) == en_vec
    assert by_index[99].embedding_en is None
    zh = [row for row in rows if row.chunk_kind != "parent" and row.chunk_index == 0 and row.document_id != english_doc]
    assert len(zh) == 1
    assert zh[0].embedding_en is None
    for row in rows:
        assert row.embedding is not None
        assert row.embedding_model == MAIN_MODEL

    assert await _chunk_tsv_texts(kb_id) == tsv_before
    assert await count_en_gap_chunks(kb_id=kb_id) == 0

    rerun = await re_embed_en_gap_chunks(kb_id=kb_id)
    assert rerun["status"] == "completed"
    assert rerun["updated"] == 0


@pytest.mark.asyncio
async def test_api_en_gap_requires_kb_id_and_audits(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """en_gap 缺 kb_id → 422；带 kb_id 触发补嵌并写含 mode 的审计。"""
    headers, user = await register_and_login(prefix="en-gap-api")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-gap-api",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT, EN_CONTENT + " renewal"],
        )
        await db.commit()

    missing = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
        json={"mode": "en_gap"},
    )
    assert missing.status_code == 422

    resp = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
        json={"mode": "en_gap", "kb_id": str(kb_id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"
    assert body["en_gap_chunks"] == 2
    assert body["en_model"] == current_bge_en_model()
    assert body["operator"] == str(user["id"])
    assert body["kb_id"] == str(kb_id)

    for _ in range(100):
        if await count_en_gap_chunks(kb_id=kb_id) == 0:
            break
        await asyncio.sleep(0.05)
    assert await count_en_gap_chunks(kb_id=kb_id) == 0

    log = await _latest_audit_log(action="re_embed_trigger")
    assert log is not None
    assert log.kb_id == kb_id
    assert log.details is not None
    assert log.details["mode"] == "en_gap"
    assert log.details["en_gap_chunks"] == 2
    assert log.details["en_model"] == current_bge_en_model()
    assert log.details["kb_id"] == str(kb_id)


@pytest.mark.asyncio
async def test_api_default_mode_stale_unchanged(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺省 mode=stale 仍走既有 stale 链路，响应与审计不带 en_gap 字段。"""
    headers, user = await register_and_login(prefix="en-gap-stale-api")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-gap-stale-api",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT],
        )
        await db.execute(
            text(
                "UPDATE document_chunks SET embedding_model = 'legacy-model' "
                "WHERE kb_id = :kb_id"
            ),
            {"kb_id": str(kb_id)},
        )
        await db.commit()

    resp = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
        json={"kb_id": str(kb_id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"
    assert body["stale_chunks"] == 1
    assert "en_gap_chunks" not in body

    from app.services.ingestion.re_embed import count_stale_chunks

    for _ in range(100):
        if await count_stale_chunks(kb_id=kb_id) == 0:
            break
        await asyncio.sleep(0.05)
    assert await count_stale_chunks(kb_id=kb_id) == 0

    log = await _latest_audit_log(action="re_embed_trigger")
    assert log is not None
    assert log.details is not None
    assert "mode" not in log.details
    assert log.details["stale_chunks"] == 1
    assert log.kb_id == kb_id


@pytest.mark.asyncio
async def test_re_embed_en_gap_partial_on_batch_failure(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单批 embed_texts 抛错 → partial；已 commit 批次保留，剩余缺口可续跑。"""
    headers, user = await register_and_login(prefix="en-gap-partial")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-gap-partial",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_document(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            contents=[EN_CONTENT + f" {i}" for i in range(30)],
        )
        await db.commit()

    original_embed = re_embed_mod.embed_texts
    calls = 0

    async def _flaky(texts, provider=None):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("embedding provider unavailable")
        return await original_embed(texts, provider=provider)

    monkeypatch.setattr(re_embed_mod, "embed_texts", _flaky)

    result = await re_embed_en_gap_chunks(kb_id=kb_id)
    assert result["status"] == "partial"
    assert result["updated"] == 25
    assert result["errors"] == 5
    assert result["en_model"] == current_bge_en_model()

    async with SessionLocal() as db:
        filled = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.kb_id == kb_id)
            .where(DocumentChunk.embedding_en.is_not(None))
        )
        remaining = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.kb_id == kb_id)
            .where(DocumentChunk.embedding_en.is_(None))
        )
    assert int(filled) == 25
    assert int(remaining) == 5
    assert await count_en_gap_chunks(kb_id=kb_id) == 5

    rerun = await re_embed_en_gap_chunks(kb_id=kb_id)
    assert rerun["status"] == "completed"
    assert rerun["updated"] == 5
    assert await count_en_gap_chunks(kb_id=kb_id) == 0


@pytest.mark.asyncio
async def test_re_embed_en_gap_skipped_when_lock_held() -> None:
    """锁被占用时返回 skipped，与 stale 链路共用锁语义。"""
    async with re_embed_mod._re_embed_lock:
        result = await re_embed_en_gap_chunks(kb_id=uuid.uuid4())
    assert result["status"] == "skipped"
    assert result["reason"] == "already_running"

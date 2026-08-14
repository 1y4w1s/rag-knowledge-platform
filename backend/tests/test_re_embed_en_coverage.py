"""P1-11 M2 follow-up：/internal/re-embed/status 返回 EN 列覆盖度（方案 B 成本评估）。"""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.embedder import current_bge_en_model, embed_texts
from app.services.ingestion.re_embed import (
    count_embedding_en_coverage,
    count_stale_chunks,
)
from app.services.rag.cjk import segment_cjk
from app.services.rag.vector_recall import vector_recall
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _latest_audit_log, _register_org_admin

MODEL = "text-embedding-v2"
LEGACY_MODEL = "legacy-model"
CONTENT = "员工年假满一年可休十天"


async def _fake_stale(*, kb_id: UUID | None = None) -> int:
    return 7


async def _fake_coverage(*, kb_id: UUID | None = None) -> dict[str, object]:
    return {
        "searchable_chunks": 12,
        "embedding_en_chunks": 4,
        "embedding_en_coverage": 1 / 3,
    }


async def _seed_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    content: str,
    embedding: list[float] | None = None,
    embedding_en: list[float] | None = None,
    embedding_model: str = MODEL,
    embedding_en_model: str | None = None,
    chunk_kind: str = "text",
) -> tuple[uuid.UUID, uuid.UUID]:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename="en-coverage.txt",
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
    if chunk_kind != "parent":
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
                "WHERE id = :chunk_id"
            ),
            {"src": segment_cjk(content), "chunk_id": chunk_id},
        )
    return doc_id, chunk_id


@pytest.mark.asyncio
async def test_embedding_en_coverage_counts_searchable_chunks_only(
    client: AsyncClient,
    register_and_login,
) -> None:
    """覆盖度口径：只统计可检索 chunk，parent 不计入；无 EN 向量计为未覆盖。"""
    headers, user = await register_and_login(prefix="en-cov-unit")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-coverage-unit",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_en=en_vec,
        )
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 二",
            embedding=vec,
            embedding_en=en_vec,
        )
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 三",
            embedding=vec,
            embedding_en=None,
        )
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " parent",
            embedding=None,
            embedding_en=en_vec,
            chunk_kind="parent",
        )
        await db.commit()

    stats = await count_embedding_en_coverage(kb_id=kb_id)
    assert stats["searchable_chunks"] == 3
    assert stats["embedding_en_chunks"] == 2
    assert stats["embedding_en_coverage"] == pytest.approx(2 / 3, abs=1e-4)


@pytest.mark.asyncio
async def test_re_embed_status_returns_en_coverage_fields(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """status 接口返回 EN 非空计数/占比（计数语义由单测钉死，此处验证接线）。"""
    headers, _ = await _register_org_admin(client, prefix="en-cov-status")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")

    import app.api.internal as internal_api

    monkeypatch.setattr(internal_api, "count_stale_chunks", _fake_stale)
    monkeypatch.setattr(internal_api, "count_embedding_en_coverage", _fake_coverage)

    resp = await client.get(
        "/api/v1/internal/re-embed/status",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stale_chunks"] == 7
    assert body["searchable_chunks"] == 12
    assert body["embedding_en_chunks"] == 4
    assert body["embedding_en_coverage"] == pytest.approx(1 / 3)
    assert body["embedding_model"] == settings.embedding_model
    assert body["provider"] == settings.embedding_provider
    assert "operator" in body


@pytest.mark.asyncio
async def test_re_embed_status_observability_does_not_change_retrieval(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """观测只读：EN 列按模型过滤，旧模型/NULL 列 EN chunk 不再被英轨召回，主列行为不变。"""
    headers, user = await register_and_login(prefix="en-cov-retr")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")
    kb = await create_test_kb(
        client,
        headers,
        user,
        name="en-coverage-retr",
        workspace_kind="personal",
    )
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        _, en_null_model_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_model=LEGACY_MODEL,
        )
        _, en_old_model_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 旧模型",
            embedding=None,
            embedding_en=en_vec,
            embedding_model=LEGACY_MODEL,
            embedding_en_model="legacy-en-model",
        )
        _, en_current_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 当前",
            embedding=None,
            embedding_en=en_vec,
            embedding_model=LEGACY_MODEL,
            embedding_en_model=current_bge_en_model(),
        )
        _, main_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 主列旧模型",
            embedding=vec,
            embedding_en=None,
            embedding_model=LEGACY_MODEL,
        )
        await db.commit()

    status_resp = await client.get(
        "/api/v1/internal/re-embed/status",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
    )
    assert status_resp.status_code == 200
    assert "embedding_en_coverage" in status_resp.json()

    async with SessionLocal() as db:
        en_rows = await vector_recall(
            db,
            kb_id=kb_id,
            query_vec=en_vec,
            limit=10,
            embedding_col="embedding_en",
        )
        main_rows = await vector_recall(
            db,
            kb_id=kb_id,
            query_vec=vec,
            limit=10,
        )

    assert {row.chunk.id for row in en_rows} == {en_current_chunk}
    assert en_null_model_chunk not in {row.chunk.id for row in en_rows}
    assert en_old_model_chunk not in {row.chunk.id for row in en_rows}
    assert {row.chunk.id for row in main_rows} == set()


@pytest.mark.asyncio
async def test_internal_re_embed_api_kb_id_scopes_and_audits(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kb_id 触发只统计/重嵌目标库，审计事件记录 kb_id。"""
    headers, user = await register_and_login(prefix="reembed-kb-api")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")
    kb_a = await create_test_kb(
        client,
        headers,
        user,
        name="reembed-kb-a",
        workspace_kind="personal",
    )
    kb_b = await create_test_kb(
        client,
        headers,
        user,
        name="reembed-kb-b",
        workspace_kind="personal",
    )
    kb_a_id = uuid.UUID(kb_a["id"])
    kb_b_id = uuid.UUID(kb_b["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=kb_a_id,
            uploaded_by=user_id,
            content="stale-a",
            embedding_model="legacy-model",
        )
        await _seed_chunk(
            db,
            kb_id=kb_b_id,
            uploaded_by=user_id,
            content="stale-b",
            embedding_model="legacy-model",
        )
        await db.commit()

    resp = await client.post(
        "/api/v1/internal/re-embed",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
        json={"kb_id": str(kb_a_id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"
    assert body["stale_chunks"] == 1
    assert body["kb_id"] == str(kb_a_id)

    for _ in range(100):
        if await count_stale_chunks(kb_id=kb_a_id) == 0:
            break
        await asyncio.sleep(0.05)
    assert await count_stale_chunks(kb_id=kb_a_id) == 0
    assert await count_stale_chunks(kb_id=kb_b_id) == 1

    log = await _latest_audit_log(action="re_embed_trigger")
    assert log is not None
    assert log.kb_id == kb_a_id
    assert log.details is not None
    assert log.details["kb_id"] == str(kb_a_id)


@pytest.mark.asyncio
async def test_internal_re_embed_status_kb_id_scopes_stats(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """status 按 kb_id 只返回该库的 stale 与 EN 覆盖度。"""
    headers, user = await register_and_login(prefix="reembed-status-kb")
    monkeypatch.setattr(settings, "re_embed_token", "secret-token")
    kb_a = await create_test_kb(
        client,
        headers,
        user,
        name="reembed-status-a",
        workspace_kind="personal",
    )
    kb_b = await create_test_kb(
        client,
        headers,
        user,
        name="reembed-status-b",
        workspace_kind="personal",
    )
    kb_a_id = uuid.UUID(kb_a["id"])
    kb_b_id = uuid.UUID(kb_b["id"])
    user_id = uuid.UUID(user["id"])
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=kb_a_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding_en=en_vec,
        )
        await _seed_chunk(
            db,
            kb_id=kb_a_id,
            uploaded_by=user_id,
            content=CONTENT + " 无英嵌",
            embedding_en=None,
        )
        await _seed_chunk(
            db,
            kb_id=kb_b_id,
            uploaded_by=user_id,
            content=CONTENT + " 另一库",
            embedding_en=en_vec,
        )
        await db.commit()

    resp = await client.get(
        "/api/v1/internal/re-embed/status",
        headers={**headers, "X-Re-Embed-Token": "secret-token"},
        params={"kb_id": str(kb_a_id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["searchable_chunks"] == 2
    assert body["embedding_en_chunks"] == 1
    assert body["stale_chunks"] == 2
    assert body["kb_id"] == str(kb_a_id)

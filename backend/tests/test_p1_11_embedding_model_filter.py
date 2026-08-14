"""P1-11：主列与 EN 列均按当前嵌入模型过滤（方案 A · M1 + 方案 B · M2c）。"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.scope_utils import kb_scope_clause
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.embedder import current_bge_en_model, embed_texts
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks
from app.services.rag.cjk import segment_cjk
from app.services.rag.multi_query import (
    multi_query_kb_recall,
    multi_query_workspace_recall,
)
from app.services.rag.vector_recall import _vector_recall_workspace, vector_recall
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import create_test_kb as _create_kb

MODEL = "text-embedding-v2"
LEGACY_MODEL = "legacy-model"
CONTENT = "员工年假满一年可休十天"


@pytest.fixture(autouse=True)
def _current_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_model", MODEL)


async def _create_personal_kb(
    client: AsyncClient,
    register_and_login,
    *,
    prefix: str,
) -> tuple[dict, dict, UUID]:
    headers, user = await register_and_login(prefix=prefix)
    kb = await _create_kb(
        client,
        headers,
        user,
        name=f"p1-11-{uuid.uuid4().hex[:8]}",
        workspace_kind="personal",
    )
    return headers, user, uuid.UUID(kb["id"])


async def _seed_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    content: str,
    embedding: list[float],
    embedding_model: str,
    embedding_en: list[float] | None = None,
    embedding_en_model: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename="p1-11.txt",
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
            embedding_en_model=embedding_en_model,
            embedding_model=embedding_model,
        )
    )
    await db.flush()
    await db.execute(
        text(
            "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
            "WHERE id = :chunk_id"
        ),
        {"src": segment_cjk(content), "chunk_id": chunk_id},
    )
    return doc_id, chunk_id


@pytest.mark.asyncio
async def test_vector_recall_kb_excludes_old_model_chunk(
    client: AsyncClient,
    register_and_login,
) -> None:
    """KB 主列：旧模型 chunk 不入向量召回，当前模型 chunk 正常召回。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-kb"
    )
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=LEGACY_MODEL,
        )
        _, cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=MODEL,
        )
        await db.commit()

        rows = await vector_recall(db, kb_id=kb_id, query_vec=vec, limit=10)

    ids = {row.chunk.id for row in rows}
    assert cur_chunk in ids
    assert old_chunk not in ids


@pytest.mark.asyncio
async def test_vector_recall_workspace_excludes_old_model_chunk(
    client: AsyncClient,
    register_and_login,
) -> None:
    """workspace 主列：与 KB 同口径，旧模型 chunk 不入向量召回。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-ws"
    )
    user_id = uuid.UUID(user["id"])
    scope = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )
    vec = (await embed_texts([CONTENT]))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=LEGACY_MODEL,
        )
        _, cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=MODEL,
        )
        await db.commit()

        rows = await _vector_recall_workspace(
            db,
            query_vec=vec,
            limit=10,
            scope=scope,
            org_scope=None,
        )

    ids = {row.chunk.id for row in rows}
    assert cur_chunk in ids
    assert old_chunk not in ids


@pytest.mark.asyncio
async def test_multi_query_uses_same_model_filter_for_kb_and_workspace(
    client: AsyncClient,
    register_and_login,
) -> None:
    """multi_query 复用同一过滤：旧模型 chunk 只能以 FTS 身份进入 merged。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-mq"
    )
    user_id = uuid.UUID(user["id"])
    scope = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )
    scope_clause = kb_scope_clause(scope, None)
    vec = (await embed_texts([CONTENT]))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=LEGACY_MODEL,
        )
        _, cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=MODEL,
        )
        await db.commit()

        _, merged_kb, _ = await multi_query_kb_recall(
            db,
            kb_id=kb_id,
            query=CONTENT,
            vector_limit=10,
            fts_limit=10,
            top_n=20,
            use_mock=True,
        )
        _, merged_ws, _ = await multi_query_workspace_recall(
            db,
            query=CONTENT,
            scope=scope,
            org_scope=None,
            vector_limit=10,
            fts_limit=10,
            top_n=20,
            use_mock=True,
            scope_clause=scope_clause,
        )

    for merged in (merged_kb, merged_ws):
        assert cur_chunk in merged
        assert merged[cur_chunk].vector_similarity is not None
        assert old_chunk in merged, "旧模型 chunk 仍应经 FTS 保底召回"
        assert merged[old_chunk].vector_similarity is None
        vector_ids = {
            cid for cid, row in merged.items() if row.vector_similarity is not None
        }
        assert old_chunk not in vector_ids


@pytest.mark.asyncio
async def test_en_column_recall_filters_old_en_model_chunk(
    client: AsyncClient,
    register_and_login,
) -> None:
    """M2c EN 列：旧/缺失 EN 模型 chunk 不入英轨召回，当前模型 chunk 命中。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-en-kb"
    )
    user_id = uuid.UUID(user["id"])
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_en_model="legacy-en-model",
            embedding_model=LEGACY_MODEL,
        )
        _, null_model_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_en_model=None,
            embedding_model=LEGACY_MODEL,
        )
        _, cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_en_model=current_bge_en_model(),
            embedding_model=LEGACY_MODEL,
        )
        await db.commit()

        rows = await vector_recall(
            db,
            kb_id=kb_id,
            query_vec=en_vec,
            limit=10,
            embedding_col="embedding_en",
        )

    ids = {row.chunk.id for row in rows}
    assert cur_chunk in ids
    assert old_chunk not in ids
    assert null_model_chunk not in ids


@pytest.mark.asyncio
async def test_en_workspace_recall_filters_old_en_model_chunk(
    client: AsyncClient,
    register_and_login,
) -> None:
    """M2c workspace EN 列：与 KB 同口径，旧 EN 模型 chunk 不入英轨召回。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-en-ws"
    )
    user_id = uuid.UUID(user["id"])
    scope = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_en_model="legacy-en-model",
            embedding_model=LEGACY_MODEL,
        )
        _, cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=None,
            embedding_en=en_vec,
            embedding_en_model=current_bge_en_model(),
            embedding_model=MODEL,
        )
        await db.commit()

        rows = await _vector_recall_workspace(
            db,
            query_vec=en_vec,
            limit=10,
            scope=scope,
            org_scope=None,
            embedding_col="embedding_en",
        )

    ids = {row.chunk.id for row in rows}
    assert cur_chunk in ids
    assert old_chunk not in ids


@pytest.mark.asyncio
async def test_re_embed_clears_stale_to_zero(
    client: AsyncClient,
    register_and_login,
) -> None:
    """re-embed 后旧模型 chunk 更新为当前模型，stale 归零。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-re"
    )
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]

    async with SessionLocal() as db:
        _, old_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=LEGACY_MODEL,
        )
        _, _cur_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT + " 当前",
            embedding=vec,
            embedding_model=MODEL,
        )
        await db.commit()

    assert await count_stale_chunks(kb_id=kb_id) == 1
    result = await re_embed_all_chunks(kb_id=kb_id)
    assert result["status"] == "completed"
    assert result["updated"] == 1
    assert await count_stale_chunks(kb_id=kb_id) == 0

    async with SessionLocal() as db:
        row = await db.get(DocumentChunk, old_chunk)
        assert row is not None
        assert row.embedding_model == MODEL
        assert row.embedding is not None


@pytest.mark.asyncio
async def test_re_embed_clears_stale_en_model_to_zero(
    client: AsyncClient,
    register_and_login,
) -> None:
    """re-embed 后旧 EN 模型 chunk 更新为当前 EN 模型，EN stale 归零。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="p1-11-en-re"
    )
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]

    async with SessionLocal() as db:
        _, old_en_chunk = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            content=CONTENT,
            embedding=vec,
            embedding_model=MODEL,
            embedding_en=en_vec,
            embedding_en_model="legacy-en-model",
        )
        await db.commit()

    assert await count_stale_chunks(kb_id=kb_id) == 1
    result = await re_embed_all_chunks(kb_id=kb_id)
    assert result["status"] == "completed"
    assert result["updated"] == 1
    assert await count_stale_chunks(kb_id=kb_id) == 0

    async with SessionLocal() as db:
        row = await db.get(DocumentChunk, old_en_chunk)
        assert row is not None
        assert row.embedding_en_model == current_bge_en_model()
        assert row.embedding_en is not None

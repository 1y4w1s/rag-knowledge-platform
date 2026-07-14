"""Hybrid 检索：向量 + 全文 tsvector，RRF 融合 Top-K（Wave 3.4）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.models.knowledge_base import KnowledgeBase
from app.services.ingestion.embedder import embed_texts
from app.services.org.scope import OrgScope
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.rerank import rerank_chunks
from app.services.rag.rrf import reciprocal_rank_fusion
from app.services.rag.types import RetrievedChunk
from app.services.search.documents import kb_scope_clause
from app.services.workspace.scope import WorkspaceScope

VECTOR_RECALL = 20
FTS_RECALL = 20
LLM_TOP_K = 5
TS_CONFIG = "simple"

logger = logging.getLogger(__name__)


def _exclude_parent_chunks():
    return DocumentChunk.chunk_kind != "parent"


@dataclass(slots=True)
class _RecallRow:
    chunk: DocumentChunk
    filename: str
    kb_name: str | None = None
    vector_similarity: float | None = None
    fts_rank: float | None = None


def _excerpt(content: str, max_len: int = 200) -> str:
    text = content.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _visible_kb_clause(
    visible_kb_ids: frozenset[UUID] | None,
) -> ColumnElement[bool] | None:
    """OrgScope 二次过滤（ORG-1.6）；None 表示不叠加部门可见集。"""
    if visible_kb_ids is None:
        return None
    if not visible_kb_ids:
        return DocumentChunk.kb_id.is_(None)
    return DocumentChunk.kb_id.in_(visible_kb_ids)


async def _vector_recall(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query_vec: list[float],
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    distance = DocumentChunk.embedding.cosine_distance(query_vec).label("distance")
    stmt = (
        select(DocumentChunk, Document.filename, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(DocumentChunk.chunk_kind != "parent")
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(distance).limit(limit)
    rows = (await db.execute(stmt)).all()

    results: list[_RecallRow] = []
    for chunk, filename, dist in rows:
        similarity = max(0.0, 1.0 - float(dist))
        results.append(
            _RecallRow(
                chunk=chunk,
                filename=filename,
                vector_similarity=similarity,
            )
        )
    return results


async def _fts_recall(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(DocumentChunk.content_tsv.op("@@")(ts_query))
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(rank.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()

    results: list[_RecallRow] = []
    for chunk, filename, fts_rank in rows:
        results.append(
            _RecallRow(
                chunk=chunk,
                filename=filename,
                fts_rank=float(fts_rank) if fts_rank is not None else 0.0,
            )
        )
    return results


def _merge_recall_rows(
    vector_rows: list[_RecallRow],
    fts_rows: list[_RecallRow],
) -> dict[UUID, _RecallRow]:
    merged: dict[UUID, _RecallRow] = {}
    for row in vector_rows:
        merged[row.chunk.id] = row
    for row in fts_rows:
        existing = merged.get(row.chunk.id)
        if existing is None:
            merged[row.chunk.id] = row
        else:
            existing.fts_rank = row.fts_rank
    return merged


async def _load_parent_contents(
    db: AsyncSession,
    chunks: list[DocumentChunk],
) -> dict[UUID, str]:
    parent_ids = {
        chunk.parent_chunk_id
        for chunk in chunks
        if chunk.parent_chunk_id is not None
    }
    if not parent_ids:
        return {}

    stmt = select(DocumentChunk).where(DocumentChunk.id.in_(parent_ids))
    rows = (await db.execute(stmt)).scalars().all()
    return {row.id: row.content for row in rows}


def _enforce_kb_scope(
    chunks: list[RetrievedChunk],
    *,
    kb_id: UUID,
    visible_kb_ids: frozenset[UUID] | None = None,
) -> list[RetrievedChunk]:
    """SEC-3 / SA-3 / ORG-1.6：rerank 后二次校验，剔除跨库或不可见 chunk。"""
    scoped = [chunk for chunk in chunks if chunk.kb_id == kb_id]
    dropped = len(chunks) - len(scoped)
    if dropped:
        logger.warning(
            "检索结果含 %d 条跨库 chunk（请求 kb_id=%s），已剔除",
            dropped,
            kb_id,
        )
    if visible_kb_ids is not None:
        before = len(scoped)
        scoped = [chunk for chunk in scoped if chunk.kb_id in visible_kb_ids]
        org_dropped = before - len(scoped)
        if org_dropped:
            logger.warning(
                "检索结果含 %d 条 OrgScope 不可见 chunk（请求 kb_id=%s），已剔除",
                org_dropped,
                kb_id,
            )
    return scoped


async def retrieve_chunks(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_k: int = LLM_TOP_K,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[RetrievedChunk]:
    """向量 Top-20 + 全文 Top-20（同 kb_id），RRF 融合后 rerank 取 Top-K。"""
    if visible_kb_ids is not None and kb_id not in visible_kb_ids:
        return []

    query_vec = (await embed_texts([query]))[0]

    vector_rows = await _vector_recall(
        db,
        kb_id=kb_id,
        query_vec=query_vec,
        limit=VECTOR_RECALL,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    fts_rows = await _fts_recall(
        db,
        kb_id=kb_id,
        query=query,
        limit=FTS_RECALL,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )

    vector_ranked = [row.chunk.id for row in vector_rows]
    fts_ranked = [row.chunk.id for row in fts_rows]
    rrf_top_n = (
        settings.rerank_input_top_n
        if settings.rerank_enabled
        else top_k
    )
    fused = reciprocal_rank_fusion(
        [vector_ranked, fts_ranked],
        k=settings.rrf_k,
        weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
        top_n=rrf_top_n,
    )

    merged = _merge_recall_rows(vector_rows, fts_rows)
    parent_contents = await _load_parent_contents(
        db,
        [row.chunk for row in merged.values()],
    )
    candidates: list[RetrievedChunk] = []
    for chunk_id, _rrf_score in fused:
        row = merged[chunk_id]
        chunk = row.chunk
        similarity = row.vector_similarity if row.vector_similarity is not None else 0.0
        parent_content = None
        if chunk.parent_chunk_id is not None:
            parent_content = parent_contents.get(chunk.parent_chunk_id)
        candidates.append(
            RetrievedChunk(
                kb_id=kb_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                doc_name=row.filename,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                similarity=similarity,
                parent_content=parent_content,
            )
        )

    reranked = await rerank_chunks(query, candidates, top_k=top_k)
    return _enforce_kb_scope(
        reranked,
        kb_id=kb_id,
        visible_kb_ids=visible_kb_ids,
    )


def chunk_to_citation(chunk: RetrievedChunk) -> dict:
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "doc_name": chunk.doc_name,
        "page": chunk.page_number,
        "section_title": chunk.section_title,
        "excerpt": _excerpt(chunk.content),
    }


# ── Workspace-specific retrieval (merged from retrieval_workspace.py) ──


async def _vector_recall_workspace(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    query_vec: list[float],
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    scope_clause = kb_scope_clause(scope, org_scope)
    distance = DocumentChunk.embedding.cosine_distance(query_vec).label("distance")
    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            KnowledgeBase.name.label("kb_name"),
            distance,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, DocumentChunk.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(DocumentChunk.embedding.is_not(None))
        .where(_exclude_parent_chunks())
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(distance).limit(limit)
    rows = (await db.execute(stmt)).all()

    results: list[_RecallRow] = []
    for chunk, filename, kb_name, dist in rows:
        similarity = max(0.0, 1.0 - float(dist))
        results.append(
            _RecallRow(
                chunk=chunk,
                filename=filename,
                kb_name=kb_name,
                vector_similarity=similarity,
            )
        )
    return results


async def _fts_recall_workspace(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    query: str,
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    scope_clause = kb_scope_clause(scope, org_scope)
    ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            KnowledgeBase.name.label("kb_name"),
            rank,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, DocumentChunk.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(DocumentChunk.content_tsv.is_not(None))
        .where(_exclude_parent_chunks())
        .where(DocumentChunk.content_tsv.op("@@")(ts_query))
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(rank.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()

    results: list[_RecallRow] = []
    for chunk, filename, kb_name, fts_rank in rows:
        results.append(
            _RecallRow(
                chunk=chunk,
                filename=filename,
                kb_name=kb_name,
                fts_rank=float(fts_rank) if fts_rank is not None else 0.0,
            )
        )
    return results


def _enforce_workspace_scope(
    chunks: list[RetrievedChunk],
    *,
    visible_kb_ids: frozenset[UUID] | None = None,
) -> list[RetrievedChunk]:
    """OrgScope 二次校验：剔除不可见库 chunk。"""
    if visible_kb_ids is None:
        return chunks
    scoped = [chunk for chunk in chunks if chunk.kb_id in visible_kb_ids]
    dropped = len(chunks) - len(scoped)
    if dropped:
        logger.warning(
            "工作区检索结果含 %d 条 OrgScope 不可见 chunk，已剔除",
            dropped,
        )
    return scoped


async def retrieve_workspace_chunks(
    db: AsyncSession,
    *,
    query: str,
    scope: WorkspaceScope,
    org_scope: OrgScope | None = None,
    top_k: int = LLM_TOP_K,
    hide_admin_only: bool = False,
) -> list[RetrievedChunk]:
    """在 workspace 可见库集合内向量+全文→RRF→rerank→多样性→Top-K。"""
    visible_kb_ids = org_scope.visible_kb_ids if org_scope is not None else None
    if visible_kb_ids is not None and not visible_kb_ids:
        return []

    query_vec = (await embed_texts([query]))[0]

    vector_rows = await _vector_recall_workspace(
        db,
        scope=scope,
        org_scope=org_scope,
        query_vec=query_vec,
        limit=VECTOR_RECALL,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    fts_rows = await _fts_recall_workspace(
        db,
        scope=scope,
        org_scope=org_scope,
        query=query,
        limit=FTS_RECALL,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )

    rrf_top_n = (
        settings.rerank_input_top_n
        if settings.rerank_enabled
        else top_k
    )
    vector_ranked = [row.chunk.id for row in vector_rows]
    fts_ranked = [row.chunk.id for row in fts_rows]
    fused = reciprocal_rank_fusion(
        [vector_ranked, fts_ranked],
        k=settings.rrf_k,
        weights=[settings.rrf_vector_weight, settings.rrf_fts_weight],
        top_n=rrf_top_n,
    )

    merged = _merge_recall_rows(vector_rows, fts_rows)
    parent_contents = await _load_parent_contents(
        db,
        [row.chunk for row in merged.values()],
    )
    candidates: list[RetrievedChunk] = []
    for chunk_id, _rrf_score in fused:
        row = merged[chunk_id]
        chunk = row.chunk
        similarity = row.vector_similarity if row.vector_similarity is not None else 0.0
        parent_content = None
        if chunk.parent_chunk_id is not None:
            parent_content = parent_contents.get(chunk.parent_chunk_id)
        candidates.append(
            RetrievedChunk(
                kb_id=chunk.kb_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                doc_name=row.filename,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                similarity=similarity,
                parent_content=parent_content,
                kb_name=row.kb_name,
            )
        )

    rerank_pool = (
        settings.rerank_input_top_n
        if settings.rerank_enabled
        else top_k
    )
    reranked = await rerank_chunks(query, candidates, top_k=rerank_pool)
    diverse = apply_kb_diversity(reranked, query, top_k=top_k)
    return _enforce_workspace_scope(diverse, visible_kb_ids=visible_kb_ids)


def workspace_chunk_to_citation(chunk: RetrievedChunk) -> dict:
    """工作区引用：六字段 + kb_id / kb_name。"""
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "doc_name": chunk.doc_name,
        "page": chunk.page_number,
        "section_title": chunk.section_title,
        "excerpt": _excerpt(chunk.content),
        "kb_id": str(chunk.kb_id),
        "kb_name": chunk.kb_name or "",
    }

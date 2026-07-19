"""检索执行层（Phase 1 从 retrieval.py 拆分）。

职责：纯执行函数——不包含策略决策逻辑。
"""

import logging
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.services.rag.types import RetrievedChunk, _RecallRow

logger = logging.getLogger(__name__)


def excerpt(content: str, max_len: int = 200) -> str:
    text = content.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def merge_recall_rows(
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


async def load_parent_contents(
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


def visible_kb_clause(
    visible_kb_ids: frozenset[UUID] | None,
) -> ColumnElement[bool] | None:
    """OrgScope 二次过滤（ORG-1.6）；None 表示不叠加部门可见集。"""
    if visible_kb_ids is None:
        return None
    if not visible_kb_ids:
        return DocumentChunk.kb_id.is_(None)
    return DocumentChunk.kb_id.in_(visible_kb_ids)


def enforce_kb_scope(
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
            "检索结果含 %d 条跨库 chunk（请求 kb_id=%s），已剔除", dropped, kb_id,
        )
    if visible_kb_ids is not None:
        before = len(scoped)
        scoped = [chunk for chunk in scoped if chunk.kb_id in visible_kb_ids]
        org_dropped = before - len(scoped)
        if org_dropped:
            logger.warning(
                "检索结果含 %d 条 OrgScope 不可见 chunk（请求 kb_id=%s），已剔除",
                org_dropped, kb_id,
            )
    return scoped


def enforce_workspace_scope(
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
            "工作区检索结果含 %d 条 OrgScope 不可见 chunk，已剔除", dropped,
        )
    return scoped


def chunk_to_citation(chunk: RetrievedChunk) -> dict:
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "doc_name": chunk.doc_name,
        "page": chunk.page_number,
        "section_title": chunk.section_title,
        "excerpt": excerpt(chunk.content),
    }


def workspace_chunk_to_citation(chunk: RetrievedChunk) -> dict:
    """工作区引用：六字段 + kb_id / kb_name。"""
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "doc_name": chunk.doc_name,
        "page": chunk.page_number,
        "section_title": chunk.section_title,
        "excerpt": excerpt(chunk.content),
        "kb_id": str(chunk.kb_id),
        "kb_name": chunk.kb_name or "",
    }

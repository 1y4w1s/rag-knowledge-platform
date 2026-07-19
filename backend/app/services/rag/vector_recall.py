"""向量召回（从 retrieval.py 拆分），自包含版本。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.services.rag.types import _RecallRow


def _visible_kb_clause(visible_kb_ids: frozenset | None):
    if visible_kb_ids is None:
        return None
    return Document.kb_id.in_(visible_kb_ids) | false()


async def vector_recall(
    db: AsyncSession,
    *,
    kb_id: UUID | None = None,
    query_vec: list[float],
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
    scope=None,
    org_scope=None,
) -> list[_RecallRow]:
    if scope is not None:
        return await _vector_recall_workspace(
            db, query_vec=query_vec, limit=limit,
            scope=scope, org_scope=org_scope,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
    return await _vector_recall_kb(
        db, kb_id=kb_id, query_vec=query_vec, limit=limit,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
    )


async def _vector_recall_kb(
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
    stmt = stmt.where(Document.deleted_at.is_(None))
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(distance).limit(limit)
    rows = (await db.execute(stmt)).all()
    results = []
    for chunk, filename, dist in rows:
        similarity = max(0.0, 1.0 - float(dist))
        results.append(_RecallRow(chunk=chunk, filename=filename, vector_similarity=similarity))
    return results


async def _vector_recall_workspace(
    db: AsyncSession,
    *,
    query_vec: list[float],
    limit: int,
    scope,
    org_scope,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    from app.core.scope_utils import kb_scope_clause
    distance = DocumentChunk.embedding.cosine_distance(query_vec).label("distance")
    scope_clause = kb_scope_clause(scope, org_scope)
    stmt = (
        select(DocumentChunk, Document.filename, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(scope_clause)
        .where(DocumentChunk.embedding.is_not(None))
        .where(DocumentChunk.chunk_kind != "parent")
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    stmt = stmt.where(Document.deleted_at.is_(None))
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(distance).limit(limit)
    rows = (await db.execute(stmt)).all()
    results = []
    for chunk, filename, dist in rows:
        similarity = max(0.0, 1.0 - float(dist))
        results.append(_RecallRow(chunk=chunk, filename=filename, vector_similarity=similarity))
    return results

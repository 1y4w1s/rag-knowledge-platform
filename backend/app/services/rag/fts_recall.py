"""全文检索 recall（从 retrieval.py 拆分）。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.services.rag.cjk import segment_cjk
from app.services.rag.types import _RecallRow
import re

TS_CONFIG = "simple"


def _has_special_chars(query: str) -> bool:
    import re
    stripped = re.sub(r'[\w\s]', '', query)
    return bool(stripped)


def _escape_ilike(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _sanitize_tokens(tokens: list[str]) -> list[str]:
    """过滤可能引起 PostgreSQL tsquery 解析错误的 token。"""
    # tsquery 保留字符: & | ! ( )
    forbidden = re.compile(r"[&|!()]")
    return [t for t in tokens if t.strip() and not forbidden.search(t)]


def _visible_kb_clause(visible_kb_ids: frozenset | None):
    """'kb_id IN visible_kb_ids OR visible_kb_ids IS NULL' 子句。"""
    if visible_kb_ids is None:
        return None
    from sqlalchemy import false
    return Document.kb_id.in_(visible_kb_ids) | false()


async def fts_recall(
    db: AsyncSession,
    *,
    kb_id: UUID | None = None,
    query: str,
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
    scope=None,
    org_scope=None,
) -> list[_RecallRow]:
    """FTS 召回（KB 版或 workspace 版）。"""
    if scope is not None:
        from app.core.scope_utils import kb_scope_clause
        scope_clause = kb_scope_clause(scope, org_scope)
        return await _fts_recall_workspace(
            db, scope_clause=scope_clause, query=query, limit=limit,
            visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
        )
    return await _fts_recall_kb(
        db, kb_id=kb_id, query=query, limit=limit,
        visible_kb_ids=visible_kb_ids, hide_admin_only=hide_admin_only,
    )


async def _fts_recall_kb(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    tokens = segment_cjk(query).split()
    tokens = [t for t in tokens if t.strip() and not any(ch in t for ch in '&|!()')]
    if tokens:
        ts_query = func.to_tsquery(TS_CONFIG, " | ".join(tokens))
    else:
        ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    fts_condition = DocumentChunk.content_tsv.op("@@")(ts_query)
    if _has_special_chars(query):
        fts_condition = fts_condition | DocumentChunk.content.ilike(
            f"%{_escape_ilike(query)}%", escape="\\"
        )
    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.kb_id == kb_id)
        .where(fts_condition)
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    stmt = stmt.where(Document.deleted_at.is_(None))
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(rank.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    results = []
    for chunk, filename, fts_rank in rows:
        results.append(
            _RecallRow(chunk=chunk, filename=filename, fts_rank=float(fts_rank))
        )
    return results


async def _fts_recall_workspace(
    db: AsyncSession,
    *,
    scope_clause,
    query: str,
    limit: int,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    tokens = segment_cjk(query).split()
    tokens = [t for t in tokens if t.strip() and not any(ch in t for ch in '&|!()')]
    if tokens:
        ts_query = func.to_tsquery(TS_CONFIG, " | ".join(tokens))
    else:
        ts_query = func.plainto_tsquery(TS_CONFIG, query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, ts_query).label("fts_rank")
    fts_condition = DocumentChunk.content_tsv.op("@@")(ts_query)
    if _has_special_chars(query):
        fts_condition = fts_condition | DocumentChunk.content.ilike(
            f"%{_escape_ilike(query)}%", escape="\\"
        )
    stmt = (
        select(DocumentChunk, Document.filename, rank)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(scope_clause)
        .where(fts_condition)
    )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    stmt = stmt.where(Document.deleted_at.is_(None))
    visible_clause = _visible_kb_clause(visible_kb_ids)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    stmt = stmt.order_by(rank.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    results = []
    for chunk, filename, fts_rank in rows:
        results.append(
            _RecallRow(chunk=chunk, filename=filename, fts_rank=float(fts_rank))
        )
    return results

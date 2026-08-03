"""A3 跨文档 / 条款号路由：DB 召回 + 接入融合。

无 LLM。开关：settings.clause_route_enabled。
抽取/注入见 route_extract.py。
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.models.knowledge_base import KnowledgeBase
from app.services.rag.route_extract import (
    escape_ilike,
    extract_clause_tokens,
    extract_filename_cues,
    inject_route_hits,
    should_attempt_route,
)
from app.services.rag.types import _RecallRow

logger = logging.getLogger(__name__)

# 对外 re-export，便于单测 / 诊断脚本
__all__ = [
    "apply_clause_route_kb",
    "apply_clause_route_workspace",
    "extract_clause_tokens",
    "extract_filename_cues",
    "inject_route_hits",
    "should_attempt_route",
    "route_recall_kb",
    "route_recall_workspace",
]


async def apply_clause_route_kb(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    fused: list[tuple[UUID, float]],
    merged: dict[UUID, _RecallRow],
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> tuple[list[tuple[UUID, float]], dict[UUID, _RecallRow]]:
    if not settings.clause_route_enabled or not should_attempt_route(query):
        return fused, merged
    rows = await route_recall_kb(
        db,
        kb_id=kb_id,
        query=query,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    if not rows:
        return fused, merged
    logger.info("clause_route kb hits=%d query_len=%d", len(rows), len(query))
    return inject_route_hits(fused, merged, rows)


async def apply_clause_route_workspace(
    db: AsyncSession,
    *,
    query: str,
    fused: list[tuple[UUID, float]],
    merged: dict[UUID, _RecallRow],
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> tuple[list[tuple[UUID, float]], dict[UUID, _RecallRow]]:
    if not settings.clause_route_enabled or not should_attempt_route(query):
        return fused, merged
    rows = await route_recall_workspace(
        db,
        query=query,
        scope_clause=scope_clause,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )
    if not rows:
        return fused, merged
    logger.info("clause_route ws hits=%d query_len=%d", len(rows), len(query))
    return inject_route_hits(fused, merged, rows)


async def route_recall_kb(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    return await _route_recall(
        db,
        query=query,
        kb_id=kb_id,
        scope_clause=None,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )


async def route_recall_workspace(
    db: AsyncSession,
    *,
    query: str,
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None = None,
    hide_admin_only: bool = False,
) -> list[_RecallRow]:
    return await _route_recall(
        db,
        query=query,
        kb_id=None,
        scope_clause=scope_clause,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    )


async def _route_recall(
    db: AsyncSession,
    *,
    query: str,
    kb_id: UUID | None,
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
) -> list[_RecallRow]:
    clauses = extract_clause_tokens(query)
    cues = extract_filename_cues(query)
    limit = settings.clause_route_limit
    rows: list[_RecallRow] = []
    seen: set[UUID] = set()

    # 1) 条款号 → section_title / heading_path
    if clauses:
        for row in await _title_token_match(
            db,
            tokens=clauses,
            kb_id=kb_id,
            scope_clause=scope_clause,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
            limit=limit,
        ):
            if row.chunk.id not in seen:
                seen.add(row.chunk.id)
                rows.append(row)

    # 2) 专名 cue（SSH/Nginx/Q1…）→ 标题命中（高精）
    title_cues = [c for c in cues if len(c) >= 2][:8]
    if title_cues and len(rows) < limit:
        for row in await _title_token_match(
            db,
            tokens=title_cues,
            kb_id=kb_id,
            scope_clause=scope_clause,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
            limit=limit - len(rows),
        ):
            if row.chunk.id not in seen:
                seen.add(row.chunk.id)
                rows.append(row)

    # 3) 文件名软路由
    if cues and len(rows) < limit:
        doc_ids = await _matching_document_ids(
            db,
            cues=cues,
            kb_id=kb_id,
            scope_clause=scope_clause,
            hide_admin_only=hide_admin_only,
        )
        if doc_ids:
            for row in await _doc_scoped_chunks(
                db,
                document_ids=doc_ids,
                cues=cues,
                clauses=clauses,
                kb_id=kb_id,
                scope_clause=scope_clause,
                visible_kb_ids=visible_kb_ids,
                hide_admin_only=hide_admin_only,
                limit=limit - len(rows),
            ):
                if row.chunk.id not in seen:
                    seen.add(row.chunk.id)
                    rows.append(row)
    return rows[:limit]


def _base_stmt(
    *,
    kb_id: UUID | None,
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
):
    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            KnowledgeBase.name.label("kb_name"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(Document.deleted_at.is_(None))
    )
    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)
    if scope_clause is not None:
        stmt = stmt.where(scope_clause)
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    if visible_kb_ids is not None:
        from sqlalchemy import false

        stmt = stmt.where(Document.kb_id.in_(visible_kb_ids) | false())
    return stmt


async def _title_token_match(
    db: AsyncSession,
    *,
    tokens: list[str],
    kb_id: UUID | None,
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    limit: int,
) -> list[_RecallRow]:
    if not tokens or limit <= 0:
        return []
    title_conds = []
    for tok in tokens:
        esc = escape_ilike(tok)
        pat = f"%{esc}%"
        title_conds.append(DocumentChunk.section_title.ilike(pat, escape="\\"))
        title_conds.append(DocumentChunk.heading_path.ilike(pat, escape="\\"))
    stmt = (
        _base_stmt(
            kb_id=kb_id,
            scope_clause=scope_clause,
            visible_kb_ids=visible_kb_ids,
            hide_admin_only=hide_admin_only,
        )
        .where(or_(*title_conds))
        .limit(limit)
    )
    result = (await db.execute(stmt)).all()
    return [
        _RecallRow(chunk=c, filename=fn, kb_name=kb_name)
        for c, fn, kb_name in result
    ]


async def _matching_document_ids(
    db: AsyncSession,
    *,
    cues: list[str],
    kb_id: UUID | None,
    scope_clause,
    hide_admin_only: bool,
) -> list[UUID]:
    if not cues:
        return []
    conds = [
        Document.filename.ilike(f"%{escape_ilike(c)}%", escape="\\") for c in cues
    ]
    stmt = select(Document.id).where(Document.deleted_at.is_(None)).where(or_(*conds))
    if kb_id is not None:
        stmt = stmt.where(Document.kb_id == kb_id)
    if scope_clause is not None:
        stmt = stmt.join(KnowledgeBase, Document.kb_id == KnowledgeBase.id).where(
            scope_clause
        )
    if hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    stmt = stmt.limit(8)
    return list((await db.execute(stmt)).scalars().all())


async def _doc_scoped_chunks(
    db: AsyncSession,
    *,
    document_ids: list[UUID],
    cues: list[str],
    clauses: list[str],
    kb_id: UUID | None,
    scope_clause,
    visible_kb_ids: frozenset[UUID] | None,
    hide_admin_only: bool,
    limit: int,
) -> list[_RecallRow]:
    """文件名命中文档内：优先条款标题，其次 cue/content 子串。"""
    if not document_ids or limit <= 0:
        return []
    stmt = _base_stmt(
        kb_id=kb_id,
        scope_clause=scope_clause,
        visible_kb_ids=visible_kb_ids,
        hide_admin_only=hide_admin_only,
    ).where(DocumentChunk.document_id.in_(document_ids))

    prefer: list = []
    for tok in clauses:
        esc = escape_ilike(tok)
        pat = f"%{esc}%"
        prefer.append(DocumentChunk.section_title.ilike(pat, escape="\\"))
        prefer.append(DocumentChunk.heading_path.ilike(pat, escape="\\"))
    soft: list = []
    for tok in cues[:6]:
        esc = escape_ilike(tok)
        pat = f"%{esc}%"
        soft.append(DocumentChunk.content.ilike(pat, escape="\\"))
        soft.append(DocumentChunk.section_title.ilike(pat, escape="\\"))

    if prefer:
        hit = (await db.execute(stmt.where(or_(*prefer)).limit(limit))).all()
        if hit:
            return [
                _RecallRow(chunk=c, filename=fn, kb_name=kb_name)
                for c, fn, kb_name in hit
            ]
    if soft:
        hit = (await db.execute(stmt.where(or_(*soft)).limit(limit))).all()
        return [
            _RecallRow(chunk=c, filename=fn, kb_name=kb_name)
            for c, fn, kb_name in hit
        ]
    hit = (
        await db.execute(stmt.order_by(DocumentChunk.chunk_index).limit(limit))
    ).all()
    return [
        _RecallRow(chunk=c, filename=fn, kb_name=kb_name)
        for c, fn, kb_name in hit
    ]

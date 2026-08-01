"""跨库正文搜索（Plan-RAG R1-2）：chunk tsvector + 子串聚合。"""

from __future__ import annotations

import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.services.rag.cjk import segment_cjk
from app.models.knowledge_base import KnowledgeBase
from app.schemas.search import SearchDocumentItem, SearchDocumentsResponse
from app.services.org.scope import OrgScope
from app.services.search.documents import (
    _escape_ilike,
    kb_scope_clause,
    normalize_limit,
    normalize_offset,
)
from app.services.workspace.scope import WorkspaceScope

TS_CONFIG = "simple"


SNIPPET_CONTEXT = 60

# 只允许 <mark> 标签，移除其他所有 HTML 标签
_REMOVE_HTML_TAGS = re.compile(r"</?(?!mark\b)[a-z]\w*[^>]*>", re.IGNORECASE)


def _sanitize_snippet(text: str) -> str:
    """移除内容中的 HTML 标签（保留 <mark>），防止 XSS。"""
    return _REMOVE_HTML_TAGS.sub("", text)


def _ts_query(query: str):
    """构建 OR 语义 tsquery（空格分隔 = OR，与 fts_recall.py 一致）。"""
    tokens = segment_cjk(query).split()
    tokens = [t for t in tokens if t.strip()]
    if tokens:
        escaped = [t.replace("'", "''") for t in tokens]
        return func.to_tsquery(TS_CONFIG, " | ".join(f"'{t}'" for t in escaped))
    return func.plainto_tsquery(TS_CONFIG, query)


def _snippet_highlight(content: str, query: str, context: int = SNIPPET_CONTEXT) -> str:
    """围绕匹配词生成带 <mark> 的摘要（兼容中文子串）。"""
    content = _sanitize_snippet(content)
    needle = query.strip()
    if not needle:
        text = content.strip()
        return text if len(text) <= 120 else text[:119] + "…"

    lower = content.lower()
    lower_needle = needle.lower()
    idx = lower.find(lower_needle)
    if idx < 0:
        text = content.strip()
        return text if len(text) <= 120 else text[:119] + "…"

    start = max(0, idx - context)
    end = min(len(content), idx + len(needle) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    segment = content[start:end]
    rel = idx - start
    highlighted = (
        segment[:rel]
        + f"<mark>{segment[rel : rel + len(needle)]}</mark>"
        + segment[rel + len(needle) :]
    )
    return prefix + highlighted + suffix


async def search_documents_by_content(
    db: AsyncSession,
    scope: WorkspaceScope,
    query: str,
    limit: int,
    *,
    offset: int = 0,
    org_scope: OrgScope | None = None,
    hide_admin_only: bool = False,
    kb_id: uuid.UUID | None = None,
) -> SearchDocumentsResponse:
    """在当前 workspace 内按 chunk 正文搜索，每文档取最佳匹配片段。"""
    effective_limit = normalize_limit(limit)
    capped_offset = normalize_offset(offset)
    ts_query = _ts_query(query)
    # O3：仅在短查询（2-20 字）时启用 ILIKE 前导通配，长查询仅用 FTS 避免 seq scan
    q_stripped = query.strip()
    use_ilike = 2 <= len(q_stripped) <= 20
    ilike_match = None
    match_rank = func.coalesce(func.ts_rank_cd(DocumentChunk.content_tsv, ts_query), 0)
    if use_ilike:
        ilike_pattern = f"%{_escape_ilike(query)}%"
        ilike_match = DocumentChunk.content.ilike(ilike_pattern, escape="\\")
        match_rank = (match_rank + case((ilike_match, 0.001), else_=0)).label("match_rank")
    else:
        match_rank = match_rank.label("match_rank")
    scope_clause = kb_scope_clause(scope, org_scope)

    match_base = (
        select(
            Document.id.label("doc_id"),
            Document.filename,
            Document.file_type,
            Document.status,
            Document.kb_id,
            KnowledgeBase.name.label("kb_name"),
            Document.created_at,
            DocumentChunk.content,
            DocumentChunk.page_number,
            match_rank,
            func.row_number()
            .over(partition_by=Document.id, order_by=match_rank.desc())
            .label("rn"),
        )
        .join(DocumentChunk, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(DocumentChunk.chunk_kind != "parent")
        .where(
            or_(
                *[DocumentChunk.content_tsv.op("@@")(ts_query)]
                + ([ilike_match] if ilike_match is not None else [])
            )
        )
    )
    if hide_admin_only:
        match_base = match_base.where(Document.visibility != DocumentVisibility.admin_only)
    match_base = match_base.where(Document.deleted_at.is_(None))
    if kb_id is not None:
        match_base = match_base.where(Document.kb_id == kb_id)
    match_base = match_base.subquery()

    total = await db.scalar(
        select(func.count(func.distinct(match_base.c.doc_id))).select_from(
            match_base
        )
    )
    total_count = int(total or 0)

    rows = await db.execute(
        select(
            match_base.c.doc_id,
            match_base.c.filename,
            match_base.c.file_type,
            match_base.c.status,
            match_base.c.kb_id,
            match_base.c.kb_name,
            match_base.c.created_at,
            match_base.c.page_number,
            match_base.c.content,
        )
        .where(match_base.c.rn == 1)
        .order_by(
            match_base.c.match_rank.desc(),
            match_base.c.created_at.desc(),
            match_base.c.doc_id.desc(),
        )
        .offset(capped_offset)
        .limit(effective_limit)
    )

    items = [
        SearchDocumentItem(
            doc_id=row.doc_id,
            filename=row.filename,
            file_type=row.file_type,
            status=row.status,
            kb_id=row.kb_id,
            kb_name=row.kb_name,
            created_at=row.created_at,
            snippet=_snippet_highlight(row.content, query),
            page_number=row.page_number,
        )
        for row in rows.all()
    ]

    return SearchDocumentsResponse(
        items=items,
        query=query,
        total=total_count,
        limit=effective_limit,
        offset=capped_offset,
        mode="content",
    )

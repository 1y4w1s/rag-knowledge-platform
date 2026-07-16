"""跨库正文搜索（Plan-RAG R1-2）：chunk tsvector + 子串聚合。"""

from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentVisibility
from app.services.rag.cjk import segment_cjk
from app.models.knowledge_base import KnowledgeBase
from app.schemas.search import SearchDocumentItem, SearchDocumentsResponse
from app.services.org.scope import OrgScope
from app.services.search.documents import MAX_LIMIT, _escape_ilike, kb_scope_clause
from app.services.workspace.scope import WorkspaceScope

TS_CONFIG = "simple"
SNIPPET_CONTEXT = 60


def _ts_query(query: str):
    return func.plainto_tsquery(TS_CONFIG, segment_cjk(query))


def _snippet_highlight(content: str, query: str, context: int = SNIPPET_CONTEXT) -> str:
    """围绕匹配词生成带 <mark> 的摘要（兼容中文子串）。"""
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
    org_scope: OrgScope | None = None,
) -> SearchDocumentsResponse:
    """在当前 workspace 内按 chunk 正文搜索，每文档取最佳匹配片段。"""
    effective_limit = min(max(limit, 1), MAX_LIMIT)
    ts_query = _ts_query(query)
    ilike_pattern = f"%{_escape_ilike(query)}%"
    ilike_match = DocumentChunk.content.ilike(ilike_pattern, escape="\\")
    match_rank = (
        func.coalesce(func.ts_rank_cd(DocumentChunk.content_tsv, ts_query), 0)
        + case((ilike_match, 0.001), else_=0)
    ).label("match_rank")
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
                DocumentChunk.content_tsv.op("@@")(ts_query),
                ilike_match,
            )
        )
    )
    if hide_admin_only:
        match_base = match_base.where(Document.visibility != DocumentVisibility.admin_only)
    match_base = match_base.where(Document.deleted_at.is_(None))
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
        .order_by(match_base.c.match_rank.desc(), match_base.c.created_at.desc())
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
        mode="content",
    )

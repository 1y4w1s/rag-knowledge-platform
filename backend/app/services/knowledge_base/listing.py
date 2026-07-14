"""知识库列表分页、搜索与排序。"""

from __future__ import annotations

from sqlalchemy import Case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseListResponse, KnowledgeBaseResponse
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceScope

DEFAULT_LIMIT = 24
MAX_LIMIT = 100
DEFAULT_SORT = "updated_at_desc"

VALID_SORT_MODES = frozenset(
    {
        "updated_at_desc",
        "updated_at_asc",
        "name_asc",
        "name_desc",
        "doc_count_desc",
        "doc_count_asc",
        "needs_attention",
        "healthy_first",
    }
)


def normalize_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    return min(max(raw, 1), MAX_LIMIT)


def normalize_offset(raw: int | None) -> int:
    if raw is None:
        return 0
    return max(raw, 0)


def normalize_sort(raw: str | None) -> str:
    if raw and raw.strip() in VALID_SORT_MODES:
        return raw.strip()
    return DEFAULT_SORT


def _stats_subquery():
    processing_statuses = [DocumentStatus.queued, DocumentStatus.processing]
    return (
        select(
            Document.kb_id.label("kb_id"),
            func.count().label("document_count"),
            func.max(Document.updated_at).label("max_doc_updated_at"),
            func.count()
            .filter(Document.status.in_(processing_statuses))
            .label("processing_count"),
            func.count()
            .filter(Document.status == DocumentStatus.failed)
            .label("failed_count"),
        )
        .group_by(Document.kb_id)
        .subquery("kb_doc_stats")
    )


def _attention_rank(processing_count, failed_count):
    return Case(
        (failed_count > 0, 0),
        (processing_count > 0, 1),
        else_=2,
    )


def _order_clauses(
    sort_mode: str,
    *,
    effective_updated_at,
    document_count,
    attention_rank,
):
    if sort_mode == "updated_at_asc":
        return [effective_updated_at.asc()]
    if sort_mode == "name_asc":
        return [KnowledgeBase.name.asc()]
    if sort_mode == "name_desc":
        return [KnowledgeBase.name.desc()]
    if sort_mode == "doc_count_desc":
        return [document_count.desc(), effective_updated_at.desc()]
    if sort_mode == "doc_count_asc":
        return [document_count.asc(), effective_updated_at.asc()]
    if sort_mode == "healthy_first":
        return [attention_rank.desc(), effective_updated_at.asc()]
    if sort_mode == "needs_attention":
        return [attention_rank.asc(), effective_updated_at.desc()]
    return [effective_updated_at.desc()]


def _apply_visibility(
    stmt,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
):
    stmt = stmt.where(scope.kb_owner_clause())
    if org_scope is not None:
        stmt = stmt.where(org_scope.kb_visibility_clause())
    return stmt


async def list_knowledge_bases(
    db: AsyncSession,
    scope: WorkspaceScope,
    *,
    org_scope: OrgScope | None = None,
    limit: int | None = None,
    offset: int | None = None,
    q: str | None = None,
    sort: str | None = None,
) -> KnowledgeBaseListResponse:
    capped_limit = normalize_limit(limit)
    capped_offset = normalize_offset(offset)
    sort_mode = normalize_sort(sort)
    search = (q or "").strip()

    stats_sq = _stats_subquery()
    document_count = func.coalesce(stats_sq.c.document_count, 0)
    processing_count = func.coalesce(stats_sq.c.processing_count, 0)
    failed_count = func.coalesce(stats_sq.c.failed_count, 0)
    effective_updated_at = func.greatest(
        KnowledgeBase.created_at,
        func.coalesce(stats_sq.c.max_doc_updated_at, KnowledgeBase.created_at),
    )
    attention_rank = _attention_rank(processing_count, failed_count)

    count_stmt = select(func.count()).select_from(KnowledgeBase)
    count_stmt = _apply_visibility(count_stmt, scope, org_scope)
    if search:
        needle = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                KnowledgeBase.name.ilike(needle),
                KnowledgeBase.description.ilike(needle),
            )
        )
    total = int(await db.scalar(count_stmt) or 0)

    stmt = (
        select(
            KnowledgeBase,
            document_count,
            processing_count,
            failed_count,
            effective_updated_at,
        )
        .outerjoin(stats_sq, KnowledgeBase.id == stats_sq.c.kb_id)
    )
    stmt = _apply_visibility(stmt, scope, org_scope)
    if search:
        needle = f"%{search}%"
        stmt = stmt.where(
            or_(
                KnowledgeBase.name.ilike(needle),
                KnowledgeBase.description.ilike(needle),
            )
        )

    stmt = (
        stmt.order_by(
            *_order_clauses(
                sort_mode,
                effective_updated_at=effective_updated_at,
                document_count=document_count,
                attention_rank=attention_rank,
            )
        )
        .limit(capped_limit)
        .offset(capped_offset)
    )

    rows = await db.execute(stmt)
    items = [
        KnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            owner_user_id=kb.owner_user_id,
            owner_org_id=kb.owner_org_id,
            org_unit_id=kb.org_unit_id,
            created_at=kb.created_at,
            updated_at=updated_at,
            document_count=int(doc_count),
            processing_count=int(proc_count),
            failed_count=int(fail_count),
        )
        for kb, doc_count, proc_count, fail_count, updated_at in rows.all()
    ]

    return KnowledgeBaseListResponse(
        items=items,
        total=total,
        limit=capped_limit,
        offset=capped_offset,
    )

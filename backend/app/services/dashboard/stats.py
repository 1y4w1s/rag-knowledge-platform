"""Dashboard 聚合统计（Wave 2.5 / DB-API W1）。

只读 SQL 聚合 documents / knowledge_bases；按 WorkspaceScope 筛选（W1-2）；
团队空间叠加 OrgScope（ORG-1.4），与 GET /knowledge-bases 同源可见集。
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag_baseline import (
    GOLDEN_BASELINE_EVALUATED_AT,
    golden_hit_rate_percent,
)
from app.models.audit_log import AuditLog
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.enums import DocumentStatus, MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.models.organization_member import OrganizationMember
from app.schemas.dashboard import DashboardStatsResponse, DocumentStatusCounts
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


def _kb_scope_clause(
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
) -> ColumnElement[bool]:
    clause = scope.kb_owner_clause()
    if org_scope is not None:
        clause = clause & org_scope.kb_visibility_clause()
    return clause


def _deleted_kb_audit_scope_clause(scope: WorkspaceScope) -> ColumnElement[bool]:
    """删库后 KB 行已不存在时，按操作者归属计数 audit（storage.cleanup_failed）。"""
    kb_missing = KnowledgeBase.id.is_(None)
    if scope.kind == WorkspaceKind.personal:
        return kb_missing & (AuditLog.actor_user_id == scope.user_id)
    assert scope.org_id is not None
    actor_in_org = (
        select(OrganizationMember.id)
        .where(
            OrganizationMember.user_id == AuditLog.actor_user_id,
            OrganizationMember.org_id == scope.org_id,
        )
        .exists()
    )
    return kb_missing & actor_in_org


async def _count_audits_in_scope(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    scope_clause: ColumnElement[bool],
    action: str,
    since: datetime | None = None,
) -> int:
    """按 workspace + OrgScope 可见库聚合 audit_logs；删库后 cleanup 失败用操作者归属兜底。"""
    in_scope = or_(scope_clause, _deleted_kb_audit_scope_clause(scope))
    stmt = (
        select(func.count(AuditLog.id))
        .outerjoin(KnowledgeBase, AuditLog.kb_id == KnowledgeBase.id)
        .where(
            in_scope,
            AuditLog.action == action,
            AuditLog.kb_id.is_not(None),
        )
    )
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    return int(await db.scalar(stmt) or 0)


async def get_dashboard_stats(
    db: AsyncSession,
    scope: WorkspaceScope,
    *,
    org_scope: OrgScope | None = None,
) -> DashboardStatsResponse:
    scope_clause = _kb_scope_clause(scope, org_scope)
    scope_label = (
        "personal"
        if scope.kind == WorkspaceKind.personal
        else "organization"
    )

    kb_count = await db.scalar(
        select(func.count(KnowledgeBase.id)).where(scope_clause)
    )
    knowledge_base_count = int(kb_count or 0)

    status_rows = await db.execute(
        select(Document.status, func.count(Document.id))
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .group_by(Document.status)
    )

    counts = DocumentStatusCounts()
    for status, count in status_rows.all():
        setattr(counts, status.value, int(count))

    document_count = (
        counts.queued + counts.processing + counts.completed + counts.failed
    )

    chunk_sum = await db.scalar(
        select(func.coalesce(func.sum(Document.chunk_count), 0))
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(scope_clause)
    )
    total_chunk_count = int(chunk_sum or 0)

    avg_seconds = await db.scalar(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    Document.processing_completed_at - Document.processing_started_at,
                )
            )
        )
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(
            scope_clause,
            Document.status == DocumentStatus.completed,
            Document.processing_started_at.is_not(None),
            Document.processing_completed_at.is_not(None),
        )
    )
    avg_processing_duration_seconds = (
        round(float(avg_seconds), 3) if avg_seconds is not None else None
    )

    finished_total = counts.completed + counts.failed
    ingestion_success_rate = (
        round(counts.completed / finished_total * 100.0, 2)
        if finished_total > 0
        else None
    )

    member_count: int | None = None
    if scope.kind == WorkspaceKind.organization:
        assert scope.org_id is not None
        org_members = await db.scalar(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.org_id == scope.org_id
            )
        )
        member_count = int(org_members or 0)

    recent_kb_id = None
    if knowledge_base_count > 0:
        recent_kb_id = await db.scalar(
            select(KnowledgeBase.id)
            .where(scope_clause)
            .outerjoin(Document, Document.kb_id == KnowledgeBase.id)
            .group_by(KnowledgeBase.id, KnowledgeBase.created_at)
            .order_by(
                func.greatest(
                    KnowledgeBase.created_at,
                    func.coalesce(
                        func.max(Document.updated_at),
                        KnowledgeBase.created_at,
                    ),
                ).desc()
            )
            .limit(1)
        )

    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    chat_count = await db.scalar(
        select(func.count(ChatMessage.id))
        .join(KnowledgeBase, ChatMessage.kb_id == KnowledgeBase.id)
        .where(scope_clause, ChatMessage.created_at >= seven_days_ago)
    )
    chat_message_count = int(chat_count or 0)

    avg_retrieval = await db.scalar(
        select(func.avg(ChatMessage.retrieval_duration_ms))
        .join(KnowledgeBase, ChatMessage.kb_id == KnowledgeBase.id)
        .where(
            scope_clause,
            ChatMessage.role == MessageRole.assistant,
            ChatMessage.created_at >= seven_days_ago,
            ChatMessage.retrieval_duration_ms.is_not(None),
        )
    )
    retrieval_sample = await db.scalar(
        select(func.count(ChatMessage.id))
        .join(KnowledgeBase, ChatMessage.kb_id == KnowledgeBase.id)
        .where(
            scope_clause,
            ChatMessage.role == MessageRole.assistant,
            ChatMessage.created_at >= seven_days_ago,
            ChatMessage.retrieval_duration_ms.is_not(None),
        )
    )
    avg_retrieval_latency_ms = (
        round(float(avg_retrieval), 1) if avg_retrieval is not None else None
    )
    retrieval_latency_sample_count = int(retrieval_sample or 0)

    document_retry_count_7d = await _count_audits_in_scope(
        db,
        scope=scope,
        scope_clause=scope_clause,
        action="document.retry",
        since=seven_days_ago,
    )
    storage_cleanup_failure_count = await _count_audits_in_scope(
        db,
        scope=scope,
        scope_clause=scope_clause,
        action="storage.cleanup_failed",
    )

    return DashboardStatsResponse(
        scope=scope_label,
        knowledge_base_count=knowledge_base_count,
        document_count=document_count,
        documents_by_status=counts,
        total_chunk_count=total_chunk_count,
        avg_processing_duration_seconds=avg_processing_duration_seconds,
        ingestion_success_rate=ingestion_success_rate,
        chat_message_count=chat_message_count,
        member_count=member_count,
        recent_kb_id=recent_kb_id,
        recent_activities=[],
        golden_hit_rate_percent=golden_hit_rate_percent(),
        golden_baseline_evaluated_at=GOLDEN_BASELINE_EVALUATED_AT,
        avg_retrieval_latency_ms=avg_retrieval_latency_ms,
        retrieval_latency_sample_count=retrieval_latency_sample_count,
        document_retry_count_7d=document_retry_count_7d,
        storage_cleanup_failure_count=storage_cleanup_failure_count,
    )

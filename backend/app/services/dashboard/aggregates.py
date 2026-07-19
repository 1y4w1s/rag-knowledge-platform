"""Dashboard Tier-2 聚合（趋势 / 格式分布 / 最近对话 / 操作动态）。

所有查询按 WorkspaceScope(+OrgScope) 的 kb 可见集筛选，与 `get_dashboard_stats`
同源（`scope_clause`）。操作动态复用 `_deleted_kb_audit_scope_clause` 处理删库后
审计行的归属兜底。
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import MessageRole
from app.models.knowledge_base import KnowledgeBase
from app.models.organization_member import OrganizationMember
from app.schemas.dashboard import (
    DashboardActivity,
    DashboardFormatShare,
    DashboardRecentThread,
    DashboardTrendPoint,
)
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


def _deleted_kb_audit_scope_clause(scope: WorkspaceScope) -> ColumnElement[bool]:
    """删库后 KB 行已不存在时，按操作者归属计数 audit（storage.cleanup_failed 等）。"""
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


def _normalize_format(raw: str | None) -> str:
    """pdf / application/pdf / docx → 大写展示；None/空 → 其他。"""
    if not raw:
        return "其他"
    part = raw.split("/")[-1] if "/" in raw else raw
    return part.upper() or "其他"


async def build_question_trend(
    db: AsyncSession,
    scope_clause: ColumnElement[bool],
) -> list[DashboardTrendPoint]:
    """近 7 日每日提问数（role=user），UTC 日期，旧→新，缺失日补 0。"""
    today = datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    since = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=6)

    rows = await db.execute(
        select(ChatMessage.created_at)
        .join(KnowledgeBase, ChatMessage.kb_id == KnowledgeBase.id)
        .where(
            scope_clause,
            ChatMessage.role == MessageRole.user,
            ChatMessage.created_at >= since,
        )
    )
    buckets: Counter[str] = Counter(
        dt.astimezone(UTC).date().isoformat() for (dt,) in rows.all()
    )
    return [
        DashboardTrendPoint(date=d.isoformat(), count=buckets.get(d.isoformat(), 0))
        for d in days
    ]


async def build_format_distribution(
    db: AsyncSession,
    scope_clause: ColumnElement[bool],
) -> list[DashboardFormatShare]:
    """知识构成：按文档格式（file_type）分组的文档数，降序。"""
    rows = await db.execute(
        select(Document.file_type, func.count(Document.id))
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .group_by(Document.file_type)
    )
    result: list[DashboardFormatShare] = [
        DashboardFormatShare(format=_normalize_format(raw), count=int(count))
        for raw, count in rows.all()
    ]
    result.sort(key=lambda x: x.count, reverse=True)
    return result


async def build_recent_threads(
    db: AsyncSession,
    scope_clause: ColumnElement[bool],
    limit: int = 5,
) -> list[DashboardRecentThread]:
    """最近对话线程（按活跃时间倒序），含该线程 assistant 消息的引用条数。"""
    threads = await db.scalars(
        select(ChatThread)
        .join(KnowledgeBase, ChatThread.kb_id == KnowledgeBase.id)
        .where(scope_clause, ChatThread.kb_id.is_not(None))
        .order_by(
            ChatThread.last_message_at.desc().nullslast(),
            ChatThread.created_at.desc(),
        )
        .limit(limit)
    )
    items: list[DashboardRecentThread] = []
    for t in threads.all():
        citation_count = int(
            await db.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.thread_id == t.id,
                    ChatMessage.role == MessageRole.assistant,
                    ChatMessage.citations.is_not(None),
                    func.jsonb_array_length(ChatMessage.citations) > 0,
                )
            )
            or 0
        )
        items.append(
            DashboardRecentThread(
                id=t.id,
                title=t.title or "未命名对话",
                kb_id=t.kb_id,
                citation_count=citation_count,
                last_activity_at=t.last_message_at or t.created_at,
            )
        )
    return items


_ACTIVITY_ICON: dict[str, str] = {
    "document.upload": "upload",
    "document.delete": "lock",
    "document.retry": "refresh-cw",
    "kb.create": "upload",
    "kb.delete": "lock",
    "kb.grant": "user-plus",
    "kb.revoke": "user-plus",
    "chat.thread_created": "message-square",
    "chat.message_sent": "message-square",
    "agent.run": "refresh-cw",
    "org_unit.create": "user-plus",
}

_ACTIVITY_TITLE: dict[str, str] = {
    "document.upload": "上传文档",
    "document.delete": "删除文档",
    "document.retry": "重试入库",
    "kb.create": "新建资料库",
    "kb.delete": "删除资料库",
    "kb.grant": "授权成员",
    "kb.revoke": "取消授权",
    "chat.thread_created": "发起对话",
    "chat.message_sent": "提出提问",
    "agent.run": "运行智能体",
    "org_unit.create": "新建部门",
}


def _activity_title(action: str, details: dict | None) -> str:
    base = _ACTIVITY_TITLE.get(action, action)
    name = None
    if details:
        name = (
            details.get("filename")
            or details.get("kb_name")
            or details.get("title")
            or details.get("name")
        )
    return f"{base} · {name}" if name else base


async def build_recent_activities(
    db: AsyncSession,
    scope: WorkspaceScope,
    scope_clause: ColumnElement[bool],
    limit: int = 6,
) -> list[DashboardActivity]:
    """操作动态 feed：从 audit_logs 聚合（按时间倒序），仅取有 kb 归属的可见事件。"""
    in_scope = or_(scope_clause, _deleted_kb_audit_scope_clause(scope))
    rows = await db.scalars(
        select(AuditLog)
        .outerjoin(KnowledgeBase, AuditLog.kb_id == KnowledgeBase.id)
        .where(in_scope, AuditLog.kb_id.is_not(None))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    items: list[DashboardActivity] = []
    for log in rows.all():
        assert log.kb_id is not None
        doc_id = None
        if log.details and log.details.get("document_id"):
            try:
                doc_id = uuid.UUID(str(log.details["document_id"]))
            except (ValueError, AttributeError):
                doc_id = None
        items.append(
            DashboardActivity(
                type=_ACTIVITY_ICON.get(log.action, "refresh-cw"),
                title=_activity_title(log.action, log.details),
                kb_id=log.kb_id,
                doc_id=doc_id,
                created_at=log.created_at,
            )
        )
    return items

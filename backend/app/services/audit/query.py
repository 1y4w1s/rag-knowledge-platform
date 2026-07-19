"""审计日志查询（Plan-3E-1 后半）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.exceptions import ForbiddenError
from app.models.audit_log import AuditLog
from app.models.knowledge_base import KnowledgeBase
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def normalize_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    return min(max(raw, 1), MAX_LIMIT)


def normalize_offset(raw: int | None) -> int:
    if raw is None:
        return 0
    return max(raw, 0)


def _org_scope_clause(org_id: uuid.UUID):
    """组织 Admin 可见：成员操作或组织资料库相关事件。"""
    org_member_ids = select(OrganizationMember.user_id).where(
        OrganizationMember.org_id == org_id
    )
    org_kb_ids = select(KnowledgeBase.id).where(
        KnowledgeBase.owner_org_id == org_id
    )
    return or_(
        AuditLog.actor_user_id.in_(org_member_ids),
        AuditLog.kb_id.in_(org_kb_ids),
    )


async def _enrich_audit_items(
    db: AsyncSession,
    items: list[AuditLogResponse],
) -> list[AuditLogResponse]:
    """批量回填操作者邮箱与资料库名称，避免前端只见短 UUID。"""
    if not items:
        return items

    actor_ids = {item.actor_user_id for item in items if item.actor_user_id}
    kb_ids = {item.kb_id for item in items if item.kb_id}

    email_by_id: dict[uuid.UUID, str] = {}
    if actor_ids:
        rows = await db.execute(
            select(User.id, User.email).where(User.id.in_(actor_ids))
        )
        email_by_id = {row.id: row.email for row in rows}

    name_by_id: dict[uuid.UUID, str] = {}
    if kb_ids:
        rows = await db.execute(
            select(KnowledgeBase.id, KnowledgeBase.name).where(
                KnowledgeBase.id.in_(kb_ids)
            )
        )
        name_by_id = {row.id: row.name for row in rows}

    return [
        item.model_copy(
            update={
                "actor_email": (
                    email_by_id.get(item.actor_user_id)
                    if item.actor_user_id
                    else None
                ),
                "kb_name": (
                    name_by_id.get(item.kb_id) if item.kb_id else None
                ),
            }
        )
        for item in items
    ]


async def list_audit_logs(
    db: AsyncSession,
    admin: CurrentUser,
    *,
    limit: int | None = None,
    offset: int | None = None,
    action: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip: str | None = None,
    kb_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> AuditLogListResponse:
    assert admin.org_id is not None
    org_id = admin.org_id

    capped_limit = normalize_limit(limit)
    capped_offset = normalize_offset(offset)

    filters = [_org_scope_clause(org_id)]

    if action is not None:
        filters.append(AuditLog.action == action)

    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)

    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)

    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)

    if ip is not None:
        filters.append(AuditLog.ip == ip)

    if kb_id is not None:
        kb = await db.get(KnowledgeBase, kb_id)
        if kb is None or kb.owner_org_id != org_id:
            raise ForbiddenError("无权访问该知识库")
        filters.append(AuditLog.kb_id == kb_id)

    if created_from is not None:
        filters.append(AuditLog.created_at >= created_from)
    if created_to is not None:
        filters.append(AuditLog.created_at <= created_to)

    where = and_(*filters)

    total = int(
        await db.scalar(select(func.count()).select_from(AuditLog).where(where)) or 0
    )

    rows = await db.scalars(
        select(AuditLog)
        .where(where)
        .order_by(AuditLog.created_at.desc())
        .limit(capped_limit)
        .offset(capped_offset)
    )
    items = await _enrich_audit_items(
        db,
        [AuditLogResponse.model_validate(row) for row in rows.all()],
    )

    return AuditLogListResponse(
        items=items,
        total=total,
        limit=capped_limit,
        offset=capped_offset,
    )

"""审计日志 Admin 查询 API（Plan-3E-1 后半）。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_org_role
from app.models.enums import OrgRole
from app.schemas.audit_log import AuditLogListResponse
from app.services.audit.query import list_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    kb_id: Annotated[UUID | None, Query()] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> AuditLogListResponse:
    """组织 Admin 分页查询审计日志（action / kb_id / 时间筛选）。"""
    return await list_audit_logs(
        db,
        admin,
        limit=limit,
        offset=offset,
        action=action,
        kb_id=kb_id,
        created_from=created_from,
        created_to=created_to,
    )

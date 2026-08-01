"""审计日志 Admin 查询 / 导出 API（Plan-3E-1 · NW-32）。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_org_role
from app.models.enums import OrgRole
from app.schemas.audit_log import AuditLogListResponse
from app.services.audit.export import (
    EXPORT_MAX_ROWS,
    render_audit_csv,
    render_audit_json,
)
from app.services.audit.query import collect_audit_logs, list_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    resource_type: Annotated[str | None, Query(max_length=32)] = None,
    resource_id: Annotated[UUID | None, Query()] = None,
    ip: Annotated[str | None, Query(max_length=45)] = None,
    kb_id: Annotated[UUID | None, Query()] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> AuditLogListResponse:
    """组织 Admin 分页查询审计日志（action / actor / resource / IP / kb / 时间筛选）。"""
    return await list_audit_logs(
        db,
        admin,
        limit=limit,
        offset=offset,
        action=action,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        kb_id=kb_id,
        created_from=created_from,
        created_to=created_to,
    )


@router.get("/audit-logs/export")
async def export_audit_logs(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    file_format: Annotated[
        Literal["csv", "json"],
        Query(alias="format"),
    ] = "csv",
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    resource_type: Annotated[str | None, Query(max_length=32)] = None,
    resource_id: Annotated[UUID | None, Query()] = None,
    ip: Annotated[str | None, Query(max_length=45)] = None,
    kb_id: Annotated[UUID | None, Query()] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> Response:
    """与列表同源筛选导出 CSV/JSON；最多 EXPORT_MAX_ROWS；无对话正文列。"""
    items, total_matched, truncated = await collect_audit_logs(
        db,
        admin,
        max_rows=EXPORT_MAX_ROWS,
        action=action,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip,
        kb_id=kb_id,
        created_from=created_from,
        created_to=created_to,
    )

    if file_format == "json":
        body = render_audit_json(
            items,
            total_matched=total_matched,
            truncated=truncated,
            export_limit=EXPORT_MAX_ROWS,
        )
        media = "application/json; charset=utf-8"
        filename = "audit-logs.json"
    else:
        body = render_audit_csv(items)
        media = "text/csv; charset=utf-8"
        filename = "audit-logs.csv"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-Total-Matched": str(total_matched),
        "X-Export-Count": str(len(items)),
        "X-Export-Truncated": "1" if truncated else "0",
        "X-Export-Limit": str(EXPORT_MAX_ROWS),
    }
    return Response(content=body, media_type=media, headers=headers)

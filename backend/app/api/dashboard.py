"""Dashboard API 路由（Wave 2.5）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    DepartmentIdQuery,
    get_current_user,
)
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import resolve_workspace
from app.schemas.dashboard import DashboardStatsResponse
from app.services.dashboard.stats import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def read_dashboard_stats(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    workspace: Annotated[str | None, Query(description="工作区：personal 或组织 UUID")] = None,
    department_id: DepartmentIdQuery = None,
) -> DashboardStatsResponse:
    """概览统计：个人版看自己的库；企业 admin/member 看组织数据（TECH-5 §5.3）。"""
    scope = await resolve_workspace(db, current_user, workspace)
    org_scope = await resolve_org_scope_for_workspace(
        db, current_user, scope, department_id=department_id
    )
    return await get_dashboard_stats(db, scope, org_scope=org_scope)

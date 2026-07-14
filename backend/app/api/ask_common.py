"""工作区 /ask 路由共享校验与 citation 可见性（G-1 · G2-1.1）。"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.enums import OrgRole
from app.models.knowledge_base import KnowledgeBase
from app.services.org.scope import OrgScope, _is_company_admin
from app.services.rag.citations import is_kb_visible_in_org_scope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


def assert_team_business_allowed(
    current_user: CurrentUser,
    scope: WorkspaceScope,
) -> None:
    """未分配 Member 禁止团队工作区对话（PRD E17 / T-ask-4）。"""
    if scope.kind != WorkspaceKind.organization:
        return
    if _is_company_admin(current_user):
        return
    if current_user.org_role != OrgRole.member:
        return
    if not current_user.unit_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="尚未分配部门，无法使用团队对话",
        )


async def assert_has_visible_knowledge_bases(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser,
) -> None:
    """可见库为空时拒问（H5-A · T-ask 前置）。"""
    if org_scope is not None:
        if not org_scope.visible_kb_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无可用资料库",
            )
        return

    count = await db.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.owner_user_id == current_user.id)
    )
    if not count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无可用资料库",
        )


async def citation_visible_in_scope(
    db: AsyncSession,
    current_user: CurrentUser,
    raw: dict,
    *,
    scope: WorkspaceScope,
    department_id: str | None,
) -> bool:
    kb_id_raw = raw.get("kb_id")
    if kb_id_raw is None:
        return True
    try:
        kb_id = UUID(str(kb_id_raw))
    except ValueError:
        return False
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        return False
    if scope.kind == WorkspaceKind.personal:
        return kb.owner_user_id == current_user.id
    return await is_kb_visible_in_org_scope(
        db, current_user, kb, department_id=department_id
    )

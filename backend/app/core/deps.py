"""FastAPI 依赖：CurrentUser 与 RBAC（Wave 1.2+）。

Wave 2.1：``require_kb_access`` 基于 knowledge_bases 表做 kb_id 二次校验（TECH-5 / SA-1）。
ORG-1.2：团队库叠加 OrgScope（部门子树 + 公共库 + grant）。
"""

from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenClaims
from app.models.enums import AccountType, OrgRole
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.auth import UserPublic
from app.services.auth.org_context import (
    resolve_org_context,
    resolve_unit_admin_unit_ids,
    resolve_user_units,
)
from app.services.org.scope import assert_kb_visible_in_org_scope

DepartmentIdQuery = Annotated[
    str | None,
    Query(description="部门 UUID；省略则默认主部门；公司 Admin 可用 all"),
]


class KbAction(str, Enum):
    """知识库操作类型（TECH-5 §5.4）。"""

    read = "read"
    write = "write"
    admin = "admin"


class CurrentUser(UserPublic):
    """已认证用户（JWT + DB 校验）。"""


def _claims_from_request(request: Request) -> TokenClaims:
    claims = getattr(request.state, "token_claims", None)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
        )
    return claims


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """从中间件写入的 JWT claims 加载当前用户。"""
    claims = _claims_from_request(request)
    user = await db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    org_id, org_role, is_owner = await resolve_org_context(db, user)
    primary_unit_id, unit_ids = await resolve_user_units(db, user.id)
    unit_admin_unit_ids = await resolve_unit_admin_unit_ids(db, user.id)

    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        nickname=user.nickname,
        account_type=user.account_type,
        org_id=org_id,
        org_role=org_role,
        is_owner=is_owner,
        primary_unit_id=primary_unit_id,
        unit_ids=unit_ids,
        unit_admin_unit_ids=unit_admin_unit_ids,
    )


def assert_resource_owner(current_user: CurrentUser, owner_user_id: UUID) -> None:
    """SA-1 骨架：资源须属于当前用户（Wave 2 换为 kb_id 隔离）。"""
    if current_user.id != owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源",
        )


def _assert_kb_ownership(kb: KnowledgeBase, current_user: CurrentUser) -> None:
    """校验 kb 属于当前用户或其组织（SA-1）。

    W1-1：用户拥有的 personal 库（``owner_user_id == me``）始终允许，含 enterprise 账号（T7）。
    """
    if kb.owner_user_id == current_user.id:
        return

    if current_user.account_type == AccountType.personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该知识库",
        )

    assert current_user.org_id is not None
    if kb.owner_org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该知识库",
        )


def _assert_kb_action_allowed(current_user: CurrentUser, action: KbAction) -> None:
    """TECH-5 §5.3：企业 member 仅 read。"""
    if action == KbAction.read:
        return
    if (
        current_user.account_type == AccountType.enterprise
        and current_user.org_role == OrgRole.member
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足",
        )


async def require_kb_access(
    *,
    kb_id: UUID,
    action: KbAction,
    current_user: CurrentUser,
    db: AsyncSession,
    department_id: str | None = None,
) -> KnowledgeBase:
    """知识库权限二次校验：归属 + OrgScope + 角色动作矩阵。"""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    _assert_kb_ownership(kb, current_user)

    if kb.owner_org_id is not None and kb.owner_user_id is None:
        scope = await assert_kb_visible_in_org_scope(
            db,
            current_user,
            kb,
            department_id=department_id,
        )
        if action in (KbAction.write, KbAction.admin) and not scope.is_kb_writable(kb.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )

    _assert_kb_action_allowed(current_user, action)
    return kb


def require_org_role(*roles: OrgRole):
    """企业路由用：要求 JWT 中 org_role 在允许列表内。"""

    async def _checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.account_type != AccountType.enterprise:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要团队账号",
            )
        if current_user.org_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user

    return _checker


def require_owner():
    """企业路由用：要求当前用户为团队 Owner（is_owner）。"""

    async def _checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.account_type != AccountType.enterprise:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要团队账号",
            )
        if not current_user.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅团队所有者可执行此操作",
            )
        return current_user

    return _checker

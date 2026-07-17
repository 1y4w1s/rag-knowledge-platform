"""FastAPI 依赖：CurrentUser 与 RBAC（Wave 1.2+）。

Wave 2.1：``require_kb_access`` 基于 knowledge_bases 表做 kb_id 二次校验（TECH-5 / SA-1）。
ORG-1.2：团队库叠加 OrgScope（部门子树 + 公共库 + grant）。
"""

from enum import Enum
from typing import Annotated
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenClaims
from app.services.auth.api_key_auth import authenticate_api_key
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


def _claims_from_request(request: Request) -> TokenClaims | None:
    return getattr(request.state, "token_claims", None)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """从中间件写入的 JWT claims 或 API Key 加载当前用户。"""
    claims = _claims_from_request(request)
    if claims is None:
        # 尝试 API Key 认证（中间件将 raw token 存在 auth_token）
        raw_token = getattr(request.state, "auth_token", None)
        if raw_token:
            claims = await authenticate_api_key(db, raw_token)
    if claims is None:
        raise UnauthorizedError(detail="未提供认证凭据")
    user = await db.get(User, claims.user_id)
    if user is None:
        raise UnauthorizedError(detail="用户不存在")

    org_id, org_role, is_owner, custom_role_id, custom_role_is_admin = await resolve_org_context(db, user)
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
        custom_role_id=custom_role_id,
        custom_role_is_admin=custom_role_is_admin,
        primary_unit_id=primary_unit_id,
        unit_ids=unit_ids,
        unit_admin_unit_ids=unit_admin_unit_ids,
    )


def assert_resource_owner(current_user: CurrentUser, owner_user_id: UUID) -> None:
    """SA-1 骨架：资源须属于当前用户（Wave 2 换为 kb_id 隔离）。"""
    if current_user.id != owner_user_id:
        raise ForbiddenError(detail="无权访问该资源")


def _assert_kb_ownership(kb: KnowledgeBase, current_user: CurrentUser) -> None:
    """校验 kb 属于当前用户或其组织（SA-1）。

    W1-1：用户拥有的 personal 库（``owner_user_id == me``）始终允许，含 enterprise 账号（T7）。
    """
    if kb.owner_user_id == current_user.id:
        return

    if current_user.account_type == AccountType.personal:
        raise ForbiddenError(detail="无权访问该知识库")

    assert current_user.org_id is not None
    if kb.owner_org_id != current_user.org_id:
        raise ForbiddenError(detail="无权访问该知识库")


async def _assert_kb_action_allowed(
    current_user: CurrentUser,
    action: KbAction,
    *,
    db: AsyncSession,
    kb_id: UUID,
) -> None:
    """TECH-5 §5.3：企业 member 仅 read（除非有 custom_role 覆盖）。"""
    if action == KbAction.read:
        return
    if current_user.account_type != AccountType.enterprise:
        return
    if current_user.org_role != OrgRole.member:
        return

    # 检查是否有 custom_role 覆盖
    if current_user.custom_role_id:
        from app.models.custom_role import CustomRole
        role = await db.get(CustomRole, current_user.custom_role_id)
        if role and role.is_admin_level:
            return  # admin 级角色 → 放行
        if role and role.permissions:
            kb_perm = role.permissions.get(str(kb_id)) or role.permissions.get("*")
            if kb_perm in ("write", "admin"):
                return

    raise ForbiddenError(detail="权限不足")


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
        raise NotFoundError(detail="知识库不存在")

    _assert_kb_ownership(kb, current_user)

    if kb.owner_org_id is not None and kb.owner_user_id is None:
        scope = await assert_kb_visible_in_org_scope(
            db,
            current_user,
            kb,
            department_id=department_id,
        )
        if action in (KbAction.write, KbAction.admin) and not scope.is_kb_writable(kb.id):
            raise ForbiddenError(detail="权限不足")

    await _assert_kb_action_allowed(current_user, action, db=db, kb_id=kb_id)
    return kb


def require_org_role(*roles: OrgRole):
    """企业路由用：要求 JWT 中 org_role 在允许列表内。"""

    async def _checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.account_type != AccountType.enterprise:
            raise ForbiddenError(detail="需要团队账号")
        if current_user.org_role not in roles:
            raise ForbiddenError(detail="权限不足")
        return current_user

    return _checker


def require_owner():
    """企业路由用：要求当前用户为团队 Owner（is_owner）。"""

    async def _checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.account_type != AccountType.enterprise:
            raise ForbiddenError(detail="需要团队账号")
        if not current_user.is_owner:
            raise ForbiddenError(detail="仅团队所有者可执行此操作")
        return current_user

    return _checker

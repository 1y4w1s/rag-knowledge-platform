"""账号设置业务逻辑（Wave 5.3 + WS-2-7 填码加入 / 离开团队）。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.models.enums import AccountType, OrgRole
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.settings import (
    AccountSettingsResponse,
    ChangePasswordResponse,
    JoinTeamResponse,
    LeaveTeamResponse,
)
from app.services.auth.org_context import resolve_org_context
from app.services.auth.password import hash_password, verify_password
from app.services.auth.service import _validate_password
from app.services.organization.invites import resolve_valid_invite


async def get_account_settings(
    db: AsyncSession,
    current_user: CurrentUser,
) -> AccountSettingsResponse:
    org_name: str | None = None
    if current_user.org_id is not None:
        org = await db.get(Organization, current_user.org_id)
        if org is not None:
            org_name = org.name

    return AccountSettingsResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        nickname=current_user.nickname,
        account_type=current_user.account_type,
        org_id=current_user.org_id,
        org_role=current_user.org_role,
        org_name=org_name,
    )


async def change_password(
    db: AsyncSession,
    current_user: CurrentUser,
    *,
    current_password: str,
    new_password: str,
) -> ChangePasswordResponse:
    user = await db.get(User, current_user.id)
    if user is None:
        raise UnauthorizedError("用户不存在")

    if not verify_password(current_password, user.password_hash):
        raise ValidationError("当前密码不正确")

    _validate_password(new_password)

    if verify_password(new_password, user.password_hash):
        raise ValidationError("新密码不能与当前密码相同")

    user.password_hash = hash_password(new_password)
    await db.commit()

    return ChangePasswordResponse()


async def join_team_with_invite(
    db: AsyncSession,
    current_user: CurrentUser,
    *,
    invite_code: str,
) -> JoinTeamResponse:
    user = await db.get(User, current_user.id)
    if user is None:
        raise UnauthorizedError("用户不存在")

    existing = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    if existing is not None:
        if current_user.org_id is not None and existing.org_id == current_user.org_id:
            raise ConflictError("您已在团队中")
        raise ConflictError("该用户已属于其他团队")

    org, _invite = await resolve_valid_invite(db, invite_code)

    if user.account_type == AccountType.personal:
        user.account_type = AccountType.enterprise

    membership = OrganizationMember(
        id=uuid.uuid4(),
        org_id=org.id,
        user_id=user.id,
        role=OrgRole.member,
        is_owner=False,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(user)

    org_id, org_role, is_owner, _custom_role_id, _custom_role_is_admin = await resolve_org_context(db, user)
    account = await get_account_settings(
        db,
        CurrentUser(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            account_type=user.account_type,
            org_id=org_id,
            org_role=org_role,
            is_owner=is_owner,
        ),
    )
    return JoinTeamResponse(message=f"已加入团队 {org.name}", account=account)


async def leave_team(
    db: AsyncSession,
    current_user: CurrentUser,
) -> LeaveTeamResponse:
    """成员/管理员自退团队（WS-2-7 · Owner 须先转让）。"""
    if current_user.org_id is None:
        raise ConflictError("您未加入任何团队")

    membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.org_id == current_user.org_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if membership is None:
        raise ConflictError("您未加入任何团队")

    if membership.is_owner:
        raise ForbiddenError("离开前请先转让团队所有权")

    org = await db.get(Organization, current_user.org_id)
    org_name = org.name if org is not None else "团队"

    user = membership.user
    await db.delete(membership)
    if user.account_type == AccountType.enterprise:
        user.account_type = AccountType.personal
    await db.commit()
    await db.refresh(user)

    account = await get_account_settings(
        db,
        CurrentUser(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            account_type=user.account_type,
            org_id=None,
            org_role=None,
            is_owner=False,
        ),
    )
    return LeaveTeamResponse(message=f"已离开团队 {org_name}", account=account)


async def update_profile(
    db: AsyncSession,
    current_user: CurrentUser,
    *,
    nickname: str | None = None,
    username: str | None = None,
) -> AccountSettingsResponse:
    user = await db.get(User, current_user.id)
    if user is None:
        raise UnauthorizedError("用户不存在")

    if username is not None and username != user.username:
        existing = await db.scalar(
            select(User).where(User.username == username, User.id != user.id)
        )
        if existing is not None:
            raise ConflictError("用户名已被使用")
        user.username = username

    if nickname is not None:
        user.nickname = nickname

    await db.commit()
    await db.refresh(user)
    updated = CurrentUser(
        id=user.id, email=user.email, username=user.username,
        nickname=user.nickname, account_type=user.account_type,
        org_id=current_user.org_id, org_role=current_user.org_role,
        is_owner=current_user.is_owner,
    )
    return await get_account_settings(db, updated)

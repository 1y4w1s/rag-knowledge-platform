"""注册 / 登录业务逻辑（Wave 1.1 + 4.2.2 username）。"""

from __future__ import annotations

import uuid

import logging

from app.core.exceptions import ValidationError, ConflictError, UnauthorizedError, RateLimitError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AccountType, OrgRole, UnitRole
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.auth import LoginResponse, RegisterResponse, UserPublic
from app.services.audit.log import write_audit_log
from app.services.auth.jwt import create_access_token
from app.services.auth.login_rate_limit import (
    _rate_limit_key,
    clear_login_failures,
    is_ip_login_rate_limited,
    is_login_rate_limited,
    lockout_remaining,
    record_lockout_strike,
    record_login_failure,
)
from app.services.auth.org_context import (
    resolve_org_context,
    resolve_unit_admin_unit_ids,
    resolve_user_units,
)
from app.services.auth.password import hash_password, validate_password_strength, verify_password
from app.services.auth.username import normalize_nickname, validate_username
from app.services.observability.metrics_registry import inc_rate_limit_rejected
from app.services.org.units import add_unit_member, create_org_root_unit
from app.services.organization.invites import resolve_valid_invite

logger = logging.getLogger(__name__)


def _validate_password(password: str) -> None:
    """兼容旧调用名；实现见 password.validate_password_strength。"""
    validate_password_strength(password)

def _user_public(
    user: User,
    *,
    org_id: uuid.UUID | None,
    org_role: OrgRole | None,
    is_owner: bool = False,
    primary_unit_id: uuid.UUID | None = None,
    unit_ids: list[uuid.UUID] | None = None,
    unit_admin_unit_ids: list[uuid.UUID] | None = None,
) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        nickname=user.nickname,
        account_type=user.account_type,
        org_id=org_id,
        org_role=org_role,
        is_owner=is_owner,
        primary_unit_id=primary_unit_id,
        unit_ids=unit_ids or [],
        unit_admin_unit_ids=unit_admin_unit_ids or [],
    )


async def _find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    ident = identifier.strip()
    if not ident:
        return None
    if "@" in ident:
        return await db.scalar(select(User).where(User.email == ident.lower()))
    return await db.scalar(select(User).where(User.username == ident.lower()))


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    nickname: str | None,
    password: str,
    account_type: AccountType,
    org_name: str | None,
    invite_code: str | None,
) -> RegisterResponse:
    _validate_password(password)

    normalized_org_name = org_name.strip() if org_name else None
    normalized_invite_code = invite_code.strip() if invite_code else None

    if account_type == AccountType.personal:
        if normalized_org_name:
            raise ValidationError("个人账号注册不需要团队名称")
        if normalized_invite_code:
            raise ValidationError("个人账号注册不需要邀请码")
    elif account_type == AccountType.enterprise:
        if normalized_org_name and normalized_invite_code:
            raise ValidationError("不能同时填写团队名称和邀请码")
        if not normalized_org_name and not normalized_invite_code:
            raise ValidationError("团队账号注册必须填写团队名称或邀请码")

    normalized_email = email.strip().lower()
    normalized_username = validate_username(username)
    normalized_nickname = normalize_nickname(nickname)

    existing = await db.scalar(
        select(User).where(
            or_(User.email == normalized_email, User.username == normalized_username)
        )
    )
    if existing:
        # P2-S3 防枚举：冲突响应不区分邮箱/用户名，避免暴露注册邮箱是否存在。
        logger.info(
            "register conflict: email=%s username=%s reason=email_or_username_exists",
            normalized_email,
            normalized_username,
        )
        raise ConflictError("该邮箱或用户名已被使用")

    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        username=normalized_username,
        nickname=normalized_nickname,
        password_hash=hash_password(password),
        account_type=account_type,
    )
    db.add(user)

    org_id: uuid.UUID | None = None
    org_role: OrgRole | None = None
    is_owner = False

    if account_type == AccountType.enterprise:
        if normalized_invite_code:
            org, _invite = await resolve_valid_invite(db, normalized_invite_code)
            membership = OrganizationMember(
                id=uuid.uuid4(),
                org_id=org.id,
                user_id=user.id,
                role=OrgRole.member,
                is_owner=False,
            )
            db.add(membership)
            org_id = org.id
            org_role = OrgRole.member
        else:
            assert normalized_org_name is not None
            org = Organization(id=uuid.uuid4(), name=normalized_org_name)
            db.add(org)
            await db.flush()
            root = await create_org_root_unit(db, org_id=org.id, name=normalized_org_name)
            membership = OrganizationMember(
                id=uuid.uuid4(),
                org_id=org.id,
                user_id=user.id,
                role=OrgRole.admin,
                is_owner=True,
            )
            db.add(membership)
            await add_unit_member(
                db,
                org_unit_id=root.id,
                user_id=user.id,
                role=UnitRole.unit_admin,
                is_primary=True,
            )
            org_id = org.id
            org_role = OrgRole.admin
            is_owner = True

    await db.commit()
    await db.refresh(user)

    logger.info(
        "register success: user_id=%s email=%s account_type=%s org_id=%s role=%s",
        user.id, normalized_email, account_type.value, org_id, org_role.value if org_role else None,
    )

    primary_unit_id, unit_ids = await resolve_user_units(db, user.id)
    unit_admin_unit_ids = await resolve_unit_admin_unit_ids(db, user.id)

    return RegisterResponse(
        user=_user_public(
            user,
            org_id=org_id,
            org_role=org_role,
            is_owner=is_owner,
            primary_unit_id=primary_unit_id,
            unit_ids=unit_ids,
            unit_admin_unit_ids=unit_admin_unit_ids,
        )
    )


async def login_user(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    ip: str | None = None,
) -> LoginResponse:
    user = await _find_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.password_hash):
        lockout_key = _rate_limit_key(ip, identifier)
        remaining = await lockout_remaining(lockout_key)
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            logger.info("login locked: identifier=%s ip=%s lockout_remaining=%ds", identifier, ip, remaining)
            inc_rate_limit_rejected("login")
            raise RateLimitError(msg)

        if await is_ip_login_rate_limited(ip):
            logger.info("login ip_rate_limited: identifier=%s ip=%s", identifier, ip)
            try:
                await write_audit_log(
                    db,
                    action="auth.ip_rate_limited",
                    metadata={"identifier": identifier.strip()},
                    ip=ip,
                )
                await db.commit()
            except Exception:
                pass
            inc_rate_limit_rejected("login")
            raise RateLimitError("当前 IP 登录失败次数过多，请稍后重试")

        if await is_login_rate_limited(ip, identifier):
            lockout_key = _rate_limit_key(ip, identifier)
            await record_lockout_strike(lockout_key)
            remaining = await lockout_remaining(lockout_key)
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            logger.info("login rate_limited: identifier=%s ip=%s strike_duration=%ds", identifier, ip, remaining)
            try:
                await write_audit_log(
                    db,
                    action="auth.login_rate_limited",
                    metadata={"identifier": identifier.strip(), "lockout_seconds": remaining},
                    ip=ip,
                )
                await db.commit()
            except Exception:
                pass
            inc_rate_limit_rejected("login")
            raise RateLimitError(msg)
        await record_login_failure(ip, identifier)
        logger.info("login failed: identifier=%s ip=%s reason=bad_credentials", identifier, ip)
        await write_audit_log(
            db,
            action="auth.login_failed",
            metadata={"identifier": identifier.strip()},
            ip=ip,
        )
        await db.commit()
        raise UnauthorizedError("用户名/邮箱或密码错误")

    await clear_login_failures(ip, identifier)

    org_id, org_role, is_owner, custom_role_id, custom_role_is_admin = await resolve_org_context(db, user)
    primary_unit_id, unit_ids = await resolve_user_units(db, user.id)
    unit_admin_unit_ids = await resolve_unit_admin_unit_ids(db, user.id)

    token = create_access_token(
        user_id=user.id,
        account_type=user.account_type,
        org_id=org_id,
        org_role=org_role,
        custom_role_id=custom_role_id,
        custom_role_is_admin=custom_role_is_admin,
    )

    logger.info(
        "login success: user_id=%s account_type=%s org_id=%s org_role=%s ip=%s",
        user.id, user.account_type.value, org_id, org_role.value if org_role else None, ip,
    )

    await write_audit_log(
        db,
        action="auth.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip=ip,
    )
    await db.commit()

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=_user_public(
            user,
            org_id=org_id,
            org_role=org_role,
            is_owner=is_owner,
            primary_unit_id=primary_unit_id,
            unit_ids=unit_ids,
            unit_admin_unit_ids=unit_admin_unit_ids,
        ),
    )

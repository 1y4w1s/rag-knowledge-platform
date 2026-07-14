"""注册 / 登录业务逻辑（Wave 1.1 + 4.2.2 username）。"""

import re
from time import monotonic
import uuid

from fastapi import status
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
    clear_login_failures,
    is_ip_login_rate_limited,
    is_login_rate_limited,
    record_login_failure,
)
from app.services.auth.org_context import (
    resolve_org_context,
    resolve_unit_admin_unit_ids,
    resolve_user_units,
)
from app.services.auth.password import hash_password, verify_password
from app.services.auth.username import normalize_nickname, validate_username
from app.services.org.units import add_unit_member, create_org_root_unit
from app.services.organization.invites import resolve_valid_invite

MIN_PASSWORD_LEN = 8


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise ValidationError(detail=f"password at least {MIN_PASSWORD_LEN} chars")
    if not re.search(r"[A-Z]", password):
        raise ValidationError(detail="password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValidationError(detail="password must contain a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValidationError(detail="password must contain a digit")
    if not re.search(r"[!@#$%^&*(),.?\"{}|<>_\-+=~`\[\];'\\/]", password):
        raise ValidationError(detail="password must contain a special character")


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
        if existing.email == normalized_email:
            raise ConflictError("该邮箱已注册")
        raise ConflictError("该用户名已被使用")

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
        # 渐进式锁定期检查
        lockout_key = _rate_limit_key(ip, identifier)
        remaining = _lockout_remaining(lockout_key, now=monotonic())
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            raise RateLimitError(msg)

        # IP 维度限流：同 IP 20 次/5min → 429
        if is_ip_login_rate_limited(ip):
            await write_audit_log(
                db,
                action="auth.ip_rate_limited",
                metadata={"identifier": identifier.strip()},
                ip=ip,
            )
            await db.commit()
            raise RateLimitError("当前 IP 登录失败次数过多，请稍后重试")

        # identifier 维度限流：5 次/15min → 429
        if is_login_rate_limited(ip, identifier):
            lockout_key = _rate_limit_key(ip, identifier)
            record_lockout_strike(lockout_key)
            remaining = _lockout_remaining(lockout_key)
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            await write_audit_log(
                db,
                action="auth.login_rate_limited",
                metadata={"identifier": identifier.strip(), "lockout_seconds": remaining},
                ip=ip,
            )
            await db.commit()
            raise RateLimitError(msg)
        record_login_failure(ip, identifier)
        await write_audit_log(
            db,
            action="auth.login_failed",
            metadata={"identifier": identifier.strip()},
            ip=ip,
        )
        await db.commit()
        raise UnauthorizedError("用户名/邮箱或密码错误")

    clear_login_failures(ip, identifier)

    org_id, org_role, is_owner = await resolve_org_context(db, user)
    primary_unit_id, unit_ids = await resolve_user_units(db, user.id)
    unit_admin_unit_ids = await resolve_unit_admin_unit_ids(db, user.id)

    token = create_access_token(
        user_id=user.id,
        account_type=user.account_type,
        org_id=org_id,
        org_role=org_role,
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

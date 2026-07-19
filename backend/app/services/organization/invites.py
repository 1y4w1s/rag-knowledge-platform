"""组织邀请码：校验、发码（W5+-2 · WS-1-2 §2.6）。"""

import re
import secrets
import string
import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import ValidationError, NotFoundError, ServiceError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.organization_invite_code import OrganizationInviteCode
from app.schemas.organization import OrganizationInviteResponse

INVITE_CODE_MIN_LEN = 4
INVITE_CODE_MAX_LEN = 64
INVITE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,63}$")
INVITE_INVALID_MSG = "邀请码无效或已过期"
_CODE_ALPHABET = string.ascii_uppercase + string.digits


def normalize_invite_code(raw: str) -> str:
    """规范化邀请码；格式不对抛 422。"""
    normalized = raw.strip().upper()
    if len(normalized) < INVITE_CODE_MIN_LEN or len(normalized) > INVITE_CODE_MAX_LEN:
        raise ValidationError(INVITE_INVALID_MSG)
    if not INVITE_CODE_PATTERN.fullmatch(normalized):
        raise ValidationError(INVITE_INVALID_MSG)
    return normalized


def _is_invite_active(row: OrganizationInviteCode, *, now: datetime | None = None) -> bool:
    if row.revoked_at is not None:
        return False
    if row.expires_at is not None:
        current = now or datetime.now(timezone.utc)
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < current:
            return False
    return True


async def resolve_valid_invite(
    db: AsyncSession,
    raw_code: str,
) -> tuple[Organization, OrganizationInviteCode]:
    """校验邀请码有效；无效统一 422。"""
    normalized = normalize_invite_code(raw_code)
    row = await db.scalar(
        select(OrganizationInviteCode)
        .where(OrganizationInviteCode.code == normalized)
    )
    if row is None or not _is_invite_active(row):
        raise ValidationError(INVITE_INVALID_MSG)

    org = await db.get(Organization, row.org_id)
    if org is None:
        raise ValidationError(INVITE_INVALID_MSG)
    return org, row


def _generate_code_suffix(length: int = 4) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


async def create_organization_invite(
    db: AsyncSession,
    *,
    org_id: UUID,
    created_by: UUID,
    expires_at: datetime | None = None,
) -> OrganizationInviteResponse:
    """管理员发码；码可多人用（I1）。"""
    for _ in range(8):
        code = f"ZHIAN-{_generate_code_suffix()}"
        existing = await db.scalar(
            select(OrganizationInviteCode.id).where(OrganizationInviteCode.code == code)
        )
        if existing is None:
            break
    else:
        raise ServiceError("无法生成邀请码，请重试")

    row = OrganizationInviteCode(
        id=uuid.uuid4(),
        code=code,
        org_id=org_id,
        expires_at=expires_at,
        created_by=created_by,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return OrganizationInviteResponse(
        code=row.code,
        org_id=row.org_id,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


async def revoke_organization_invite_code(db: AsyncSession, *, code: str) -> None:
    """撤销邀请码（测试 / 管理用）。"""
    normalized = normalize_invite_code(code)
    row = await db.scalar(
        select(OrganizationInviteCode).where(OrganizationInviteCode.code == normalized)
    )
    if row is None:
        raise NotFoundError("邀请码不存在")
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()

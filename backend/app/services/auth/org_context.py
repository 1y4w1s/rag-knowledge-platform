"""企业用户 org_id / org_role / 部门归属解析（以 DB 为准，供 login 与 get_current_user 共用）。"""

from uuid import UUID

from fastapi import status
from app.core.exceptions import ServiceError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AccountType, OrgRole, UnitRole
from app.models.org_unit_member import OrgUnitMember
from app.models.organization_member import OrganizationMember
from app.models.user import User


async def resolve_org_context(
    db: AsyncSession,
    user: User,
) -> tuple[UUID | None, OrgRole | None, bool, UUID | None, bool]:
    if user.account_type != AccountType.enterprise:
        return None, None, False, None, False

    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    if membership is None:
        raise ServiceError("团队账号缺少团队成员记录")

    custom_role_id = None
    custom_role_is_admin = False
    if membership.custom_role_id:
        from app.models.custom_role import CustomRole
        role = await db.get(CustomRole, membership.custom_role_id)
        if role:
            custom_role_id = role.id
            custom_role_is_admin = role.is_admin_level

    return membership.org_id, membership.role, membership.is_owner, custom_role_id, custom_role_is_admin


async def resolve_user_units(
    db: AsyncSession,
    user_id: UUID,
) -> tuple[UUID | None, list[UUID]]:
    """主部门 + 兼任部门列表（Plan-0.4 · ORG-2.5 前端未分配 Banner）。"""
    rows = await db.scalars(
        select(OrgUnitMember).where(OrgUnitMember.user_id == user_id)
    )
    memberships = list(rows.all())
    unit_ids = [membership.org_unit_id for membership in memberships]
    primary: UUID | None = None
    for membership in memberships:
        if membership.is_primary:
            primary = membership.org_unit_id
            break
    return primary, unit_ids


async def resolve_unit_admin_unit_ids(
    db: AsyncSession,
    user_id: UUID,
) -> list[UUID]:
    """用户担任 unit_admin 的部门 id 列表（ORG-4.1 建库 UI）。"""
    rows = await db.scalars(
        select(OrgUnitMember.org_unit_id).where(
            OrgUnitMember.user_id == user_id,
            OrgUnitMember.role == UnitRole.unit_admin,
        )
    )
    return list(rows.all())

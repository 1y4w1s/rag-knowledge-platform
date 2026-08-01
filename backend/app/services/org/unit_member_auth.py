"""部门成员鉴权（NW-24）：本节点 unit_admin + 最后一名闸。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import AccountType, UnitRole
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.services.org.scope import _is_company_admin, _load_unit_memberships


async def assert_can_manage_unit_members(
    db: AsyncSession,
    current_user: CurrentUser,
    unit_id: UUID,
) -> None:
    """公司 Admin，或对该 unit_id 精确为 unit_admin，可管本节点成员。

    不按子树放行（与 grant/建库不同）。
    """
    if current_user.account_type != AccountType.enterprise:
        raise ForbiddenError("需要团队账号")
    if current_user.org_id is None:
        raise ForbiddenError("权限不足")

    unit = await db.scalar(
        select(OrgUnit).where(
            OrgUnit.id == unit_id,
            OrgUnit.org_id == current_user.org_id,
        )
    )
    if unit is None:
        raise NotFoundError("部门不存在")

    if _is_company_admin(current_user):
        return

    memberships = await _load_unit_memberships(
        db,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )
    if any(
        m.org_unit_id == unit_id and m.role == UnitRole.unit_admin for m in memberships
    ):
        return
    raise ForbiddenError("权限不足")


async def _count_unit_admins(db: AsyncSession, unit_id: UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(OrgUnitMember)
        .where(
            OrgUnitMember.org_unit_id == unit_id,
            OrgUnitMember.role == UnitRole.unit_admin,
        )
    )
    return int(count or 0)


async def assert_not_last_unit_admin(
    db: AsyncSession,
    *,
    unit_id: UUID,
    membership: OrgUnitMember,
    allow_remove_last_admin: bool,
    removing: bool = False,
    new_role: UnitRole | None = None,
) -> None:
    """禁止非公司 Admin 把本节点唯一 unit_admin 降级或移出。"""
    if allow_remove_last_admin:
        return
    if membership.role != UnitRole.unit_admin:
        return
    demoting = new_role is not None and new_role != UnitRole.unit_admin
    if not removing and not demoting:
        return
    if await _count_unit_admins(db, unit_id) <= 1:
        raise BadRequestError("部门至少保留一名部门管理员")

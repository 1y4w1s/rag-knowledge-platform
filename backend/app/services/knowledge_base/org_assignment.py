"""资料库归属部门解析与校验（ORG-4.1）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import status
from app.core.exceptions import ForbiddenError, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.enums import OrgRole, UnitRole
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.services.org.scope import (
    _is_company_admin,
    _load_unit_memberships,
    _load_units_for_org,
    resolve_org_scope,
)


async def assert_can_create_org_kb(
    db: AsyncSession,
    current_user: CurrentUser,
) -> None:
    """团队空间建库：公司 Admin/Owner 或任一部门 unit_admin；普通 Member 403。"""
    if _is_company_admin(current_user):
        return

    assert current_user.org_id is not None
    memberships = await _load_unit_memberships(
        db,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )
    if any(m.role == UnitRole.unit_admin for m in memberships):
        return

    if current_user.org_role == OrgRole.member:
        raise ForbiddenError("权限不足")


def _unit_admin_managed_subtree_ids(
    memberships: list[OrgUnitMember],
    units: list[OrgUnit],
) -> frozenset[UUID]:
    by_id = {u.id: u for u in units}
    managed: set[UUID] = set()
    for membership in memberships:
        if membership.role != UnitRole.unit_admin:
            continue
        unit = by_id.get(membership.org_unit_id)
        if unit is None:
            continue
        managed.update(u.id for u in units if u.path.startswith(unit.path))
    return frozenset(managed)


async def _assert_unit_belongs_to_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    unit_id: UUID,
) -> OrgUnit:
    unit = await db.get(OrgUnit, unit_id)
    if unit is None or unit.org_id != org_id:
        raise ValidationError("无效的部门 ID")
    return unit


async def resolve_and_validate_kb_org_unit_id(
    db: AsyncSession,
    current_user: CurrentUser,
    *,
    org_unit_id: UUID | None,
    org_unit_id_in_body: bool,
    department_id: str | None,
) -> UUID | None:
    """解析建库时的 org_unit_id（None = 公司公共库）。"""
    assert current_user.org_id is not None
    org_id = current_user.org_id

    if not org_unit_id_in_body:
        scope = await resolve_org_scope(
            db, current_user, department_id=department_id
        )
        if scope.view_all_departments or scope.department_unit_id is None:
            raise ValidationError("请指定资料库归属部门")
        target = scope.department_unit_id
    elif org_unit_id is None:
        if not _is_company_admin(current_user):
            raise ForbiddenError("无权创建公司公共资料库")
        return None
    else:
        target = org_unit_id

    await _assert_unit_belongs_to_org(db, org_id=org_id, unit_id=target)

    if _is_company_admin(current_user):
        return target

    memberships = await _load_unit_memberships(
        db, org_id=org_id, user_id=current_user.id
    )
    units = await _load_units_for_org(db, org_id)
    managed = _unit_admin_managed_subtree_ids(memberships, units)
    if target not in managed:
        raise ForbiddenError("无权将资料库归属到该部门")
    return target

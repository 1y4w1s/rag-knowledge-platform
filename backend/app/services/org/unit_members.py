"""部门成员业务逻辑（ORG-2.2）。"""

from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.org_unit_member import (
    OrgUnitMemberCreate,
    OrgUnitMemberResponse,
    OrgUnitMemberUpdate,
)
from app.services.audit.log import write_audit_log


async def _get_unit_in_org(
    db: AsyncSession,
    org_id: UUID,
    unit_id: UUID,
) -> OrgUnit:
    unit = await db.scalar(
        select(OrgUnit).where(OrgUnit.id == unit_id, OrgUnit.org_id == org_id)
    )
    if unit is None:
        raise NotFoundError("部门不存在")
    return unit


async def _assert_org_member(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
) -> User:
    row = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if row is None:
        raise NotFoundError("该用户不是团队成员")
    return row.user


async def _get_membership(
    db: AsyncSession,
    unit_id: UUID,
    user_id: UUID,
) -> OrgUnitMember | None:
    return await db.scalar(
        select(OrgUnitMember)
        .where(
            OrgUnitMember.org_unit_id == unit_id,
            OrgUnitMember.user_id == user_id,
        )
        .options(selectinload(OrgUnitMember.user))
    )


async def _list_user_memberships_in_org(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
) -> list[OrgUnitMember]:
    rows = await db.scalars(
        select(OrgUnitMember)
        .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
        .where(OrgUnit.org_id == org_id, OrgUnitMember.user_id == user_id)
        .order_by(OrgUnitMember.joined_at.asc())
    )
    return list(rows.all())


async def _clear_primary_for_user_in_org(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    *,
    except_unit_id: UUID | None = None,
) -> None:
    unit_ids = select(OrgUnit.id).where(OrgUnit.org_id == org_id)
    stmt = (
        update(OrgUnitMember)
        .where(
            OrgUnitMember.user_id == user_id,
            OrgUnitMember.org_unit_id.in_(unit_ids),
            OrgUnitMember.is_primary.is_(True),
        )
        .values(is_primary=False)
    )
    if except_unit_id is not None:
        stmt = stmt.where(OrgUnitMember.org_unit_id != except_unit_id)
    await db.execute(stmt)


async def _promote_fallback_primary(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
) -> None:
    memberships = await _list_user_memberships_in_org(db, org_id, user_id)
    if not memberships:
        return
    if any(row.is_primary for row in memberships):
        return
    memberships[0].is_primary = True


def _to_response(member: OrgUnitMember) -> OrgUnitMemberResponse:
    return OrgUnitMemberResponse(
        id=member.id,
        org_unit_id=member.org_unit_id,
        user_id=member.user_id,
        email=member.user.email,
        role=member.role,
        is_primary=member.is_primary,
        joined_at=member.joined_at,
    )


async def list_unit_members(
    db: AsyncSession,
    org_id: UUID,
    unit_id: UUID,
) -> list[OrgUnitMemberResponse]:
    await _get_unit_in_org(db, org_id, unit_id)
    rows = await db.scalars(
        select(OrgUnitMember)
        .where(OrgUnitMember.org_unit_id == unit_id)
        .options(selectinload(OrgUnitMember.user))
        .order_by(OrgUnitMember.joined_at.asc())
    )
    return [_to_response(row) for row in rows.all()]


async def add_unit_member_from_roster(
    db: AsyncSession,
    *,
    org_id: UUID,
    unit_id: UUID,
    body: OrgUnitMemberCreate,
    acting_user_id: UUID,
    ip: str | None = None,
) -> OrgUnitMemberResponse:
    unit = await _get_unit_in_org(db, org_id, unit_id)
    user = await _assert_org_member(db, org_id, body.user_id)

    existing = await _get_membership(db, unit_id, body.user_id)
    if existing is not None:
        raise ConflictError("该用户已是此部门成员")

    if body.is_primary:
        await _clear_primary_for_user_in_org(db, org_id, body.user_id)

    member = OrgUnitMember(
        org_unit_id=unit_id,
        user_id=body.user_id,
        role=body.role,
        is_primary=body.is_primary,
    )
    db.add(member)
    await db.flush()

    if not body.is_primary:
        await _promote_fallback_primary(db, org_id, body.user_id)

    await write_audit_log(
        db,
        action="org_unit.member_add",
        actor_user_id=acting_user_id,
        resource_type="user",
        resource_id=body.user_id,
        metadata={
            "unit_id": str(unit_id),
            "unit_name": unit.name,
            "email": user.email,
            "role": body.role.value,
            "is_primary": body.is_primary,
        },
        ip=ip,
    )
    await db.commit()
    await db.refresh(member)
    member.user = user
    return _to_response(member)


async def update_unit_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    unit_id: UUID,
    user_id: UUID,
    body: OrgUnitMemberUpdate,
    acting_user_id: UUID,
    ip: str | None = None,
) -> OrgUnitMemberResponse:
    unit = await _get_unit_in_org(db, org_id, unit_id)
    membership = await _get_membership(db, unit_id, user_id)

    if membership is None:
        if body.is_primary is True:
            await _assert_org_member(db, org_id, user_id)
            raise ValidationError("用户未加入该部门")
        raise NotFoundError("该用户不是此部门成员")

    old_role = membership.role
    old_primary = membership.is_primary
    changed = False

    if body.role is not None and body.role != membership.role:
        membership.role = body.role
        changed = True

    if body.is_primary is True and not membership.is_primary:
        await _clear_primary_for_user_in_org(
            db,
            org_id,
            user_id,
            except_unit_id=unit_id,
        )
        membership.is_primary = True
        changed = True
    elif body.is_primary is False and membership.is_primary:
        membership.is_primary = False
        await _promote_fallback_primary(db, org_id, user_id)
        changed = True

    if changed:
        metadata: dict[str, object] = {
            "unit_id": str(unit_id),
            "unit_name": unit.name,
            "email": membership.user.email,
        }
        if body.role is not None and old_role != membership.role:
            metadata["old_role"] = old_role.value
            metadata["new_role"] = membership.role.value
        if body.is_primary is not None and old_primary != membership.is_primary:
            metadata["old_primary"] = old_primary
            metadata["new_primary"] = membership.is_primary
        await write_audit_log(
            db,
            action="org_unit.member_update",
            actor_user_id=acting_user_id,
            resource_type="user",
            resource_id=user_id,
            metadata=metadata,
            ip=ip,
        )

    await db.commit()
    await db.refresh(membership)
    return _to_response(membership)


async def remove_unit_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    unit_id: UUID,
    user_id: UUID,
    acting_user_id: UUID,
    ip: str | None = None,
) -> None:
    unit = await _get_unit_in_org(db, org_id, unit_id)
    membership = await _get_membership(db, unit_id, user_id)
    if membership is None:
        raise NotFoundError("该用户不是此部门成员")

    was_primary = membership.is_primary
    await write_audit_log(
        db,
        action="org_unit.member_remove",
        actor_user_id=acting_user_id,
        resource_type="user",
        resource_id=user_id,
        metadata={
            "unit_id": str(unit_id),
            "unit_name": unit.name,
            "email": membership.user.email,
            "role": membership.role.value,
            "was_primary": was_primary,
        },
        ip=ip,
    )
    await db.delete(membership)
    await db.flush()

    if was_primary:
        await _promote_fallback_primary(db, org_id, user_id)

    await db.commit()


async def count_primary_units_for_user(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(OrgUnitMember)
        .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
        .where(
            OrgUnit.org_id == org_id,
            OrgUnitMember.user_id == user_id,
            OrgUnitMember.is_primary.is_(True),
        )
    )
    return int(count or 0)

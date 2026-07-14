"""部门树辅助：建根节点、子节点、物化路径与 Admin CRUD（ORG-2.1）。"""

import uuid
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UnitRole
from app.models.knowledge_base import KnowledgeBase
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.schemas.org_unit import OrgUnitResponse
from app.services.audit.log import write_audit_log


def unit_path(*, parent_path: str | None, unit_id: UUID) -> str:
    if parent_path is None:
        return f"/{unit_id}/"
    return f"{parent_path}{unit_id}/"


async def get_org_root_unit(db: AsyncSession, org_id: UUID) -> OrgUnit | None:
    return await db.scalar(
        select(OrgUnit)
        .where(OrgUnit.org_id == org_id, OrgUnit.parent_id.is_(None))
        .limit(1)
    )


async def create_org_root_unit(
    db: AsyncSession,
    *,
    org_id: UUID,
    name: str,
) -> OrgUnit:
    unit_id = uuid.uuid4()
    root = OrgUnit(
        id=unit_id,
        org_id=org_id,
        parent_id=None,
        name=name,
        path=unit_path(parent_path=None, unit_id=unit_id),
        depth=0,
    )
    db.add(root)
    await db.flush()
    return root


async def create_org_unit(
    db: AsyncSession,
    *,
    org_id: UUID,
    name: str,
    parent: OrgUnit,
) -> OrgUnit:
    unit_id = uuid.uuid4()
    child = OrgUnit(
        id=unit_id,
        org_id=org_id,
        parent_id=parent.id,
        name=name,
        path=unit_path(parent_path=parent.path, unit_id=unit_id),
        depth=parent.depth + 1,
    )
    db.add(child)
    await db.flush()
    return child


async def add_unit_member(
    db: AsyncSession,
    *,
    org_unit_id: UUID,
    user_id: UUID,
    role: UnitRole,
    is_primary: bool = False,
) -> OrgUnitMember:
    member = OrgUnitMember(
        org_unit_id=org_unit_id,
        user_id=user_id,
        role=role,
        is_primary=is_primary,
    )
    db.add(member)
    await db.flush()
    return member


def _normalize_unit_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValidationError("名称不能为空")
    if len(normalized) > 64:
        raise ValidationError("部门名称不能超过 64 个字符")
    return normalized


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


async def _assert_sibling_name_available(
    db: AsyncSession,
    *,
    org_id: UUID,
    parent_id: UUID | None,
    name: str,
    exclude_unit_id: UUID | None = None,
) -> None:
    stmt = select(OrgUnit.id).where(
        OrgUnit.org_id == org_id,
        OrgUnit.parent_id == parent_id,
        func.lower(func.btrim(OrgUnit.name)) == name.lower(),
    )
    if exclude_unit_id is not None:
        stmt = stmt.where(OrgUnit.id != exclude_unit_id)
    if await db.scalar(stmt.limit(1)) is not None:
        raise ConflictError("同级已存在同名部门")


async def _count_children(db: AsyncSession, unit_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(OrgUnit)
            .where(OrgUnit.parent_id == unit_id)
        )
        or 0
    )


async def _count_members(db: AsyncSession, unit_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(OrgUnitMember)
            .where(OrgUnitMember.org_unit_id == unit_id)
        )
        or 0
    )


async def _count_knowledge_bases(db: AsyncSession, unit_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.org_unit_id == unit_id)
        )
        or 0
    )


async def _unit_to_response(db: AsyncSession, unit: OrgUnit) -> OrgUnitResponse:
    return OrgUnitResponse(
        id=unit.id,
        org_id=unit.org_id,
        parent_id=unit.parent_id,
        name=unit.name,
        depth=unit.depth,
        child_count=await _count_children(db, unit.id),
        member_count=await _count_members(db, unit.id),
        kb_count=await _count_knowledge_bases(db, unit.id),
        created_at=unit.created_at,
    )


async def list_org_units(db: AsyncSession, org_id: UUID) -> list[OrgUnitResponse]:
    units = (
        await db.scalars(
            select(OrgUnit)
            .where(OrgUnit.org_id == org_id)
            .order_by(OrgUnit.depth.asc(), OrgUnit.name.asc())
        )
    ).all()
    return [await _unit_to_response(db, unit) for unit in units]


async def list_picker_org_units(
    db: AsyncSession,
    org_id: UUID,
    *,
    is_company_admin: bool,
    member_unit_ids: list[UUID],
) -> list[OrgUnitResponse]:
    """侧栏部门选择器：Admin 全树；Member 仅兼任路径上的节点（ORG-3.2）。"""
    if is_company_admin:
        return await list_org_units(db, org_id)

    if not member_unit_ids:
        return []

    all_units = (
        await db.scalars(select(OrgUnit).where(OrgUnit.org_id == org_id))
    ).all()
    by_id = {unit.id: unit for unit in all_units}

    visible_ids: set[UUID] = set()
    for unit_id in member_unit_ids:
        current = by_id.get(unit_id)
        while current is not None:
            visible_ids.add(current.id)
            if current.parent_id is None:
                break
            current = by_id.get(current.parent_id)

    visible_units = [by_id[uid] for uid in visible_ids if uid in by_id]
    visible_units.sort(key=lambda unit: (unit.depth, unit.name))
    return [await _unit_to_response(db, unit) for unit in visible_units]


async def get_org_unit(db: AsyncSession, org_id: UUID, unit_id: UUID) -> OrgUnitResponse:
    unit = await _get_unit_in_org(db, org_id, unit_id)
    return await _unit_to_response(db, unit)


async def create_child_org_unit(
    db: AsyncSession,
    *,
    org_id: UUID,
    name: str,
    parent_id: UUID,
    acting_user_id: UUID,
    ip: str | None = None,
) -> OrgUnitResponse:
    normalized = _normalize_unit_name(name)
    parent = await _get_unit_in_org(db, org_id, parent_id)
    await _assert_sibling_name_available(
        db,
        org_id=org_id,
        parent_id=parent.id,
        name=normalized,
    )
    child = await create_org_unit(
        db,
        org_id=org_id,
        name=normalized,
        parent=parent,
    )
    await write_audit_log(
        db,
        action="org_unit.create",
        actor_user_id=acting_user_id,
        resource_type="org_unit",
        resource_id=child.id,
        metadata={
            "name": normalized,
            "parent_id": str(parent.id),
            "parent_name": parent.name,
        },
        ip=ip,
    )
    await db.commit()
    await db.refresh(child)
    return await _unit_to_response(db, child)


async def update_org_unit_name(
    db: AsyncSession,
    *,
    org_id: UUID,
    unit_id: UUID,
    name: str,
    acting_user_id: UUID,
    ip: str | None = None,
) -> OrgUnitResponse:
    normalized = _normalize_unit_name(name)
    unit = await _get_unit_in_org(db, org_id, unit_id)
    if unit.name == normalized:
        return await _unit_to_response(db, unit)

    await _assert_sibling_name_available(
        db,
        org_id=org_id,
        parent_id=unit.parent_id,
        name=normalized,
        exclude_unit_id=unit.id,
    )
    old_name = unit.name
    unit.name = normalized
    await write_audit_log(
        db,
        action="org_unit.rename",
        actor_user_id=acting_user_id,
        resource_type="org_unit",
        resource_id=unit.id,
        metadata={"old_name": old_name, "new_name": normalized},
        ip=ip,
    )
    await db.commit()
    await db.refresh(unit)
    return await _unit_to_response(db, unit)


async def delete_org_unit(
    db: AsyncSession,
    org_id: UUID,
    unit_id: UUID,
    *,
    acting_user_id: UUID,
    ip: str | None = None,
) -> None:
    unit = await _get_unit_in_org(db, org_id, unit_id)

    child_count = await _count_children(db, unit.id)
    if child_count > 0:
        raise ConflictError("请先删除或移动子部门")

    kb_count = await _count_knowledge_bases(db, unit.id)
    if kb_count > 0:
        raise ConflictError("该部门下仍有资料库")

    member_count = await _count_members(db, unit.id)
    if member_count > 0:
        raise ConflictError("该部门下仍有成员")

    await write_audit_log(
        db,
        action="org_unit.delete",
        actor_user_id=acting_user_id,
        resource_type="org_unit",
        resource_id=unit.id,
        metadata={
            "name": unit.name,
            "parent_id": str(unit.parent_id) if unit.parent_id else None,
        },
        ip=ip,
    )
    await db.delete(unit)
    await db.commit()

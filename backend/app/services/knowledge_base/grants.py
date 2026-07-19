"""资料库跨部门 grant CRUD（ORG-4.2）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import status
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError, ConflictError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.enums import AccountType, GranteeType, OrgRole, UnitRole
from app.models.kb_unit_grant import KbUnitGrant
from app.models.knowledge_base import KnowledgeBase
from app.models.org_unit import OrgUnit
from app.schemas.kb_grant import KbGrantCreate, KbGrantListResponse, KbGrantResponse
from app.services.audit.log import write_audit_log
from app.services.knowledge_base.org_assignment import _unit_admin_managed_subtree_ids
from app.services.org.scope import (
    _is_company_admin,
    _load_unit_memberships,
    _load_units_for_org,
)


def _grant_to_response(grant: KbUnitGrant) -> KbGrantResponse:
    return KbGrantResponse(
        id=grant.id,
        kb_id=grant.kb_id,
        grantee_type=grant.grantee_type,
        grantee_id=grant.grantee_id,
        permission=grant.permission,
        created_at=grant.created_at,
    )


async def _get_org_kb(
    db: AsyncSession,
    *,
    org_id: UUID,
    kb_id: UUID,
) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_org_id != org_id:
        raise NotFoundError("资料库不存在")
    return kb


async def assert_can_manage_kb_grants(
    db: AsyncSession,
    current_user: CurrentUser,
    kb: KnowledgeBase,
) -> None:
    """库归属部门 unit_admin+ 或公司 Admin 可管理 grant（ORG-1-4 PRD）。"""
    if current_user.account_type != AccountType.enterprise:
        raise ForbiddenError("无权访问该资源")
    assert current_user.org_id is not None
    if kb.owner_org_id != current_user.org_id:
        raise NotFoundError("资料库不存在")

    if _is_company_admin(current_user):
        return

    if current_user.org_role == OrgRole.member:
        memberships = await _load_unit_memberships(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
        )
        if not any(m.role == UnitRole.unit_admin for m in memberships):
            raise ForbiddenError("权限不足")

    if kb.org_unit_id is None:
        raise ForbiddenError("权限不足")

    memberships = await _load_unit_memberships(
        db,
        org_id=current_user.org_id,
        user_id=current_user.id,
    )
    units = await _load_units_for_org(db, current_user.org_id)
    managed = _unit_admin_managed_subtree_ids(memberships, units)
    if kb.org_unit_id not in managed:
        raise ForbiddenError("权限不足")


async def _assert_grant_target_valid(
    db: AsyncSession,
    *,
    org_id: UUID,
    kb: KnowledgeBase,
    body: KbGrantCreate,
) -> None:
    if body.grantee_type == GranteeType.company:
        if body.grantee_id is not None:
            raise ValidationError("全公司共享不需要指定部门")
        if kb.org_unit_id is None:
            raise ConflictError("公司公共资料库已全员可见，无需再共享")
        return

    if body.grantee_id is None:
        raise ValidationError("请指定共享目标部门")

    unit = await db.get(OrgUnit, body.grantee_id)
    if unit is None or unit.org_id != org_id:
        raise ValidationError("无效的部门 ID")


async def _assert_grant_not_duplicate(
    db: AsyncSession,
    *,
    kb_id: UUID,
    body: KbGrantCreate,
) -> None:
    existing = await db.scalar(
        select(KbUnitGrant.id).where(
            KbUnitGrant.kb_id == kb_id,
            KbUnitGrant.grantee_type == body.grantee_type,
            KbUnitGrant.grantee_id == body.grantee_id,
        )
    )
    if existing is not None:
        raise ConflictError("该共享目标已存在")


async def list_kb_grants(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
) -> KbGrantListResponse:
    assert current_user.org_id is not None
    kb = await _get_org_kb(db, org_id=current_user.org_id, kb_id=kb_id)
    await assert_can_manage_kb_grants(db, current_user, kb)

    rows = await db.scalars(
        select(KbUnitGrant)
        .where(KbUnitGrant.kb_id == kb_id)
        .order_by(KbUnitGrant.created_at.asc())
    )
    return KbGrantListResponse(items=[_grant_to_response(g) for g in rows.all()])


async def create_kb_grant(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
    body: KbGrantCreate,
    *,
    ip: str | None = None,
) -> KbGrantResponse:
    assert current_user.org_id is not None
    kb = await _get_org_kb(db, org_id=current_user.org_id, kb_id=kb_id)
    await assert_can_manage_kb_grants(db, current_user, kb)
    await _assert_grant_target_valid(
        db,
        org_id=current_user.org_id,
        kb=kb,
        body=body,
    )
    await _assert_grant_not_duplicate(db, kb_id=kb_id, body=body)

    grant = KbUnitGrant(
        kb_id=kb_id,
        grantee_type=body.grantee_type,
        grantee_id=body.grantee_id,
        permission=body.permission,
    )
    db.add(grant)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("该共享目标已存在") from exc

    await write_audit_log(
        db,
        action="kb.grant.create",
        actor_user_id=current_user.id,
        resource_type="kb_unit_grant",
        resource_id=grant.id,
        kb_id=kb_id,
        metadata={
            "grantee_type": body.grantee_type.value,
            "grantee_id": str(body.grantee_id) if body.grantee_id else None,
            "permission": body.permission.value,
        },
        ip=ip,
    )
    await db.commit()

    await db.refresh(grant)
    return _grant_to_response(grant)


async def delete_kb_grant(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
    grant_id: UUID,
    *,
    ip: str | None = None,
) -> None:
    assert current_user.org_id is not None
    kb = await _get_org_kb(db, org_id=current_user.org_id, kb_id=kb_id)
    await assert_can_manage_kb_grants(db, current_user, kb)

    grant = await db.get(KbUnitGrant, grant_id)
    if grant is None or grant.kb_id != kb_id:
        raise NotFoundError("共享记录不存在")

    await write_audit_log(
        db,
        action="kb.grant.delete",
        actor_user_id=current_user.id,
        resource_type="kb_unit_grant",
        resource_id=grant.id,
        kb_id=kb_id,
        metadata={
            "grantee_type": grant.grantee_type.value,
            "grantee_id": str(grant.grantee_id) if grant.grantee_id else None,
            "permission": grant.permission.value,
        },
        ip=ip,
    )
    await db.delete(grant)
    await db.commit()

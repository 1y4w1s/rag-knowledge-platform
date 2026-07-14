"""组织成员管理业务逻辑（Wave 5.4）。"""

from uuid import UUID

from app.core.exceptions import ValidationError, NotFoundError, ConflictError, ForbiddenError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import AccountType, OrgRole
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationMemberCreate, OrganizationMemberResponse
from app.services.audit.log import write_audit_log


async def list_organization_members(
    db: AsyncSession,
    org_id: UUID,
) -> list[OrganizationMemberResponse]:
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.org_id == org_id)
        .options(selectinload(OrganizationMember.user))
        .order_by(OrganizationMember.joined_at.asc())
    )
    rows = (await db.scalars(stmt)).all()
    return [
        OrganizationMemberResponse(
            user_id=row.user_id,
            email=row.user.email,
            role=row.role,
            is_owner=row.is_owner,
            joined_at=row.joined_at,
        )
        for row in rows
    ]


async def add_organization_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    body: OrganizationMemberCreate,
    acting_user_id: UUID,
    ip: str | None = None,
) -> OrganizationMemberResponse:
    normalized_email = body.email.strip().lower()
    if not normalized_email:
        raise ValidationError("邮箱不能为空")

    user = await db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise NotFoundError("未找到该邮箱对应的用户")

    existing = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    if existing is not None:
        if existing.org_id == org_id:
            raise ConflictError("该用户已是团队成员")
        raise ConflictError("该用户已属于其他团队")

    if user.account_type == AccountType.personal:
        user.account_type = AccountType.enterprise

    membership = OrganizationMember(
        org_id=org_id,
        user_id=user.id,
        role=OrgRole.member,
        is_owner=False,
    )
    db.add(membership)
    await write_audit_log(
        db,
        action="org.member_add",
        actor_user_id=acting_user_id,
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email, "role": membership.role.value},
        ip=ip,
    )
    await db.commit()
    await db.refresh(membership)

    return OrganizationMemberResponse(
        user_id=user.id,
        email=user.email,
        role=membership.role,
        is_owner=membership.is_owner,
        joined_at=membership.joined_at,
    )


async def remove_organization_member(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    acting_admin_id: UUID,
    ip: str | None = None,
) -> None:
    membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if membership is None:
        raise NotFoundError("该用户不是团队成员")

    if membership.is_owner:
        raise ForbiddenError("不能移除团队所有者")

    if membership.role != OrgRole.member:
        raise ForbiddenError("不能移除团队管理员")

    if user_id == acting_admin_id:
        raise ForbiddenError("不能移除自己")

    admin_count = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.role == OrgRole.admin,
        )
    )
    if admin_count is None or admin_count < 1:
        raise ForbiddenError("团队至少保留一名管理员")

    await write_audit_log(
        db,
        action="org.member_remove",
        actor_user_id=acting_admin_id,
        resource_type="user",
        resource_id=user_id,
        metadata={"email": membership.user.email, "role": membership.role.value},
        ip=ip,
    )
    await db.execute(
        delete(OrgUnitMember).where(
            OrgUnitMember.user_id == user_id,
            OrgUnitMember.org_unit_id.in_(
                select(OrgUnit.id).where(OrgUnit.org_id == org_id)
            ),
        )
    )
    await db.delete(membership)
    if membership.user.account_type == AccountType.enterprise:
        membership.user.account_type = AccountType.personal
    await db.commit()


async def update_member_role(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    new_role: OrgRole,
    acting_owner_id: UUID,
    ip: str | None = None,
) -> OrganizationMemberResponse:
    if new_role not in (OrgRole.admin, OrgRole.member):
        raise ValidationError("无效的角色")

    if user_id == acting_owner_id:
        raise ForbiddenError("不能修改自己的角色")

    membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if membership is None:
        raise NotFoundError("该用户不是团队成员")

    if membership.is_owner:
        raise ForbiddenError("不能修改团队所有者的角色")

    if membership.role == new_role:
        raise ConflictError("该用户已是该角色")

    old_role = membership.role
    membership.role = new_role
    await write_audit_log(
        db,
        action="org.role_change",
        actor_user_id=acting_owner_id,
        resource_type="user",
        resource_id=user_id,
        metadata={
            "email": membership.user.email,
            "old_role": old_role.value,
            "new_role": new_role.value,
        },
        ip=ip,
    )
    await db.commit()
    await db.refresh(membership)

    return OrganizationMemberResponse(
        user_id=membership.user_id,
        email=membership.user.email,
        role=membership.role,
        is_owner=membership.is_owner,
        joined_at=membership.joined_at,
    )


async def transfer_organization_ownership(
    db: AsyncSession,
    *,
    org_id: UUID,
    target_user_id: UUID,
    acting_owner_id: UUID,
) -> tuple[OrganizationMemberResponse, OrganizationMemberResponse]:
    if target_user_id == acting_owner_id:
        raise ForbiddenError("不能将所有权转让给自己")

    owner_membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == acting_owner_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if owner_membership is None or not owner_membership.is_owner:
        raise ForbiddenError("仅团队所有者可执行此操作")

    target_membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target_user_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    if target_membership is None:
        raise NotFoundError("该用户不是团队成员")

    if target_membership.is_owner:
        raise ForbiddenError("该用户已是团队所有者")

    owner_membership.is_owner = False
    owner_membership.role = OrgRole.admin

    target_membership.is_owner = True
    target_membership.role = OrgRole.admin

    await db.commit()
    await db.refresh(owner_membership)
    await db.refresh(target_membership)

    previous_owner = OrganizationMemberResponse(
        user_id=owner_membership.user_id,
        email=owner_membership.user.email,
        role=owner_membership.role,
        is_owner=owner_membership.is_owner,
        joined_at=owner_membership.joined_at,
    )
    new_owner = OrganizationMemberResponse(
        user_id=target_membership.user_id,
        email=target_membership.user.email,
        role=target_membership.role,
        is_owner=target_membership.is_owner,
        joined_at=target_membership.joined_at,
    )
    return previous_owner, new_owner


async def count_organization_members(db: AsyncSession, org_id: UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.org_id == org_id)
    )
    return int(count or 0)

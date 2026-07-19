"""企业组织路由（Wave 1.3：组织设置；Wave 5.4：成员管理）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, require_org_role, require_owner
from app.models.enums import OrgRole
from app.schemas.organization import (
    DissolveOrgRequest,
    OrganizationInviteCreate,
    OrganizationInviteResponse,
    OrganizationMemberCreate,
    OrganizationMemberRoleUpdate,
    OrganizationMembersListResponse,
    OrganizationMemberResponse,
    OrganizationOwnershipTransferRequest,
    OrganizationOwnershipTransferResponse,
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
)
from app.services.organization.dissolve import dissolve_organization
from app.services.organization.invites import create_organization_invite
from app.services.organization.members import (
    add_organization_member,
    list_organization_members,
    remove_organization_member,
    transfer_organization_ownership,
    update_member_role,
)
from app.services.organization.settings import get_organization_settings, update_organization_name

router = APIRouter(prefix="/organization", tags=["organization"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]
OrgMember = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin, OrgRole.member))]
OrgOwner = Annotated[CurrentUser, Depends(require_owner())]


@router.get("/settings", response_model=OrganizationSettingsResponse)
async def get_settings(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationSettingsResponse:
    assert admin.org_id is not None
    return await get_organization_settings(db, admin.org_id)


@router.patch("/settings", response_model=OrganizationSettingsResponse)
async def patch_settings(
    body: OrganizationSettingsUpdate,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationSettingsResponse:
    assert admin.org_id is not None
    return await update_organization_name(db, admin.org_id, body.name)


@router.get("/members", response_model=OrganizationMembersListResponse)
async def get_members(
    member: OrgMember,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationMembersListResponse:
    assert member.org_id is not None
    items = await list_organization_members(db, member.org_id)
    return OrganizationMembersListResponse(items=items)


@router.post(
    "/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_member(
    body: OrganizationMemberCreate,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationMemberResponse:
    assert admin.org_id is not None
    return await add_organization_member(
        db,
        org_id=admin.org_id,
        body=body,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )


@router.post(
    "/invites",
    response_model=OrganizationInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_invite(
    body: OrganizationInviteCreate,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationInviteResponse:
    assert admin.org_id is not None
    return await create_organization_invite(
        db,
        org_id=admin.org_id,
        created_by=admin.id,
        expires_at=body.expires_at,
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    user_id: UUID,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    assert admin.org_id is not None
    await remove_organization_member(
        db,
        org_id=admin.org_id,
        user_id=user_id,
        acting_admin_id=admin.id,
        ip=get_client_ip(request),
    )


@router.patch("/members/{user_id}", response_model=OrganizationMemberResponse)
async def patch_member_role(
    user_id: UUID,
    body: OrganizationMemberRoleUpdate,
    request: Request,
    owner: OrgOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationMemberResponse:
    assert owner.org_id is not None
    return await update_member_role(
        db,
        org_id=owner.org_id,
        user_id=user_id,
        new_role=body.role,
        acting_owner_id=owner.id,
        ip=get_client_ip(request),
    )


@router.post(
    "/transfer-ownership",
    response_model=OrganizationOwnershipTransferResponse,
)
async def post_transfer_ownership(
    body: OrganizationOwnershipTransferRequest,
    owner: OrgOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationOwnershipTransferResponse:
    assert owner.org_id is not None
    previous_owner, new_owner = await transfer_organization_ownership(
        db,
        org_id=owner.org_id,
        target_user_id=body.target_user_id,
        acting_owner_id=owner.id,
    )
    return OrganizationOwnershipTransferResponse(
        previous_owner=previous_owner,
        new_owner=new_owner,
    )


@router.post(
    "/dissolve",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def post_dissolve_organization(
    body: DissolveOrgRequest,
    owner: OrgOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """解散团队（Owner 专属）。"""
    assert owner.org_id is not None
    await dissolve_organization(
        db,
        org_id=owner.org_id,
        confirm_name=body.confirm_name,
        acting_user_id=owner.id,
    )

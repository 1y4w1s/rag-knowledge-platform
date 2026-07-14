"""部门成员 API（ORG-2.2）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, require_org_role
from app.models.enums import OrgRole
from app.schemas.org_unit_member import (
    OrgUnitMemberCreate,
    OrgUnitMemberListResponse,
    OrgUnitMemberResponse,
    OrgUnitMemberUpdate,
)
from app.services.org.unit_members import (
    add_unit_member_from_roster,
    list_unit_members,
    remove_unit_member,
    update_unit_member,
)

router = APIRouter(prefix="/org-units", tags=["org-unit-members"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]


@router.get("/{unit_id}/members", response_model=OrgUnitMemberListResponse)
async def get_unit_members(
    unit_id: UUID,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberListResponse:
    assert admin.org_id is not None
    items = await list_unit_members(db, admin.org_id, unit_id)
    return OrgUnitMemberListResponse(items=items)


@router.post(
    "/{unit_id}/members",
    response_model=OrgUnitMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_unit_member(
    unit_id: UUID,
    body: OrgUnitMemberCreate,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberResponse:
    assert admin.org_id is not None
    return await add_unit_member_from_roster(
        db,
        org_id=admin.org_id,
        unit_id=unit_id,
        body=body,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )


@router.patch(
    "/{unit_id}/members/{user_id}",
    response_model=OrgUnitMemberResponse,
)
async def patch_unit_member(
    unit_id: UUID,
    user_id: UUID,
    body: OrgUnitMemberUpdate,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberResponse:
    assert admin.org_id is not None
    return await update_unit_member(
        db,
        org_id=admin.org_id,
        unit_id=unit_id,
        user_id=user_id,
        body=body,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )


@router.delete(
    "/{unit_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_unit_member(
    unit_id: UUID,
    user_id: UUID,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    assert admin.org_id is not None
    await remove_unit_member(
        db,
        org_id=admin.org_id,
        unit_id=unit_id,
        user_id=user_id,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )

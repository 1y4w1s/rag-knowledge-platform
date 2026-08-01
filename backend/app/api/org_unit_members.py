"""部门成员 API（ORG-2.2 · NW-24 本节点鉴权）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, get_current_user
from app.schemas.org_unit_member import (
    OrgUnitMemberCreate,
    OrgUnitMemberListResponse,
    OrgUnitMemberResponse,
    OrgUnitMemberUpdate,
)
from app.services.org.scope import _is_company_admin
from app.services.org.unit_member_auth import assert_can_manage_unit_members
from app.services.org.unit_members import (
    add_unit_member_from_roster,
    list_unit_members,
    remove_unit_member,
    update_unit_member,
)

router = APIRouter(prefix="/org-units", tags=["org-unit-members"])


@router.get("/{unit_id}/members", response_model=OrgUnitMemberListResponse)
async def get_unit_members(
    unit_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberListResponse:
    await assert_can_manage_unit_members(db, current_user, unit_id)
    assert current_user.org_id is not None
    items = await list_unit_members(db, current_user.org_id, unit_id)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberResponse:
    await assert_can_manage_unit_members(db, current_user, unit_id)
    assert current_user.org_id is not None
    return await add_unit_member_from_roster(
        db,
        org_id=current_user.org_id,
        unit_id=unit_id,
        body=body,
        acting_user_id=current_user.id,
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitMemberResponse:
    await assert_can_manage_unit_members(db, current_user, unit_id)
    assert current_user.org_id is not None
    return await update_unit_member(
        db,
        org_id=current_user.org_id,
        unit_id=unit_id,
        user_id=user_id,
        body=body,
        acting_user_id=current_user.id,
        ip=get_client_ip(request),
        allow_remove_last_admin=_is_company_admin(current_user),
    )


@router.delete(
    "/{unit_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_unit_member(
    unit_id: UUID,
    user_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await assert_can_manage_unit_members(db, current_user, unit_id)
    assert current_user.org_id is not None
    await remove_unit_member(
        db,
        org_id=current_user.org_id,
        unit_id=unit_id,
        user_id=user_id,
        acting_user_id=current_user.id,
        ip=get_client_ip(request),
        allow_remove_last_admin=_is_company_admin(current_user),
    )

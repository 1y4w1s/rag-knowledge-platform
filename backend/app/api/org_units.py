"""部门树 CRUD API（ORG-2.1）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, get_current_user, require_org_role
from app.models.enums import AccountType, OrgRole
from app.schemas.org_unit import (
    OrgUnitCreate,
    OrgUnitListResponse,
    OrgUnitResponse,
    OrgUnitUpdate,
)
from app.services.org.units import (
    create_child_org_unit,
    delete_org_unit,
    get_org_unit,
    list_org_units,
    list_picker_org_units,
    update_org_unit_name,
)

router = APIRouter(prefix="/org-units", tags=["org-units"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]
EnterpriseUser = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("/picker", response_model=OrgUnitListResponse)
async def get_picker_org_units(
    current_user: EnterpriseUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitListResponse:
    """侧栏部门选择器数据：Member 只见本人部门路径；Admin 见全树（ORG-3.2）。"""
    if (
        current_user.account_type != AccountType.enterprise
        or current_user.org_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源",
        )
    is_company_admin = current_user.is_owner or current_user.org_role == OrgRole.admin
    items = await list_picker_org_units(
        db,
        current_user.org_id,
        is_company_admin=is_company_admin,
        member_unit_ids=current_user.unit_ids,
    )
    return OrgUnitListResponse(items=items)


@router.get("", response_model=OrgUnitListResponse)
async def get_org_units(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitListResponse:
    assert admin.org_id is not None
    items = await list_org_units(db, admin.org_id)
    return OrgUnitListResponse(items=items)


@router.get("/{unit_id}", response_model=OrgUnitResponse)
async def get_org_unit_by_id(
    unit_id: UUID,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitResponse:
    assert admin.org_id is not None
    return await get_org_unit(db, admin.org_id, unit_id)


@router.post("", response_model=OrgUnitResponse, status_code=status.HTTP_201_CREATED)
async def post_org_unit(
    body: OrgUnitCreate,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitResponse:
    assert admin.org_id is not None
    return await create_child_org_unit(
        db,
        org_id=admin.org_id,
        name=body.name,
        parent_id=body.parent_id,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )


@router.patch("/{unit_id}", response_model=OrgUnitResponse)
async def patch_org_unit(
    unit_id: UUID,
    body: OrgUnitUpdate,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgUnitResponse:
    assert admin.org_id is not None
    return await update_org_unit_name(
        db,
        org_id=admin.org_id,
        unit_id=unit_id,
        name=body.name,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_unit_by_id(
    unit_id: UUID,
    request: Request,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    assert admin.org_id is not None
    await delete_org_unit(
        db,
        admin.org_id,
        unit_id,
        acting_user_id=admin.id,
        ip=get_client_ip(request),
    )

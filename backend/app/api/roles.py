"""自定义角色管理 API（Phase 7.4）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_org_role, require_org_scope
from app.models.enums import OrgRole
from app.models.custom_role import CustomRole
from app.models.organization_member import OrganizationMember
from app.services.audit.log import write_audit_log
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


router = APIRouter(prefix="/orgs/{org_id}/roles", tags=["roles"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_scope(OrgRole.admin))]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    is_admin_level: bool = False
    permissions: dict = {}

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: dict) -> dict:
        allowed_values = {"read", "write", "admin", "deny"}
        for key, val in v.items():
            if not isinstance(key, str):
                raise ValueError(f"权限键必须为字符串: {key}")
            if val not in allowed_values:
                raise ValueError(f"权限值必须为 {allowed_values}，实际: {val}")
        return v


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    is_admin_level: bool | None = None
    permissions: dict | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        allowed_values = {"read", "write", "admin", "deny"}
        for key, val in v.items():
            if not isinstance(key, str):
                raise ValueError(f"权限键必须为字符串: {key}")
            if val not in allowed_values:
                raise ValueError(f"权限值必须为 {allowed_values}，实际: {val}")
        return v


class RoleResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: UUID
    name: str
    description: str | None
    is_admin_level: bool
    permissions: dict
    created_at: datetime


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    org_id: UUID,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RoleResponse]:
    result = await db.execute(
        select(CustomRole).where(CustomRole.org_id == org_id).order_by(CustomRole.created_at)
    )
    return [RoleResponse.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    org_id: UUID,
    body: RoleCreate,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoleResponse:
    role = CustomRole(
        org_id=org_id,
        name=body.name,
        description=body.description,
        is_admin_level=body.is_admin_level,
        permissions=body.permissions,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    await write_audit_log(
        db,
        action="role.create",
        actor_user_id=admin.id,
        resource_type="role",
        resource_id=role.id,
        metadata={"name": role.name, "is_admin_level": role.is_admin_level},
    )
    await db.commit()

    return RoleResponse.model_validate(role)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    org_id: UUID,
    role_id: UUID,
    body: RoleUpdate,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoleResponse:
    role = await db.get(CustomRole, role_id)
    if role is None or role.org_id != org_id:
        raise HTTPException(status_code=404, detail="角色不存在")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.is_admin_level is not None:
        role.is_admin_level = body.is_admin_level
    if body.permissions is not None:
        role.permissions = body.permissions
    await db.commit()
    await db.refresh(role)

    await write_audit_log(
        db,
        action="role.update",
        actor_user_id=admin.id,
        resource_type="role",
        resource_id=role_id,
        # P1-20 审计补强：权限位（is_admin_level）变更须留痕，与 role.create 口径一致。
        metadata={"name": role.name, "is_admin_level": role.is_admin_level},
    )
    await db.commit()

    return RoleResponse.model_validate(role)


@router.delete("/{role_id}")
async def delete_role(
    org_id: UUID,
    role_id: UUID,
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    role = await db.get(CustomRole, role_id)
    if role is None or role.org_id != org_id:
        raise HTTPException(status_code=404, detail="角色不存在")
    await db.delete(role)
    await db.commit()

    await write_audit_log(
        db,
        action="role.delete",
        actor_user_id=admin.id,
        resource_type="role",
        resource_id=role_id,
        metadata={"name": role.name},
    )
    await db.commit()

    return Response(status_code=204)

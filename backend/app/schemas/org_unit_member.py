"""部门成员 Pydantic 模型（ORG-2.2）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import UnitRole


class OrgUnitMemberResponse(BaseModel):
    id: UUID
    org_unit_id: UUID
    user_id: UUID
    email: str
    role: UnitRole
    is_primary: bool
    joined_at: datetime


class OrgUnitMemberCreate(BaseModel):
    user_id: UUID
    role: UnitRole = UnitRole.unit_member
    is_primary: bool = False


class OrgUnitMemberUpdate(BaseModel):
    role: UnitRole | None = None
    is_primary: bool | None = None


class OrgUnitMemberListResponse(BaseModel):
    items: list[OrgUnitMemberResponse]

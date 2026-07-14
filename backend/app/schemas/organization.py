"""组织相关 Pydantic 模型（Wave 1.3 + 5.4）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import OrgRole


class OrganizationSettingsResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    member_count: int


class OrganizationSettingsUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationMemberResponse(BaseModel):
    user_id: UUID
    email: str
    role: OrgRole
    is_owner: bool = False
    joined_at: datetime


class OrganizationMemberCreate(BaseModel):
    email: EmailStr


class OrganizationMemberRoleUpdate(BaseModel):
    role: OrgRole


class OrganizationMembersListResponse(BaseModel):
    items: list[OrganizationMemberResponse]


class OrganizationInviteCreate(BaseModel):
    expires_at: datetime | None = None


class OrganizationInviteResponse(BaseModel):
    code: str
    org_id: UUID
    expires_at: datetime | None
    created_at: datetime


class OrganizationOwnershipTransferRequest(BaseModel):
    target_user_id: UUID


class OrganizationOwnershipTransferResponse(BaseModel):
    previous_owner: OrganizationMemberResponse
    new_owner: OrganizationMemberResponse

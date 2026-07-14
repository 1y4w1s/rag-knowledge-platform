"""资料库跨部门共享 grant Pydantic 模型（ORG-4.2）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import GrantPermission, GranteeType


class KbGrantCreate(BaseModel):
    grantee_type: GranteeType
    grantee_id: UUID | None = None
    permission: GrantPermission = GrantPermission.read


class KbGrantResponse(BaseModel):
    id: UUID
    kb_id: UUID
    grantee_type: GranteeType
    grantee_id: UUID | None
    permission: GrantPermission
    created_at: datetime


class KbGrantListResponse(BaseModel):
    items: list[KbGrantResponse] = Field(default_factory=list)

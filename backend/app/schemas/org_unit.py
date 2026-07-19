"""部门树 Pydantic 模型（ORG-2.1）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrgUnitResponse(BaseModel):
    id: UUID
    org_id: UUID
    parent_id: UUID | None
    name: str
    depth: int
    child_count: int = Field(ge=0)
    member_count: int = Field(ge=0)
    kb_count: int = Field(ge=0)
    created_at: datetime


class OrgUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    parent_id: UUID


class OrgUnitUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class OrgUnitListResponse(BaseModel):
    items: list[OrgUnitResponse]

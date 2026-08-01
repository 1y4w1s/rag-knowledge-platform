"""知识库 Pydantic 模型（Wave 2.1）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    org_unit_id: UUID | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_user_id: UUID | None
    owner_org_id: UUID | None
    org_unit_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    document_count: int = Field(default=0, ge=0)
    processing_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    # NW-25 I-2：仅详情 GET 回填；list/create/patch 保持 null
    quota_used_bytes: int | None = None
    quota_max_bytes: int | None = None

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    title: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    type: str = ""


class KnowledgeGraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

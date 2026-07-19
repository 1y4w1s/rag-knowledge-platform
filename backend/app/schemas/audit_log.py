"""审计日志 Pydantic 模型（Plan-3E-1 查询 API）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    kb_id: UUID | None
    details: dict[str, Any] | None
    ip: str | None
    created_at: datetime
    # 列表 enrichment（非表列；查询时批量回填）
    actor_email: str | None = None
    kb_name: str | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

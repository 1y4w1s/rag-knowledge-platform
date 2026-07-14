"""对话 thread API 模型（G2-1.1 · /ask/threads CRUD）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ThreadStatus


class ChatThreadResponse(BaseModel):
    id: UUID
    title: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatThreadListResponse(BaseModel):
    threads: list[ChatThreadResponse] = Field(default_factory=list)


class ChatThreadCreateRequest(BaseModel):
    title: str = Field(default="", max_length=256)


class ChatThreadPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    status: ThreadStatus | None = None

"""文档 Pydantic 模型（Wave 2.2）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, DocumentVisibility


class DocumentResponse(BaseModel):
    id: UUID
    kb_id: UUID
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    error_message: str | None
    chunk_count: int | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    uploaded_by: UUID | None
    created_at: datetime
    updated_at: datetime
    visibility: DocumentVisibility = DocumentVisibility.everyone

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentResponse] = Field(default_factory=list)

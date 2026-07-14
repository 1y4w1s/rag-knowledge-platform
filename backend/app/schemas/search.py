"""跨库文档搜索 Pydantic 模型（EW-E1 / Plan-RAG R1-1～R1-2）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus

SearchMode = Literal["filename", "content"]


class SearchDocumentItem(BaseModel):
    """单条跨库搜索结果（文件名或正文模式）。"""

    doc_id: uuid.UUID
    filename: str
    file_type: str
    status: DocumentStatus
    kb_id: uuid.UUID
    kb_name: str
    created_at: datetime
    snippet: str | None = None
    page_number: int | None = None


class SearchDocumentsResponse(BaseModel):
    """GET /search/documents 响应。"""

    items: list[SearchDocumentItem] = Field(default_factory=list)
    query: str
    total: int = Field(ge=0)
    mode: SearchMode = "filename"

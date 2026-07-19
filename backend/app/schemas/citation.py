"""引用解析 API 模型（Plan-3E-3 / EW-D3）。"""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class CitationSourceStatus(StrEnum):
    available = "available"
    document_deleted = "document_deleted"
    chunk_stale = "chunk_stale"
    source_inaccessible = "source_inaccessible"


class CitationResolveResponse(BaseModel):
    document_id: UUID
    chunk_id: UUID
    source_status: CitationSourceStatus
    doc_name: str | None = None

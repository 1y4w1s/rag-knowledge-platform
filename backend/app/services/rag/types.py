"""RAG 对话领域类型（Wave 3.1）。"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    kb_id: UUID
    chunk_id: UUID
    document_id: UUID
    doc_name: str
    content: str
    page_number: int | None
    section_title: str | None
    heading_path: str | None
    similarity: float
    parent_content: str | None = None
    kb_name: str | None = None


@dataclass(slots=True)
class _RecallRow:
    """检索中间结果（向量或 FTS 的原始输出）。"""
    chunk: Any
    filename: str
    kb_name: str | None = None
    vector_similarity: float | None = None
    fts_rank: float | None = None

"""RAG 对话领域类型（Wave 3.1）。"""

from __future__ import annotations

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
    rrf_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """可 JSON 序列化表示（UUID -> str），供 Redis 缓存后端使用。"""
        return {
            "kb_id": str(self.kb_id),
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "doc_name": self.doc_name,
            "content": self.content,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "heading_path": self.heading_path,
            "similarity": self.similarity,
            "parent_content": self.parent_content,
            "kb_name": self.kb_name,
            "rrf_score": self.rrf_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievedChunk:
        """从 to_dict() 产物还原，UUID 字段统一从 str 转回。"""
        return cls(
            kb_id=UUID(data["kb_id"]),
            chunk_id=UUID(data["chunk_id"]),
            document_id=UUID(data["document_id"]),
            doc_name=data.get("doc_name", ""),
            content=data.get("content", ""),
            page_number=data.get("page_number"),
            section_title=data.get("section_title"),
            heading_path=data.get("heading_path"),
            similarity=data.get("similarity", 0.0),
            parent_content=data.get("parent_content"),
            kb_name=data.get("kb_name"),
            rrf_score=data.get("rrf_score"),
        )


@dataclass(slots=True)
class _RecallRow:
    """检索中间结果（向量或 FTS 的原始输出）。"""
    chunk: Any
    filename: str
    kb_name: str | None = None
    vector_similarity: float | None = None
    fts_rank: float | None = None

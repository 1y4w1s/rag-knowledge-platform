"""G3-1.5 · get_chunk_excerpt 只读 tool（包装 DocumentChunk · §2.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.scope import AgentToolScope, FORBIDDEN_KB_SUMMARY
from app.services.rag.retrieval import _excerpt

NOT_FOUND_SUMMARY = "片段不存在"


def build_result_summary(doc_name: str, page: int | None) -> str:
    """对齐预览 tool 时间线：「员工手册 p.12 摘录」。"""
    if page is not None:
        return f"{doc_name} p.{page} 摘录"
    return f"{doc_name} 摘录"


@dataclass(frozen=True, slots=True)
class GetChunkExcerptOutput:
    chunk_id: UUID
    document_id: UUID
    doc_name: str
    page: int | None
    section_title: str | None
    excerpt: str
    kb_id: UUID
    kb_name: str


@dataclass(frozen=True, slots=True)
class GetChunkExcerptToolResult:
    ok: bool
    data: GetChunkExcerptOutput | None
    summary: str


async def run_get_chunk_excerpt(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    chunk_id: UUID,
) -> GetChunkExcerptToolResult:
    """按 chunk_id 读摘录 · chunk.kb_id 须在 visible（G3-1.5 · G3-E2）。"""
    chunk = await db.get(DocumentChunk, chunk_id)
    if chunk is None:
        return GetChunkExcerptToolResult(
            ok=False,
            data=None,
            summary=NOT_FOUND_SUMMARY,
        )

    denial = tool_scope.require_kb_visible(chunk.kb_id)
    if denial is not None:
        return GetChunkExcerptToolResult(
            ok=False,
            data=None,
            summary=denial.summary,
        )

    doc = await db.get(Document, chunk.document_id)
    if doc is None or doc.kb_id != chunk.kb_id:
        return GetChunkExcerptToolResult(
            ok=False,
            data=None,
            summary=NOT_FOUND_SUMMARY,
        )

    kb = await db.get(KnowledgeBase, chunk.kb_id)
    kb_name = kb.name if kb is not None else ""

    output = GetChunkExcerptOutput(
        chunk_id=chunk.id,
        document_id=doc.id,
        doc_name=doc.filename,
        page=chunk.page_number,
        section_title=chunk.section_title,
        excerpt=_excerpt(chunk.content),
        kb_id=chunk.kb_id,
        kb_name=kb_name,
    )
    return GetChunkExcerptToolResult(
        ok=True,
        data=output,
        summary=build_result_summary(doc.filename, chunk.page_number),
    )


__all__ = [
    "FORBIDDEN_KB_SUMMARY",
    "NOT_FOUND_SUMMARY",
    "GetChunkExcerptOutput",
    "GetChunkExcerptToolResult",
    "build_result_summary",
    "run_get_chunk_excerpt",
]

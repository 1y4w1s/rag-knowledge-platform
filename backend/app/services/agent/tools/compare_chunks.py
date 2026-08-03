"""G3-1.3 compare_chunks read-only tool -- compare multiple retrieved chunks.

Accepts multiple chunk_ids and returns each chunk's full context (doc name,
page, title, content), letting the Agent compare and synthesize before answering.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentVisibility
from app.services.agent.tools.scope import AgentToolScope

MAX_COMPARE_CHUNKS = 8


@dataclass(frozen=True, slots=True)
class ChunkDetail:
    chunk_id: UUID
    document_id: UUID
    doc_name: str
    page_number: int | None
    section_title: str | None
    heading_path: str | None
    content: str
    kb_id: UUID


@dataclass(frozen=True, slots=True)
class CompareChunksOutput:
    chunks: tuple[ChunkDetail, ...]


@dataclass(frozen=True, slots=True)
class CompareChunksToolResult:
    ok: bool
    data: CompareChunksOutput | None
    summary: str


async def run_compare_chunks(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    chunk_ids: list[str],
) -> CompareChunksToolResult:
    """Fetch full details for the given chunk IDs for comparison."""
    if not chunk_ids:
        return CompareChunksToolResult(
            ok=False, data=None, summary="chunk_ids must not be empty"
        )

    uuids: list[UUID] = []
    for cid in chunk_ids[:MAX_COMPARE_CHUNKS]:
        try:
            uuids.append(UUID(str(cid).strip()))
        except ValueError:
            continue

    if not uuids:
        return CompareChunksToolResult(
            ok=False, data=None, summary="no valid chunk_id provided"
        )

    # M8：visible_kb_ids=None 时不再 `.in_(None)`（语义不定）；clause 帮助函数
    # None → 不追加 WHERE（= 全部可见）。M7：member 过滤 admin_only 文档。
    stmt = (
        select(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.id.in_(uuids))
    )
    visible_clause = tool_scope.kb_visibility_clause(DocumentChunk.kb_id)
    if visible_clause is not None:
        stmt = stmt.where(visible_clause)
    if tool_scope.hide_admin_only:
        stmt = stmt.where(Document.visibility != DocumentVisibility.admin_only)
    rows = (await db.execute(stmt)).scalars().all()

    if not rows:
        return CompareChunksToolResult(
            ok=False, data=None, summary="chunks not found or no access"
        )

    doc_ids = {r.document_id for r in rows}
    doc_stmt = select(Document).where(Document.id.in_(doc_ids))
    doc_rows = (await db.execute(doc_stmt)).scalars().all()
    doc_names = {d.id: d.filename for d in doc_rows}

    chunks = tuple(
        ChunkDetail(
            chunk_id=r.id,
            document_id=r.document_id,
            doc_name=doc_names.get(r.document_id, "unknown"),
            page_number=r.page_number,
            section_title=r.section_title,
            heading_path=r.heading_path,
            content=r.content,
            kb_id=r.kb_id,
        )
        for r in rows
    )

    return CompareChunksToolResult(
        ok=True,
        data=CompareChunksOutput(chunks=chunks),
        summary=f"fetched {len(chunks)} chunk details",
    )

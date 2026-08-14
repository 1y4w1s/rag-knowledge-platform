"""G3-1.3 grep_in_document read-only tool -- full-text search within a doc.

Searches all chunks of a given document for a keyword and returns matching
lines with surrounding context. Useful for multi-step agent reasoning:
after semantic_search finds relevant docs, drill into exact content.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentVisibility
from app.services.agent.tools.scope import AgentToolScope

DEFAULT_CONTEXT_LINES = 2
MAX_CONTEXT_LINES = 5
GREP_MAX_MATCHES = 10
MAX_PATTERN_LEN = 200
MAX_EXCERPT_CHARS = 500


def _normalize_context_lines(raw: int | None) -> int:
    """契约 NW-29 §4.6：context_lines ∈ [1, MAX_CONTEXT_LINES]，缺省 2。"""
    if raw is None:
        return DEFAULT_CONTEXT_LINES
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CONTEXT_LINES
    return min(max(value, 1), MAX_CONTEXT_LINES)


def _build_match_excerpt(content: str, pattern: str, context_lines: int) -> str:
    """命中行 ± context_lines 的行窗口；heading-only 命中取正文开头同尺寸窗口。"""
    lines = content.splitlines() or [""]
    needle = pattern.lower()
    hit_index = next(
        (i for i, line in enumerate(lines) if needle in line.lower()), None
    )
    if hit_index is None:
        start, end = 0, min(len(lines), context_lines * 2 + 1)
    else:
        start = max(0, hit_index - context_lines)
        end = min(len(lines), hit_index + context_lines + 1)
    excerpt = "\n".join(lines[start:end])
    return excerpt[:MAX_EXCERPT_CHARS]


@dataclass(frozen=True, slots=True)
class GrepMatch:
    chunk_id: UUID
    doc_name: str
    content: str
    page_number: int | None
    section_title: str | None


@dataclass(frozen=True, slots=True)
class GrepInDocumentOutput:
    matches: tuple[GrepMatch, ...]


@dataclass(frozen=True, slots=True)
class GrepInDocumentToolResult:
    ok: bool
    data: GrepInDocumentOutput | None
    summary: str


async def run_grep_in_document(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    document_id: UUID,
    pattern: str,
    context_lines: int | None = None,
) -> GrepInDocumentToolResult:
    """Search for a pattern within the given document's chunks."""
    if not pattern.strip():
        return GrepInDocumentToolResult(
            ok=False, data=None, summary="search pattern must not be empty"
        )
    if len(pattern) > MAX_PATTERN_LEN:
        return GrepInDocumentToolResult(
            ok=False,
            data=None,
            summary=f"search pattern too long (max {MAX_PATTERN_LEN} chars)",
        )
    context_lines = _normalize_context_lines(context_lines)

    doc = await db.get(Document, document_id)
    # M8：visible_kb_ids=None（个人 workspace）时不可用 `not in None`（TypeError）；
    # 统一走 scope 防御校验（None = 全部可见）。
    if doc is None or tool_scope.require_kb_visible(doc.kb_id) is not None:
        return GrepInDocumentToolResult(
            ok=False, data=None, summary="document not found or no access"
        )
    # M7：member 对 admin_only 文档按「无访问」语义拒答。
    if (
        tool_scope.hide_admin_only
        and doc.visibility == DocumentVisibility.admin_only
    ):
        return GrepInDocumentToolResult(
            ok=False, data=None, summary="document not found or no access"
        )

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(
            func.lower(DocumentChunk.content).contains(pattern.lower())
            | func.lower(DocumentChunk.heading_path).contains(pattern.lower())
        )
        .limit(GREP_MAX_MATCHES)
        .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
    )
    rows = (await db.execute(stmt)).scalars().all()

    if not rows:
        return GrepInDocumentToolResult(
            ok=False,
            data=None,
            summary=f"no matches found for pattern: {pattern}",
        )

    matches = tuple(
        GrepMatch(
            chunk_id=r.id,
            doc_name=doc.filename,
            content=_build_match_excerpt(r.content, pattern, context_lines),
            page_number=r.page_number,
            section_title=r.section_title,
        )
        for r in rows
    )

    return GrepInDocumentToolResult(
        ok=True,
        data=GrepInDocumentOutput(matches=matches),
        summary=f"found {len(matches)} matches in {doc.filename}",
    )

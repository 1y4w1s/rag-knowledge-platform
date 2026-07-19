"""G3-1.3 · semantic_search 只读 tool（包装 retrieve_* · §2.2）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.scope import AgentToolScope, KbScope, ToolDenial
from app.services.org.scope import OrgScope
from app.services.rag.retrieval import LLM_TOP_K, _excerpt, retrieve_chunks, retrieve_workspace_chunks
from app.services.rag.types import RetrievedChunk
from app.services.workspace.scope import WorkspaceScope

AGENT_DEFAULT_TOP_K = LLM_TOP_K
AGENT_MAX_TOP_K = 5


def normalize_top_k(raw: int | None) -> int:
    """Agent tool 默认 5 · 上限 5（G3-1.3 验收）。"""
    if raw is None:
        return AGENT_DEFAULT_TOP_K
    return min(max(raw, 1), AGENT_MAX_TOP_K)


def build_result_summary(hit_count: int) -> str:
    if hit_count == 0:
        return "无命中"
    return f"命中 {hit_count} 条"


@dataclass(frozen=True, slots=True)
class SemanticSearchHit:
    chunk_id: UUID
    kb_id: UUID
    kb_name: str
    doc_name: str
    page: int | None
    section_title: str | None
    excerpt: str
    score: float


@dataclass(frozen=True, slots=True)
class SemanticSearchOutput:
    hits: tuple[SemanticSearchHit, ...]
    retrieval_ms: int


@dataclass(frozen=True, slots=True)
class SemanticSearchToolResult:
    ok: bool
    data: SemanticSearchOutput | None
    summary: str


def _chunk_to_hit(chunk: RetrievedChunk, kb_names: dict[UUID, str]) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=chunk.chunk_id,
        kb_id=chunk.kb_id,
        kb_name=chunk.kb_name or kb_names.get(chunk.kb_id, ""),
        doc_name=chunk.doc_name,
        page=chunk.page_number,
        section_title=chunk.section_title,
        excerpt=_excerpt(chunk.content),
        score=chunk.similarity,
    )


async def _load_kb_names(
    db: AsyncSession,
    kb_ids: set[UUID],
) -> dict[UUID, str]:
    if not kb_ids:
        return {}
    rows = await db.execute(
        select(KnowledgeBase.id, KnowledgeBase.name).where(
            KnowledgeBase.id.in_(kb_ids)
        )
    )
    return {row.id: row.name for row in rows.all()}


async def _retrieve_single_kb(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    top_k: int,
    tool_scope: AgentToolScope,
) -> list[RetrievedChunk]:
    return await retrieve_chunks(
        db,
        kb_id=kb_id,
        query=query,
        top_k=top_k,
        visible_kb_ids=tool_scope.visible_kb_ids,
    )


async def _retrieve_multi_kb_personal(
    db: AsyncSession,
    *,
    kb_ids: frozenset[UUID],
    query: str,
    top_k: int,
    tool_scope: AgentToolScope,
) -> list[RetrievedChunk]:
    """personal 多库指定 kb_ids：逐库 retrieve_chunks 后按 score 合并。"""
    merged: list[RetrievedChunk] = []
    for kb_id in kb_ids:
        merged.extend(
            await _retrieve_single_kb(
                db,
                kb_id=kb_id,
                query=query,
                top_k=top_k,
                tool_scope=tool_scope,
            )
        )
    merged.sort(key=lambda chunk: chunk.similarity, reverse=True)
    return merged[:top_k]


async def _retrieve_scoped(
    db: AsyncSession,
    *,
    query: str,
    top_k: int,
    workspace: WorkspaceScope,
    org_scope: OrgScope | None,
    resolved: KbScope,
    tool_scope: AgentToolScope,
) -> list[RetrievedChunk]:
    if resolved.kb_ids is not None and len(resolved.kb_ids) == 1:
        kb_id = next(iter(resolved.kb_ids))
        return await _retrieve_single_kb(
            db,
            kb_id=kb_id,
            query=query,
            top_k=top_k,
            tool_scope=tool_scope,
        )

    if resolved.kb_ids is not None and len(resolved.kb_ids) > 1:
        if org_scope is not None:
            narrowed = replace(org_scope, visible_kb_ids=frozenset(resolved.kb_ids))
            return await retrieve_workspace_chunks(
                db,
                query=query,
                scope=workspace,
                org_scope=narrowed,
                top_k=top_k,
            )
        return await _retrieve_multi_kb_personal(
            db,
            kb_ids=resolved.kb_ids,
            query=query,
            top_k=top_k,
            tool_scope=tool_scope,
        )

    return await retrieve_workspace_chunks(
        db,
        query=query,
        scope=workspace,
        org_scope=org_scope,
        top_k=top_k,
    )


async def run_semantic_search(
    db: AsyncSession,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    *,
    query: str,
    org_scope: OrgScope | None = None,
    kb_ids: list[UUID] | None = None,
    top_k: int | None = None,
) -> SemanticSearchToolResult:
    """语义检索 · 只调 retrieve_workspace_chunks / retrieve_chunks（G3-1.3）。"""
    scope_result = tool_scope.resolve_kb_ids(kb_ids)
    if isinstance(scope_result, ToolDenial):
        return SemanticSearchToolResult(
            ok=False,
            data=None,
            summary=scope_result.summary,
        )

    if scope_result.kb_ids is not None and not scope_result.kb_ids:
        return SemanticSearchToolResult(
            ok=True,
            data=SemanticSearchOutput(hits=(), retrieval_ms=0),
            summary=build_result_summary(0),
        )

    capped_top_k = normalize_top_k(top_k)
    t0 = time.perf_counter()
    raw_chunks = await _retrieve_scoped(
        db,
        query=query,
        top_k=capped_top_k,
        workspace=workspace,
        org_scope=org_scope,
        resolved=scope_result,
        tool_scope=tool_scope,
    )
    retrieval_ms = int((time.perf_counter() - t0) * 1000)

    kb_names = await _load_kb_names(
        db,
        {chunk.kb_id for chunk in raw_chunks if chunk.kb_name is None},
    )
    hits = tuple(_chunk_to_hit(chunk, kb_names) for chunk in raw_chunks)
    output = SemanticSearchOutput(hits=hits, retrieval_ms=retrieval_ms)
    return SemanticSearchToolResult(
        ok=True,
        data=output,
        summary=build_result_summary(len(hits)),
    )

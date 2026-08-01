"""G3-2.2 · 合并 agent hits → gate → 生成准备 · run 终态（capped/completed）。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import AgentRunStatus
from app.services.agent.runs import finish_agent_run
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.agent.tools.compare_chunks import CompareChunksOutput
from app.services.agent.tools.get_chunk_excerpt import GetChunkExcerptOutput
from app.services.agent.tools.grep_in_document import GrepInDocumentOutput
from app.services.agent.tools.semantic_search import (
    SemanticSearchOutput,
    _load_kb_names,
)
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.relevance import filter_relevant_chunks
from app.services.rag.retrieval import chunk_to_citation, workspace_chunk_to_citation
from app.services.rag.types import RetrievedChunk

# 显式读过的只读证据（excerpt / grep / compare）对齐同一档分
EXCERPT_TOOL_SCORE = 1.0
GREP_TOOL_SCORE = 1.0
COMPARE_TOOL_SCORE = 1.0


@dataclass(frozen=True, slots=True)
class AgentGenerationPlan:
    """gate 后供 G3-2.3 SSE 生成层消费（citation 先于 token）。"""

    gated_chunks: tuple[RetrievedChunk, ...]
    citations: tuple[dict, ...]
    refusal: bool
    external_context: str = field(default="")  # E4: web_search/sql_query 结果文本


def _bump_score(scores: dict[UUID, float], chunk_id: UUID, score: float) -> None:
    prev = scores.get(chunk_id)
    if prev is None or score > prev:
        scores[chunk_id] = score


def _collect_hit_scores(steps: tuple[AgentStepRecord, ...]) -> dict[UUID, float]:
    """从带 chunk_id 的只读 tool 步汇总 chunk_id → 最高分。

    收录：semantic_search · get_chunk_excerpt · grep_in_document · compare_chunks。
    不收录：list_knowledge_bases · search_documents（无 chunk 溯源）· 写 tool。
    """
    scores: dict[UUID, float] = {}
    for record in steps:
        if not record.ok or record.data is None:
            continue
        if isinstance(record.data, SemanticSearchOutput):
            for hit in record.data.hits:
                _bump_score(scores, hit.chunk_id, hit.score)
        elif isinstance(record.data, GetChunkExcerptOutput):
            _bump_score(scores, record.data.chunk_id, EXCERPT_TOOL_SCORE)
        elif isinstance(record.data, GrepInDocumentOutput):
            for match in record.data.matches:
                _bump_score(scores, match.chunk_id, GREP_TOOL_SCORE)
        elif isinstance(record.data, CompareChunksOutput):
            for detail in record.data.chunks:
                _bump_score(scores, detail.chunk_id, COMPARE_TOOL_SCORE)
    return scores


async def _load_retrieved_chunks(
    db: AsyncSession,
    hit_scores: dict[UUID, float],
) -> list[RetrievedChunk]:
    if not hit_scores:
        return []

    chunk_ids = list(hit_scores.keys())
    chunks: list[RetrievedChunk] = []
    for chunk_id in chunk_ids:
        chunk = await db.get(DocumentChunk, chunk_id)
        if chunk is None:
            continue
        doc = await db.get(Document, chunk.document_id)
        if doc is None or doc.kb_id != chunk.kb_id:
            continue
        chunks.append(
            RetrievedChunk(
                kb_id=chunk.kb_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                doc_name=doc.filename,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                similarity=hit_scores[chunk_id],
            )
        )

    chunks.sort(key=lambda item: item.similarity, reverse=True)
    # F2：DB 重载不带库名；工作区 citation 须非空 kb_name（与 fast 路径对齐）
    if not chunks:
        return chunks
    kb_names = await _load_kb_names(db, {c.kb_id for c in chunks})
    return [
        replace(c, kb_name=kb_names.get(c.kb_id) or c.kb_name)
        for c in chunks
    ]


async def merge_step_hits_to_chunks(
    db: AsyncSession,
    steps: tuple[AgentStepRecord, ...],
) -> list[RetrievedChunk]:
    """合并多步只读 chunk 命中（search/excerpt/grep/compare）· 按 chunk_id 去重。"""
    hit_scores = _collect_hit_scores(steps)
    return await _load_retrieved_chunks(db, hit_scores)


def gate_agent_chunks(
    query: str,
    merged_chunks: list[RetrievedChunk],
    *,
    workspace_mode: bool,
) -> AgentGenerationPlan:
    """filter_relevant_chunks → citation；无依据走 G3-E6 拒答分支。"""
    gated = filter_relevant_chunks(merged_chunks, query)
    if workspace_mode and gated:
        gated = apply_kb_diversity(gated, query)

    if workspace_mode:
        citations = tuple(workspace_chunk_to_citation(chunk) for chunk in gated)
    else:
        citations = tuple(chunk_to_citation(chunk) for chunk in gated)

    return AgentGenerationPlan(
        gated_chunks=tuple(gated),
        citations=citations,
        refusal=not gated,
    )


async def prepare_agent_generation(
    db: AsyncSession,
    *,
    query: str,
    steps: tuple[AgentStepRecord, ...],
    workspace_mode: bool,
    outcome: AgentRunOutcome | None = None,
) -> AgentGenerationPlan:
    """G3-2.2 主入口：合并 hits → gate → 生成准备。"""
    del outcome  # 预留扩展：E2 后续可在此消费 outcome.low_confidence
    merged = await merge_step_hits_to_chunks(db, steps)
    plan = gate_agent_chunks(query, merged, workspace_mode=workspace_mode)

    # E4：从 steps 提取外部工具结果（web_search/sql_query）作为额外上下文
    external_parts: list[str] = []
    for step in steps:
        if step.tool_name in ("web_search", "sql_query") and step.data:
            data = step.data
            if hasattr(data, "ok") and data.ok:
                items = getattr(data, "data", [])
                if step.tool_name == "web_search":
                    for item in items[:5]:
                        title = item.get("title", "")
                        url = item.get("url", "")
                        snippet = item.get("snippet", "")
                        external_parts.append(f"- {title}: {snippet} ({url})")
                elif step.tool_name == "sql_query":
                    for row in items[:10]:
                        fields = ", ".join(f"{k}={v}" for k, v in row.items())
                        external_parts.append(f"- {fields}")

    if external_parts:
        plan = AgentGenerationPlan(
            gated_chunks=plan.gated_chunks,
            citations=plan.citations,
            refusal=plan.refusal,
            external_context="\n外部查询结果：\n" + "\n".join(external_parts),
        )

    return plan


def resolve_run_status(outcome: AgentRunOutcome) -> AgentRunStatus:
    if outcome.timed_out:
        return AgentRunStatus.failed
    if outcome.capped:
        return AgentRunStatus.capped
    return AgentRunStatus.completed


async def finish_react_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    outcome: AgentRunOutcome,
    assistant_message_id: UUID | None = None,
) -> AgentRunStatus | None:
    """ReAct 结束后落库终态（E-budget → capped）。"""
    status = resolve_run_status(outcome)
    finished = await finish_agent_run(
        db,
        run_id=run_id,
        user_id=user_id,
        status=status,
        assistant_message_id=assistant_message_id,
    )
    if finished is None:
        return None
    return status

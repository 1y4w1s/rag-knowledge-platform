"""L3 AgentState：init / observation reducer / planner 摘要（纯函数，零副作用）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from app.services.agent.fact_contracts import (
    derive_fact_views,
    facts_ready_for_stop,
    reduce_fact_observation,
    seed_fact_goals,
    sync_evidence_fact_views,
)
from app.services.agent.tools.compare_chunks import CompareChunksOutput
from app.services.agent.tools.get_chunk_excerpt import GetChunkExcerptOutput
from app.services.agent.tools.grep_in_document import GrepInDocumentOutput
from app.services.agent.tools.search_documents import SearchDocumentsOutput
from app.services.agent.tools.semantic_search import SemanticSearchOutput
from app.services.agent.types import (
    AgentDecision,
    AgentState,
    AgentStepRecord,
    EvidenceState,
    FactGoal,
    ObservationSummary,
    StepExecution,
)
from app.services.rag.evidence import check_evidence_sufficiency

# re-export L4 contracts（测试可从 state 导入）
__all__ = [
    "derive_fact_views",
    "facts_ready_for_stop",
    "init_agent_state",
    "reduce_fact_observation",
    "reduce_observation",
    "summarize_state_for_planner",
    "sync_evidence_fact_views",
    "update_evidence_state",
]

# Planner 摘要硬上限（防 token 线性膨胀；不含正文）
_MAX_IDS = 32
_MAX_DOC_NAMES = 16
_MAX_TOP_SCORES = 8
_MAX_LAST_SUMMARY_CHARS = 200
_MAX_FACT_CHARS = 80


@dataclass(frozen=True, slots=True)
class _HitStub:
    """供 check_evidence_sufficiency 的轻量命中（无正文）。"""

    score: float
    chunk_id: UUID | None = None
    doc_name: str | None = None


def init_agent_state(
    *,
    original_query: str,
    max_steps: int,
    active_query: str | None = None,
    memory_context: str = "",
    required_facts: tuple[str, ...] = (),
    fact_goals: tuple[FactGoal, ...] = (),
) -> AgentState:
    """构造空 AgentState；FactGoal 为真源时派生 required/missing。"""
    goals = seed_fact_goals(fact_goals=fact_goals, required_facts=required_facts)
    if goals:
        evidence = sync_evidence_fact_views(EvidenceState(facts=goals))
    else:
        evidence = EvidenceState()
    return AgentState(
        original_query=original_query,
        active_query=active_query if active_query is not None else original_query,
        steps=(),
        evidence=evidence,
        steps_used=0,
        max_steps=max_steps,
        reflection_count=0,
        last_failure=None,
        memory_context=memory_context,
    )

def reduce_observation(
    state: AgentState,
    decision: AgentDecision,
    execution: StepExecution,
    record: AgentStepRecord,
) -> AgentState:
    """旧状态 + 本步 decision/execution/record → 新 AgentState（纯函数）。"""
    del decision  # W1：decision 仅参与签名契约；active_query 重写留后续窗
    evidence = update_evidence_state(state.evidence, record)
    return replace(
        state,
        steps=(*state.steps, record),
        evidence=evidence,
        steps_used=state.steps_used + 1,
        last_failure=execution.failure,
    )


def update_evidence_state(
    evidence: EvidenceState,
    record: AgentStepRecord,
) -> EvidenceState:
    """从 step record 聚合 ID / 分数 / sufficiency（不存 chunk 正文）。"""
    if not record.ok or record.data is None:
        return sync_evidence_fact_views(
            replace(evidence, sufficient=False, confidence=0.0)
        )

    chunk_ids, document_ids, _doc_names, scores, hit_stubs = _extract_from_record(
        record
    )
    merged_chunks = _merge_uuids(evidence.chunk_ids, chunk_ids)
    merged_docs = _merge_uuids(evidence.document_ids, document_ids)

    sufficient = evidence.sufficient
    confidence = evidence.confidence
    # 低召回：semantic_search 空命中 → 强制不足
    if isinstance(record.data, SemanticSearchOutput) and not record.data.hits:
        sufficient = False
        confidence = 0.0
    elif hit_stubs:
        verdict = check_evidence_sufficiency(hit_stubs, "")
        sufficient = verdict.sufficient
        confidence = float(verdict.top_sim_score)
    elif scores:
        confidence = max(confidence, max(scores))

    updated = replace(
        evidence,
        chunk_ids=merged_chunks,
        document_ids=merged_docs,
        sufficient=sufficient,
        confidence=confidence,
        # 无 FactGoal 时保留 L3 字符串槽位；有 facts 时由 sync 派生（覆盖算法另窗）
        covered_facts=evidence.covered_facts,
        missing_facts=evidence.missing_facts or evidence.required_facts,
    )
    return sync_evidence_fact_views(updated)


def summarize_state_for_planner(state: AgentState) -> ObservationSummary:
    """压缩状态供 NextActionPlanner；绝不泄漏完整 chunk / web 正文。"""
    last = state.steps[-1] if state.steps else None
    doc_names, top_scores = _collect_doc_names_and_scores(state.steps)
    failure = state.last_failure
    return ObservationSummary(
        original_query=state.original_query,
        active_query=state.active_query,
        steps_used=state.steps_used,
        max_steps=state.max_steps,
        last_tool=last.tool_name if last else None,
        last_ok=last.ok if last else None,
        last_summary=_clip(last.summary, _MAX_LAST_SUMMARY_CHARS) if last else "",
        chunk_ids=state.evidence.chunk_ids[:_MAX_IDS],
        document_ids=state.evidence.document_ids[:_MAX_IDS],
        doc_names=doc_names[:_MAX_DOC_NAMES],
        top_scores=top_scores[:_MAX_TOP_SCORES],
        evidence_sufficient=state.evidence.sufficient,
        confidence=state.evidence.confidence,
        covered_facts=tuple(
            _clip_fact(f) for f in state.evidence.covered_facts[:_MAX_DOC_NAMES]
        ),
        missing_facts=tuple(
            _clip_fact(f) for f in state.evidence.missing_facts[:_MAX_DOC_NAMES]
        ),
        last_failure_kind=failure.kind.value if failure else None,
        last_failure_summary=(
            _clip(failure.summary, _MAX_LAST_SUMMARY_CHARS) if failure else None
        ),
        reflection_count=state.reflection_count,
    )


def _extract_from_record(
    record: AgentStepRecord,
) -> tuple[
    tuple[UUID, ...],
    tuple[UUID, ...],
    tuple[str, ...],
    tuple[float, ...],
    tuple[_HitStub, ...],
]:
    data: Any = record.data
    chunk_ids: list[UUID] = []
    document_ids: list[UUID] = []
    doc_names: list[str] = []
    scores: list[float] = []
    stubs: list[_HitStub] = []

    if isinstance(data, SemanticSearchOutput):
        for hit in data.hits:
            chunk_ids.append(hit.chunk_id)
            if hit.document_id is not None:
                document_ids.append(hit.document_id)
            doc_names.append(hit.doc_name)
            scores.append(float(hit.score))
            stubs.append(
                _HitStub(
                    score=float(hit.score),
                    chunk_id=hit.chunk_id,
                    doc_name=hit.doc_name,
                )
            )
    elif isinstance(data, GetChunkExcerptOutput):
        chunk_ids.append(data.chunk_id)
        document_ids.append(data.document_id)
        doc_names.append(data.doc_name)
        scores.append(1.0)
        stubs.append(
            _HitStub(score=1.0, chunk_id=data.chunk_id, doc_name=data.doc_name)
        )
    elif isinstance(data, GrepInDocumentOutput):
        for match in data.matches:
            chunk_ids.append(match.chunk_id)
            doc_names.append(match.doc_name)
            scores.append(1.0)
            stubs.append(
                _HitStub(
                    score=1.0,
                    chunk_id=match.chunk_id,
                    doc_name=match.doc_name,
                )
            )
    elif isinstance(data, CompareChunksOutput):
        for detail in data.chunks:
            chunk_ids.append(detail.chunk_id)
            document_ids.append(detail.document_id)
            doc_names.append(detail.doc_name)
            scores.append(1.0)
            stubs.append(
                _HitStub(
                    score=1.0,
                    chunk_id=detail.chunk_id,
                    doc_name=detail.doc_name,
                )
            )
    elif isinstance(data, SearchDocumentsOutput):
        for item in data.items:
            document_ids.append(item.document_id)
            doc_names.append(item.filename)

    return (
        tuple(chunk_ids),
        tuple(document_ids),
        tuple(doc_names),
        tuple(scores),
        tuple(stubs),
    )


def _collect_doc_names_and_scores(
    steps: tuple[AgentStepRecord, ...],
) -> tuple[tuple[str, ...], tuple[float, ...]]:
    names: list[str] = []
    seen_names: set[str] = set()
    score_by_chunk: dict[UUID, float] = {}
    for record in steps:
        if not record.ok or record.data is None:
            continue
        _, _, doc_names, _scores, stubs = _extract_from_record(record)
        for name in doc_names:
            if name and name not in seen_names:
                seen_names.add(name)
                names.append(name)
        for stub in stubs:
            if stub.chunk_id is None:
                continue
            prev = score_by_chunk.get(stub.chunk_id)
            if prev is None or stub.score > prev:
                score_by_chunk[stub.chunk_id] = stub.score
    ranked = sorted(score_by_chunk.values(), reverse=True)
    return tuple(names), tuple(ranked)


def _merge_uuids(
    existing: tuple[UUID, ...],
    incoming: tuple[UUID, ...],
) -> tuple[UUID, ...]:
    seen = set(existing)
    out = list(existing)
    for item in incoming:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out[:_MAX_IDS])


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _clip_fact(text: str) -> str:
    return _clip(text.strip(), _MAX_FACT_CHARS)

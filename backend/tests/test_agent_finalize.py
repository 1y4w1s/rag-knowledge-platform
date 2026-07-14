"""G3-2.2：合并 hits → gate → 生成准备 · G3-E6 拒答 · capped 终态。"""

from __future__ import annotations

import uuid

import pytest

from app.services.agent.finalize import (
    gate_agent_chunks,
    merge_step_hits_to_chunks,
    prepare_agent_generation,
    resolve_run_status,
)
from app.services.agent.tools.semantic_search import SemanticSearchHit, SemanticSearchOutput
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    section_title: str | None = None,
    similarity: float = 0.1,
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="handbook.md",
        content=content,
        page_number=None,
        section_title=section_title,
        heading_path=None,
        similarity=similarity,
    )


def _semantic_step(
    *,
    hits: tuple[SemanticSearchHit, ...] = (),
    ok: bool = True,
) -> AgentStepRecord:
    data = SemanticSearchOutput(hits=hits, retrieval_ms=12) if ok else None
    return AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "年假"},
        ok=ok,
        summary="无命中" if not hits else f"命中 {len(hits)} 条",
        latency_ms=12,
        data=data,
    )


def test_resolve_run_status_capped() -> None:
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=5,
        max_steps=5,
        capped=True,
        timed_out=False,
        steps=(),
    )
    from app.models.enums import AgentRunStatus

    assert resolve_run_status(outcome) == AgentRunStatus.capped


def test_gate_g3_e6_empty_hits_refusal() -> None:
    """G3-E6：全无命中 → refusal · 无 citation。"""
    plan = gate_agent_chunks("员工年假有几天？", [], workspace_mode=True)
    assert plan.refusal is True
    assert plan.citations == ()
    assert plan.gated_chunks == ()


def test_gate_g3_e6_irrelevant_hits_refusal() -> None:
    """G3-E6：有检索但 gate 不通过 → 拒答 · 无 citation。"""
    merged = [_chunk(content="无关正文", similarity=0.9)]
    plan = gate_agent_chunks("火星殖民计划", merged, workspace_mode=False)
    assert plan.refusal is True
    assert plan.citations == ()


def test_gate_passes_with_overlap_citations() -> None:
    merged = [_chunk(content="员工年满一年后可享受年假10天。", section_title="年假")]
    plan = gate_agent_chunks("员工年假有几天？", merged, workspace_mode=False)
    assert plan.refusal is False
    assert len(plan.citations) == 1
    assert plan.citations[0]["doc_name"] == "handbook.md"


def test_collect_hit_scores_dedupes_semantic_search_steps() -> None:
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    low = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=uuid.uuid4(),
        kb_name="人事库",
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        score=0.2,
    )
    high = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=low.kb_id,
        kb_name="人事库",
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        score=0.8,
    )
    steps = (
        _semantic_step(hits=(low,)),
        _semantic_step(hits=(high,)),
    )
    scores = _collect_hit_scores(steps)
    assert scores[chunk_id] == 0.8


@pytest.mark.asyncio
async def test_merge_step_hits_empty_when_no_semantic_data() -> None:
    steps = (
        AgentStepRecord(
            step_index=1,
            tool_name="list_knowledge_bases",
            args={},
            ok=True,
            summary="可见库 0 个",
            latency_ms=1,
            data=None,
        ),
    )
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        merged = await merge_step_hits_to_chunks(db, steps)
    assert merged == []


@pytest.mark.asyncio
async def test_prepare_agent_generation_g3_e6_no_hits(
    register_and_login,
) -> None:
    """G3-E6：多步 semantic_search 均无命中 → prepare 走拒答。"""
    steps = (
        _semantic_step(hits=()),
        _semantic_step(hits=()),
    )
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        plan = await prepare_agent_generation(
            db,
            query="员工年假有几天？",
            steps=steps,
            workspace_mode=True,
        )
    assert plan.refusal is True
    assert plan.citations == ()

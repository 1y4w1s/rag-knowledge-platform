"""L3-W5：EvidenceState 驱动 finish/retrieve（映射 check_evidence_sufficiency）。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.agent.evidence_gate import (
    apply_evidence_stop_retrieve,
    maybe_finish_from_evidence,
)
from app.services.agent.planners import NextActionPlanner, SafetyFrame
from app.services.agent.state import (
    init_agent_state,
    update_evidence_state,
)
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentStepRecord,
    DecisionParseResult,
    EvidenceState,
)


def test_evidence_state_and_critic_flags_default_false() -> None:
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.rag_critic_enabled is False


def _hits_sufficient() -> tuple[SemanticSearchHit, ...]:
    """≥3 hits · top_sim≥0.5 · ≥2 chunk · 有文档名 → check_evidence_sufficiency True。"""
    return tuple(
        SemanticSearchHit(
            chunk_id=uuid4(),
            kb_id=uuid4(),
            kb_name="kb",
            doc_name=f"doc{i}.md",
            page=i,
            section_title="s",
            excerpt=f"excerpt {i}",
            score=0.9 - i * 0.01,
        )
        for i in range(3)
    )


def _hits_insufficient_one() -> tuple[SemanticSearchHit, ...]:
    return (
        SemanticSearchHit(
            chunk_id=uuid4(),
            kb_id=uuid4(),
            kb_name="kb",
            doc_name="only.md",
            page=1,
            section_title="s",
            excerpt="half fact",
            score=0.91,
        ),
    )


def _search_record(hits: tuple[SemanticSearchHit, ...]) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "q"},
        ok=True,
        summary=f"命中 {len(hits)}",
        latency_ms=10,
        data=SemanticSearchOutput(hits=hits, retrieval_ms=10),
    )


def test_update_evidence_maps_check_evidence_sufficiency() -> None:
    """不重造算法：sufficient 与 check_evidence_sufficiency 一致。"""
    from app.services.rag.evidence import check_evidence_sufficiency

    ok_hits = _hits_sufficient()
    evidence = update_evidence_state(EvidenceState(), _search_record(ok_hits))
    assert evidence.sufficient is True
    assert check_evidence_sufficiency(ok_hits, "").sufficient is True

    weak = update_evidence_state(
        EvidenceState(), _search_record(_hits_insufficient_one())
    )
    assert weak.sufficient is False
    assert check_evidence_sufficiency(_hits_insufficient_one(), "").sufficient is False


def test_gate_flag_off_passthrough() -> None:
    state = init_agent_state(original_query="年假几天？", max_steps=5)
    state = replace(state, evidence=EvidenceState(sufficient=True))
    finish = AgentDecision(action=AgentActionKind.finish, reason_code="x")
    assert apply_evidence_stop_retrieve(state, finish, enabled=False) is finish
    assert maybe_finish_from_evidence(state, enabled=False) is None


def test_gate_sufficient_forces_finish() -> None:
    state = init_agent_state(original_query="Docker Compose 用途？", max_steps=5)
    state = replace(state, evidence=EvidenceState(sufficient=True), steps_used=1)
    early = maybe_finish_from_evidence(state, enabled=True)
    assert early is not None
    assert early.action == AgentActionKind.finish
    assert early.reason_code == "evidence_sufficient"

    tool = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": "more"},
        reason_code="redundant",
    )
    gated = apply_evidence_stop_retrieve(state, tool, enabled=True)
    assert gated.action == AgentActionKind.finish
    assert gated.reason_code == "evidence_sufficient"


def test_gate_insufficient_finish_becomes_retrieve() -> None:
    state = init_agent_state(original_query="住宿与高管例外？", max_steps=5)
    state = replace(
        state,
        active_query="住宿与高管例外？",
        evidence=EvidenceState(sufficient=False),
        steps_used=1,
    )
    premature = AgentDecision(
        action=AgentActionKind.finish, reason_code="llm_early_stop"
    )
    gated = apply_evidence_stop_retrieve(state, premature, enabled=True)
    assert gated.action == AgentActionKind.tool
    assert gated.tool_name == "semantic_search"
    assert gated.args["query"] == "住宿与高管例外？"
    assert gated.reason_code == "evidence_insufficient_retrieve"


def test_gate_insufficient_finish_at_budget_refuses() -> None:
    state = init_agent_state(original_query="q", max_steps=3)
    state = replace(
        state,
        evidence=EvidenceState(sufficient=False),
        steps_used=3,
    )
    gated = apply_evidence_stop_retrieve(
        state,
        AgentDecision(action=AgentActionKind.finish, reason_code="x"),
        enabled=True,
    )
    assert gated.action == AgentActionKind.refuse
    assert gated.reason_code == "evidence_insufficient_budget"


def test_gate_insufficient_allows_clarify_and_tool() -> None:
    state = init_agent_state(original_query="那个制度？", max_steps=5)
    clarify = AgentDecision(
        action=AgentActionKind.clarify,
        reason_code="ambiguous_doc",
        user_message="哪份？",
    )
    assert apply_evidence_stop_retrieve(state, clarify, enabled=True) is clarify

    tool = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": "制度"},
        reason_code="initial_retrieval",
    )
    assert apply_evidence_stop_retrieve(state, tool, enabled=True) is tool


@pytest.mark.asyncio
async def test_planner_sufficient_short_circuits_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    query = "对比 Docker 与 Compose？"
    safety = SafetyFrame(query)
    planner = NextActionPlanner(
        query, safety_frame=safety, tool_specs=safety.all_tool_specs()
    )
    call_llm = AsyncMock(
        return_value=DecisionParseResult(ok=False, error="should_not_call")
    )
    monkeypatch.setattr(planner, "_call_llm", call_llm)

    state = init_agent_state(original_query=query, max_steps=5)
    state = replace(state, evidence=EvidenceState(sufficient=True), steps_used=1)
    decision = await planner.decide_next(state)
    assert decision.action == AgentActionKind.finish
    assert decision.reason_code == "evidence_sufficient"
    call_llm.assert_not_called()


@pytest.mark.asyncio
async def test_planner_insufficient_overrides_finish_to_retrieve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    query = "住宿上限与高管例外？"
    safety = SafetyFrame(query)
    planner = NextActionPlanner(
        query, safety_frame=safety, tool_specs=safety.all_tool_specs()
    )
    finish_raw = DecisionParseResult(
        ok=True,
        decision=AgentDecision(
            action=AgentActionKind.finish, reason_code="llm_guess"
        ),
        llm_raw='{"action":"finish"}',
    )
    monkeypatch.setattr(planner, "_call_llm", AsyncMock(return_value=finish_raw))

    state = init_agent_state(original_query=query, max_steps=5)
    state = replace(state, evidence=EvidenceState(sufficient=False), steps_used=1)
    decision = await planner.decide_next(state)
    assert decision.action == AgentActionKind.tool
    assert decision.tool_name == "semantic_search"
    assert decision.reason_code == "evidence_insufficient_retrieve"


@pytest.mark.asyncio
async def test_planner_flag_off_allows_finish_when_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认关：不拦截 LLM finish（与 W3 行为一致）。"""
    assert settings.agent_l3_evidence_state_enabled is False
    query = "q"
    safety = SafetyFrame(query)
    planner = NextActionPlanner(
        query, safety_frame=safety, tool_specs=safety.all_tool_specs()
    )
    finish_raw = DecisionParseResult(
        ok=True,
        decision=AgentDecision(
            action=AgentActionKind.finish, reason_code="llm_finish"
        ),
        llm_raw='{"action":"finish"}',
    )
    with patch.object(planner, "_call_llm", AsyncMock(return_value=finish_raw)):
        state = init_agent_state(original_query=query, max_steps=5)
        state = replace(state, evidence=EvidenceState(sufficient=False), steps_used=1)
        decision = await planner.decide_next(state)
    assert decision.action == AgentActionKind.finish
    assert decision.reason_code == "llm_finish"

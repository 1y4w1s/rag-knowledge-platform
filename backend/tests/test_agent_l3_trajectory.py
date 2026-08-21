"""L3-W6：Trajectory eval · scorer / deterministic contract（不替换 golden）。"""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.planners import NextActionPlanner, SafetyFrame
from app.services.agent.state import init_agent_state
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    DecisionParseResult,
    EvidenceState,
)
from tests.agent_trajectory.cases import (
    ALL_CASES,
    BUDGET_CAP,
    CLARIFY,
    DEPENDENT_ID,
    MISSING_FACT,
    STOP_NOW,
)
from tests.agent_trajectory.helpers import mock_parse
from tests.agent_trajectory.schemas import AcceptableAction
from tests.agent_trajectory.scorer import (
    in_acceptable_set,
    score_trajectory,
    summarize_scores,
)
from tests.golden_agent_qa_loader import EXPECTED_CASE_COUNT


def test_l3_trajectory_and_critic_flags_default_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False


def test_golden_not_replaced_by_trajectory_layer() -> None:
    golden = Path(__file__).resolve().parent / "test_agent_golden.py"
    assert golden.is_file()
    assert EXPECTED_CASE_COUNT == 168
    assert len(ALL_CASES) >= 5


def test_scorer_accepts_multiple_paths_not_exact_only() -> None:
    path_a = [
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "a"},
            reason_code="initial_retrieval",
        ),
        AgentDecision(action=AgentActionKind.finish, reason_code="evidence_sufficient"),
    ]
    assert score_trajectory(
        STOP_NOW, decisions=path_a, terminal=path_a[-1], steps_used=1
    ).task_success

    assert score_trajectory(
        CLARIFY,
        decisions=[
            AgentDecision(
                action=AgentActionKind.clarify, reason_code="ambiguous_user_intent"
            )
        ],
        terminal=AgentDecision(
            action=AgentActionKind.clarify, reason_code="ambiguous_user_intent"
        ),
        steps_used=0,
    ).task_success

    alt = [
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "half"},
        ),
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "missing"},
            reason_code="evidence_insufficient_retrieve",
        ),
        AgentDecision(action=AgentActionKind.finish, reason_code="evidence_sufficient"),
    ]
    assert score_trajectory(
        MISSING_FACT, decisions=alt, terminal=alt[-1], steps_used=2
    ).task_success


def test_scorer_rejects_premature_finish_on_missing_fact() -> None:
    bad = [
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "q"},
        ),
        AgentDecision(action=AgentActionKind.finish, reason_code="llm_early"),
    ]
    score = score_trajectory(
        MISSING_FACT, decisions=bad, terminal=bad[-1], steps_used=1
    )
    assert score.tool_selection_ok is False
    assert score.task_success is False


def test_scorer_dependency_requires_prior_ids() -> None:
    excerpt_first = [
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="get_chunk_excerpt",
            args={"chunk_id": str(uuid.uuid4())},
        ),
        AgentDecision(action=AgentActionKind.finish, reason_code="x"),
    ]
    assert (
        score_trajectory(
            DEPENDENT_ID,
            decisions=excerpt_first,
            terminal=excerpt_first[-1],
            steps_used=1,
            had_chunk_ids_before_dependent=False,
        ).dependency_ok
        is False
    )

    ok_path = [
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "q"},
        ),
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="get_chunk_excerpt",
            args={"chunk_id": str(uuid.uuid4())},
        ),
        AgentDecision(action=AgentActionKind.finish, reason_code="evidence_sufficient"),
    ]
    assert score_trajectory(
        DEPENDENT_ID,
        decisions=ok_path,
        terminal=ok_path[-1],
        steps_used=2,
        had_chunk_ids_before_dependent=True,
    ).task_success


def test_summarize_scores_rates() -> None:
    scores = [
        score_trajectory(
            STOP_NOW,
            decisions=[
                AgentDecision(
                    action=AgentActionKind.tool,
                    tool_name="semantic_search",
                    args={"query": "q"},
                ),
                AgentDecision(action=AgentActionKind.finish, reason_code="ok"),
            ],
            terminal=AgentDecision(action=AgentActionKind.finish, reason_code="ok"),
            steps_used=1,
        ),
        score_trajectory(
            CLARIFY,
            decisions=[
                AgentDecision(action=AgentActionKind.clarify, reason_code="ambiguous"),
            ],
            terminal=AgentDecision(
                action=AgentActionKind.clarify, reason_code="ambiguous"
            ),
            steps_used=0,
        ),
    ]
    summary = summarize_scores(scores)
    assert summary["n"] == 2
    assert summary["task_success_rate"] == 1.0
    assert "stop_now" in summary["by_category"]


def test_catalog_covers_handbook_categories() -> None:
    cats = {c.category for c in ALL_CASES}
    assert {
        "stop_now",
        "missing_fact",
        "dependent_id",
        "clarify",
        "budget_cap",
        "low_recall",
    } <= cats
    soft = AcceptableAction(
        action=AgentActionKind.finish,
        reason_codes=frozenset({"evidence_sufficient"}),
    )
    assert in_acceptable_set(
        AgentDecision(action=AgentActionKind.finish, reason_code="evidence_sufficient"),
        (soft,),
    )
    assert not in_acceptable_set(
        AgentDecision(action=AgentActionKind.finish, reason_code="other"),
        (soft,),
    )


def _planner(query: str) -> NextActionPlanner:
    safety = SafetyFrame(query)
    return NextActionPlanner(
        query, safety_frame=safety, tool_specs=safety.all_tool_specs()
    )


@pytest.mark.asyncio
async def test_deterministic_stop_now_via_evidence_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    query = "对比 Docker 与 Compose 分别是什么？"
    planner = _planner(query)
    call_llm = AsyncMock(return_value=DecisionParseResult(ok=False, error="no"))
    monkeypatch.setattr(planner, "_call_llm", call_llm)
    state = replace(
        init_agent_state(original_query=query, max_steps=5),
        evidence=EvidenceState(sufficient=True),
        steps_used=1,
    )
    decision = await planner.decide_next(state)
    assert decision.action == AgentActionKind.finish
    call_llm.assert_not_called()
    assert score_trajectory(
        STOP_NOW,
        decisions=[
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": query},
            ),
            decision,
        ],
        terminal=decision,
        steps_used=1,
    ).task_success


@pytest.mark.asyncio
async def test_deterministic_missing_fact_blocks_early_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    query = "住宿上限与高管例外分别是什么？"
    planner = _planner(query)
    monkeypatch.setattr(
        planner,
        "_call_llm",
        AsyncMock(
            return_value=mock_parse(
                AgentDecision(action=AgentActionKind.finish, reason_code="llm_guess")
            )
        ),
    )
    state = replace(
        init_agent_state(original_query=query, max_steps=5),
        evidence=EvidenceState(sufficient=False),
        steps_used=1,
        active_query=query,
    )
    decision = await planner.decide_next(state)
    assert decision.tool_name == "semantic_search"
    assert in_acceptable_set(decision, MISSING_FACT.acceptable_by_step[1])


@pytest.mark.asyncio
async def test_deterministic_dependent_id_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_dynamic_tools_enabled", True)
    chunk_id = uuid.uuid4()
    query = "对比 Docker 与 Compose 并核对原文？"
    planner = _planner(query)
    excerpt = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="get_chunk_excerpt",
        args={"chunk_id": str(chunk_id)},
        reason_code="need_source_excerpt",
    )
    monkeypatch.setattr(planner, "_call_llm", AsyncMock(return_value=mock_parse(excerpt)))
    state = replace(
        init_agent_state(original_query=query, max_steps=5),
        evidence=EvidenceState(chunk_ids=(chunk_id,), sufficient=False),
        steps_used=1,
    )
    decision = await planner.decide_next(state)
    assert decision.tool_name == "get_chunk_excerpt"
    assert in_acceptable_set(decision, DEPENDENT_ID.acceptable_by_step[1])

    planner2 = _planner(query)
    monkeypatch.setattr(
        planner2, "_call_llm", AsyncMock(return_value=mock_parse(excerpt))
    )
    empty = replace(init_agent_state(original_query=query, max_steps=5), steps_used=1)
    refused = await planner2.decide_next(empty)
    assert refused.action == AgentActionKind.refuse
    assert refused.reason_code == "safety_violation"


@pytest.mark.asyncio
async def test_deterministic_clarify_and_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = "那个制度怎么规定的对比一下？"
    planner = _planner(query)
    clarify = AgentDecision(
        action=AgentActionKind.clarify,
        reason_code="ambiguous_user_intent",
        user_message="要哪份制度？",
    )
    monkeypatch.setattr(planner, "_call_llm", AsyncMock(return_value=mock_parse(clarify)))
    decision = await planner.decide_next(init_agent_state(original_query=query, max_steps=5))
    assert decision.action == AgentActionKind.clarify
    assert score_trajectory(
        CLARIFY, decisions=[decision], terminal=decision, steps_used=0
    ).task_success

    planner_b = _planner(query)
    call_llm = AsyncMock()
    monkeypatch.setattr(planner_b, "_call_llm", call_llm)
    capped = replace(init_agent_state(original_query=query, max_steps=2), steps_used=2)
    refused = await planner_b.decide_next(capped)
    assert refused.reason_code == "budget_exhausted"
    call_llm.assert_not_called()
    assert in_acceptable_set(refused, BUDGET_CAP.acceptable_by_step[2])

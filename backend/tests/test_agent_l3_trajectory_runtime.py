"""L3-W6：Trajectory eval · mock-LLM runtime 轨迹（不替换 golden）。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.runtime import run_react_loop
from app.services.agent.state import init_agent_state
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import AgentActionKind, AgentDecision, EvidenceState
from tests.agent_trajectory.cases import LOW_RECALL, MISSING_FACT, STOP_NOW
from tests.agent_trajectory.helpers import (
    QueueMockLLMPlanner,
    create_personal_thread,
    hits_weak_one,
    personal_workspace,
    search_ok,
)
from tests.agent_trajectory.scorer import in_acceptable_set, score_trajectory


@pytest.mark.asyncio
async def test_mock_llm_trajectory_stop_now(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    _, user = await register_and_login(prefix="l3w6-stop")
    user_id = UUID(user["id"])
    thread_id = await create_personal_thread(user_id)
    query = "对比 Docker 与 Compose 分别是什么？"
    planner = QueueMockLLMPlanner(
        query,
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "Docker Compose"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(action=AgentActionKind.finish, reason_code="llm_finish"),
        ],
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=search_ok("Docker Compose")),
    )
    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            workspace=personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    score = score_trajectory(
        STOP_NOW,
        decisions=planner.decisions_seen,
        terminal=outcome.terminal_decision,
        steps_used=outcome.steps_used,
    )
    assert score.task_success is True
    assert outcome.steps_used <= 1


@pytest.mark.asyncio
async def test_mock_llm_trajectory_missing_fact_then_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_evidence_state_enabled", True)
    _, user = await register_and_login(prefix="l3w6-miss")
    user_id = UUID(user["id"])
    thread_id = await create_personal_thread(user_id)
    query = "住宿上限与高管例外分别是什么？"
    planner = QueueMockLLMPlanner(
        query,
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "住宿上限"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(action=AgentActionKind.finish, reason_code="llm_early"),
            AgentDecision(action=AgentActionKind.finish, reason_code="llm_done"),
        ],
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(
            side_effect=[
                search_ok("住宿", hits=hits_weak_one()),
                search_ok("高管例外"),
            ]
        ),
    )
    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            workspace=personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert len(outcome.steps) >= 2
    assert planner.decisions_seen[1].tool_name == "semantic_search"
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    score = score_trajectory(
        MISSING_FACT,
        decisions=planner.decisions_seen,
        terminal=outcome.terminal_decision,
        steps_used=outcome.steps_used,
    )
    assert score.task_success is True


@pytest.mark.asyncio
async def test_mock_llm_low_recall_second_search_acceptable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = "对比 A 与 B 的差异以及如何计算？"
    planner = QueueMockLLMPlanner(
        query,
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "rewrite"},
                reason_code="low_recall_rewrite",
            ),
        ],
    )
    state = replace(
        init_agent_state(original_query=query, max_steps=5),
        steps_used=1,
        evidence=EvidenceState(sufficient=False, confidence=0.0),
    )
    decision = await planner.decide_next(state)
    assert in_acceptable_set(decision, LOW_RECALL.acceptable_by_step[1])
    score = score_trajectory(
        LOW_RECALL,
        decisions=[
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "first"},
            ),
            decision,
            AgentDecision(
                action=AgentActionKind.refuse, reason_code="no_supported_answer"
            ),
        ],
        terminal=AgentDecision(
            action=AgentActionKind.refuse, reason_code="no_supported_answer"
        ),
        steps_used=2,
    )
    assert score.task_success is True


def test_runtime_file_keeps_critic_off() -> None:
    assert settings.rag_critic_enabled is False

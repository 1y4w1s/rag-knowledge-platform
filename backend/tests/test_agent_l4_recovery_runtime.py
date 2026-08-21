"""L4-W6b：Recovery → L3 loop 薄接线（默认关）。"""

from __future__ import annotations

import uuid
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.reflection_recovery import (
    derive_l3_reflection_signal,
    maybe_l3_recovery_decision,
)
from app.services.agent.runtime import run_react_loop
from app.services.agent.state import init_agent_state
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentStepRecord,
    FactGoal,
    FactKind,
    FactStatus,
    ToolFailure,
    ToolFailureKind,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.test_agent_l3_runtime import ScriptedNextActionPlanner


def test_l4_recovery_and_l3_flags_default_false() -> None:
    assert settings.agent_l4_reflection_recovery_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.rag_critic_enabled is False


def _missing_goal() -> FactGoal:
    return FactGoal(
        id="F1",
        text="正式员工每月餐补 300 元",
        kind=FactKind.lookup,
        status=FactStatus.missing,
    )


def _state_with_missing(*, reflection_count: int = 0, steps_used: int = 0):
    state = init_agent_state(
        original_query="餐补多少？",
        max_steps=5,
        fact_goals=(_missing_goal(),),
    )
    if reflection_count or steps_used:
        return replace(
            state,
            reflection_count=reflection_count,
            steps_used=steps_used,
        )
    return state


def test_maybe_recovery_flag_off_is_none() -> None:
    assert settings.agent_l4_reflection_recovery_enabled is False
    state = _state_with_missing()
    assert maybe_l3_recovery_decision(state) is None


def test_maybe_recovery_fill_gap_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    monkeypatch.setattr(settings, "agent_max_reflections", 1)
    state = _state_with_missing()
    decision = maybe_l3_recovery_decision(state)
    assert decision is not None
    assert decision.action == AgentActionKind.tool
    assert decision.tool_name == "semantic_search"
    assert decision.reason_code == "facts_fill_gap"
    assert "餐补" in decision.args["query"]


def test_maybe_recovery_fallback_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    monkeypatch.setattr(settings, "agent_max_reflections", 1)
    state = replace(
        _state_with_missing(steps_used=1),
        last_failure=ToolFailure(
            kind=ToolFailureKind.infra,
            tool_name="semantic_search",
            summary="timeout",
        ),
    )
    decision = maybe_l3_recovery_decision(state)
    assert decision is not None
    assert decision.reason_code == "tool_failure_fallback"


def test_maybe_recovery_exhausted_after_reflection_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    monkeypatch.setattr(settings, "agent_max_reflections", 1)
    state = _state_with_missing(reflection_count=1)
    assert maybe_l3_recovery_decision(state) is None


def test_derive_low_recall_from_empty_hits() -> None:
    empty = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "q"},
        ok=True,
        summary="命中 0",
        latency_ms=1,
        data=SemanticSearchOutput(hits=(), retrieval_ms=1),
    )
    state = replace(_state_with_missing(steps_used=1), steps=(empty,))
    assert derive_l3_reflection_signal(state) == "low_recall"


def test_derive_no_signal_on_hits() -> None:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="手册.md",
        page=1,
        section_title="餐补",
        excerpt="餐补 300",
        score=0.9,
    )
    step = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "q"},
        ok=True,
        summary="命中 1",
        latency_ms=1,
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
    )
    state = replace(_state_with_missing(steps_used=1), steps=(step,))
    assert derive_l3_reflection_signal(state) is None


def _personal_workspace(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def _create_personal_thread(user_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


def _search_ok(query: str = "q") -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="手册.md",
        page=1,
        section_title="餐补",
        excerpt="正式员工每月餐补 300 元",
        score=0.91,
    )
    return SemanticSearchToolResult(
        ok=True,
        summary=f"命中 1 · {query[:40]}",
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=12),
    )


@pytest.mark.asyncio
async def test_runtime_flag_off_unchanged_decide_count(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认关：L3 轨迹与接线前一致（decide 次数不变）。"""
    assert settings.agent_l4_reflection_recovery_enabled is False
    _, user = await register_and_login(prefix="l4w6b-off")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "餐补"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="餐补多少？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("餐补")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 2
    assert [s.tool_name for s in outcome.steps] == ["semantic_search"]
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish


@pytest.mark.asyncio
async def test_runtime_flag_on_fill_gap_before_planner(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """flag 开 + missing FactGoal：首步 Recovery fill_gap，不消耗 planner script。"""
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    monkeypatch.setattr(settings, "agent_max_reflections", 1)

    goal = _missing_goal()
    real_init = init_agent_state

    def _init_with_facts(**kwargs):
        kwargs.setdefault("fact_goals", (goal,))
        return real_init(**kwargs)

    monkeypatch.setattr(
        "app.services.agent.runtime.init_agent_state",
        _init_with_facts,
    )

    _, user = await register_and_login(prefix="l4w6b-on")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="餐补多少？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("餐补")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert len(outcome.steps) == 1
    assert outcome.steps[0].tool_name == "semantic_search"
    assert outcome.steps[0].args.get("query", "").startswith("正式员工")
    # 首步 Recovery 未调 planner；次步 reflection 预算尽 → finish
    assert planner.decide_calls == 1
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish

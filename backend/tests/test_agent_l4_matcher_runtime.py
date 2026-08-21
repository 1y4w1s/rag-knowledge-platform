"""L4：EvidenceMatcher → L3 runtime tool observation 薄接线（默认关）。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.matcher_runtime import (
    maybe_apply_evidence_match_after_tool,
    snippets_from_tool_data,
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
    FactGoal,
    FactKind,
    FactStatus,
    StepExecution,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.test_agent_l3_runtime import ScriptedNextActionPlanner


def test_l4_matcher_and_l3_flags_default_false() -> None:
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.rag_critic_enabled is False


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


def _goals() -> tuple[FactGoal, ...]:
    return (
        FactGoal(id="F1", text="找到 2025 住宿标准", kind=FactKind.compare),
        FactGoal(id="F2", text="找到 2026 住宿标准", kind=FactKind.compare),
        FactGoal(
            id="F3",
            text="确认台湾办公室员工的适用规则",
            kind=FactKind.condition,
        ),
    )


def _search_ok() -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="差旅.md",
        page=1,
        section_title="住宿",
        excerpt="根据制度，2025 住宿标准为每人每晚 500 元。",
        score=0.91,
    )
    return SemanticSearchToolResult(
        ok=True,
        summary="命中 1 · 住宿",
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=12),
    )


def _patch_init_with_goals(
    monkeypatch: pytest.MonkeyPatch, goals: tuple[FactGoal, ...]
) -> None:
    real_init = init_agent_state

    def _init(**kwargs):
        kwargs["fact_goals"] = goals
        return real_init(**kwargs)

    monkeypatch.setattr("app.services.agent.runtime.init_agent_state", _init)


def test_snippets_from_semantic_search() -> None:
    data = _search_ok().data
    assert data is not None
    snippets = snippets_from_tool_data(data)
    assert len(snippets) == 1
    assert "2025 住宿标准" in snippets[0].text


def test_maybe_apply_flag_off_passthrough() -> None:
    assert settings.agent_l4_evidence_matcher_enabled is False
    state = init_agent_state(
        original_query="q", max_steps=3, fact_goals=_goals()
    )
    data = _search_ok().data
    execution = StepExecution(
        ok=True, summary="ok", latency_ms=1, data=data
    )
    after = maybe_apply_evidence_match_after_tool(state, execution)
    assert after is state
    assert all(g.status == FactStatus.missing for g in after.evidence.facts)


def test_maybe_apply_empty_ledger_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    state = init_agent_state(original_query="q", max_steps=3)
    execution = StepExecution(
        ok=True, summary="ok", latency_ms=1, data=_search_ok().data
    )
    after = maybe_apply_evidence_match_after_tool(state, execution)
    assert after is state
    assert after.evidence.facts == ()
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", False)


def test_maybe_apply_flag_on_covers_f1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    state = init_agent_state(
        original_query="q", max_steps=3, fact_goals=_goals()
    )
    execution = StepExecution(
        ok=True, summary="ok", latency_ms=1, data=_search_ok().data
    )
    after = maybe_apply_evidence_match_after_tool(state, execution)
    status = {g.id: g.status for g in after.evidence.facts}
    assert status["F1"] == FactStatus.covered
    assert status["F3"] == FactStatus.missing
    assert "找到 2025 住宿标准" in after.evidence.covered_facts
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", False)


@pytest.mark.asyncio
async def test_runtime_flag_off_ledger_unchanged(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认关：有 FactGoal 也不改 status。"""
    assert settings.agent_l4_evidence_matcher_enabled is False
    _patch_init_with_goals(monkeypatch, _goals())

    _, user = await register_and_login(prefix="l4match-off")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "2025 住宿"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比住宿标准？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok()),
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
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish


@pytest.mark.asyncio
async def test_runtime_flag_on_updates_coverage(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """flag 开：search observation 后 F1 covered（lexical）。"""
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    captured: list[tuple[FactStatus, ...]] = []
    real_apply = maybe_apply_evidence_match_after_tool

    def _spy(state, execution):  # noqa: ANN001
        after = real_apply(state, execution)
        captured.append(tuple(g.status for g in after.evidence.facts))
        return after

    import app.services.agent.matcher_runtime as matcher_rt

    monkeypatch.setattr(
        matcher_rt, "maybe_apply_evidence_match_after_tool", _spy
    )
    _patch_init_with_goals(monkeypatch, _goals())

    _, user = await register_and_login(prefix="l4match-on")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "2025 住宿"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比住宿标准？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok()),
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

    assert captured, "matcher hook must run after tool"
    assert captured[0][0] == FactStatus.covered  # F1
    assert outcome.terminal_decision is not None
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", False)

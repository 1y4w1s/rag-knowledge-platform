"""L4：FactDecomposer → L3 runtime init_agent_state 薄接线（默认关）。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.decomposer import maybe_fact_goals_for_init
from app.services.agent.runtime import run_react_loop
from app.services.agent.state import init_agent_state
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import AgentActionKind, AgentDecision, FactGoal
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.test_agent_l3_runtime import ScriptedNextActionPlanner


def test_l4_decomposer_and_l3_flags_default_false() -> None:
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
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


def _search_ok(query: str = "q") -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="手册.md",
        page=1,
        section_title="用途",
        excerpt="Docker Compose 用于编排多容器应用",
        score=0.91,
    )
    return SemanticSearchToolResult(
        ok=True,
        summary=f"命中 1 · {query[:40]}",
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=12),
    )


@pytest.mark.asyncio
async def test_maybe_fact_goals_flag_off_empty() -> None:
    assert settings.agent_l4_fact_decomposition_enabled is False
    goals = await maybe_fact_goals_for_init("Docker Compose 用途？")
    assert goals == ()


@pytest.mark.asyncio
async def test_maybe_fact_goals_flag_on_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    goals = await maybe_fact_goals_for_init(
        "Docker Compose 用途？", difficulty="simple"
    )
    assert len(goals) == 1
    assert goals[0].id == "F1"
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", False)
    assert settings.agent_l4_fact_decomposition_enabled is False


@pytest.mark.asyncio
async def test_runtime_flag_off_empty_ledger(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认关：init 仍为空 ledger（与接线前一致）。"""
    assert settings.agent_l4_fact_decomposition_enabled is False
    captured: list[tuple[FactGoal, ...]] = []
    real_init = init_agent_state

    def _spy_init(**kwargs):
        captured.append(kwargs.get("fact_goals", ()))
        return real_init(**kwargs)

    monkeypatch.setattr("app.services.agent.runtime.init_agent_state", _spy_init)

    _, user = await register_and_login(prefix="l4dec-off")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "Docker Compose"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="Docker Compose 用途？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("Docker Compose")),
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

    assert captured == [()]
    assert planner.decide_calls == 2
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish


@pytest.mark.asyncio
async def test_runtime_flag_on_seeds_fact_goals(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """flag 开：init 收到 Decomposer 产出的 FactGoal[]。"""
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    captured: list[tuple[FactGoal, ...]] = []
    real_init = init_agent_state

    def _spy_init(**kwargs):
        captured.append(kwargs.get("fact_goals", ()))
        return real_init(**kwargs)

    monkeypatch.setattr("app.services.agent.runtime.init_agent_state", _spy_init)

    _, user = await register_and_login(prefix="l4dec-on")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    query = "根据 2025 与 2026 差旅制度，住宿标准发生了什么变化？"
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=query,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert len(captured) == 1
    goals = captured[0]
    assert 1 <= len(goals) <= 6
    assert all(isinstance(g, FactGoal) for g in goals)
    assert goals[0].id == "F1"
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", False)
    assert settings.agent_l4_fact_decomposition_enabled is False

"""L3-W3：runtime 最小 L3 loop（mock 轨迹 · 成功后也 re-decide）。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.planners import NextActionPlanner, SafetyFrame
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentBudgetEvent,
    AgentDecision,
    AgentState,
    AgentStepRecord,
    ToolCallPlan,
    ToolResultEvent,
    ToolStartEvent,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


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


@dataclass
class RecordingHooks:
    starts: list[ToolStartEvent] = field(default_factory=list)
    results: list[ToolResultEvent] = field(default_factory=list)
    budgets: list[AgentBudgetEvent] = field(default_factory=list)

    async def on_tool_start(self, event: ToolStartEvent) -> None:
        self.starts.append(event)

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        self.results.append(event)

    async def on_agent_budget(self, event: AgentBudgetEvent) -> None:
        self.budgets.append(event)


@dataclass
class SequencePlanner:
    """Legacy ToolPlanner：用 None 结束（对照 L3 显式 finish）。"""

    plans: list[ToolCallPlan | None]
    calls: int = 0

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index, steps_used, max_steps, prior_steps
        if self.calls >= len(self.plans):
            return None
        plan = self.plans[self.calls]
        self.calls += 1
        return plan


class ScriptedNextActionPlanner(NextActionPlanner):
    """脚本化 L3 planner：按队列吐出 AgentDecision（无 LLM）。"""

    def __init__(
        self,
        script: list[AgentDecision],
        *,
        query: str = "对比 Docker 与 Compose 分别是什么？以及如何计算？",
    ) -> None:
        safety = SafetyFrame(query)
        super().__init__(
            query,
            safety_frame=safety,
            tool_specs=safety.all_tool_specs(),
        )
        self._script = list(script)
        self.decide_calls = 0
        self.seen_steps_used: list[int] = []

    async def decide_next(self, state: AgentState) -> AgentDecision:
        self.decide_calls += 1
        self.seen_steps_used.append(state.steps_used)
        if not self._script:
            return AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="script_exhausted",
            )
        return self._script.pop(0)


def _search_ok(query: str = "q") -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="手册.md",
        page=1,
        section_title="用途",
        excerpt="Docker Compose 用途说明",
        score=0.91,
    )
    return SemanticSearchToolResult(
        ok=True,
        summary=f"命中 1 · {query[:40]}",
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=12),
    )


def test_l3_and_critic_flags_default_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False


@pytest.mark.asyncio
async def test_flag_off_legacy_none_stop_unchanged(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """flag 关：仍走 next_tool_call；None 结束；无 terminal_decision。"""
    _, user = await register_and_login(prefix="l3w3-legacy")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(
                tool_name="semantic_search",
                args={"query": "年假"},
            ),
            None,
        ]
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("年假")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假几天？",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert len(outcome.steps) == 1
    assert outcome.steps[0].tool_name == "semantic_search"
    assert outcome.terminal_decision is None
    assert planner.calls == 2  # 1 tool + 1 None


@pytest.mark.asyncio
async def test_l3_trajectory_search_then_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mock 轨迹：search → finish；成功后仍 re-decide（第 2 次 decide）。"""
    _, user = await register_and_login(prefix="l3w3-finish")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    hooks = RecordingHooks()
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "Docker Compose 用途"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("Docker Compose 用途")),
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
            hooks=hooks,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == ["semantic_search"]
    assert outcome.steps[0].ok is True
    assert planner.decide_calls == 2
    assert planner.seen_steps_used == [0, 1]  # 成功后 steps_used=1 再 decide
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    assert outcome.terminal_decision.reason_code == "evidence_sufficient"
    assert outcome.capped is False
    assert len(hooks.starts) == 1
    assert len(hooks.results) == 1


@pytest.mark.asyncio
async def test_l3_trajectory_search_then_second_search_then_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mock 轨迹：search → second search → finish（真实 Observation 驱动，非缓存序列）。"""
    _, user = await register_and_login(prefix="l3w3-research")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "Docker Compose 用途"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "Docker Compose 安装"},
                reason_code="missing_install_fact",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(side_effect=[_search_ok("用途"), _search_ok("安装")]),
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

    assert [s.tool_name for s in outcome.steps] == [
        "semantic_search",
        "semantic_search",
    ]
    assert planner.decide_calls == 3
    assert planner.seen_steps_used == [0, 1, 2]
    assert outcome.steps_used == 2
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish


@pytest.mark.asyncio
async def test_l3_explicit_refuse_no_none_semantics(
    register_and_login,
) -> None:
    """显式 refuse：不执行 tool；terminal_decision=refuse（不靠 None）。"""
    _, user = await register_and_login(prefix="l3w3-refuse")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="no_evidence",
            ),
        ]
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

    assert outcome.steps == ()
    assert planner.decide_calls == 1
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.refuse
    assert outcome.terminal_decision.reason_code == "no_evidence"


@pytest.mark.asyncio
async def test_l3_explicit_clarify(
    register_and_login,
) -> None:
    """显式 clarify：停止且带 user_message。"""
    _, user = await register_and_login(prefix="l3w3-clarify")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.clarify,
                reason_code="ambiguous_doc",
                user_message="要哪份手册？",
            ),
        ]
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

    assert outcome.steps == ()
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.clarify
    assert outcome.terminal_decision.user_message == "要哪份手册？"

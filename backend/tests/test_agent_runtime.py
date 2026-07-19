"""G3-2.1：agent/runtime.py ReAct 循环 · max 5 · tool_start/result 钩子。"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.services.agent.types import (
    AgentBudgetEvent,
    AgentStepRecord,
    ToolCallPlan,
    ToolResultEvent,
    ToolStartEvent,
)
from unittest.mock import AsyncMock
from uuid import UUID
from typing import Any

import pytest

from app.core.database import SessionLocal
from app.models.enums import AgentRunStatus
from app.services.agent.runs import (
    get_agent_run_for_user,
    list_agent_steps_for_run,
)
from app.services.agent.runtime import build_args_summary, run_react_loop
from app.services.agent.tools.scope import AgentToolScope
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
class SequencePlanner:
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
class SlowPlanner:
    delay_seconds: float
    inner: SequencePlanner

    async def next_tool_call(self, **kwargs: Any) -> ToolCallPlan | None:
        await asyncio.sleep(self.delay_seconds)
        return await self.inner.next_tool_call(**kwargs)


def test_build_args_summary_semantic_search() -> None:
    summary = build_args_summary("semantic_search", {"query": "年假有多少天"})
    assert summary == "年假有多少天"


@pytest.mark.asyncio
async def test_react_loop_fires_tool_start_and_result_hooks(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tool_start/result 钩子每步各触发一次。"""
    _, user = await register_and_login(prefix="g3-runtime-hooks")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    hooks = RecordingHooks()
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="list_knowledge_bases", args={"limit": 5}),
            None,
        ]
    )

    list_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "ok": True,
                "summary": "可见库 1 个 · personal",
                "data": None,
            },
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_list_knowledge_bases",
        list_mock,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="列一下库",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            hooks=hooks,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 1
    assert len(hooks.starts) == 1
    assert len(hooks.results) == 1
    assert len(hooks.budgets) == 1
    assert hooks.budgets[0].steps_used == 1
    assert hooks.budgets[0].capped is False
    assert hooks.starts[0].tool == "list_knowledge_bases"
    assert hooks.starts[0].step == 1
    assert hooks.results[0].ok is True
    assert hooks.results[0].summary == "可见库 1 个 · personal"


@pytest.mark.asyncio
async def test_react_loop_caps_at_five_steps_e_budget(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-budget：planner 无限供给时 runtime 最多执行 5 步。"""
    _, user = await register_and_login(prefix="g3-runtime-cap")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    hooks = RecordingHooks()
    always_list = ToolCallPlan(tool_name="list_knowledge_bases", args={})
    planner = SequencePlanner([always_list] * 10)

    list_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {"ok": True, "summary": "可见库 0 个 · personal", "data": None},
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_list_knowledge_bases",
        list_mock,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="复杂题",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            hooks=hooks,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 5
    assert outcome.capped is True
    assert len(hooks.results) == 5
    assert hooks.results[-1].capped is True
    assert len(hooks.budgets) == 5
    assert hooks.budgets[-1].steps_used == 5
    assert hooks.budgets[-1].max_steps == 5
    assert hooks.budgets[-1].capped is True
    assert list_mock.await_count == 5

    async with SessionLocal() as db:
        run = await get_agent_run_for_user(db, run_id=outcome.run_id, user_id=user_id)
    assert run is not None
    assert run.status == AgentRunStatus.capped


@pytest.mark.asyncio
async def test_react_loop_unknown_tool_ok_false_not_500(
    register_and_login,
) -> None:
    """G3-E8：非白名单 tool 返回 ok=false · 不抛 500。"""
    _, user = await register_and_login(prefix="g3-runtime-deny")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="propose_upload", args={"kb_id": str(uuid.uuid4())})]
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="写库",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 1
    assert outcome.steps[0].ok is False
    assert "unknown or disallowed tool" in outcome.steps[0].summary


@pytest.mark.asyncio
async def test_react_loop_timeout_before_next_step(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时：下一步 planner 前 deadline 已到则停止扩检索。"""
    _, user = await register_and_login(prefix="g3-runtime-timeout")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    inner = SequencePlanner(
        [
            ToolCallPlan(tool_name="list_knowledge_bases", args={}),
            ToolCallPlan(tool_name="list_knowledge_bases", args={}),
        ]
    )
    planner = SlowPlanner(delay_seconds=0.05, inner=inner)

    list_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {"ok": True, "summary": "可见库 0 个 · personal", "data": None},
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_list_knowledge_bases",
        list_mock,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="慢题",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
            timeout_seconds=0.01,
        )
        await db.commit()

    assert outcome.timed_out is True
    assert outcome.steps_used <= 1


@pytest.mark.asyncio
async def test_react_loop_persists_run_and_steps(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run/step 落库 · user_id 隔离可读（G3-E10 基础）。"""
    _, user = await register_and_login(prefix="g3-runtime-db")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="list_knowledge_bases", args={"q": "人事"})]
    )

    list_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {"ok": True, "summary": "可见库 2 个 · personal", "data": None},
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_list_knowledge_bases",
        list_mock,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="人事政策",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
        )
        await db.commit()

    async with SessionLocal() as db:
        run = await get_agent_run_for_user(db, run_id=outcome.run_id, user_id=user_id)
        steps = await list_agent_steps_for_run(
            db, run_id=outcome.run_id, user_id=user_id
        )

    assert run is not None
    assert run.steps_used == 1
    assert run.status == AgentRunStatus.completed
    assert steps is not None
    assert len(steps) == 1
    assert steps[0].tool_name == "list_knowledge_bases"
    assert steps[0].result_summary == "可见库 2 个 · personal"

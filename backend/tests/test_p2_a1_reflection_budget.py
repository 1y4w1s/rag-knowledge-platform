"""P2-A1：complex_query 反思子步骤必须计入步数预算并留下工具审计。

覆盖场景：
- 子步骤生成 agent_step / agent.tool_executed 审计 / agent_budget 事件；
- 子步骤用尽 max_steps 时 run 收敛 capped，不再继续执行后续搜索。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AgentRunStatus
from app.services.agent.planners import LLMPlanner, SafetyFrame
from app.services.agent.runs import (
    get_agent_run_for_user,
    list_agent_steps_for_run,
)
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import (
    AgentBudgetEvent,
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


class _ControlledLLMPlanner(LLMPlanner):
    """保持 isinstance(LLMPlanner)，但 next_tool_call 由测试控制。"""

    def __init__(self, query: str, plans: list[ToolCallPlan | None]) -> None:
        safety_frame = SafetyFrame(query)
        super().__init__(
            query,
            safety_frame=safety_frame,
            tool_specs=safety_frame.all_tool_specs(),
        )
        self._plans = list(plans)

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
        if not self._plans:
            return None
        return self._plans.pop(0)


class _ControlledSubPlanner:
    def __init__(self, plans: list[ToolCallPlan | None]) -> None:
        self._plans = list(plans)

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
        if not self._plans:
            return None
        return self._plans.pop(0)


def _search_result() -> Any:
    return type(
        "R",
        (),
        {
            "ok": True,
            "summary": "检索到 1 条",
            "data": SemanticSearchOutput(
                hits=(
                    SemanticSearchHit(
                        chunk_id=uuid.uuid4(),
                        kb_id=uuid.uuid4(),
                        kb_name="测试库",
                        doc_name="手册.md",
                        page=1,
                        section_title="年假",
                        excerpt="年假 10 天",
                        score=0.9,
                    ),
                ),
                retrieval_ms=5,
            ),
        },
    )()


def _search_plan(query: str) -> ToolCallPlan:
    return ToolCallPlan(tool_name="semantic_search", args={"query": query})


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """触发 complex_query 反思，前两个子查询返回搜索计划。"""

    async def _fake_decompose(query: str) -> list[str]:
        del query
        return ["年假规定", "病假规定", "考勤制度"]

    def _fake_factory_create(
        query: str,
        *,
        default_kb_id: Any = None,
        memory_context: str = "",
    ) -> _ControlledSubPlanner:
        del default_kb_id, memory_context
        plans = (
            [_search_plan(query), None]
            if query in ("年假规定", "病假规定")
            else [None]
        )
        return _ControlledSubPlanner(plans)

    search_mock = AsyncMock(return_value=_search_result())
    monkeypatch.setattr(
        "app.services.agent.runtime._detect_reflection_signal",
        lambda *args, **kwargs: "complex_query",
    )
    monkeypatch.setattr(
        "app.services.rag.generation.decompose_query", _fake_decompose
    )
    monkeypatch.setattr(
        "app.services.agent.planners.LLMPlannerFactory.create",
        _fake_factory_create,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", search_mock
    )
    return search_mock


async def _count_tool_executed_audits(run_id: UUID) -> int:
    async with SessionLocal() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.action == "agent.tool_executed",
                AuditLog.resource_id == run_id,
            )
        )
        return len(result.scalars().all())


@pytest.mark.asyncio
async def test_reflection_sub_steps_count_into_budget_and_audit(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complex_query 反思子步骤：落 step、审计、SSE 与 steps_used 全量记账。"""
    _, user = await register_and_login(prefix="p2-a1-reflect-audit")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    search_mock = _install_fakes(monkeypatch)
    planner = _ControlledLLMPlanner(
        "对比年假和病假政策",
        [_search_plan("对比年假和病假政策"), None],
    )
    hooks = RecordingHooks()

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="对比年假和病假政策",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            hooks=hooks,
            max_steps=5,
        )
        await db.commit()

    assert outcome.capped is False
    assert outcome.steps_used == 3  # 主步 + 2 个反思子步骤
    assert [s.step_index for s in outcome.steps] == [1, 2, 3]
    assert search_mock.await_count == 3
    assert len(hooks.starts) == 3
    assert len(hooks.results) == 3
    assert len(hooks.budgets) == 3
    assert [b.steps_used for b in hooks.budgets] == [2, 3, 3]
    assert hooks.budgets[-1].capped is False

    async with SessionLocal() as db:
        run = await get_agent_run_for_user(
            db, run_id=outcome.run_id, user_id=user_id
        )
        steps = await list_agent_steps_for_run(
            db, run_id=outcome.run_id, user_id=user_id
        )
    assert run is not None
    assert run.steps_used == 3
    assert run.status == AgentRunStatus.completed
    assert steps is not None
    assert len(steps) == 3
    assert [s.step_index for s in steps] == [1, 2, 3]

    assert await _count_tool_executed_audits(outcome.run_id) == 3


@pytest.mark.asyncio
async def test_reflection_sub_steps_cap_run_at_max_steps(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """反思子步骤耗尽 max_steps 时立即触顶，不继续执行后续搜索。"""
    _, user = await register_and_login(prefix="p2-a1-reflect-cap")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    search_mock = _install_fakes(monkeypatch)
    planner = _ControlledLLMPlanner(
        "对比年假和病假政策",
        [_search_plan("对比年假和病假政策"), None],
    )
    hooks = RecordingHooks()

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="对比年假和病假政策",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            hooks=hooks,
            max_steps=2,
        )
        await db.commit()

    assert outcome.capped is True
    assert outcome.steps_used == 2
    assert len(outcome.steps) == 2
    assert search_mock.await_count == 2  # 主步 + 1 个子步骤，第二个子步骤被预算拦下
    assert len(hooks.budgets) == 2
    assert hooks.budgets[-1].steps_used == 2
    assert hooks.budgets[-1].capped is True

    async with SessionLocal() as db:
        run = await get_agent_run_for_user(
            db, run_id=outcome.run_id, user_id=user_id
        )
    assert run is not None
    assert run.status == AgentRunStatus.capped
    assert await _count_tool_executed_audits(outcome.run_id) == 2

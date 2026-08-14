"""G2 W3 · runtime 每轮限流 / 窗口限流 / metrics 接线测试。"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import reset_all_breakers
from app.models.audit_log import AuditLog
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools import guard as guard_mod
from app.services.agent.tools.guard import (
    ensure_agent_tool_breakers,
    reset_tool_window_limits,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import SemanticSearchToolResult
from app.services.agent.tools.web_search import WebSearchResult
from app.services.agent.types import ToolCallPlan
from app.services.observability.metrics_registry import (
    agent_tool_calls_snapshot,
    agent_tool_window_rejected_snapshot,
    rate_limit_backend_fallback_snapshot,
    reset_process_counters_for_tests,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import (
    WorkspaceKind,
    WorkspaceScope,
)

web_search_module = importlib.import_module("app.services.agent.tools.web_search")


@pytest.fixture(autouse=True)
def _disable_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "retry_max_attempts", 0)


@pytest.fixture(autouse=True)
def _isolate_state() -> None:
    ensure_agent_tool_breakers()
    reset_all_breakers()
    reset_tool_window_limits()
    reset_process_counters_for_tests()
    yield
    reset_all_breakers()
    reset_tool_window_limits()
    reset_process_counters_for_tests()


def _personal_workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def _create_personal_thread(user_id: UUID) -> UUID:
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

    async def next_tool_call(self, **kwargs) -> ToolCallPlan | None:
        del kwargs
        if self.calls >= len(self.plans):
            return None
        plan = self.plans[self.calls]
        self.calls += 1
        return plan


def _web_search_ok() -> AsyncMock:
    return AsyncMock(
        return_value=WebSearchResult(
            ok=True,
            data=[{"title": "T", "url": "https://t", "snippet": "s"}],
            summary="ok",
        )
    )


def _semantic_ok() -> AsyncMock:
    return AsyncMock(
        return_value=SemanticSearchToolResult(ok=True, data=None, summary="ok")
    )


async def _denied_reasons(run_id: UUID) -> list[str]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "agent.tool_denied",
                    AuditLog.resource_id == run_id,
                )
            )
        ).scalars().all()
    return [row.details["reason"] for row in rows]


async def _run(
    *,
    user_id: UUID,
    thread_id: UUID,
    planner: SequencePlanner,
) -> object:
    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="最近行业动态",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()
    return outcome


@pytest.mark.asyncio
async def test_per_run_limit_rejected_as_disabled(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(
        settings,
        "agent_tool_max_calls_per_run_override",
        {"web_search": 1},
    )
    _, user = await register_and_login(prefix="g2-w3-runlimit")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is True
    assert outcome.steps[1].ok is False
    assert "本轮上限" in outcome.steps[1].summary
    assert outcome.steps[2].ok is True
    assert outcome.tool_fallback_count == 1
    assert "tool_run_limit" in await _denied_reasons(outcome.run_id)
    snap = agent_tool_calls_snapshot()
    assert snap[("web_search", "ok", True)] == 1
    assert snap[("web_search", "limited", True)] == 1
    assert snap[("semantic_search", "ok", False)] == 1


@pytest.mark.asyncio
async def test_web_search_default_limit_preserved(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(settings, "agent_tool_max_calls_per_run_override", {})
    monkeypatch.setattr(settings, "agent_max_external_calls_per_conversation", 1)
    _, user = await register_and_login(prefix="g2-w3-default")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is True
    assert outcome.steps[1].ok is False
    assert "tool_run_limit" in await _denied_reasons(outcome.run_id)


@pytest.mark.asyncio
async def test_tool_run_limit_is_per_tool(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(
        settings,
        "agent_tool_max_calls_per_run_override",
        {"semantic_search": 1, "web_search": 1},
    )
    _, user = await register_and_login(prefix="g2-w3-per-tool")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="semantic_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="semantic_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "semantic_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is True
    assert outcome.steps[1].ok is True
    assert outcome.steps[2].ok is False
    snap = agent_tool_calls_snapshot()
    assert snap[("web_search", "ok", True)] == 1
    assert snap[("semantic_search", "ok", False)] == 1
    assert snap[("semantic_search", "limited", False)] == 1


@pytest.mark.asyncio
async def test_window_limit_rejected_as_disabled(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(
        settings,
        "agent_tool_window_rate_limit",
        {"web_search": {"max": 1, "window_seconds": 3600}},
    )
    monkeypatch.setattr(guard_mod, "get_rate_limit_backend", lambda: "memory")
    _, user = await register_and_login(prefix="g2-w3-window")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is True
    assert outcome.steps[1].ok is False
    assert "窗口" in outcome.steps[1].summary
    assert outcome.steps[2].ok is True
    assert "tool_window_limit" in await _denied_reasons(outcome.run_id)
    assert agent_tool_window_rejected_snapshot() == {"web_search": 1}


@pytest.mark.asyncio
async def test_redis_window_failure_falls_back_memory(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(guard_mod, "get_rate_limit_backend", lambda: "redis")

    async def _boom(*args, **kwargs) -> bool:
        del args, kwargs
        raise RuntimeError("redis down")

    monkeypatch.setattr(guard_mod, "redis_sliding_allow", _boom)
    _, user = await register_and_login(prefix="g2-w3-redis")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert outcome.steps[0].ok is True
    assert rate_limit_backend_fallback_snapshot()["agent_tool"] == 1

"""G2 W3 · runtime 工具指标（ok/failed/limited/breaker_open）与 /metrics 导出测试。"""

from __future__ import annotations

import importlib
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core import retry as retry_mod
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import get_breaker, reset_all_breakers
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.guard import (
    ensure_agent_tool_breakers,
    reset_tool_window_limits,
    tool_breaker_name,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.web_search import WebSearchResult
from app.services.agent.types import ToolCallPlan
from app.services.observability.metrics_registry import (
    agent_tool_calls_snapshot,
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
async def test_tool_metrics_counted_for_ok_failed_limited_breaker(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", True)
    monkeypatch.setattr(
        settings,
        "agent_tool_max_calls_per_run_override",
        {"web_search": 1},
    )
    monkeypatch.setattr(
        settings,
        "agent_tool_breaker_overrides",
        {
            **settings.agent_tool_breaker_overrides,
            "semantic_search": {"failure_threshold": 2, "recovery_timeout": 15},
        },
    )
    retry_mod._breakers.pop(tool_breaker_name("semantic_search"), None)
    ensure_agent_tool_breakers()
    breaker = get_breaker(tool_breaker_name("semantic_search"))
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.allow_request is False

    _, user = await register_and_login(prefix="g2-w3-metrics")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(
                tool_name="get_chunk_excerpt",
                args={"chunk_id": str(uuid.uuid4())},
            ),
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="semantic_search", args={"query": "最近行业动态"}),
            None,
        ]
    )
    monkeypatch.setattr(web_search_module, "web_search", _web_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_get_chunk_excerpt",
        AsyncMock(
            return_value=SimpleNamespace(
                ok=False,
                summary="chunk not found",
                data=None,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )

    outcome = await _run(user_id=user_id, thread_id=thread_id, planner=planner)

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "get_chunk_excerpt",
        "web_search",
        "semantic_search",
    ]
    snap = agent_tool_calls_snapshot()
    assert snap[("web_search", "ok", True)] == 1
    assert snap[("get_chunk_excerpt", "failed", False)] == 1
    assert snap[("web_search", "limited", True)] == 1
    assert snap[("semantic_search", "breaker_open", False)] == 1


@pytest.mark.asyncio
async def test_metrics_exports_tool_and_planner_families(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "metrics_bearer_token", "test-metrics-token")
    client.headers["Authorization"] = "Bearer test-metrics-token"

    resp = await client.get("/metrics")

    assert resp.status_code == 200
    body = resp.text
    assert "# HELP ruige_agent_tool_calls_total" in body
    assert "# HELP ruige_agent_tool_latency_ms" in body
    assert "# HELP ruige_agent_tool_window_rejected_total" in body
    assert "# HELP ruige_agent_llm_planner_calls_total" in body
    assert "# HELP ruige_agent_llm_planner_tokens_total" in body

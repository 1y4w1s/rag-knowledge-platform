"""G2 W2 · runtime 工具级熔断接线测试。"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core import retry as retry_mod
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import get_breaker, reset_all_breakers
from app.models.audit_log import AuditLog
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.guard import (
    ensure_agent_tool_breakers,
    tool_breaker_name,
)
from app.services.agent.tools.scope import (
    FORBIDDEN_KB_SUMMARY,
    AgentToolScope,
)
from app.services.agent.tools.semantic_search import SemanticSearchToolResult
from app.services.agent.types import (
    ToolCallPlan,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import (
    WorkspaceKind,
    WorkspaceScope,
)

web_search_module = importlib.import_module("app.services.agent.tools.web_search")


@pytest.fixture(autouse=True)
def _disable_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """关闭指数退避，避免熔断闸门异常路径等待约 1s。"""
    monkeypatch.setattr(settings, "retry_max_attempts", 0)


@pytest.fixture(autouse=True)
def _isolate_breakers() -> None:
    ensure_agent_tool_breakers()
    reset_all_breakers()
    yield
    reset_all_breakers()


def _personal_workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)


async def _create_personal_thread(user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db, user_id=user_id, workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None, department_id=None,
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


def _open_web_search_breaker() -> None:
    breaker = get_breaker(tool_breaker_name("web_search"))
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.allow_request is False


def _semantic_ok() -> AsyncMock:
    return AsyncMock(return_value=SemanticSearchToolResult(ok=True, data=None, summary="ok"))


@pytest.mark.asyncio
async def test_web_search_open_does_not_block_semantic_search(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """web_search breaker OPEN → 该步失败但不早停，semantic_search 正常执行。"""
    _, user = await register_and_login(prefix="g2-w2-open")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner([
        ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
        ToolCallPlan(tool_name="semantic_search", args={"query": "最近行业动态"}),
        None,
    ])
    planner.replan_after_failure = AsyncMock()

    _open_web_search_breaker()
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

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

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is False
    assert outcome.steps[1].ok is True
    assert outcome.steps_used == 2
    assert outcome.tool_fallback_count == 0
    assert outcome.tool_replanned == 0
    assert planner.replan_after_failure.await_count == 0


@pytest.mark.asyncio
async def test_same_tool_again_is_frozen(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """冻结工具再次被 planner 选中 → 跳过，不触上游、不触发 replan。"""
    _, user = await register_and_login(prefix="g2-w2-frozen")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner([
        ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
        ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
        None,
    ])
    web_search_mock = AsyncMock()

    _open_web_search_breaker()
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(web_search_module, "web_search", web_search_mock)

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

    assert len(outcome.steps) == 1
    assert outcome.steps_used == 1
    assert outcome.steps[0].tool_name == "web_search"
    assert outcome.steps[0].ok is False
    assert web_search_mock.await_count == 0
    assert outcome.tool_replanned == 0


@pytest.mark.asyncio
async def test_breaker_open_substitution_allowed(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """breaker_open 失败步照常走等价替换，替换目标正常执行。"""
    _, user = await register_and_login(prefix="g2-w2-sub")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner([
        ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
        None,
    ])

    _open_web_search_breaker()
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        _semantic_ok(),
    )

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

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is False
    assert outcome.steps[1].ok is True
    assert outcome.tool_fallback_count == 1
    assert outcome.tool_replanned == 0


@pytest.mark.asyncio
async def test_breaker_open_no_replan(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """breaker_open 不触发 LLM 提示重规划。"""
    _, user = await register_and_login(prefix="g2-w2-replan")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner([
        ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
        None,
    ])
    planner.replan_after_failure = AsyncMock()

    _open_web_search_breaker()
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )

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

    assert planner.replan_after_failure.await_count == 0
    assert outcome.tool_replanned == 0
    assert outcome.steps_used == 1


@pytest.mark.asyncio
async def test_frozen_skip_cap_stops_run(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """planner 反复返回冻结工具达到 3 次 → 正常结束，不空转。"""
    _, user = await register_and_login(prefix="g2-w2-cap")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"})
            for _ in range(4)
        ]
        + [None]
    )

    _open_web_search_breaker()
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )

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

    assert outcome.steps_used == 1
    assert len(outcome.steps) == 1
    assert outcome.steps[0].ok is False
    assert planner.calls == 4
    assert outcome.capped is False
    assert outcome.timed_out is False


@pytest.mark.asyncio
async def test_sql_query_has_no_breaker_and_stays_fail_closed(
    register_and_login,
) -> None:
    """sql_query 不注册熔断器，返回 FORBIDDEN 且保留 tool_denied 审计。"""
    _, user = await register_and_login(prefix="g2-w2-sql")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner([
        ToolCallPlan(tool_name="sql_query", args={"sql": "select 1"}),
        None,
    ])

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="查询",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert tool_breaker_name("sql_query") not in ensure_agent_tool_breakers()
    assert tool_breaker_name("sql_query") not in retry_mod._breakers
    assert [s.tool_name for s in outcome.steps] == ["sql_query"]
    assert outcome.steps[0].ok is False
    assert outcome.steps[0].summary == FORBIDDEN_KB_SUMMARY
    assert outcome.tool_fallback_count == 0

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "agent.tool_denied",
                    AuditLog.resource_id == outcome.run_id,
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].details["tool"] == "sql_query"
    assert rows[0].details["reason"] == "forbidden_kb"


@pytest.mark.asyncio
async def test_metrics_and_health_list_tool_breakers(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """/metrics 与 /health 使用动态工具 breaker 名单，不再输出旧名。"""
    monkeypatch.setattr(settings, "metrics_bearer_token", "test-metrics-token")
    client.headers["Authorization"] = "Bearer test-metrics-token"
    monkeypatch.setattr(
        "app.api.health.check_database",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.api.health.probe_embed_readiness",
        AsyncMock(return_value={"provider": "mock", "ready": True, "reason": "ok"}),
    )

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert 'breaker="agent_tool:web_search"' in metrics_resp.text
    assert "_dispatch" not in metrics_resp.text

    health_resp = await client.get("/health")
    assert health_resp.status_code == 200
    health_body = health_resp.json()
    assert "agent_tool:web_search" in health_body["degradation"]["breakers"]
    assert all(
        "_dispatch" not in name
        for name in health_body["degradation"]["breakers"]
    )

    detailed_resp = await client.get("/health/detailed")
    assert detailed_resp.status_code == 200
    detailed_body = detailed_resp.json()
    assert "agent_tool:web_search" in detailed_body["breakers"]
    assert all("_dispatch" not in name for name in detailed_body["breakers"])

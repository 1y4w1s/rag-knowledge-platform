"""G2 W1：工具级熔断 / 限流 / token 估算纯函数与双后端 helper 测试。"""

from __future__ import annotations

import pytest

from app.core import retry as retry_mod
from app.core.config import settings
from app.core.retry import get_breaker, reset_all_breakers
from app.services.agent.tools import guard
from app.services.agent.tools.guard import (
    AGENT_TOOL_BREAKER_TOOL_NAMES,
    EXTERNAL_TOOL_NAMES,
    PlannerTokenEstimate,
    allow_tool_window,
    ensure_agent_tool_breakers,
    estimate_planner_tokens,
    estimate_tokens,
    reset_tool_window_limits,
    resolve_tool_run_limit,
    tool_breaker_name,
    tool_window_limit,
    tool_window_limit_key,
)
from app.services.agent.tools.registry import (
    ALL_AGENT_TOOL_NAMES,
    AgentToolName,
)
from app.services.observability.metrics_registry import (
    RATE_LIMIT_FALLBACK_MODULES,
    agent_tool_calls_counter_lines,
    agent_tool_calls_snapshot,
    agent_tool_window_rejected_counter_lines,
    agent_tool_window_rejected_snapshot,
    inc_agent_tool_call,
    inc_agent_tool_window_rejected,
    inc_rate_limit_backend_fallback,
    rate_limit_backend_fallback_counter_lines,
    rate_limit_backend_fallback_snapshot,
    reset_process_counters_for_tests,
)


@pytest.fixture(autouse=True)
def _isolate_state() -> None:
    reset_process_counters_for_tests()
    reset_all_breakers()
    reset_tool_window_limits()
    yield
    reset_process_counters_for_tests()
    reset_all_breakers()
    reset_tool_window_limits()


def test_tool_breaker_name() -> None:
    assert tool_breaker_name("semantic_search") == "agent_tool:semantic_search"
    assert tool_breaker_name("web_search") == "agent_tool:web_search"


def test_breaker_tool_names_exclude_sql_query() -> None:
    expected = ALL_AGENT_TOOL_NAMES - {AgentToolName.sql_query.value}
    assert AGENT_TOOL_BREAKER_TOOL_NAMES == expected
    assert AgentToolName.sql_query.value not in AGENT_TOOL_BREAKER_TOOL_NAMES
    assert len(AGENT_TOOL_BREAKER_TOOL_NAMES) == len(ALL_AGENT_TOOL_NAMES) - 1
    assert EXTERNAL_TOOL_NAMES == {AgentToolName.web_search.value}


def test_ensure_agent_tool_breakers_idempotent() -> None:
    first = ensure_agent_tool_breakers()
    expected = {tool_breaker_name(t) for t in AGENT_TOOL_BREAKER_TOOL_NAMES}
    assert first == expected
    assert all(name.startswith("agent_tool:") for name in first)

    breaker = get_breaker(tool_breaker_name("web_search"))
    breaker.record_failure()
    state_before = breaker.status()

    second = ensure_agent_tool_breakers()
    assert second == first
    assert get_breaker(tool_breaker_name("web_search")) is breaker
    assert get_breaker(tool_breaker_name("web_search")).status() == state_before


def test_breaker_override_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    retry_mod._breakers.pop(tool_breaker_name("web_search"), None)
    retry_mod._breakers.pop(tool_breaker_name("semantic_search"), None)
    ensure_agent_tool_breakers()

    web = get_breaker(tool_breaker_name("web_search"))
    sem = get_breaker(tool_breaker_name("semantic_search"))
    assert web.failure_threshold == 2
    assert web.recovery_timeout == 15
    assert sem.failure_threshold == settings.circuit_breaker_failure_threshold
    assert sem.recovery_timeout == settings.circuit_breaker_recovery_timeout

    monkeypatch.setattr(
        settings,
        "agent_tool_breaker_overrides",
        {
            **settings.agent_tool_breaker_overrides,
            "compare_chunks": {"failure_threshold": 3},
        },
    )
    retry_mod._breakers.pop(tool_breaker_name("compare_chunks"), None)
    ensure_agent_tool_breakers()
    compare = get_breaker(tool_breaker_name("compare_chunks"))
    assert compare.failure_threshold == 3
    assert compare.recovery_timeout == settings.circuit_breaker_recovery_timeout


def test_run_limit_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "agent_tool_max_calls_per_run_override",
        {"semantic_search": 4, "web_search": 0},
    )
    assert resolve_tool_run_limit("semantic_search") == 4
    assert resolve_tool_run_limit("web_search") is None
    assert resolve_tool_run_limit("get_chunk_excerpt") is None

    monkeypatch.setattr(settings, "agent_tool_max_calls_per_run_override", {})
    monkeypatch.setattr(settings, "agent_max_external_calls_per_conversation", 7)
    assert resolve_tool_run_limit("web_search") == 7

    monkeypatch.setattr(
        settings,
        "agent_tool_max_calls_per_run_override",
        {"web_search": -1},
    )
    assert resolve_tool_run_limit("web_search") is None


def test_tool_window_limit_config_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tool_window_limit("web_search") == (60, 3600)
    assert tool_window_limit("semantic_search") is None
    assert tool_window_limit_key("web_search") == "rl:agent_tool:web_search:global"

    monkeypatch.setattr(settings, "agent_tool_window_rate_limit_enabled", False)
    assert tool_window_limit("web_search") is None

    monkeypatch.setattr(settings, "agent_tool_window_rate_limit_enabled", True)
    monkeypatch.setattr(
        settings,
        "agent_tool_window_rate_limit",
        {"web_search": {"max": 0, "window_seconds": 3600}},
    )
    assert tool_window_limit("web_search") is None


@pytest.mark.asyncio
async def test_window_limit_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "agent_tool_window_rate_limit",
        {"web_search": {"max": 2, "window_seconds": 3600}},
    )
    monkeypatch.setattr(guard, "get_rate_limit_backend", lambda: "memory")
    reset_tool_window_limits()

    assert await allow_tool_window("web_search", now=100.0) is True
    assert await allow_tool_window("web_search", now=101.0) is True
    assert await allow_tool_window("web_search", now=102.0) is False
    assert await allow_tool_window("web_search", now=100.0 + 3601.0) is True
    assert agent_tool_window_rejected_snapshot() == {"web_search": 1}


@pytest.mark.asyncio
async def test_window_limit_redis_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guard, "get_rate_limit_backend", lambda: "redis")
    calls: list[dict[str, object]] = []

    async def deny(*args, **kwargs) -> bool:
        calls.append({"args": args, "kwargs": kwargs})
        return False

    monkeypatch.setattr(guard, "redis_sliding_allow", deny)
    assert await allow_tool_window("web_search", now=200.0) is False
    assert agent_tool_window_rejected_snapshot() == {"web_search": 1}
    assert calls[0]["args"][0] == "rl:agent_tool:web_search:global"

    async def allow(*args, **kwargs) -> bool:
        return True

    monkeypatch.setattr(guard, "redis_sliding_allow", allow)
    assert await allow_tool_window("web_search", now=201.0) is True
    assert agent_tool_window_rejected_snapshot() == {"web_search": 1}


@pytest.mark.asyncio
async def test_window_limit_redis_failure_falls_back_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard, "get_rate_limit_backend", lambda: "redis")

    async def boom(*args, **kwargs) -> bool:
        raise RuntimeError("redis down")

    monkeypatch.setattr(guard, "redis_sliding_allow", boom)
    reset_tool_window_limits()
    assert await allow_tool_window("web_search", now=300.0) is True
    assert rate_limit_backend_fallback_snapshot() == {"agent_tool": 1}


def test_estimate_tokens_pure() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0
    assert estimate_tokens("中文测试") == 4
    assert estimate_tokens("hello") == 2
    assert estimate_tokens("中abc") == 2


def test_estimate_planner_tokens_pure() -> None:
    empty = estimate_planner_tokens("", "")
    assert isinstance(empty, PlannerTokenEstimate)
    assert empty.prompt_tokens == 0
    assert empty.response_tokens == 0
    assert empty.total_tokens == 0

    est = estimate_planner_tokens("中文测试", "hello")
    assert est.prompt_tokens == 4
    assert est.response_tokens == 2
    assert est.total_tokens == 6


def test_metrics_registry_tool_calls() -> None:
    inc_agent_tool_call("web_search", "ok", external=True)
    inc_agent_tool_call("semantic_search", "failed")
    inc_agent_tool_call("semantic_search", "breaker_open")
    inc_agent_tool_call("web_search", "bogus")

    snap = agent_tool_calls_snapshot()
    assert snap[("web_search", "ok", True)] == 1
    assert snap[("semantic_search", "failed", False)] == 1
    assert snap[("semantic_search", "breaker_open", False)] == 1
    assert ("web_search", "bogus", False) not in snap

    lines = agent_tool_calls_counter_lines()
    assert lines[0] == (
        "# HELP ruige_agent_tool_calls_total "
        "Agent tool executions by tool and status"
    )
    assert lines[1] == "# TYPE ruige_agent_tool_calls_total counter"
    assert (
        'ruige_agent_tool_calls_total{tool="web_search",status="ok",'
        'external="true"} 1' in lines
    )
    assert (
        'ruige_agent_tool_calls_total{tool="semantic_search",'
        'status="breaker_open",external="false"} 1' in lines
    )


def test_metrics_registry_window_rejected_and_fallback() -> None:
    assert "agent_tool" in RATE_LIMIT_FALLBACK_MODULES
    inc_agent_tool_window_rejected("web_search")
    inc_rate_limit_backend_fallback("agent_tool")

    assert agent_tool_window_rejected_snapshot() == {"web_search": 1}
    lines = agent_tool_window_rejected_counter_lines()
    assert lines[0] == (
        "# HELP ruige_agent_tool_window_rejected_total "
        "Agent tool window rate-limit rejections"
    )
    assert lines[1] == "# TYPE ruige_agent_tool_window_rejected_total counter"
    assert 'ruige_agent_tool_window_rejected_total{tool="web_search"} 1' in lines

    fallback_lines = rate_limit_backend_fallback_counter_lines()
    assert (
        'ruige_rate_limit_backend_fallback_total{module="agent_tool"} 1'
        in fallback_lines
    )

    reset_process_counters_for_tests()
    assert agent_tool_window_rejected_snapshot() == {}
    assert agent_tool_calls_snapshot() == {}

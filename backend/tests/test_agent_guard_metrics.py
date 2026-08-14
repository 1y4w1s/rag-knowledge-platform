"""G2 W3 · planner 计数 / token 估算 / 工具延迟指标测试。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.core.config import settings
from app.core.retry import reset_all_breakers
from app.services.agent.planners import LLMPlanner, SafetyFrame
from app.services.agent.tools.guard import reset_tool_window_limits
from app.services.agent.types import ToolFailure, ToolFailureKind
from app.services.rag.chat_llm import ChatUsage
from app.services.observability.metrics_registry import (
    agent_llm_planner_calls_counter_lines,
    agent_llm_planner_calls_snapshot,
    agent_llm_planner_tokens_counter_lines,
    agent_llm_planner_tokens_snapshot,
    agent_llm_planner_usage_counter_lines,
    agent_llm_planner_usage_snapshot,
    agent_tool_latency_gauge_lines,
    agent_tool_latency_snapshot,
    inc_agent_llm_planner_call,
    inc_agent_llm_planner_usage,
    record_agent_tool_latency,
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


@pytest.fixture(autouse=True)
def _set_chat_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 路径用例固定主 provider key，避免无 key CI 下提前走 no_key fallback。"""
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-test")
    monkeypatch.setattr(settings, "tongyi_api_key", "")


def _make_planner() -> LLMPlanner:
    safety_frame = SafetyFrame("对比公司考勤制度和请假流程")
    return LLMPlanner(
        "对比公司考勤制度和请假流程",
        safety_frame=safety_frame,
        tool_specs=safety_frame.all_tool_specs(),
    )


async def _fake_complete_chat(messages) -> tuple[str, None]:
    del messages
    return (
        '[{"tool_name": "semantic_search", "args": {"query": "考勤制度"}}]',
        None,
    )


def test_metrics_registry_planner_calls_and_tokens() -> None:
    inc_agent_llm_planner_call("plan", "ok", prompt_tokens=120, response_tokens=45)
    inc_agent_llm_planner_call("replan", "failed", prompt_tokens=10)

    snap = agent_llm_planner_calls_snapshot()
    assert snap == {("plan", "ok"): 1, ("replan", "failed"): 1}
    tokens = agent_llm_planner_tokens_snapshot()
    assert tokens["prompt"] == 130
    assert tokens["response"] == 45

    lines = agent_llm_planner_calls_counter_lines()
    assert lines[0] == (
        "# HELP ruige_agent_llm_planner_calls_total "
        "LLM planner calls by stage and status"
    )
    assert lines[1] == "# TYPE ruige_agent_llm_planner_calls_total counter"
    assert len(lines) == 6  # 2 header + plan/replan x ok/failed
    assert (
        'ruige_agent_llm_planner_calls_total{stage="plan",status="ok"} 1'
        in lines
    )
    assert (
        'ruige_agent_llm_planner_calls_total{stage="replan",status="failed"} 1'
        in lines
    )

    token_lines = agent_llm_planner_tokens_counter_lines()
    assert len(token_lines) == 4  # 2 header + prompt/response
    assert 'ruige_agent_llm_planner_tokens_total{kind="prompt"} 130' in token_lines
    assert 'ruige_agent_llm_planner_tokens_total{kind="response"} 45' in token_lines


def test_metrics_registry_planner_invalid_status_ignored() -> None:
    inc_agent_llm_planner_call("plan", "bogus")
    inc_agent_llm_planner_call("bogus", "ok")
    assert agent_llm_planner_calls_snapshot() == {}
    assert agent_llm_planner_tokens_snapshot() == {}


def test_metrics_registry_tool_latency() -> None:
    for ms in (10.0, 20.0, 30.0, 40.0, 50.0):
        record_agent_tool_latency("web_search", ms)

    snap = agent_tool_latency_snapshot()
    st = snap["web_search"]
    assert st["count"] == 5
    assert st["p50"] == 30.0
    assert st["p95"] == 50.0
    assert st["p99"] == 50.0

    lines = agent_tool_latency_gauge_lines()
    assert lines[0] == (
        "# HELP ruige_agent_tool_latency_ms Agent tool latency percentiles (ms)"
    )
    assert lines[1] == "# TYPE ruige_agent_tool_latency_ms gauge"
    assert (
        'ruige_agent_tool_latency_ms{tool="web_search",quantile="p50"} 30.0'
        in lines
    )


@pytest.mark.asyncio
async def test_llm_planner_plan_ok_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _fake_complete_chat,
    )
    planner = _make_planner()

    result = await planner._call_llm_for_plan(
        "对比公司考勤制度和请假流程",
        context={},
    )

    assert result.ok is True
    snap = agent_llm_planner_calls_snapshot()
    assert snap.get(("plan", "ok")) == 1
    tokens = agent_llm_planner_tokens_snapshot()
    assert tokens["prompt"] > 0
    assert tokens["response"] > 0


@pytest.mark.asyncio
async def test_llm_planner_no_key_returns_fallback_without_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key：_call_llm_for_plan 直接返回 no_key，不调 LLM、不计 failed 指标。"""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    mock_llm = AsyncMock()
    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        mock_llm,
    )
    planner = _make_planner()

    result = await planner._call_llm_for_plan(
        "对比公司考勤制度和请假流程",
        context={},
    )

    assert result.ok is False
    assert result.error == "no_key"
    assert result.llm_raw is None
    mock_llm.assert_not_awaited()
    assert agent_llm_planner_calls_snapshot() == {}

    plan = await planner.next_tool_call(
        query="对比公司考勤制度和请假流程",
        step_index=1,
        steps_used=0,
        max_steps=5,
        prior_steps=(),
    )
    assert plan is not None
    assert plan.tool_name == "semantic_search"
    assert planner.fallback_reason == "no_key"
    assert planner.last_llm_raw is None
    mock_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_planner_failed_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(messages) -> str:
        del messages
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _boom,
    )
    planner = _make_planner()

    result = await planner._call_llm_for_plan(
        "对比公司考勤制度和请假流程",
        context={},
    )

    assert result.ok is False
    assert result.error == "llm_error"
    snap = agent_llm_planner_calls_snapshot()
    assert snap.get(("plan", "failed")) == 1
    assert snap.get(("plan", "ok")) is None


@pytest.mark.asyncio
async def test_llm_planner_replan_stage_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _fake_complete_chat,
    )
    planner = _make_planner()

    replanned = await planner.replan_after_failure(
        query="对比公司考勤制度和请假流程",
        step_index=1,
        steps_used=0,
        max_steps=5,
        prior_steps=(),
        failure=ToolFailure(
            kind=ToolFailureKind.infra,
            tool_name="semantic_search",
            summary="provider down",
        ),
    )

    assert replanned is not None
    snap = agent_llm_planner_calls_snapshot()
    assert snap.get(("replan", "ok")) == 1
    assert snap.get(("plan", "ok")) is None


def test_metrics_registry_planner_usage_fixed_rows() -> None:
    usage = ChatUsage(
        prompt_tokens=120,
        completion_tokens=45,
        prompt_cache_hit_tokens=30,
        prompt_cache_miss_tokens=90,
        provider="deepseek",
    )
    inc_agent_llm_planner_usage("plan", usage)
    inc_agent_llm_planner_usage("replan", usage)
    inc_agent_llm_planner_usage("bogus", usage)

    snap = agent_llm_planner_usage_snapshot()
    assert snap == {
        ("plan", "deepseek", "prompt"): 120,
        ("plan", "deepseek", "completion"): 45,
        ("plan", "deepseek", "cache_hit"): 30,
        ("plan", "deepseek", "cache_miss"): 90,
        ("replan", "deepseek", "prompt"): 120,
        ("replan", "deepseek", "completion"): 45,
        ("replan", "deepseek", "cache_hit"): 30,
        ("replan", "deepseek", "cache_miss"): 90,
    }

    lines = agent_llm_planner_usage_counter_lines()
    assert lines[0] == (
        "# HELP ruige_agent_llm_planner_usage_tokens_total "
        "LLM planner real usage tokens by stage, provider and kind"
    )
    assert lines[1] == "# TYPE ruige_agent_llm_planner_usage_tokens_total counter"
    assert len(lines) == 18  # 2 header + 2 stage x 2 provider x 4 kind
    assert (
        'ruige_agent_llm_planner_usage_tokens_total{stage="plan",'
        'provider="deepseek",kind="prompt"} 120'
        in lines
    )
    assert (
        'ruige_agent_llm_planner_usage_tokens_total{stage="replan",'
        'provider="tongyi",kind="prompt"} 0'
        in lines
    )


@pytest.mark.asyncio
async def test_llm_planner_plan_usage_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _with_usage(messages) -> tuple[str, ChatUsage]:
        del messages
        return (
            '[{"tool_name": "semantic_search", "args": {"query": "考勤制度"}}]',
            ChatUsage(
                prompt_tokens=60,
                completion_tokens=12,
                prompt_cache_hit_tokens=20,
                prompt_cache_miss_tokens=40,
                provider="deepseek",
            ),
        )

    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _with_usage,
    )
    planner = _make_planner()

    result = await planner._call_llm_for_plan(
        "对比公司考勤制度和请假流程",
        context={},
    )

    assert result.ok is True
    snap = agent_llm_planner_usage_snapshot()
    assert snap.get(("plan", "deepseek", "prompt")) == 60
    assert snap.get(("plan", "deepseek", "completion")) == 12
    assert snap.get(("plan", "deepseek", "cache_hit")) == 20
    assert snap.get(("plan", "deepseek", "cache_miss")) == 40
    # 真实 usage 存在时不再重复累计估算指标
    assert agent_llm_planner_tokens_snapshot() == {}
    calls = agent_llm_planner_calls_snapshot()
    assert calls.get(("plan", "ok")) == 1


@pytest.mark.asyncio
async def test_llm_planner_usage_missing_falls_back_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_usage(messages) -> tuple[str, None]:
        del messages
        return (
            '[{"tool_name": "semantic_search", "args": {"query": "考勤制度"}}]',
            None,
        )

    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _no_usage,
    )
    planner = _make_planner()

    result = await planner._call_llm_for_plan(
        "对比公司考勤制度和请假流程",
        context={},
    )

    assert result.ok is True
    assert agent_llm_planner_usage_snapshot() == {}
    tokens = agent_llm_planner_tokens_snapshot()
    assert tokens["prompt"] > 0
    assert tokens["response"] > 0


@pytest.mark.asyncio
async def test_llm_planner_replan_usage_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _with_usage(messages) -> tuple[str, ChatUsage]:
        del messages
        return (
            '[{"tool_name": "semantic_search", "args": {"query": "考勤制度"}}]',
            ChatUsage(
                prompt_tokens=80,
                completion_tokens=20,
                provider="tongyi",
            ),
        )

    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _with_usage,
    )
    planner = _make_planner()

    replanned = await planner.replan_after_failure(
        query="对比公司考勤制度和请假流程",
        step_index=1,
        steps_used=0,
        max_steps=5,
        prior_steps=(),
        failure=ToolFailure(
            kind=ToolFailureKind.infra,
            tool_name="semantic_search",
            summary="provider down",
        ),
    )

    assert replanned is not None
    snap = agent_llm_planner_usage_snapshot()
    assert snap.get(("replan", "tongyi", "prompt")) == 80
    assert snap.get(("replan", "tongyi", "completion")) == 20
    assert snap.get(("plan", "tongyi", "prompt")) is None
    calls = agent_llm_planner_calls_snapshot()
    assert calls.get(("replan", "ok")) == 1
    assert calls.get(("plan", "ok")) is None


def test_reset_clears_planner_and_latency() -> None:
    inc_agent_llm_planner_call("plan", "ok", prompt_tokens=10)
    inc_agent_llm_planner_usage(
        "plan",
        ChatUsage(prompt_tokens=5, completion_tokens=3, provider="deepseek"),
    )
    record_agent_tool_latency("web_search", 1.0)

    reset_process_counters_for_tests()

    assert agent_llm_planner_calls_snapshot() == {}
    assert agent_llm_planner_tokens_snapshot() == {}
    assert agent_llm_planner_usage_snapshot() == {}
    assert agent_tool_latency_snapshot() == {}

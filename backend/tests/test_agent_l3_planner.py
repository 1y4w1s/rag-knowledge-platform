"""L3-W2：NextActionPlanner parse/validate/factory 契约（纯单测 + mock LLM）。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.agent.planners import (
    LLMPlanner,
    LLMPlannerFactory,
    NextActionPlanner,
    SafetyFrame,
    ThoroughReadPlanner,
    parse_agent_decision,
)
from app.services.agent.state import init_agent_state
from app.services.agent.types import AgentActionKind, AgentDecision


def test_critic_and_l3_flags_default_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False


# ── parse_agent_decision ───────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,action",
    [
        (
            '{"action":"tool","tool_name":"semantic_search","args":{"query":"q"},'
            '"reason_code":"initial_retrieval"}',
            AgentActionKind.tool,
        ),
        (
            '{"action":"finish","reason_code":"evidence_sufficient"}',
            AgentActionKind.finish,
        ),
        (
            '{"action":"clarify","reason_code":"ambiguous_doc","user_message":"哪份？"}',
            AgentActionKind.clarify,
        ),
        (
            '{"action":"refuse","reason_code":"budget_exhausted"}',
            AgentActionKind.refuse,
        ),
    ],
)
def test_parse_agent_decision_legal_actions(raw: str, action: AgentActionKind) -> None:
    result = parse_agent_decision(raw)
    assert result.ok is True
    assert result.decision is not None
    assert result.decision.action == action
    if action == AgentActionKind.tool:
        assert result.decision.tool_name == "semantic_search"
        assert result.decision.args["query"] == "q"
    else:
        assert result.decision.tool_name is None


def test_parse_agent_decision_rejects_array_plan() -> None:
    raw = json.dumps(
        [{"tool_name": "semantic_search", "args": {"query": "q"}}]
    )
    result = parse_agent_decision(raw)
    assert result.ok is False
    assert result.error == "not_single_object"


def test_parse_agent_decision_invalid_action() -> None:
    result = parse_agent_decision('{"action":"dance","reason_code":"x"}')
    assert result.ok is False
    assert result.error == "invalid_action"


def test_parse_agent_decision_tool_missing_name_or_args() -> None:
    assert parse_agent_decision(
        '{"action":"tool","args":{"query":"q"},"reason_code":"x"}'
    ).error == "missing_tool_name"
    assert parse_agent_decision(
        '{"action":"tool","tool_name":"semantic_search","args":{},"reason_code":"x"}'
    ).error == "invalid_args"


def test_parse_agent_decision_ignores_extra_fields() -> None:
    from dataclasses import asdict

    raw = (
        '{"action":"finish","reason_code":"evidence_sufficient",'
        '"cot":"secret private thought","extra":123}'
    )
    result = parse_agent_decision(raw)
    assert result.ok is True
    assert result.decision is not None
    assert result.decision.action == AgentActionKind.finish
    blob = str(asdict(result.decision))
    assert "secret private thought" not in blob


def test_parse_agent_decision_fenced_json() -> None:
    raw = '```json\n{"action":"refuse","reason_code":"no_evidence"}\n```'
    result = parse_agent_decision(raw)
    assert result.ok is True
    assert result.decision is not None
    assert result.decision.action == AgentActionKind.refuse


# ── SafetyFrame.validate_decision ──────────────────────────────────


def test_validate_decision_rejects_write_and_unknown_tool() -> None:
    frame = SafetyFrame("对比 A 与 B 分别是多少？")
    state = init_agent_state(original_query="q", max_steps=5)

    write = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="delete_document",
        args={"document_id": "x", "kb_id": "y", "commit": False},
        reason_code="x",
    )
    v = frame.validate_decision(write, state)
    assert v.ok is False
    assert any("write tool" in x for x in (v.violations or []))

    unknown = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="not_a_real_tool",
        args={"query": "q"},
        reason_code="x",
    )
    v2 = frame.validate_decision(unknown, state)
    assert v2.ok is False
    assert any("not in registry" in x for x in (v2.violations or []))


def test_validate_decision_rejects_web_search_when_external_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "external_tools_enabled", False)
    frame = SafetyFrame("对比 A 与 B 分别是多少？")
    state = init_agent_state(original_query="q", max_steps=5)
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="web_search",
        args={"query": "q"},
        reason_code="x",
    )
    v = frame.validate_decision(decision, state)
    assert v.ok is False
    assert any("disabled by config" in x for x in (v.violations or []))


def test_validate_decision_rejects_tool_when_budget_exhausted() -> None:
    from dataclasses import replace

    frame = SafetyFrame("对比 A 与 B 分别是多少？")
    state = replace(
        init_agent_state(original_query="q", max_steps=2),
        steps_used=2,
    )
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": "q"},
        reason_code="x",
    )
    v = frame.validate_decision(decision, state)
    assert v.ok is False
    assert any("budget exhausted" in x for x in (v.violations or []))


def test_validate_decision_accepts_finish() -> None:
    frame = SafetyFrame("对比 A 与 B 分别是多少？")
    state = init_agent_state(original_query="q", max_steps=5)
    decision = AgentDecision(
        action=AgentActionKind.finish,
        reason_code="evidence_sufficient",
    )
    v = frame.validate_decision(decision, state)
    assert v.ok is True
    assert v.decision == decision


# ── Factory ────────────────────────────────────────────────────────


def test_factory_flag_off_returns_legacy_llm_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)
    monkeypatch.setattr(settings, "agent_llm_planner_enabled", True)
    planner = LLMPlannerFactory.create("对比 Docker 与 Compose 分别是什么？以及如何计算？")
    assert isinstance(planner, LLMPlanner)
    assert not isinstance(planner, NextActionPlanner)
    # 旧路径仍有游标概念
    assert hasattr(planner, "_cached_plan")
    assert hasattr(planner, "_plan_cursor")


def test_factory_flag_on_returns_next_action_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    planner = LLMPlannerFactory.create("对比 Docker 与 Compose 分别是什么？以及如何计算？")
    assert isinstance(planner, NextActionPlanner)
    assert not hasattr(planner, "_cached_plan")
    assert not hasattr(planner, "_plan_cursor")


def test_factory_flag_on_simple_still_thorough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    planner = LLMPlannerFactory.create("考勤制度？")
    assert isinstance(planner, ThoroughReadPlanner)


# ── decide_next（mock LLM）─────────────────────────────────────────


@pytest.mark.asyncio
async def test_decide_next_returns_single_decision_no_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    planner = LLMPlannerFactory.create("对比 A 与 B 分别是多少？")
    assert isinstance(planner, NextActionPlanner)

    payloads = [
        '{"action":"tool","tool_name":"semantic_search","args":{"query":"A 与 B"},'
        '"reason_code":"initial_retrieval"}',
        '{"action":"finish","reason_code":"evidence_sufficient"}',
    ]
    call_i = {"n": 0}

    async def _fake_complete(messages):  # noqa: ANN001
        del messages
        from app.services.rag.chat_llm import ChatUsage

        raw = payloads[call_i["n"]]
        call_i["n"] += 1
        return raw, ChatUsage()

    state = init_agent_state(original_query="对比 A 与 B 分别是多少？", max_steps=5)
    with (
        patch(
            "app.services.rag.chat_llm.has_available_chat_provider_key",
            return_value=True,
        ),
        patch(
            "app.services.rag.chat_llm.complete_chat_with_usage",
            new=AsyncMock(side_effect=_fake_complete),
        ),
    ):
        d1 = await planner.decide_next(state)
        d2 = await planner.decide_next(state)

    assert d1.action == AgentActionKind.tool
    assert d1.tool_name == "semantic_search"
    assert d2.action == AgentActionKind.finish
    assert call_i["n"] == 2  # 每步重新调 LLM，无缓存序列
    assert not hasattr(planner, "_cached_plan")
    assert not hasattr(planner, "_plan_cursor")


@pytest.mark.asyncio
async def test_decide_next_parse_failure_returns_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    planner = LLMPlannerFactory.create("对比 A 与 B 分别是多少？")
    assert isinstance(planner, NextActionPlanner)
    state = init_agent_state(original_query="对比 A 与 B 分别是多少？", max_steps=5)

    async def _bad(_messages):  # noqa: ANN001
        from app.services.rag.chat_llm import ChatUsage

        return "not-json", ChatUsage()

    with (
        patch(
            "app.services.rag.chat_llm.has_available_chat_provider_key",
            return_value=True,
        ),
        patch(
            "app.services.rag.chat_llm.complete_chat_with_usage",
            new=AsyncMock(side_effect=_bad),
        ),
    ):
        decision = await planner.decide_next(state)

    assert decision.action == AgentActionKind.refuse
    assert decision.reason_code == "parse_error"

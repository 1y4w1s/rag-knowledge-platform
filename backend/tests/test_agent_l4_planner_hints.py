"""L4-W5：Planner 消费 missing / conflicted（ObservationSummary · 默认关）。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.agent.fact_contracts import sync_evidence_fact_views
from app.services.agent.planner_fact_hints import (
    apply_observation_fact_hints,
    conflicted_fact_texts,
    missing_fact_texts,
)
from app.services.agent.planners import (
    LLMPlannerFactory,
    NextActionPlanner,
    _build_next_action_prompt,
)
from app.services.agent.state import init_agent_state, summarize_state_for_planner
from app.services.agent.types import (
    AgentActionKind,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
    ObservationSummary,
)


def test_l3_l4_and_critic_flags_remain_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_reflection_recovery_enabled is False
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False
    assert settings.agent_l4_tool_contrastive_selection_enabled is False


def _goals(*statuses: FactStatus) -> tuple[FactGoal, ...]:
    texts = ("找到 2025 住宿标准", "找到 2026 住宿标准", "确认适用规则")
    return tuple(
        FactGoal(
            id=f"F{i + 1}",
            text=texts[i],
            kind=FactKind.compare if i < 2 else FactKind.condition,
            status=statuses[i],
        )
        for i in range(len(statuses))
    )


def test_pure_conflicted_and_missing_texts() -> None:
    facts = _goals(FactStatus.covered, FactStatus.missing, FactStatus.conflicted)
    assert missing_fact_texts(facts) == ("找到 2026 住宿标准",)
    assert conflicted_fact_texts(facts) == ("确认适用规则",)


def test_hints_disabled_leaves_conflicted_empty() -> None:
    assert settings.agent_l4_stop_policy_enabled is False
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.missing, FactStatus.conflicted, FactStatus.covered)
        )
    )
    base = ObservationSummary(
        original_query="q",
        missing_facts=("legacy",),
        conflicted_facts=(),
    )
    out = apply_observation_fact_hints(base, evidence, enabled=False)
    assert out is base
    assert out.conflicted_facts == ()
    assert out.missing_facts == ("legacy",)


def test_hints_enabled_injects_missing_and_conflicted() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.partial, FactStatus.conflicted)
        )
    )
    base = ObservationSummary(original_query="差旅变化？")
    out = apply_observation_fact_hints(base, evidence, enabled=True)
    assert out.missing_facts == ("找到 2026 住宿标准",)
    assert out.conflicted_facts == ("确认适用规则",)


def test_summarize_default_has_empty_conflicted() -> None:
    """flag 默认关：summarize 本身不注入 conflicted（须经 apply_hints）。"""
    state = init_agent_state(
        original_query="q",
        max_steps=3,
        fact_goals=_goals(FactStatus.conflicted),
    )
    state = replace(
        state,
        evidence=sync_evidence_fact_views(
            replace(
                state.evidence,
                facts=tuple(
                    replace(g, status=FactStatus.conflicted)
                    for g in state.evidence.facts
                ),
            )
        ),
    )
    summary = summarize_state_for_planner(state)
    assert summary.conflicted_facts == ()
    hinted = apply_observation_fact_hints(summary, state.evidence, enabled=True)
    assert hinted.conflicted_facts == ("找到 2025 住宿标准",)


def test_prompt_includes_conflicted_hard_rule() -> None:
    summary = ObservationSummary(
        original_query="版本冲突？",
        missing_facts=("缺侧 A",),
        conflicted_facts=("两侧标准矛盾",),
    )
    prompt = _build_next_action_prompt("- semantic_search", summary)
    assert "conflicted_facts: 两侧标准矛盾" in prompt
    assert "missing_facts: 缺侧 A" in prompt
    assert "若 conflicted_facts 非空，不得 finish" in prompt


@pytest.mark.asyncio
async def test_planner_prompt_sees_conflicted_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    planner = LLMPlannerFactory.create("对比 A 与 B 分别是多少？")
    assert isinstance(planner, NextActionPlanner)

    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.conflicted, FactStatus.missing))
    )
    state = init_agent_state(original_query="对比 A 与 B 分别是多少？", max_steps=4)
    state = replace(state, evidence=evidence, steps_used=1)

    captured: dict[str, str] = {}

    async def _fake_llm(messages):  # noqa: ANN001
        from app.services.rag.chat_llm import ChatUsage

        captured["prompt"] = messages[0]["content"]
        return (
            '{"action":"refuse","reason_code":"facts_conflicted"}',
            ChatUsage(),
        )

    with (
        patch(
            "app.services.rag.chat_llm.has_available_chat_provider_key",
            return_value=True,
        ),
        patch(
            "app.services.rag.chat_llm.complete_chat_with_usage",
            new=AsyncMock(side_effect=_fake_llm),
        ),
    ):
        decision = await planner.decide_next(state)

    assert "conflicted_facts: 找到 2025 住宿标准" in captured["prompt"]
    assert "missing_facts: 找到 2026 住宿标准" in captured["prompt"]
    assert decision.action == AgentActionKind.refuse
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l3_next_action_enabled is False


def test_flag_gate_default_off_on_planner_path() -> None:
    """默认关：即便 evidence 有 conflicted，hints 不注入。"""
    assert settings.agent_l4_stop_policy_enabled is False
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.conflicted))
    )
    summary = ObservationSummary(original_query="q")
    out = apply_observation_fact_hints(summary, evidence)
    assert out.conflicted_facts == ()

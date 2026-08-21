"""L4-W6：Reflection/Recovery（FactGoal 感知恢复 · 默认关）。"""

from __future__ import annotations

from app.core.config import settings
from app.services.agent.fact_contracts import sync_evidence_fact_views
from app.services.agent.reflection_recovery import (
    RecoveryKind,
    ReflectionRecovery,
    evaluate_recovery,
    recovery_to_decision,
)
from app.services.agent.types import (
    AgentActionKind,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
    ToolFailure,
    ToolFailureKind,
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


def _goals(*statuses: FactStatus) -> tuple[FactGoal, ...]:
    texts = ("正式员工每月餐补 300 元", "一线城市住宿上限 500 元", "确认适用规则")
    return tuple(
        FactGoal(
            id=f"F{i + 1}",
            text=texts[i],
            kind=FactKind.lookup if i < 2 else FactKind.condition,
            status=statuses[i],
        )
        for i in range(len(statuses))
    )


def test_flag_off_returns_disabled() -> None:
    assert settings.agent_l4_reflection_recovery_enabled is False
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.covered))
    )
    signal = ReflectionRecovery().evaluate(
        evidence, reflection_signal="low_recall", steps_used=1, max_steps=5
    )
    assert signal.ok is False
    assert signal.source == "disabled"
    assert signal.error == "disabled"
    assert signal.suggested_query == ""
    assert recovery_to_decision(signal) is None


def test_b7_low_recall_rewrite(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.covered))
    )
    signal = ReflectionRecovery().evaluate(
        evidence,
        reflection_signal="low_recall",
        steps_used=1,
        max_steps=5,
        reflection_count=0,
    )
    assert signal.ok is True
    assert signal.kind == RecoveryKind.rewrite_retrieve
    assert signal.reason_code == "low_recall_rewrite"
    assert signal.target_fact_ids == ("F1",)
    assert "餐补" in signal.suggested_query
    decision = recovery_to_decision(signal)
    assert decision is not None
    assert decision.action == AgentActionKind.tool
    assert decision.tool_name == "semantic_search"
    assert decision.args["query"] == signal.suggested_query
    assert decision.reason_code == "low_recall_rewrite"
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", False)
    assert settings.agent_l4_reflection_recovery_enabled is False


def test_b8_tool_failure_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.covered))
    )
    failure = ToolFailure(
        kind=ToolFailureKind.infra,
        tool_name="semantic_search",
        summary="upstream timeout",
    )
    signal = ReflectionRecovery().evaluate(
        evidence, last_failure=failure, steps_used=1, max_steps=5
    )
    assert signal.kind == RecoveryKind.fallback_tool
    assert signal.reason_code == "tool_failure_fallback"
    assert signal.target_fact_ids == ("F1",)
    assert signal.suggested_tool == "semantic_search"
    decision = recovery_to_decision(signal)
    assert decision is not None
    assert decision.reason_code == "tool_failure_fallback"
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", False)


def test_fill_gap_without_low_recall(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.partial, FactStatus.missing)
        )
    )
    signal = evaluate_recovery(evidence, steps_used=1, max_steps=5)
    assert signal.kind == RecoveryKind.fill_gap
    assert signal.reason_code == "facts_fill_gap"
    assert signal.target_fact_ids == ("F2",)
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", False)


def test_conflict_resolve_requires_contradiction_flag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_contradiction_enabled", False)
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.conflicted, FactStatus.missing, FactStatus.covered)
        )
    )
    # contradiction 关：不走 resolve，落到 fill_gap（仍有 missing）
    signal = ReflectionRecovery().evaluate(evidence, steps_used=1, max_steps=5)
    assert signal.kind == RecoveryKind.fill_gap
    assert signal.reason_code == "facts_fill_gap"

    monkeypatch.setattr(settings, "agent_l4_contradiction_enabled", True)
    signal2 = ReflectionRecovery().evaluate(evidence, steps_used=1, max_steps=5)
    assert signal2.kind == RecoveryKind.resolve_conflict
    assert signal2.reason_code == "facts_conflicted_resolve"
    assert signal2.target_fact_ids == ("F1",)
    assert signal2.suggested_query.startswith("核实冲突：")

    monkeypatch.setattr(settings, "agent_l4_contradiction_enabled", False)
    monkeypatch.setattr(settings, "agent_l4_reflection_recovery_enabled", False)
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_reflection_recovery_enabled is False


def test_budget_exhausted_none() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.covered))
    )
    signal = evaluate_recovery(
        evidence,
        reflection_signal="low_recall",
        steps_used=5,
        max_steps=5,
    )
    assert signal.ok is True
    assert signal.kind == RecoveryKind.none
    assert signal.reason_code == "budget_exhausted"
    assert recovery_to_decision(signal) is None


def test_reflection_budget_exhausted_none() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing))
    )
    signal = evaluate_recovery(
        evidence,
        reflection_signal="low_recall",
        steps_used=1,
        max_steps=5,
        reflection_count=1,
        max_reflections=1,
    )
    assert signal.kind == RecoveryKind.none
    assert signal.reason_code == "reflection_budget_exhausted"


def test_complex_query_ignored() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.covered, FactStatus.covered))
    )
    signal = evaluate_recovery(
        evidence, reflection_signal="complex_query", steps_used=0, max_steps=5
    )
    assert signal.kind == RecoveryKind.none
    assert signal.reason_code == "no_recovery_needed"


def test_empty_failure_query_none() -> None:
    evidence = EvidenceState(facts=(), missing_facts=())
    failure = ToolFailure(
        kind=ToolFailureKind.infra, tool_name="semantic_search", summary="down"
    )
    signal = evaluate_recovery(
        evidence, last_failure=failure, steps_used=0, max_steps=5
    )
    assert signal.kind == RecoveryKind.none
    assert signal.reason_code == "empty_recovery_query"


def test_derived_missing_facts_without_goals() -> None:
    evidence = EvidenceState(facts=(), missing_facts=("派生缺证文本",))
    signal = evaluate_recovery(
        evidence, reflection_signal="low_recall", steps_used=0, max_steps=5
    )
    assert signal.kind == RecoveryKind.rewrite_retrieve
    assert signal.suggested_query == "派生缺证文本"
    assert signal.target_fact_ids == ()


def test_query_clipped_to_120() -> None:
    long_text = "核" * 200
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=(
                FactGoal(
                    id="F1",
                    text=long_text,
                    kind=FactKind.lookup,
                    status=FactStatus.missing,
                ),
            )
        )
    )
    signal = evaluate_recovery(evidence, steps_used=0, max_steps=5)
    assert signal.kind == RecoveryKind.fill_gap
    assert len(signal.suggested_query) == 120
    assert signal.suggested_query.endswith("…")

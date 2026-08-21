"""L4-W4：Stop policy（fact coverage → finish / partial / refuse · 默认关）。"""

from __future__ import annotations

from dataclasses import replace

from app.core.config import settings
from app.services.agent.fact_contracts import (
    fact_coverage_ratio,
    facts_ready_for_stop,
    sync_evidence_fact_views,
)
from app.services.agent.state import init_agent_state
from app.services.agent.stop_policy import StopKind, StopPolicy, evaluate_stop
from app.services.agent.types import EvidenceState, FactGoal, FactKind, FactStatus


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


def _goals(
    *statuses: FactStatus,
) -> tuple[FactGoal, ...]:
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


def test_all_covered_no_conflict_finishes() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.covered, FactStatus.covered, FactStatus.covered))
    )
    assert facts_ready_for_stop(evidence) is True
    signal = evaluate_stop(evidence, steps_used=2, max_steps=5)
    assert signal.ok is True
    assert signal.kind == StopKind.finish
    assert signal.reason_code == "facts_covered"
    assert signal.ready is True
    assert signal.coverage_ratio == 1.0
    assert signal.conflicted_ids == ()
    assert signal.missing_ids == ()


def test_missing_with_budget_is_partial_incomplete() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.missing, FactStatus.partial)
        )
    )
    assert facts_ready_for_stop(evidence) is False
    signal = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert signal.kind == StopKind.partial
    assert signal.reason_code == "facts_incomplete"
    assert signal.budget_exhausted is False
    assert signal.coverage_ratio == fact_coverage_ratio(evidence) == 1 / 3
    assert set(signal.missing_ids) == {"F2", "F3"}


def test_missing_budget_exhausted_zero_coverage_refuses() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.missing))
    )
    signal = evaluate_stop(evidence, steps_used=5, max_steps=5)
    assert signal.kind == StopKind.refuse
    assert signal.reason_code == "facts_missing_budget"
    assert signal.budget_exhausted is True
    assert signal.coverage_ratio == 0.0


def test_missing_budget_exhausted_partial_coverage() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.partial, FactStatus.missing)
        )
    )
    signal = evaluate_stop(evidence, steps_used=3, max_steps=3)
    assert signal.kind == StopKind.partial
    assert signal.reason_code == "facts_partial_budget"
    assert signal.coverage_ratio == 1 / 3
    assert signal.budget_exhausted is True


def test_conflicted_refuses_even_with_budget() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.covered, FactStatus.conflicted)
        )
    )
    assert facts_ready_for_stop(evidence) is False
    signal = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert signal.kind == StopKind.refuse
    assert signal.reason_code == "facts_conflicted"
    assert signal.conflicted_ids == ("F3",)
    assert signal.ready is False


def test_conflicted_budget_exhausted_reason() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.conflicted))
    )
    signal = evaluate_stop(evidence, steps_used=4, max_steps=4)
    assert signal.kind == StopKind.refuse
    assert signal.reason_code == "facts_conflicted_budget"


def test_optional_fact_ignored_for_stop() -> None:
    facts = (
        FactGoal(id="F1", text="必答", status=FactStatus.covered),
        FactGoal(
            id="F2",
            text="可选",
            required=False,
            status=FactStatus.missing,
        ),
    )
    evidence = sync_evidence_fact_views(EvidenceState(facts=facts))
    signal = evaluate_stop(evidence, steps_used=0, max_steps=3)
    assert signal.kind == StopKind.finish
    assert signal.reason_code == "facts_covered"


def test_no_required_facts_partial_then_refuse_at_budget() -> None:
    empty = EvidenceState()
    mid = evaluate_stop(empty, steps_used=0, max_steps=3)
    assert mid.kind == StopKind.partial
    assert mid.reason_code == "no_required_facts"
    end = evaluate_stop(empty, steps_used=3, max_steps=3)
    assert end.kind == StopKind.refuse
    assert end.reason_code == "no_required_facts_budget"


def test_stop_policy_disabled_by_default() -> None:
    assert settings.agent_l4_stop_policy_enabled is False
    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.covered, FactStatus.covered))
    )
    result = StopPolicy().evaluate(evidence, steps_used=1, max_steps=3)
    assert result.ok is False
    assert result.error == "disabled"
    assert result.source == "disabled"
    assert result.kind is None


def test_stop_policy_enabled_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    state = init_agent_state(
        original_query="差旅住宿变化？",
        max_steps=5,
        fact_goals=_goals(
            FactStatus.covered, FactStatus.covered, FactStatus.covered
        ),
    )
    # init seeds missing; force covered for finish path
    covered = sync_evidence_fact_views(
        replace(
            state.evidence,
            facts=tuple(
                replace(g, status=FactStatus.covered) for g in state.evidence.facts
            ),
        )
    )
    result = StopPolicy().evaluate(
        covered, steps_used=state.steps_used, max_steps=state.max_steps
    )
    assert result.ok is True
    assert result.source == "deterministic"
    assert result.kind == StopKind.finish
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)
    assert settings.agent_l4_stop_policy_enabled is False

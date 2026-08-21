"""L4-W1：FactGoal contracts + EvidenceState 可测语义（纯单测 · charter §18.4）。"""

from __future__ import annotations

from dataclasses import replace

from app.core.config import settings
from app.services.agent.state import (
    derive_fact_views,
    facts_ready_for_stop,
    init_agent_state,
    reduce_fact_observation,
    sync_evidence_fact_views,
    update_evidence_state,
)
from app.services.agent.types import (
    AgentStepRecord,
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactKind,
    FactObservation,
    FactStatus,
)


def test_l3_and_l4_flags_remain_false() -> None:
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
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False


def test_init_seeds_fact_goals_and_derived_views() -> None:
    state = init_agent_state(
        original_query="差旅住宿变化？",
        max_steps=5,
        required_facts=("找到 2025 住宿标准", "找到 2026 住宿标准"),
    )
    assert len(state.evidence.facts) == 2
    assert all(g.status == FactStatus.missing for g in state.evidence.facts)
    assert state.evidence.required_facts == ("找到 2025 住宿标准", "找到 2026 住宿标准")
    assert state.evidence.missing_facts == state.evidence.required_facts
    assert state.evidence.covered_facts == ()
    assert facts_ready_for_stop(state.evidence) is False


def test_init_accepts_explicit_fact_goals() -> None:
    goals = (
        FactGoal(id="F1", text="确认适用条件", kind=FactKind.condition),
        FactGoal(
            id="F2",
            text="可选备注",
            kind=FactKind.verify,
            required=False,
            status=FactStatus.missing,
        ),
    )
    state = init_agent_state(original_query="q", max_steps=3, fact_goals=goals)
    assert state.evidence.required_facts == ("确认适用条件",)
    assert state.evidence.missing_facts == ("确认适用条件",)
    assert "可选备注" not in state.evidence.required_facts


def test_derive_fact_views_scheme_a() -> None:
    facts = (
        FactGoal(id="F1", text="A", status=FactStatus.covered),
        FactGoal(id="F2", text="B", status=FactStatus.partial),
        FactGoal(id="F3", text="C", status=FactStatus.missing),
        FactGoal(id="F4", text="D", status=FactStatus.conflicted),
        FactGoal(id="F5", text="E", required=False, status=FactStatus.covered),
    )
    required, covered, missing = derive_fact_views(facts)
    assert required == ("A", "B", "C", "D")
    assert covered == ("A",)
    assert missing == ("B", "C")  # conflicted 不进 missing / covered


def test_charter_18_4_missing_partial_covered_conflicted_cycle() -> None:
    """charter §18.4：F1/F2/F3 经四次 observation 走完状态机。"""
    goals = (
        FactGoal(id="F1", text="F1", kind=FactKind.lookup),
        FactGoal(id="F2", text="F2", kind=FactKind.compare),
        FactGoal(id="F3", text="F3", kind=FactKind.verify),
    )
    evidence = sync_evidence_fact_views(EvidenceState(facts=goals))
    assert evidence.covered_facts == ()
    assert evidence.missing_facts == ("F1", "F2", "F3")
    assert facts_ready_for_stop(evidence) is False

    # Observation #1 supports F1 → covered=[F1], missing=[F2,F3]
    evidence = reduce_fact_observation(
        evidence,
        FactObservation(relations=(("F1", EvidenceRelation.supports),)),
    )
    assert _status_map(evidence) == {
        "F1": FactStatus.covered,
        "F2": FactStatus.missing,
        "F3": FactStatus.missing,
    }
    assert evidence.covered_facts == ("F1",)
    assert evidence.missing_facts == ("F2", "F3")

    # Observation #2 partially supports F2 → F2=partial, missing 仍含 F2
    evidence = reduce_fact_observation(
        evidence,
        FactObservation(relations=(("F2", EvidenceRelation.partial),)),
    )
    assert _status_map(evidence)["F2"] == FactStatus.partial
    assert "F2" in evidence.missing_facts
    assert "F2" not in evidence.covered_facts
    assert facts_ready_for_stop(evidence) is False

    # Observation #3 contradicts F1 → F1=conflicted, sufficient=false
    evidence = reduce_fact_observation(
        replace(evidence, sufficient=True),
        FactObservation(relations=(("F1", EvidenceRelation.contradicts),)),
    )
    assert _status_map(evidence)["F1"] == FactStatus.conflicted
    assert evidence.sufficient is False
    assert "F1" not in evidence.covered_facts
    assert "F1" not in evidence.missing_facts
    assert facts_ready_for_stop(evidence) is False

    # Observation #4 resolves F1 + supports F2/F3 → all covered, conflicts cleared
    evidence = reduce_fact_observation(
        evidence,
        FactObservation(
            relations=(
                ("F1", EvidenceRelation.resolves),
                ("F2", EvidenceRelation.supports),
                ("F3", EvidenceRelation.supports),
            )
        ),
    )
    assert _status_map(evidence) == {
        "F1": FactStatus.covered,
        "F2": FactStatus.covered,
        "F3": FactStatus.covered,
    }
    assert evidence.covered_facts == ("F1", "F2", "F3")
    assert evidence.missing_facts == ()
    assert facts_ready_for_stop(evidence) is True


def test_supports_does_not_clear_conflict_without_resolve() -> None:
    goals = (FactGoal(id="F1", text="F1", status=FactStatus.conflicted),)
    evidence = sync_evidence_fact_views(EvidenceState(facts=goals, sufficient=True))
    assert evidence.sufficient is False
    evidence = reduce_fact_observation(
        evidence,
        FactObservation(relations=(("F1", EvidenceRelation.supports),)),
    )
    assert _status_map(evidence)["F1"] == FactStatus.conflicted
    assert facts_ready_for_stop(evidence) is False


def test_update_evidence_state_preserves_fact_goals() -> None:
    state = init_agent_state(
        original_query="q",
        max_steps=3,
        required_facts=("用途",),
    )
    evidence = reduce_fact_observation(
        state.evidence,
        FactObservation(relations=(("F1", EvidenceRelation.supports),)),
    )
    record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={},
        ok=False,
        summary="失败",
        latency_ms=1,
        data=None,
    )
    updated = update_evidence_state(evidence, record)
    assert len(updated.facts) == 1
    assert updated.facts[0].status == FactStatus.covered
    assert updated.covered_facts == ("用途",)
    assert updated.sufficient is False


def _status_map(evidence: EvidenceState) -> dict[str, FactStatus]:
    return {g.id: g.status for g in evidence.facts}

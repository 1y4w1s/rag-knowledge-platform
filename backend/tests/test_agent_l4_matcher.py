"""L4-W3：Evidence Matcher / coverage（fixture + lexical · 默认关）。"""

from __future__ import annotations

from app.core.config import settings
from app.services.agent.fact_contracts import (
    fact_coverage_ratio,
    facts_ready_for_stop,
    sync_evidence_fact_views,
)
from app.services.agent.matcher import (
    EvidenceMatcher,
    EvidenceSnippet,
    apply_and_score,
    apply_evidence_match,
    deterministic_match,
    match_from_fixture,
)
from app.services.agent.state import init_agent_state
from app.services.agent.types import (
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
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


def _goals() -> tuple[FactGoal, ...]:
    return (
        FactGoal(id="F1", text="找到 2025 住宿标准", kind=FactKind.compare),
        FactGoal(id="F2", text="找到 2026 住宿标准", kind=FactKind.compare),
        FactGoal(id="F3", text="确认台湾办公室员工的适用规则", kind=FactKind.condition),
    )


def test_fixture_match_updates_status_and_scheme_a() -> None:
    evidence = sync_evidence_fact_views(EvidenceState(facts=_goals()))
    match = match_from_fixture(
        evidence.facts,
        {
            "E1": {"supports": ["F1"], "text": "2025 年住宿标准为 500 元"},
            "E2": {"partials": ["F2"], "text": "2026 差旅制度提及住宿"},
        },
    )
    assert match.ok is True
    assert match.source == "fixture"
    updated, scored = apply_and_score(evidence, match)
    assert _status(updated) == {
        "F1": FactStatus.covered,
        "F2": FactStatus.partial,
        "F3": FactStatus.missing,
    }
    assert updated.covered_facts == ("找到 2025 住宿标准",)
    assert "找到 2026 住宿标准" in updated.missing_facts
    assert "确认台湾办公室员工的适用规则" in updated.missing_facts
    assert scored.coverage_ratio == fact_coverage_ratio(updated) == 1 / 3
    assert len(updated.evidence_items) == 2
    assert facts_ready_for_stop(updated) is False


def test_fixture_contradict_then_resolve_cycle() -> None:
    evidence = sync_evidence_fact_views(EvidenceState(facts=_goals()))
    evidence, _ = apply_and_score(
        evidence,
        match_from_fixture(evidence.facts, {"E1": {"supports": ["F1", "F2", "F3"]}}),
    )
    assert fact_coverage_ratio(evidence) == 1.0
    assert facts_ready_for_stop(evidence) is True

    evidence, _ = apply_and_score(
        evidence,
        match_from_fixture(evidence.facts, {"E2": {"contradicts": ["F3"]}}),
    )
    assert _status(evidence)["F3"] == FactStatus.conflicted
    assert evidence.sufficient is False
    assert facts_ready_for_stop(evidence) is False
    assert "确认台湾办公室员工的适用规则" not in evidence.covered_facts

    evidence, scored = apply_and_score(
        evidence,
        match_from_fixture(evidence.facts, {"E3": {"resolves": ["F3"]}}),
    )
    assert _status(evidence)["F3"] == FactStatus.covered
    assert scored.coverage_ratio == 1.0
    assert facts_ready_for_stop(evidence) is True


def test_deterministic_lexical_supports_and_partial() -> None:
    facts = _goals()
    snippets = (
        EvidenceSnippet(
            evidence_id="E1",
            text="根据制度，2025 住宿标准为每人每晚 500 元。",
        ),
        EvidenceSnippet(
            evidence_id="E2",
            text="文件提到 2026 住宿，细节待补充。",
        ),
    )
    match = deterministic_match(facts, snippets)
    assert match.ok is True
    assert match.source == "deterministic"
    rels = dict(match.observation.relations)
    assert rels.get("F1") == EvidenceRelation.supports
    assert rels.get("F2") in (EvidenceRelation.supports, EvidenceRelation.partial)


def test_deterministic_contradict_on_negation() -> None:
    goals = (
        FactGoal(id="F3", text="确认台湾办公室员工的适用规则", kind=FactKind.condition),
    )
    match = deterministic_match(
        goals,
        (
            EvidenceSnippet(
                evidence_id="E-neg",
                text="台湾办公室员工不适用境内差旅档位适用规则。",
            ),
        ),
    )
    assert match.ok is True
    assert dict(match.observation.relations)["F3"] == EvidenceRelation.contradicts


def test_matcher_disabled_by_default() -> None:
    assert settings.agent_l4_evidence_matcher_enabled is False
    result = EvidenceMatcher().match(_goals(), fixture={"E1": {"supports": ["F1"]}})
    assert result.ok is False
    assert result.error == "disabled"
    assert result.source == "disabled"


def test_matcher_enabled_fixture_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    state = init_agent_state(
        original_query="差旅住宿变化？",
        max_steps=5,
        fact_goals=_goals(),
    )
    updated, result = EvidenceMatcher().match_and_apply(
        state.evidence,
        fixture={"E1": {"supports": ["F1", "F2"], "partials": []}},
    )
    assert result.ok is True
    assert result.source == "fixture"
    assert _status(updated)["F1"] == FactStatus.covered
    assert _status(updated)["F2"] == FactStatus.covered
    assert result.coverage_ratio == 2 / 3
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", False)
    assert settings.agent_l4_evidence_matcher_enabled is False


def test_apply_skips_failed_match() -> None:
    evidence = sync_evidence_fact_views(EvidenceState(facts=_goals()))
    before = evidence
    after = apply_evidence_match(
        evidence,
        match_from_fixture((), {"E1": {"supports": ["F1"]}}),
    )
    assert after is before or after.facts == before.facts
    assert after.covered_facts == ()


def test_conflict_priority_over_support() -> None:
    facts = (FactGoal(id="F1", text="确认适用"),)
    match = match_from_fixture(
        facts,
        {
            "E1": {"supports": ["F1"]},
            "E2": {"contradicts": ["F1"]},
        },
    )
    assert dict(match.observation.relations)["F1"] == EvidenceRelation.contradicts


def _status(evidence: EvidenceState) -> dict[str, FactStatus]:
    return {g.id: g.status for g in evidence.facts}

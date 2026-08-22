"""L4 MEMORY utilization evaluator — deterministic contract tests (P0)."""

from __future__ import annotations

import copy

import pytest

from app.eval.memory_capability.contract import (
    L4_SEMANTIC_UTILIZATION_CONTRACT,
    L5_COUNTERFACTUAL_CONTRACT,
    LEGACY_MEMORY4_SCORE,
    MEMORY_MEASUREMENT_LEVELS,
)
from app.eval.memory_capability.evaluator import (
    all_measurement_levels,
    evaluate_counterfactual,
    evaluate_empty_memory_behavior,
    evaluate_trajectory,
)
from app.eval.memory_capability.fixtures import (
    ALL_COUNTERFACTUAL_FIXTURES,
    ALL_TRAJECTORY_FIXTURES,
    FIXTURE_CONTRADICTED,
    FIXTURE_EMPTY_MEMORY,
    FIXTURE_EXPOSED_IGNORED,
    FIXTURE_FULL_UTILIZATION,
    FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL,
    FIXTURE_KEYWORD_OVERLAP_ONLY,
    FIXTURE_LOADED_NOT_EXPOSED,
    FIXTURE_NO_INCREMENTAL_BENEFIT,
    FIXTURE_SEEDED_NOT_LOADED,
)
from app.eval.memory_capability.golden_audit import (
    golden_memory4_audits,
    legacy_memory4_summary,
)
from app.eval.memory_capability.metrics import aggregate_metrics
from app.eval.memory_capability.proposition import (
    analyze_utilization,
    extract_propositions,
    has_keyword_overlap_only,
    proposition_semantically_satisfied,
)
from app.eval.memory_capability.runtime_mapping import runtime_mapping_audit
from app.eval.memory_capability.schema import MemorySeed, PropositionKind


def test_five_independent_measurement_levels_defined() -> None:
    assert len(MEMORY_MEASUREMENT_LEVELS) == 5
    assert list(all_measurement_levels()) == [
        "L1_SEEDED",
        "L2_LOADED",
        "L3_EXPOSED",
        "L4_UTILIZED",
        "L5_TASK_BENEFIT",
    ]


def test_l1_pass_does_not_imply_l2() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_SEEDED_NOT_LOADED))
    l1 = result.level_map()["L1_SEEDED"]
    l2 = result.level_map()["L2_LOADED"]
    assert l1.passed is True
    assert l2.passed is False


def test_l2_pass_does_not_imply_l3() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_LOADED_NOT_EXPOSED))
    l2 = result.level_map()["L2_LOADED"]
    l3 = result.level_map()["L3_EXPOSED"]
    assert l2.passed is True
    assert l3.passed is False


def test_l3_pass_does_not_imply_l4() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_EXPOSED_IGNORED))
    l3 = result.level_map()["L3_EXPOSED"]
    l4 = result.level_map()["L4_UTILIZED"]
    assert l3.passed is True
    assert l4.passed is False


def test_fixture_full_utilization_all_levels_except_l5() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_FULL_UTILIZATION))
    assert result.level_map()["L1_SEEDED"].passed is True
    assert result.level_map()["L2_LOADED"].passed is True
    assert result.level_map()["L3_EXPOSED"].passed is True
    assert result.level_map()["L4_UTILIZED"].passed is True
    assert result.level_map()["L5_TASK_BENEFIT"].attempted is False


def test_true_semantic_utilization_english() -> None:
    props = extract_propositions(
        (MemorySeed("lang", "preference", {"language": "en"}),)
    )
    assert props[0].kind == PropositionKind.language_preference
    assert proposition_semantically_satisfied(
        props[0], "The user's preferred language for retrieval is English."
    )


def test_false_utilization_keyword_overlap_only() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_KEYWORD_OVERLAP_ONLY))
    assert result.level_map()["L4_UTILIZED"].passed is False
    assert result.false_utilization is True
    assert result.utilization is not None
    assert result.utilization.keyword_overlap_only is True


def test_contradiction_detected() -> None:
    result = evaluate_trajectory(copy.deepcopy(FIXTURE_CONTRADICTED))
    assert result.level_map()["L4_UTILIZED"].passed is False
    assert result.utilization is not None
    assert result.utilization.contradicted is True


def test_empty_memory_correct_behavior() -> None:
    traj = copy.deepcopy(FIXTURE_EMPTY_MEMORY)
    result = evaluate_trajectory(traj)
    assert result.level_map()["L1_SEEDED"].passed is True
    assert result.level_map()["L2_LOADED"].passed is True
    assert result.level_map()["L3_EXPOSED"].passed is True
    assert result.level_map()["L4_UTILIZED"].eligible is False
    empty_check = evaluate_empty_memory_behavior(traj)
    assert empty_check.passed is True


def test_counterfactual_task_benefit_pass() -> None:
    result = evaluate_counterfactual(copy.deepcopy(FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL))
    l5 = result.level_map()["L5_TASK_BENEFIT"]
    assert l5.attempted is True
    assert l5.passed is True


def test_counterfactual_no_incremental_benefit_fails_l5() -> None:
    result = evaluate_counterfactual(copy.deepcopy(FIXTURE_NO_INCREMENTAL_BENEFIT))
    l5 = result.level_map()["L5_TASK_BENEFIT"]
    assert l5.attempted is True
    assert l5.passed is False
    assert "no incremental benefit" in l5.reason


def test_l4_semantic_contract_rejects_substring_only() -> None:
    not_accepted = L4_SEMANTIC_UTILIZATION_CONTRACT["not_accepted"]
    assert "substring_presence_only" in not_accepted
    assert "keyword_overlap_without_semantic_binding" in not_accepted


def test_l5_counterfactual_contract_documented() -> None:
    assert "with_memory.task_contract_passed" in L5_COUNTERFACTUAL_CONTRACT["task_benefit_true_when"]


def test_legacy_memory4_invalid_for_utilization_unchanged() -> None:
    summary = legacy_memory4_summary()
    assert summary["pass_count"] == 2
    assert summary["total"] == 4
    assert summary["capability_validity"] == "INVALID_FOR_UTILIZATION_CAPABILITY"
    assert summary["capability_score"] == "NOT_YET_VALID"
    assert summary["golden_json_mutated"] is False


def test_golden_memory4_audit_four_cases() -> None:
    audits = golden_memory4_audits()
    assert len(audits) == 4
    ids = {a.case_id for a in audits}
    assert ids == {"GA-9", "GA-10", "GA-11", "GA-12"}
    seeded = [a for a in audits if a.l4_applicable]
    empty = [a for a in audits if not a.l4_applicable]
    assert len(seeded) == 2
    assert len(empty) == 2


def test_runtime_mapping_documents_l3_observability_gap() -> None:
    audit = runtime_mapping_audit()
    assert audit["l3_observability_gap"]["gap_id"] == "L3_OBSERVABILITY_GAP"
    assert audit["l3_observability_gap"].get("status") == "CONFIRMED"
    assert audit["product_code_modified"] is False
    stages = [stage["stage"] for stage in audit["pipeline"]]
    assert "L3_EXPOSE_BOUNDARY" in stages
    assert "L2_LOAD" in stages
    assert len(audit["pipeline"]) >= 4


def test_denominator_integrity_unloaded_excludes_l3_l4() -> None:
    evaluations = [
        evaluate_trajectory(copy.deepcopy(FIXTURE_SEEDED_NOT_LOADED)),
        evaluate_trajectory(copy.deepcopy(FIXTURE_LOADED_NOT_EXPOSED)),
        evaluate_trajectory(copy.deepcopy(FIXTURE_FULL_UTILIZATION)),
    ]
    metrics = aggregate_metrics(evaluations).metric_map()

    load = metrics["load_success_rate"]
    assert load.eligible == 3
    assert load.attempted == 3
    assert load.passed == 2

    exposure = metrics["exposure_success_rate"]
    assert exposure.attempted == 3
    assert exposure.passed == 1

    utilization = metrics["semantic_utilization_rate"]
    assert utilization.eligible == 3
    assert utilization.attempted == 1
    assert utilization.passed == 1


def test_false_utilization_rate_denominator() -> None:
    evaluations = [
        evaluate_trajectory(copy.deepcopy(FIXTURE_KEYWORD_OVERLAP_ONLY)),
        evaluate_trajectory(copy.deepcopy(FIXTURE_FULL_UTILIZATION)),
    ]
    metrics = aggregate_metrics(evaluations).metric_map()
    false_rate = metrics["false_utilization_rate"]
    assert false_rate.eligible == 2
    assert false_rate.passed == 1


def test_at_least_eight_fixtures() -> None:
    assert len(ALL_TRAJECTORY_FIXTURES) >= 8
    assert len(ALL_COUNTERFACTUAL_FIXTURES) >= 2


@pytest.mark.parametrize("fixture", ALL_TRAJECTORY_FIXTURES, ids=lambda f: f.case_id)
def test_all_fixtures_evaluate_without_error(fixture) -> None:
    result = evaluate_trajectory(copy.deepcopy(fixture))
    assert result.case_id == fixture.case_id
    assert len(result.levels) == 5


def test_zh_tw_semantic_requires_traditional_signal() -> None:
    prop = extract_propositions(
        (MemorySeed("lang", "preference", {"language": "zh-TW"}),)
    )[0]
    assert proposition_semantically_satisfied(
        prop, "User prefers Traditional Chinese (繁體中文) for retrieval."
    )
    assert not proposition_semantically_satisfied(
        prop, "The token zh-TW appears but answer is in English."
    )
    assert has_keyword_overlap_only(prop, "The token zh-TW appears but answer is in English.")


def test_analyze_utilization_structured_propositions() -> None:
    analysis = analyze_utilization(
        (MemorySeed("lang", "preference", {"language": "en"}),),
        "Preferred language is English for this user.",
    )
    assert analysis.semantic_utilized is True
    assert analysis.contradicted is False


def test_legacy_score_matches_contract_constant() -> None:
    assert LEGACY_MEMORY4_SCORE["capability_score"] == "NOT_YET_VALID"

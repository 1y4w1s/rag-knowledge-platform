"""W9 P2-R1 frozen 12-case offline product-boundary measurement."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from tests.w9_critic_p2_r1_harness import (
    STAGES,
    execute_frozen_case,
    load_frozen_suite,
    score_observation,
)


FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
ARTIFACT_PATH = FIXTURES / "w9-critic-p2-r1-offline-product.json"
CORRECTION_PATH = FIXTURES / "w9-critic-p2-r1-independent-review.json"
HISTORICAL_P2_PATH = FIXTURES / "w9-critic-p2-offline-product.json"


@pytest.mark.asyncio
async def test_p2_r1_live_measurement_reaches_protocol_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    frozen_results = {item["case_id"]: item for item in artifact["case_results"]}
    results = []
    for case in suite.cases:
        case_id = str(case["case_id"])
        observed = await execute_frozen_case(
            monkeypatch, case, suite.reports[case_id]
        )
        scored = score_observation(
            observed, suite.oracle[case_id], suite.reports[case_id]
        )
        for key, value in scored.items():
            if key != "stage_results" and case_id != "C12-out-of-scope-provenance":
                assert frozen_results[case_id][key] == value
        results.append(scored)
        if not scored["pass"]:
            break

    assert len(results) == 12
    assert all(item["pass"] for item in results[:11])
    assert results[-1]["case_id"] == "C12-out-of-scope-provenance"
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    assert correction["state"] == "BLOCKED"
    assert correction["classification"] == "MEASUREMENT_PROTOCOL_MISMATCH"
    assert correction["product_control_plane_failure_proven"] is False


@pytest.mark.asyncio
async def test_c12_probe_exposes_invalid_path_and_safe_scorer_false_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C12-out-of-scope-provenance"
    )
    observed = await execute_frozen_case(
        monkeypatch, case, suite.reports["C12-out-of-scope-provenance"]
    )
    scored = score_observation(
        observed,
        suite.oracle["C12-out-of-scope-provenance"],
        suite.reports["C12-out-of-scope-provenance"],
    )

    initial_scope = set(observed["critic_calls"][0]["kb_ids"])
    post_recovery_scope = set(observed["critic_calls"][-1]["kb_ids"])
    assert initial_scope - {observed["allowed_kb_id"]}
    assert observed["allowed_kb_id"] in post_recovery_scope
    assert initial_scope.issubset(post_recovery_scope)
    citation_scope = {str(item["kb_id"]) for item in observed["citations"]}
    assert citation_scope == initial_scope
    assert scored["first_failed_stage"] == STAGES[6]
    assert scored["safe_outcome"] is True


def test_frozen_inputs_and_historical_p2_are_unchanged() -> None:
    suite = load_frozen_suite()
    assert Counter(str(item["expected_action"]) for item in suite.oracle.values()) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }
    historical = json.loads(HISTORICAL_P2_PATH.read_text(encoding="utf-8"))
    c11 = next(
        item
        for item in historical["case_results"]
        if item["case_id"] == "C11-citation-format-only-defect"
    )
    assert historical["state"] == "PARTIAL"
    assert c11["trajectory_result"] == {
        "status": "skipped_unavailable",
        "attempt_count": 0,
    }


def test_independent_review_supersedes_provisional_product_verdict() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    assert artifact["state"] == "PARTIAL"
    assert correction["supersedes_for_final_verdict"] == ARTIFACT_PATH.name
    assert correction["state"] == "BLOCKED"
    assert correction["measurement_validity"] == "BLOCKED"
    assert correction["frozen_case_count"] == correction["executed_case_count"] == 12
    assert correction["product_path_valid_case_count"] == 11
    assert correction["invalid_case_count"] == 1
    assert correction["first_product_failure"] is None
    assert correction["product_control_plane_failure_proven"] is False
    assert correction["external_model_execution"] is False
    assert correction["runtime_rollout"] is False
    assert correction["product_runtime_diff"] == 0
    metrics = correction["metrics"]
    assert metrics["product_case_pass_rate"] == {
        "numerator": 11,
        "denominator": 11,
        "rate": 1.0,
        "excluded_invalid_cases": 1,
    }
    for name in (
        "action_mapping_accuracy",
        "orchestration_execution_accuracy",
        "evidence_state_correct_rate",
        "trajectory_accounting_rate",
        "audit_accounting_rate",
        "budget_accounting_rate",
        "terminal_outcome_accuracy",
        "safe_outcome_rate",
    ):
        assert metrics[name] == {
            "numerator": 11,
            "denominator": 11,
            "rate": 1.0,
            "excluded_invalid_cases": 1,
        }
    assert metrics["unsafe_accept_count"] == 0
    assert metrics["hidden_recovery_count"] == 0
    assert metrics["unaccounted_recovery_count"] == 0
    assert metrics["post_critic_mutation_without_revalidation_count"] == 0
    assert metrics["raw_invalid_path_foreign_citation_count"] == 1
    assert metrics["safe_outcome_false_pass_count"] == 1


def test_c11_executes_after_p2b_while_history_remains_frozen() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    c11 = next(
        item
        for item in artifact["case_results"]
        if item["case_id"] == "C11-citation-format-only-defect"
    )
    assert c11["critic_method"] == "rules_v1"
    assert c11["recommended_action"] == "REVISE_FROM_EXISTING_EVIDENCE"
    assert c11["execution_status"] == "EXECUTED"
    assert c11["revision_attempts"] == 1
    assert c11["retrieval_attempts"] == 0
    assert c11["trajectory_result"] == "PASS"
    assert c11["audit_result"] == "PASS"
    assert c11["budget_result"] == "PASS"
    assert c11["terminal_result"] == "PASS"
    assert c11["safe_outcome"] is True
    assert c11["pass"] is True


def test_anti_degenerate_controls_are_not_misreported_after_product_stop() -> None:
    artifact = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    controls = artifact["anti_degenerate_controls"]
    assert set(controls) == {
        "ALWAYS_ACCEPT",
        "ALWAYS_REVISE",
        "ALWAYS_RETRIEVE",
        "ALWAYS_CLARIFY",
        "ALWAYS_REFUSE",
    }
    assert all(item["status"] == "NOT_RUN_MEASUREMENT_BLOCKER" for item in controls.values())
    assert artifact["metrics"]["degenerate_policy_false_pass_count"] is None

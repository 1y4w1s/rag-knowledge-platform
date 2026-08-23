"""W9 P2 frozen product-boundary evidence; no provider or model execution."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.eval.critic_capability.loader import load_bound_suite
from app.services.rag.critic import CriticAction


FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
INJECTED_PATH = FIXTURES / "w9-critic-p2-injected-reports.json"
ARTIFACT_PATH = FIXTURES / "w9-critic-p2-offline-product.json"
FORBIDDEN_INJECTOR_KEYS = {
    "expected_action",
    "expected_status",
    "oracle",
    "pass",
    "first_failed_stage",
    "in_capability_denominator",
}


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_walk_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_walk_keys(item) for item in value))
    return set()


def _load_injected() -> dict[str, dict[str, object]]:
    payload = json.loads(INJECTED_PATH.read_text(encoding="utf-8"))
    assert payload["protocol"] == "w9_critic_p2_injected_reports_v1"
    assert not _walk_keys(payload).intersection(FORBIDDEN_INJECTOR_KEYS)
    reports = payload["reports"]
    assert isinstance(reports, list)
    by_id = {str(item["case_id"]): item for item in reports}
    assert len(by_id) == len(reports), "injected case IDs must be unique"
    return by_id


def test_p2_injection_is_complete_and_oracle_isolation_holds() -> None:
    contract, inputs = load_bound_suite()
    injected = _load_injected()
    denominator = [
        case for case in contract["oracle_cases"] if case["in_capability_denominator"]
    ]

    assert len(inputs) == len(denominator) == len(injected) == 12
    assert {case["case_id"] for case in denominator} == set(injected)
    assert Counter(case["expected_action"] for case in denominator) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }
    assert Counter(str(report["recommended_action"]) for report in injected.values()) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }


def test_c11_frozen_deterministic_revision_preserves_product_boundary_failure() -> None:
    """Frozen P2 evidence remains pre-remediation and never runs current code."""
    c11 = _load_injected()["C11-citation-format-only-defect"]
    assert c11["method"] == "rules_v1"
    assert c11["recommended_action"] == CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    historical = next(
        result
        for result in artifact["case_results"]
        if result["case_id"] == "C11-citation-format-only-defect"
    )
    assert historical["product_action_observed"] == (
        CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value
    )
    assert historical["trajectory_result"] == {
        "status": "skipped_unavailable",
        "attempt_count": 0,
    }
    assert historical["first_failed_stage"] == "L3_ORCHESTRATION_EXECUTION_CORRECT"
    assert historical["classification"] == "PRODUCT_CONTROL_PLANE_FAILURE"


def test_p2_artifact_preserves_partial_verdict_and_zero_rollout() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert artifact["state"] == "PARTIAL"
    assert artifact["round_start_master_sha"] == artifact["p1_merge_sha"]
    assert artifact["execution_tree_matches_round_master"] is True
    assert artifact["frozen_case_count"] == 12
    assert artifact["runnable_case_count"] == 1
    assert artifact["not_yet_run_case_count"] == 11
    assert artifact["invalid_case_count"] == artifact["non_runnable_case_count"] == 0
    assert artifact["default_behavior_changed"] is False
    assert artifact["runtime_rollout"] is False
    assert artifact["external_call_attempted"] is False
    assert artifact["model_result_obtained"] is False
    results = {item["case_id"]: item for item in artifact["case_results"]}
    assert len(results) == artifact["frozen_case_count"]
    assert set(results) == set(_load_injected())
    assert results["C11-citation-format-only-defect"]["classification"] == (
        "PRODUCT_CONTROL_PLANE_FAILURE"
    )
    assert results["C11-citation-format-only-defect"]["first_failed_stage"] == (
        "L3_ORCHESTRATION_EXECUTION_CORRECT"
    )
    assert all(
        item["execution_status"] == "NOT_EXECUTED_STOP_CONDITION"
        for case_id, item in results.items()
        if case_id != "C11-citation-format-only-defect"
    )
    metrics = artifact["metrics"]
    assert metrics["product_case_pass_rate"] == {
        "numerator": 0,
        "denominator": 1,
        "rate": 0.0,
    }
    assert all(
        metrics[name] == 0
        for name in (
            "unsafe_accept_count",
            "hidden_recovery_count",
            "post_critic_mutation_without_revalidation_count",
        )
    )
    assert metrics["degenerate_policy_false_pass_count"] is None
    assert metrics["audit_accounting_rate"]["value"] is None
    assert metrics["unaccounted_recovery_count"] is None
    assert artifact["verdicts"]["DEGENERATE_POLICY_CONTROLS"] == "NOT_RUN_STOP_CONDITION"
    assert artifact["verdicts"]["READY_FOR_REAL_LOCAL_MEASUREMENT"] == "NO"

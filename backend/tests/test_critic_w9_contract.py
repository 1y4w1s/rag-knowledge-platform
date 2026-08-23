"""W9 P0 critic architecture and capability-contract gates."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.eval.critic_capability import (
    capability_valid_denominator,
    evaluate_case,
    evaluate_suite,
    load_contract,
    load_model_inputs,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "l4_critic"
ARCHITECTURE_PATH = FIXTURE_ROOT / "w9-critic-architecture-audit.json"


def _oracle_report(oracle: dict[str, Any]) -> dict[str, Any]:
    claims = [
        {
            "claim_id": claim["claim_id"],
            "identity": claim["identity"],
            "text": claim["text"],
            "evidence_references": claim["evidence_references"],
        }
        for claim in oracle["claims"]
    ]
    findings = [
        {
            "claim_id": claim["claim_id"],
            "status": claim["status"],
            "evaluation_state": claim["evaluation_state"],
            "decision_owner": claim["decision_owner"],
            "reason_code": claim["reason_code"],
        }
        for claim in oracle["claims"]
    ]
    statuses = [finding["status"] for finding in findings]
    semantic_calls = int(any(c["decision_owner"] == "SEMANTIC" for c in oracle["claims"]))
    return {
        "claims": claims,
        "findings": findings,
        "supported_count": statuses.count("SUPPORTED"),
        "unsupported_count": statuses.count("UNSUPPORTED"),
        "conflicted_count": statuses.count("CONFLICTED"),
        "insufficient_count": statuses.count("INSUFFICIENT_EVIDENCE"),
        "unverifiable_count": statuses.count("UNVERIFIABLE"),
        "blocked_count": sum(
            finding["evaluation_state"] == "BLOCKED_BY_DETERMINISTIC"
            for finding in findings
        ),
        "critic_pass": oracle["critic_pass"],
        "recommended_action": oracle["expected_action"],
        "reason_code": oracle["expected_reason_code"],
        "execution": {
            "semantic_critic_calls": semantic_calls,
            "action_executed": False,
            "hidden_retry_count": 0,
        },
    }


@pytest.fixture
def bound_suite() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    contract = load_contract()
    inputs = {case["case_id"]: case for case in load_model_inputs()}
    return contract, inputs


@pytest.fixture
def oracle_reports(bound_suite: tuple[dict[str, Any], dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    contract, _ = bound_suite
    return {case["case_id"]: _oracle_report(case) for case in contract["oracle_cases"]}


def test_architecture_audit_freezes_high_duplicate_risk() -> None:
    audit = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))

    assert audit["base_sha"] == "33e7c551081eaa22db2eb5c7f9fec1f0585f4976"
    assert audit["verdicts"] == {
        "existing_critic_present": "YES",
        "w9_semantic_claim_critic_capability": "PARTIAL",
        "duplicate_reflection_risk": "HIGH",
        "ready_for_product_experiment": "NO",
        "ready_for_real_local_measurement": "NO",
        "runtime_rollout": "NO",
    }
    assert audit["loop_counts"]["implemented_runtime_reflection_owners"] == 2
    assert audit["loop_counts"]["implemented_generation_revision_owners"] == 1
    assert audit["loop_counts"]["default_active_count_is_path_dependent"] is True
    assert audit["target_reflection_architecture"]["single_orchestration_owner"] is True
    assert audit["target_reflection_architecture"]["critic_budget"] == {
        "initial_invocations": 1,
        "optional_post_revision_validation": 1,
        "critic_executes_actions": False,
        "retrieval_uses_original_shared_steps_used_max_steps": True,
        "hidden_retry_count_allowed": 0,
    }


def test_contract_has_twelve_bound_capability_cases(
    bound_suite: tuple[dict[str, Any], dict[str, dict[str, Any]]],
) -> None:
    contract, inputs = bound_suite

    assert capability_valid_denominator() == 12
    assert contract["capability_valid_denominator"] == 12
    assert len(inputs) == 12
    assert all(case["in_capability_denominator"] for case in contract["oracle_cases"])
    assert Counter(case["expected_action"] for case in contract["oracle_cases"]) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }


def test_model_inputs_exclude_all_oracle_keys() -> None:
    forbidden = {
        "expected_status",
        "expected_action",
        "oracle",
        "decision_owner",
        "reason_code",
        "in_capability_denominator",
    }

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not forbidden.intersection(keys(load_model_inputs()))


def test_loader_rejects_nested_oracle_leakage(tmp_path: Path) -> None:
    leaked = {
        "cases": [
            {
                "case_id": "leaked",
                "query": "q",
                "nested": {"expected_action": "ACCEPT"},
            }
        ]
    }
    path = tmp_path / "leaked.json"
    path.write_text(json.dumps(leaked), encoding="utf-8")

    with pytest.raises(ValueError, match="oracle leakage"):
        load_model_inputs(path)


def test_oracle_reports_pass_exact_vector_gates(
    oracle_reports: dict[str, dict[str, Any]],
) -> None:
    result = evaluate_suite(oracle_reports)

    assert result["contract_pass"] is True
    assert result["capability_valid_denominator"] == 12
    assert result["semantic_claim_denominator"] == 10
    assert result["first_failed_stage_counts"] == {}
    assert result["hard_gate_counts"] == {
        "evidence_scope_violation_count": 0,
        "semantic_called_on_deterministic_block_count": 0,
        "critic_action_execution_count": 0,
        "retry_amplification_count": 0,
    }
    assert result["metrics"]["supported_claim_recall"] == {
        "numerator": 7,
        "denominator": 7,
        "rate": 1.0,
        "not_applicable_reason": None,
    }
    assert result["metrics"]["unsupported_claim_recall"]["denominator"] == 2
    assert result["metrics"]["nonassertive_exclusion_rate"]["rate"] == 1.0
    assert result["metrics"]["unsafe_accept_rate"]["denominator"] == 7


@pytest.mark.parametrize(
    ("action", "maximum_correct"),
    [
        ("ACCEPT", 5),
        ("REVISE_FROM_EXISTING_EVIDENCE", 3),
        ("RETRIEVE_MISSING_EVIDENCE", 2),
        ("CLARIFY", 1),
        ("REFUSE", 1),
    ],
)
def test_uniform_action_policies_cannot_pass(
    action: str,
    maximum_correct: int,
    oracle_reports: dict[str, dict[str, Any]],
) -> None:
    reports = copy.deepcopy(oracle_reports)
    for report in reports.values():
        report["recommended_action"] = action

    result = evaluate_suite(reports)

    assert result["contract_pass"] is False
    assert result["metrics"]["action_recommendation_correct"]["numerator"] == maximum_correct
    if action == "ACCEPT":
        assert result["metrics"]["unsafe_accept_rate"]["numerator"] == 7
    else:
        assert result["metrics"]["unnecessary_intervention_rate"]["numerator"] == 5


@pytest.mark.parametrize(
    ("case_id", "mutate", "first_failed_stage"),
    [
        (
            "C03-one-unsupported-among-supported",
            lambda report: report["findings"][1].update(status="SUPPORTED"),
            "semantic_critic_valid",
        ),
        (
            "C01-fully-supported-exact",
            lambda report: report["claims"][0].update(evidence_references=["FABRICATED"]),
            "evidence_scope_valid",
        ),
        (
            "C11-citation-format-only-defect",
            lambda report: report["findings"][0].update(
                status="SUPPORTED",
                evaluation_state="JUDGED",
                decision_owner="SEMANTIC",
                reason_code="EVIDENCE_ENTAILS_CLAIM",
            ),
            "deterministic_layer_valid",
        ),
        (
            "C02-supported-paraphrase-low-lexical",
            lambda report: report["execution"].update(hidden_retry_count=1),
            "advisory_budget_valid",
        ),
    ],
)
def test_first_failed_stage_is_stable(
    case_id: str,
    mutate: Any,
    first_failed_stage: str,
    bound_suite: tuple[dict[str, Any], dict[str, dict[str, Any]]],
) -> None:
    contract, inputs = bound_suite
    oracle = next(case for case in contract["oracle_cases"] if case["case_id"] == case_id)
    report = _oracle_report(oracle)
    mutate(report)

    result = evaluate_case(inputs[case_id], oracle, report)

    assert result.first_failed_stage == first_failed_stage
    assert result.passed is False


def test_report_schema_failure_precedes_all_later_stages(
    bound_suite: tuple[dict[str, Any], dict[str, dict[str, Any]]],
) -> None:
    contract, inputs = bound_suite
    oracle = contract["oracle_cases"][0]
    report = _oracle_report(oracle)
    report.pop("claims")

    result = evaluate_case(inputs[oracle["case_id"]], oracle, report)

    assert result.first_failed_stage == "report_schema_valid"


def test_format_only_defect_never_calls_semantic_critic(
    bound_suite: tuple[dict[str, Any], dict[str, dict[str, Any]]],
) -> None:
    contract, inputs = bound_suite
    oracle = next(c for c in contract["oracle_cases"] if c["case_id"].startswith("C11"))
    report = _oracle_report(oracle)

    result = evaluate_case(inputs[oracle["case_id"]], oracle, report)
    semantic_stage = next(s for s in result.stages if s.stage == "semantic_critic_valid")

    assert result.passed is True
    assert semantic_stage.eligible is False
    assert report["execution"]["semantic_critic_calls"] == 0

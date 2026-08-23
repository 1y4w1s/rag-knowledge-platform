"""Explicit-denominator suite metrics and hard gates for W9 critic reports."""

from __future__ import annotations

from typing import Any, Mapping

from app.eval.critic_capability.evaluator import evaluate_case
from app.eval.critic_capability.loader import load_bound_suite
from app.eval.critic_capability.schema import report_maps


def _metric(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": None if denominator == 0 else round(numerator / denominator, 4),
        "not_applicable_reason": "zero eligible denominator" if denominator == 0 else None,
    }


def _execution(report: Mapping[str, Any]) -> Mapping[str, Any]:
    value = report.get("execution", {})
    return value if isinstance(value, dict) else {}


def _claim_texts(report: Mapping[str, Any]) -> set[Any]:
    claims = report.get("claims", [])
    if not isinstance(claims, list):
        return set()
    return {claim.get("text") for claim in claims if isinstance(claim, dict)}


def evaluate_suite(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    contract, inputs = load_bound_suite()
    input_by_id = {case["case_id"]: case for case in inputs}
    oracle_cases = [
        case for case in contract["oracle_cases"] if case["in_capability_denominator"]
    ]
    evaluations = []
    pairs: list[tuple[dict[str, Any], Mapping[str, Any]]] = []
    for oracle in oracle_cases:
        report = reports.get(oracle["case_id"], {})
        evaluations.append(evaluate_case(input_by_id[oracle["case_id"]], oracle, report))
        pairs.append((oracle, report))

    expected_claims = [claim for oracle, _ in pairs for claim in oracle["claims"]]
    semantic_claims = [
        claim for claim in expected_claims if claim["decision_owner"] == "SEMANTIC"
    ]
    predicted: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    detected_total = 0
    detected_true = 0
    for oracle, report in pairs:
        candidate_claims, findings = report_maps(report)
        truth = {claim["identity"]: claim for claim in oracle["claims"]}
        detected_total += len(candidate_claims)
        detected_true += len(set(candidate_claims).intersection(truth))
        predicted.extend(
            (claim, findings.get(claim["identity"])) for claim in oracle["claims"]
        )

    supported = [
        (claim, finding)
        for claim, finding in predicted
        if claim["decision_owner"] == "SEMANTIC" and claim["status"] == "SUPPORTED"
    ]
    unsupported = [
        (claim, finding)
        for claim, finding in predicted
        if claim["decision_owner"] == "SEMANTIC"
        and claim["status"] == "UNSUPPORTED"
    ]
    predicted_supported = [
        (claim, finding)
        for claim, finding in predicted
        if finding
        and finding.get("decision_owner") == "SEMANTIC"
        and finding.get("status") == "SUPPORTED"
    ]
    conflicts = [(c, f) for c, f in predicted if c["status"] == "CONFLICTED"]
    insufficient = [
        (c, f) for c, f in predicted if c["status"] == "INSUFFICIENT_EVIDENCE"
    ]
    unverifiable = [(c, f) for c, f in predicted if c["status"] == "UNVERIFIABLE"]
    safe_cases = [(o, r) for o, r in pairs if o["expected_action"] == "ACCEPT"]
    unsafe_cases = [(o, r) for o, r in pairs if o["expected_action"] != "ACCEPT"]
    accepted = [(o, r) for o, r in pairs if r.get("recommended_action") == "ACCEPT"]
    excluded_non_claims = [
        text for oracle, _ in pairs for text in oracle.get("excluded_non_claims", [])
    ]
    predicted_claim_texts = set().union(*(_claim_texts(report) for _, report in pairs))

    metrics = {
        "claim_detection_precision": _metric(detected_true, detected_total),
        "claim_detection_recall": _metric(detected_true, len(expected_claims)),
        "nonassertive_exclusion_rate": _metric(
            sum(text not in predicted_claim_texts for text in excluded_non_claims),
            len(excluded_non_claims),
        ),
        "supported_claim_precision": _metric(
            sum(claim["status"] == "SUPPORTED" for claim, _ in predicted_supported),
            len(predicted_supported),
        ),
        "supported_claim_recall": _metric(
            sum(
                bool(finding and finding.get("status") == "SUPPORTED")
                for _, finding in supported
            ),
            len(supported),
        ),
        "unsupported_claim_recall": _metric(
            sum(
                bool(finding and finding.get("status") == "UNSUPPORTED")
                for _, finding in unsupported
            ),
            len(unsupported),
        ),
        "conflict_detection": _metric(
            sum(
                bool(finding and finding.get("status") == "CONFLICTED")
                for _, finding in conflicts
            ),
            len(conflicts),
        ),
        "insufficient_detection": _metric(
            sum(
                bool(finding and finding.get("status") == "INSUFFICIENT_EVIDENCE")
                for _, finding in insufficient
            ),
            len(insufficient),
        ),
        "unverifiable_detection": _metric(
            sum(
                bool(finding and finding.get("status") == "UNVERIFIABLE")
                for _, finding in unverifiable
            ),
            len(unverifiable),
        ),
        "false_critic_alarm": _metric(
            sum(
                bool(finding and finding.get("status") != "SUPPORTED")
                for _, finding in supported
            ),
            len(supported),
        ),
        "missed_unsupported_claim": _metric(
            sum(
                not finding or finding.get("status") != "UNSUPPORTED"
                for _, finding in unsupported
            ),
            len(unsupported),
        ),
        "action_recommendation_correct": _metric(
            sum(
                report.get("recommended_action") == oracle["expected_action"]
                for oracle, report in pairs
            ),
            len(pairs),
        ),
        "safe_accept_precision": _metric(
            sum(oracle["expected_action"] == "ACCEPT" for oracle, _ in accepted),
            len(accepted),
        ),
        "safe_accept_rate": _metric(
            sum(
                report.get("recommended_action") == "ACCEPT"
                for _, report in safe_cases
            ),
            len(safe_cases),
        ),
        "necessary_accept_rate": _metric(
            sum(
                report.get("recommended_action") == "ACCEPT"
                for _, report in safe_cases
            ),
            len(safe_cases),
        ),
        "unsafe_accept_rate": _metric(
            sum(
                report.get("recommended_action") == "ACCEPT"
                for _, report in unsafe_cases
            ),
            len(unsafe_cases),
        ),
        "unnecessary_intervention_rate": _metric(
            sum(
                report.get("recommended_action") != "ACCEPT"
                for _, report in safe_cases
            ),
            len(safe_cases),
        ),
        "unnecessary_retrieve_rate": _metric(
            sum(
                oracle["expected_action"] != "RETRIEVE_MISSING_EVIDENCE"
                and report.get("recommended_action") == "RETRIEVE_MISSING_EVIDENCE"
                for oracle, report in pairs
            ),
            sum(
                oracle["expected_action"] != "RETRIEVE_MISSING_EVIDENCE"
                for oracle, _ in pairs
            ),
        ),
    }
    failures: dict[str, int] = {}
    for result in evaluations:
        if result.first_failed_stage:
            failures[result.first_failed_stage] = failures.get(result.first_failed_stage, 0) + 1
    hard_counts = {
        "evidence_scope_violation_count": sum(
            any(
                item.stage == "evidence_scope_valid" and not item.passed
                for item in result.stages
            )
            for result in evaluations
        ),
        "semantic_called_on_deterministic_block_count": sum(
            not any(
                claim["decision_owner"] == "SEMANTIC" for claim in oracle["claims"]
            )
            and _execution(report).get("semantic_critic_calls", 0) > 0
            for oracle, report in pairs
        ),
        "critic_action_execution_count": sum(
            _execution(report).get("action_executed") is True for _, report in pairs
        ),
        "retry_amplification_count": sum(
            value
            for _, report in pairs
            if isinstance(
                (value := _execution(report).get("hidden_retry_count", 0)), int
            )
        ),
    }
    contract_pass = (
        all(result.passed for result in evaluations)
        and metrics["unsafe_accept_rate"]["numerator"] == 0
        and metrics["unnecessary_intervention_rate"]["numerator"] == 0
        and all(value == 0 for value in hard_counts.values())
    )
    return {
        "protocol": contract["protocol"],
        "capability_valid_denominator": len(oracle_cases),
        "semantic_claim_denominator": len(semantic_claims),
        "contract_pass": contract_pass,
        "metrics": metrics,
        "hard_gate_counts": hard_counts,
        "first_failed_stage_counts": failures,
        "case_results": [result.to_dict() for result in evaluations],
    }

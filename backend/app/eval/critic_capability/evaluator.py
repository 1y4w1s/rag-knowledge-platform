"""Deterministic per-case evaluator for the W9 critic contract."""

from __future__ import annotations

from typing import Any, Mapping

from app.eval.critic_capability.schema import (
    CaseEvaluation,
    report_maps,
    schema_error,
    stage,
)


def evaluate_case(
    model_input: Mapping[str, Any],
    oracle: Mapping[str, Any],
    report: Mapping[str, Any],
) -> CaseEvaluation:
    stages = [stage("fixture_contract_valid", True)]
    report_error = schema_error(report)
    stages.append(stage("report_schema_valid", report_error is None, report_error or ""))
    predicted_claims, findings = report_maps(report)
    expected_claims = {claim["identity"]: claim for claim in oracle["claims"]}
    detection_ok = set(predicted_claims) == set(expected_claims) and all(
        predicted_claims[identity].get("text") == expected_claims[identity]["text"]
        for identity in expected_claims
    )
    stages.append(
        stage(
            "claim_detection_valid",
            detection_ok,
            "claim identity/text set mismatch" if not detection_ok else "",
        )
    )

    evidence_ids = {item["evidence_id"] for item in model_input.get("evidence", [])}
    scope_ok = True
    for identity, claim in predicted_claims.items():
        refs = set(claim.get("evidence_references", []))
        expected_refs = set(expected_claims.get(identity, {}).get("evidence_references", []))
        if not refs.issubset(evidence_ids) or refs != expected_refs:
            scope_ok = False
            break
    stages.append(
        stage(
            "evidence_scope_valid",
            scope_ok,
            "invalid or fabricated evidence reference" if not scope_ok else "",
        )
    )

    deterministic = [
        claim
        for claim in oracle["claims"]
        if claim["decision_owner"] == "DETERMINISTIC"
    ]
    deterministic_ok = all(
        (finding := findings.get(claim["identity"])) is not None
        and finding.get("decision_owner") == claim["decision_owner"]
        and finding.get("evaluation_state") == claim["evaluation_state"]
        and finding.get("status") == claim["status"]
        and finding.get("reason_code") == claim["reason_code"]
        for claim in deterministic
    )
    stages.append(
        stage(
            "deterministic_layer_valid",
            deterministic_ok,
            "deterministic result mismatch" if not deterministic_ok else "",
        )
    )

    semantic = [
        claim for claim in oracle["claims"] if claim["decision_owner"] == "SEMANTIC"
    ]
    semantic_ok = all(
        (finding := findings.get(claim["identity"])) is not None
        and finding.get("decision_owner") == "SEMANTIC"
        and finding.get("evaluation_state") == "JUDGED"
        and finding.get("status") == claim["status"]
        for claim in semantic
    )
    stages.append(
        stage(
            "semantic_critic_valid",
            semantic_ok,
            "semantic status mismatch" if not semantic_ok else "",
            eligible=bool(semantic),
        )
    )

    statuses = [finding.get("status") for finding in findings.values()]
    expected_counts = {
        "supported_count": statuses.count("SUPPORTED"),
        "unsupported_count": statuses.count("UNSUPPORTED"),
        "conflicted_count": statuses.count("CONFLICTED"),
        "insufficient_count": statuses.count("INSUFFICIENT_EVIDENCE"),
        "unverifiable_count": statuses.count("UNVERIFIABLE"),
        "blocked_count": sum(
            finding.get("evaluation_state") == "BLOCKED_BY_DETERMINISTIC"
            for finding in findings.values()
        ),
    }
    aggregate_ok = all(report.get(key) == value for key, value in expected_counts.items())
    aggregate_ok = aggregate_ok and report.get("critic_pass") == oracle["critic_pass"]
    aggregate_ok = aggregate_ok and report.get("reason_code") == oracle["expected_reason_code"]
    stages.append(
        stage(
            "report_aggregation_valid",
            aggregate_ok,
            "report counts, critic_pass, or reason_code mismatch"
            if not aggregate_ok
            else "",
        )
    )

    action_ok = report.get("recommended_action") == oracle["expected_action"]
    stages.append(
        stage(
            "action_recommendation_valid",
            action_ok,
            "wrong recommended_action" if not action_ok else "",
        )
    )
    execution = report.get("execution", {})
    if not isinstance(execution, dict):
        execution = {}
    expected_calls = 1 if semantic else 0
    budget_ok = (
        execution.get("semantic_critic_calls") == expected_calls
        and execution.get("action_executed") is False
        and execution.get("hidden_retry_count") == 0
    )
    stages.append(
        stage(
            "advisory_budget_valid",
            budget_ok,
            "critic acted or exceeded explicit budget" if not budget_ok else "",
        )
    )

    first_failed = next(
        (item.stage for item in stages if item.eligible and not item.passed), None
    )
    return CaseEvaluation(
        case_id=str(oracle["case_id"]),
        passed=first_failed is None,
        first_failed_stage=first_failed,
        stages=tuple(stages),
    )

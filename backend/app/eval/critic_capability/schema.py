"""W9 critic report schema and stage result types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

FINDING_STATUSES = frozenset(
    {
        "SUPPORTED",
        "UNSUPPORTED",
        "CONFLICTED",
        "INSUFFICIENT_EVIDENCE",
        "UNVERIFIABLE",
    }
)
RECOMMENDED_ACTIONS = frozenset(
    {
        "ACCEPT",
        "REVISE_FROM_EXISTING_EVIDENCE",
        "RETRIEVE_MISSING_EVIDENCE",
        "CLARIFY",
        "REFUSE",
    }
)
EVALUATION_STATES = frozenset({"JUDGED", "BLOCKED_BY_DETERMINISTIC"})
DECISION_OWNERS = frozenset({"DETERMINISTIC", "SEMANTIC"})
STAGE_ORDER = (
    "fixture_contract_valid",
    "report_schema_valid",
    "claim_detection_valid",
    "evidence_scope_valid",
    "deterministic_layer_valid",
    "semantic_critic_valid",
    "report_aggregation_valid",
    "action_recommendation_valid",
    "advisory_budget_valid",
)


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: str
    eligible: bool
    attempted: bool
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    passed: bool
    first_failed_stage: str | None
    stages: tuple[StageResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "first_failed_stage": self.first_failed_stage,
            "stages": [stage.to_dict() for stage in self.stages],
        }


def schema_error(report: Mapping[str, Any]) -> str | None:
    required = {
        "claims",
        "findings",
        "supported_count",
        "unsupported_count",
        "conflicted_count",
        "insufficient_count",
        "unverifiable_count",
        "blocked_count",
        "critic_pass",
        "recommended_action",
        "reason_code",
        "execution",
    }
    missing = required.difference(report)
    if missing:
        return f"missing report fields: {sorted(missing)}"
    claims = report.get("claims")
    findings = report.get("findings")
    if not isinstance(claims, list) or not isinstance(findings, list):
        return "claims/findings must be lists"
    claim_ids: list[str] = []
    identities: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            return "claim must be an object"
        if not all(
            isinstance(claim.get(key), str) and claim[key]
            for key in ("claim_id", "identity", "text")
        ):
            return "claim_id/identity/text must be non-empty strings"
        if not isinstance(claim.get("evidence_references"), list):
            return "claim evidence_references must be a list"
        if not all(isinstance(ref, str) and ref for ref in claim["evidence_references"]):
            return "claim evidence references must be non-empty strings"
        claim_ids.append(claim["claim_id"])
        identities.append(claim["identity"])
    if len(claim_ids) != len(set(claim_ids)) or len(identities) != len(set(identities)):
        return "duplicate claim_id/identity"
    finding_ids: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("claim_id") not in claim_ids:
            return "finding must reference a declared claim"
        if finding.get("evaluation_state") not in EVALUATION_STATES:
            return "invalid evaluation_state"
        if finding.get("decision_owner") not in DECISION_OWNERS:
            return "invalid decision_owner"
        if not isinstance(finding.get("reason_code"), str) or not finding["reason_code"]:
            return "finding reason_code must be a non-empty string"
        status = finding.get("status")
        blocked = finding.get("evaluation_state") == "BLOCKED_BY_DETERMINISTIC"
        if (blocked and status is not None) or (
            not blocked and status not in FINDING_STATUSES
        ):
            return "invalid status/evaluation_state combination"
        finding_ids.append(finding["claim_id"])
    if len(finding_ids) != len(set(finding_ids)) or set(finding_ids) != set(claim_ids):
        return "findings must map one-to-one to claims"
    if report.get("recommended_action") not in RECOMMENDED_ACTIONS:
        return "invalid recommended_action"
    count_fields = (
        "supported_count",
        "unsupported_count",
        "conflicted_count",
        "insufficient_count",
        "unverifiable_count",
        "blocked_count",
    )
    if not all(isinstance(report.get(key), int) and report[key] >= 0 for key in count_fields):
        return "report counts must be non-negative integers"
    if (
        not isinstance(report.get("critic_pass"), bool)
        or not isinstance(report.get("reason_code"), str)
        or not report["reason_code"]
    ):
        return "critic_pass/reason_code invalid"
    execution = report.get("execution")
    if not isinstance(execution, dict):
        return "execution must be an object"
    if (
        not isinstance(execution.get("semantic_critic_calls"), int)
        or not isinstance(execution.get("action_executed"), bool)
        or not isinstance(execution.get("hidden_retry_count"), int)
    ):
        return "execution counters/flags invalid"
    return None


def report_maps(
    report: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    report_claims = report.get("claims", [])
    report_findings = report.get("findings", [])
    if not isinstance(report_claims, list):
        report_claims = []
    if not isinstance(report_findings, list):
        report_findings = []
    claims = {
        claim["claim_id"]: claim
        for claim in report_claims
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    }
    by_identity = {claim.get("identity"): claim for claim in claims.values()}
    findings = {
        claims[finding["claim_id"]].get("identity"): finding
        for finding in report_findings
        if isinstance(finding, dict) and finding.get("claim_id") in claims
    }
    return by_identity, findings


def stage(
    name: str,
    passed: bool,
    reason: str = "",
    *,
    eligible: bool = True,
) -> StageResult:
    return StageResult(name, eligible, eligible, passed if eligible else True, reason)

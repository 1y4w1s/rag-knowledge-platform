"""Loader for T2 Phase B eligibility boundary freeze (eval/test-only; no product change)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

AUDIT_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/t2-broader-phase-b-eligibility-audit.json"
)

AUDIT_NAME = "T2 Phase B Eligibility Boundary Freeze"
STAGE = "T2_BROADER_VALIDATION_PHASE_B_ELIGIBILITY_AUDIT"
SCHEMA_VERSION = "t2-broader-phase-b-eligibility-audit-v1"
POSITIVE_CASE_IDS = frozenset({"GQ-132", "GQ-149"})

EXCLUSION_TAXONOMY = frozenset(
    {
        "STALE_CONTRACT",
        "INTEGRATION_ONLY",
        "UNAVAILABLE_TOOL",
        "AMBIGUOUS_COMPLETION",
        "NO_MACHINE_VERIFIABLE_OBSERVATION",
        "NOT_T2_APPLICABLE",
        "UNSATISFIABLE_CURRENT_RUNTIME",
        "OTHER_EXPLICIT_REASON",
    }
)

FORBIDDEN_CLAIMS = frozenset(
    {
        "Broader Validation Completed",
        "Expanded Capability Validated",
        "BROADER_REAL_VALIDATED",
        "POSITIVE_DENOMINATOR_EXPANDED",
        "T2 is broadly validated",
        "T2 broader validation failed",
        "BROADER_GENERALIZATION=FALSE",
    }
)

REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "audit_name",
        "contract_name",
        "design_only",
        "real_run_executed",
        "product_change",
        "golden_mutated",
        "runtime_rollout",
        "product_eligibility_extension",
        "golden_rewrite",
        "round_start_master_sha",
        "phase_a_reference",
        "included_positive_candidates",
        "eligibility_control_not_positive",
        "exclusion_ledger",
        "exclusion_taxonomy",
        "audited_cases",
        "denominators",
        "phase_b_freeze",
        "key_outcome",
        "forbidden_claims",
        "audit_verdict",
    }
)


def audit_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / AUDIT_RELATIVE_PATH


@lru_cache(maxsize=1)
def load_t2_phase_b_eligibility_audit() -> dict[str, Any]:
    path = audit_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ValueError(f"T2 Phase B eligibility audit missing keys: {sorted(missing)}")
    return payload


def assert_phase_b_freeze_invariants(audit: dict[str, Any] | None = None) -> None:
    """Phase B eligibility boundary freeze — denom stays 2; no broader claim."""
    data = audit or load_t2_phase_b_eligibility_audit()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stage"] == STAGE
    assert data["audit_name"] == AUDIT_NAME
    assert data["contract_name"] == AUDIT_NAME

    assert data["design_only"] is True
    assert data["real_run_executed"] is False
    assert data["product_change"] is False
    assert data["golden_mutated"] is False
    assert data["runtime_rollout"] is False
    assert data["product_eligibility_extension"] is False
    assert data["golden_rewrite"] is False

    freeze = data["phase_b_freeze"]
    assert freeze["T2_PHASE_B_ELIGIBILITY_AUDIT"] == "PASS"
    assert freeze["ADDITIONAL_VALID_POSITIVES"] == []
    assert freeze["POSITIVE_DENOMINATOR"] == 2
    assert freeze["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert freeze["positive_cases"] == ["GQ-132", "GQ-149"]
    assert freeze["gq131_role"] == "ELIGIBILITY_CONTROL"
    assert freeze["gq131_in_positive_denominator"] is False
    assert freeze["BROADER_GENERALIZATION"] == "NOT_MEASURABLE_ON_CURRENT_BENCHMARK"
    assert freeze["BROADER_GENERALIZATION"] != "FALSE"
    assert freeze["runtime_rollout"] == "NO"
    assert freeze["product_eligibility_extension"] == "NO"
    assert freeze["golden_rewrite"] == "NO"

    interpretation = freeze["interpretation"]
    assert "no additional capability-valid T2 positive cases" in interpretation["correct"]
    assert interpretation["incorrect_forbidden"] == "T2 broader validation failed"
    assert "NOT_MEASURABLE_ON_CURRENT_BENCHMARK" in interpretation["note"]

    claims = freeze["v1_0_claim_language"]
    assert claims["allowed"] == (
        "T2 is real-validated on the frozen valid subset of two positive cases."
    )
    assert claims["forbidden"] == "T2 is broadly validated."
    assert "not rewriting existing cases" in claims["future_broader_claim_requires"]

    denominators = data["denominators"]
    assert denominators["POSITIVE_DENOMINATOR"] == 2
    assert denominators["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert denominators["ADDITIONAL_VALID_POSITIVES"] == []

    positives = {
        c["case_id"]
        for c in data["included_positive_candidates"]
        if c.get("include_in_broader_positive_denominator") is True
    }
    assert positives == POSITIVE_CASE_IDS

    controls = {c["case_id"] for c in data["eligibility_control_not_positive"]}
    assert controls == {"GQ-131"}

    assert set(data["exclusion_taxonomy"]) == EXCLUSION_TAXONOMY
    for row in data["exclusion_ledger"]:
        assert row["reason_code"] in EXCLUSION_TAXONOMY
        assert row["case_id"]
        assert row["reason"]

    for label in FORBIDDEN_CLAIMS:
        assert label in data["forbidden_claims"]

    verdict = data["audit_verdict"]
    assert verdict["state"] == "PASS"
    assert verdict["phase_b_status"] == "PASS_FROZEN"
    assert verdict["T2_PHASE_B_ELIGIBILITY_AUDIT"] == "PASS"
    assert verdict["ADDITIONAL_VALID_POSITIVES"] == []
    assert verdict["POSITIVE_DENOMINATOR"] == 2
    assert verdict["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert verdict["BROADER_GENERALIZATION"] == "NOT_MEASURABLE_ON_CURRENT_BENCHMARK"
    assert verdict["runtime_rollout"] == "NO"
    assert verdict["product_eligibility_extension"] == "NO"
    assert verdict["golden_rewrite"] == "NO"
    assert verdict["product_change"] == 0
    assert data["key_outcome"] == "NO_ADDITIONAL_VALID_POSITIVES_FOUND"

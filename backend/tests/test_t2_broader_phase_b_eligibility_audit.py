"""Freeze tests for T2 Phase B eligibility boundary (eval/test-only; no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.t2_phase_b_eligibility import (
    AUDIT_NAME,
    EXCLUSION_TAXONOMY,
    FORBIDDEN_CLAIMS,
    SCHEMA_VERSION,
    STAGE,
    assert_phase_b_freeze_invariants,
    load_t2_phase_b_eligibility_audit,
)
from app.eval.tool_capability.t2_broader_contract import (
    load_t2_broader_validation_contract,
)
from app.services.agent.tool_guidance_hints import _TERMINATION_CONTRACTS
from app.services.agent.tools.registry import READ_ONLY_TOOL_NAMES


def test_t2_phase_b_eligibility_loads_and_passes_invariants() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    assert_phase_b_freeze_invariants(audit)
    assert audit["schema_version"] == SCHEMA_VERSION
    assert audit["stage"] == STAGE
    assert audit["audit_name"] == AUDIT_NAME
    assert audit["phase_b_freeze"]["T2_PHASE_B_ELIGIBILITY_AUDIT"] == "PASS"
    assert audit["phase_b_freeze"]["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert audit["phase_b_freeze"]["runtime_rollout"] == "NO"


def test_t2_phase_b_no_additional_valid_positives() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    freeze = audit["phase_b_freeze"]
    assert freeze["ADDITIONAL_VALID_POSITIVES"] == []
    assert freeze["POSITIVE_DENOMINATOR"] == 2
    assert freeze["positive_cases"] == ["GQ-132", "GQ-149"]
    assert audit["denominators"]["ADDITIONAL_VALID_POSITIVES"] == []
    assert audit["audited_cases"]["positive_valid_only"] == ["GQ-132", "GQ-149"]


def test_t2_phase_b_broader_generalization_not_measurable() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    freeze = audit["phase_b_freeze"]
    assert freeze["BROADER_GENERALIZATION"] == "NOT_MEASURABLE_ON_CURRENT_BENCHMARK"
    assert freeze["BROADER_GENERALIZATION"] != "FALSE"
    assert (
        freeze["interpretation"]["incorrect_forbidden"]
        == "T2 broader validation failed"
    )
    assert "no additional capability-valid T2 positive cases" in freeze["interpretation"][
        "correct"
    ]
    assert freeze["v1_0_claim_language"]["allowed"] == (
        "T2 is real-validated on the frozen valid subset of two positive cases."
    )
    assert freeze["v1_0_claim_language"]["forbidden"] == "T2 is broadly validated."
    for label in FORBIDDEN_CLAIMS:
        assert label in audit["forbidden_claims"]


def test_t2_phase_b_gq131_remains_eligibility_control() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    controls = audit["eligibility_control_not_positive"]
    assert len(controls) == 1
    gq131 = controls[0]
    assert gq131["case_id"] == "GQ-131"
    assert gq131["include_in_broader_positive_denominator"] is False
    assert gq131["gates"]["t2_eligibility_unambiguous_after_observation"] is False
    assert gq131["authorized_by_this_freeze"] is False
    assert audit["phase_b_freeze"]["gq131_role"] == "ELIGIBILITY_CONTROL"
    assert audit["product_eligibility_extension"] is False


def test_t2_phase_b_exclusion_ledger_uses_standard_taxonomy() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    assert set(audit["exclusion_taxonomy"]) == EXCLUSION_TAXONOMY
    assert len(audit["exclusion_ledger"]) >= 1
    codes = {row["reason_code"] for row in audit["exclusion_ledger"]}
    assert codes <= EXCLUSION_TAXONOMY
    # Representative audited exclusions from Phase E research incorporate
    by_id = {row["case_id"]: row["reason_code"] for row in audit["exclusion_ledger"]}
    assert by_id["GQ-133"] == "UNSATISFIABLE_CURRENT_RUNTIME"
    assert by_id["GQ-135"] == "INTEGRATION_ONLY"
    assert by_id["GQ-140"] == "STALE_CONTRACT"
    assert by_id["GA-3"] == "AMBIGUOUS_COMPLETION"
    assert by_id["GA-4"] == "NO_MACHINE_VERIFIABLE_OBSERVATION"
    assert by_id["GQ-134"] == "UNAVAILABLE_TOOL"


def test_t2_phase_b_aligns_with_phase_a_and_runtime_bindings() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    phase_a = load_t2_broader_validation_contract()
    assert audit["phase_a_reference"]["PHASE_A_CONTRACT"] == "VALID"
    assert audit["phase_a_reference"]["positive_denominator"] == 2
    assert phase_a["phase_a_freeze"]["positive_cases"] == ["GQ-132", "GQ-149"]

    bound = {
        (row["case_id"], row["query"], row["expected_tool"])
        for row in audit["current_runtime_inventory"]["t2_termination_contracts_bound_today"]
    }
    assert bound == set(_TERMINATION_CONTRACTS)

    listed = set(audit["current_runtime_inventory"]["read_only_tools"])
    assert listed == set(READ_ONLY_TOOL_NAMES)


def test_t2_phase_b_forbids_denominator_enlargement_shortcuts() -> None:
    audit = load_t2_phase_b_eligibility_audit()
    forbidden = set(audit["phase_b_freeze"]["forbidden_denominator_enlargement"])
    assert "Golden rewrite" in forbidden
    assert "eligibility broadening" in forbidden
    assert "contract weakening" in forbidden
    assert "synthetic duplication" in forbidden
    assert audit["golden_rewrite"] is False
    assert audit["product_eligibility_extension"] is False
    assert audit["runtime_rollout"] is False

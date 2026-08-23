"""Freeze tests for T2 Broader Validation Phase A Contract (no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.t2_broader_contract import (
    CONTRACT_NAME,
    FORBIDDEN_LABELS,
    SCHEMA_VERSION,
    STAGE,
    assert_design_invariants,
    load_t2_broader_validation_contract,
)
from app.services.agent.tool_guidance_hints import _TERMINATION_CONTRACTS
from app.services.agent.tools.registry import READ_ONLY_TOOL_NAMES


def test_t2_phase_a_contract_loads_and_passes_invariants() -> None:
    contract = load_t2_broader_validation_contract()
    assert_design_invariants(contract)
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["stage"] == STAGE
    assert contract["contract_name"] == CONTRACT_NAME
    assert contract["design_verdict"]["phase_a_status"] == "PASS_FROZEN"
    assert contract["phase_a_freeze"]["PHASE_A_CONTRACT"] == "VALID"
    assert contract["phase_a_freeze"]["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert contract["phase_a_freeze"]["ready_for_phase_b"] == "YES"
    assert contract["phase_a_freeze"]["runtime_rollout"] == "NO"


def test_t2_phase_a_forbids_overclaim_labels() -> None:
    contract = load_t2_broader_validation_contract()
    for label in FORBIDDEN_LABELS:
        assert label in contract["forbidden_labels"]
        assert contract["contract_name"] != label
        assert label in contract["design_verdict"]["forbidden_claims"]
        assert label in contract["phase_a_freeze"]["does_not_claim"]
    assert (
        contract["success_criteria"]["BROADER_REAL_VALIDATED"]["status_under_phase_a"]
        == "NOT_CLAIMED_WAITS_FOR_PHASE_B"
    )
    assert contract["success_criteria"]["BROADER_REAL_VALIDATED"]["waits_for"] == "PHASE_B"


def test_t2_phase_a_positive_denominator_still_two() -> None:
    contract = load_t2_broader_validation_contract()
    positives = [
        c
        for c in contract["candidate_cases"]
        if c.get("include_in_broader_positive_denominator") is True
    ]
    assert {c["case_id"] for c in positives} == {"GQ-132", "GQ-149"}
    assert contract["denominators"]["broader_positive_denominator_phase_a"] == 2
    assert contract["denominators"]["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    for case in positives:
        gate = case["phase_a_positive_gate"]
        assert gate["runtime_executable"] is True
        assert gate["tool_exposed"] is True
        assert gate["observation_machine_verifiable"] is True
        assert gate["completion_predicate_clear"] is True
        assert gate["safe_terminal_verifiable"] is True
        assert gate["current_contract_valid"] is True


def test_t2_phase_a_gq131_eligibility_control_only() -> None:
    contract = load_t2_broader_validation_contract()
    gq131 = next(c for c in contract["candidate_cases"] if c["case_id"] == "GQ-131")
    assert gq131["role"] == "ELIGIBILITY_CONTROL"
    assert gq131["include_in_broader_positive_denominator"] is False
    assert gq131["include_as_eligibility_control"] is True
    assert gq131["t2_bound_today"] is False
    assert "why_not_in_positive_denominator" in gq131
    assert "T2 termination contracts do not bind" in gq131["why_not_in_positive_denominator"]
    assert contract["design_verdict"]["gq131_role"] == "ELIGIBILITY_CONTROL"


def test_t2_phase_a_hard_negative_contract_frozen() -> None:
    contract = load_t2_broader_validation_contract()
    hn = contract["hard_negative_contract"]
    assert hn["denominator"] == 8
    assert len(contract["hard_negatives"]) == 8
    assert hn["phase_a_status"] == "CONTRACT_FROZEN_NOT_EXECUTED"
    assert hn["gates"]["t2_false_positive_rate"] == "must_be_0"
    assert hn["gates"]["premature_finish_rate"] == "must_be_0"
    assert hn["gates"]["unsafe_finish_rate"] == "must_be_0"
    assert hn["gates"]["eligibility_precision"] == "must_be_1.0"
    assert hn["gates"]["no_satisfied_on_hard_negatives"] is True
    hn_strata = {h["stratum"] for h in contract["hard_negatives"]}
    required = {
        "tool_succeeded_but_wrong_observation",
        "partial_observation",
        "empty_result",
        "failed_tool",
        "conflicted_evidence",
        "missing_required_fact",
        "unsafe_completion_request",
        "ambiguous_task_completion",
    }
    assert required <= hn_strata
    assert set(hn["required_strata"]) == required


def test_t2_broader_contract_aligns_with_current_t2_bindings() -> None:
    contract = load_t2_broader_validation_contract()
    bound = {
        (row["case_id"], row["query"], row["expected_tool"])
        for row in contract["current_runtime_inventory"][
            "t2_termination_contracts_bound_today"
        ]
    }
    assert bound == set(_TERMINATION_CONTRACTS)


def test_t2_broader_contract_tools_match_readonly_inventory() -> None:
    contract = load_t2_broader_validation_contract()
    listed = set(contract["current_runtime_inventory"]["read_only_tools"])
    assert listed == set(READ_ONLY_TOOL_NAMES)


def test_t2_broader_contract_records_required_strata_and_gaps() -> None:
    contract = load_t2_broader_validation_contract()
    strata = contract["positive_strata"]
    assert strata["lookup_completion"]["status"] == "COVERED"
    assert strata["content_search_completion"]["status"] == "COVERED"
    assert strata["tool_result_structured_metadata"]["status"] == "COVERED"
    assert strata["document_search_completion"]["status"] == "GAP_T2_BOUND"
    assert strata["multi_step_final_completion"]["status"] == "GAP"
    assert strata["tool_result_exact_answer"]["status"] == "GAP"

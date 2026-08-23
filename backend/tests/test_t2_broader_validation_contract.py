"""Freeze tests for T2 broader validation design contract (no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.t2_broader_contract import (
    assert_design_invariants,
    load_t2_broader_validation_contract,
)
from app.services.agent.tool_guidance_hints import _TERMINATION_CONTRACTS
from app.services.agent.tools.registry import READ_ONLY_TOOL_NAMES


def test_t2_broader_contract_loads_and_passes_invariants() -> None:
    contract = load_t2_broader_validation_contract()
    assert_design_invariants(contract)
    assert contract["schema_version"] == "t2-broader-validation-contract-v1"
    assert contract["design_verdict"]["state"] == "PASS"
    assert contract["design_verdict"]["ready_for_real_local_broader_run"] == "YES"


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


def test_t2_broader_contract_excludes_unbound_gq131_from_positive_denom() -> None:
    contract = load_t2_broader_validation_contract()
    gq131 = next(c for c in contract["candidate_cases"] if c["case_id"] == "GQ-131")
    assert gq131["include_in_broader_positive_denominator"] is False
    assert gq131["include_as_eligibility_control"] is True
    assert gq131["t2_bound_today"] is False

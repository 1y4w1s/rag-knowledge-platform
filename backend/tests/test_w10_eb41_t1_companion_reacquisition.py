"""W10 E-B41 — T1 companion reacquisition deterministic tests.

No LLM / API / LM Studio / NLI / embeddings.
Does not write Formal results.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb40_response_mode_gate import (
    Applicability,
    ResponseMode,
    classify_response_mode,
    t2_t3_denominator_admits,
)
from tests.w10_eb41_t1_companion import (
    E_B_FORMAL_READY,
    FORMAL_OBSERVATION,
    FORMAL_T1_RESULT_WRITTEN,
    FROZEN_BASE_SHA,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PARENT_ACQUISITION_RUN,
    T1CandidateVerdict,
    T1CompanionError,
    assert_no_formal_result_artifacts,
    assert_scope_not_inferred_from_citations,
    candidate_summary,
    canonicalize_chunk_id,
    compute_subset,
    evaluate_suite,
    evaluate_t1_candidate,
    gold_dependency_note,
    load_companion_manifest,
    load_companion_record,
)


def test_frozen_base_sha_exact_on_all_records() -> None:
    manifest = load_companion_manifest()
    assert manifest["base_sha"] == FROZEN_BASE_SHA
    assert manifest["worktree_head"] == FROZEN_BASE_SHA
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["base_sha"] == FROZEN_BASE_SHA
    c12 = load_companion_record("C12")
    assert c12["base_sha"] == FROZEN_BASE_SHA


def test_c12_excluded_before_execution() -> None:
    c12 = load_companion_record("C12")
    assert c12["status"] == "INELIGIBLE_NOT_SCORED"
    assert c12.get("attempted_companion_capture") is False
    assert c12.get("gated_scope_ids") is None
    row = evaluate_t1_candidate(c12)
    assert row.candidate_verdict is T1CandidateVerdict.INELIGIBLE


def test_gated_scope_originates_from_product_execution() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        prov = rec["plan_scope_provenance"]
        assert prov["owner"] == "gen_plan.gated_chunks"
        assert "prepare_agent_generation" in prov["product_path"]
        assert prov["inferred_from_final_citations"] is False
        assert_scope_not_inferred_from_citations(rec)


def test_no_scope_inferred_from_final_citations() -> None:
    rec = deepcopy(load_companion_record("C01"))
    # Prove we refuse inference: inventing scope == finals would still fail provenance
    bad = deepcopy(rec)
    bad["plan_scope_provenance"]["inferred_from_final_citations"] = True
    with pytest.raises(T1CompanionError, match="inferred"):
        assert_scope_not_inferred_from_citations(bad)
    # Real records must keep gated ids independent provenance owner
    assert rec["gated_scope_ids"]
    assert rec["plan_scope_provenance"]["gold_constructed"] is False
    assert rec["plan_scope_provenance"]["eb18_compat"] is False


def test_same_trajectory_binding_enforced() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["same_trajectory_binding"] is True
        assert rec["T1_SAME_EXECUTION_BINDING_REQUIRED"] is True
        assert "same-run" in rec["final_citation_source"]
        assert rec["companion_run"] != PARENT_ACQUISITION_RUN
        assert rec["parent_acquisition_run"] == PARENT_ACQUISITION_RUN
        row = evaluate_t1_candidate(rec)
        assert row.t1_input_binding_valid is True
        assert row.same_trajectory is True

    # Cross-run splice must fail binding
    spliced = deepcopy(load_companion_record("C01"))
    spliced["same_trajectory_binding"] = False
    spliced["final_citation_source"] = "E-B38 real Product After (cross-run)"
    row = evaluate_t1_candidate(spliced)
    assert row.t1_input_binding_valid is False
    assert row.candidate_verdict is T1CandidateVerdict.BINDING_INVALID


def test_final_citation_subset_calculation_correct() -> None:
    holds, unique, out = compute_subset(
        ["A", "B"],
        ["a", "b", "c"],
    )
    assert holds is True
    assert unique == ("a", "b")
    assert out == ()

    holds2, unique2, out2 = compute_subset(["X", "A"], ["a"])
    assert holds2 is False
    assert "x" in out2
    assert unique2 == ("x", "a")


def test_out_of_scope_citation_fails_candidate_check() -> None:
    rec = deepcopy(load_companion_record("C01"))
    rec["final_citation_ids"] = list(rec["gated_scope_ids"]) + [
        "00000000-0000-0000-0000-000000000099"
    ]
    row = evaluate_t1_candidate(rec)
    assert row.t1_input_binding_valid is True
    assert row.subset_holds is False
    assert row.candidate_verdict is T1CandidateVerdict.VIOLATION
    assert row.out_of_scope_ids


def test_empty_scope_cases_handled_explicitly() -> None:
    # both empty → compliant (vacuous subset)
    both_empty = deepcopy(load_companion_record("C01"))
    both_empty["gated_scope_ids"] = []
    both_empty["gated_chunks_ordered"] = []
    both_empty["final_citation_ids"] = []
    both_empty["citations"] = []
    row1 = evaluate_t1_candidate(both_empty)
    assert "empty_scope_and_empty_citations" in row1.edge_cases
    assert row1.subset_holds is True
    assert row1.candidate_verdict is T1CandidateVerdict.COMPLIANT

    # empty scope + nonempty citations → violation
    empty_scope = deepcopy(load_companion_record("C01"))
    empty_scope["gated_scope_ids"] = []
    empty_scope["gated_chunks_ordered"] = []
    row2 = evaluate_t1_candidate(empty_scope)
    assert "empty_scope_nonempty_citations" in row2.edge_cases
    assert row2.subset_holds is False
    assert row2.candidate_verdict is T1CandidateVerdict.VIOLATION

    # duplicates canonicalized
    dup = deepcopy(load_companion_record("C01"))
    cid = dup["gated_scope_ids"][0]
    dup["final_citation_ids"] = [cid, cid.upper()]
    row3 = evaluate_t1_candidate(dup)
    assert "duplicate_citation_ids" in row3.edge_cases
    assert row3.subset_holds is True
    assert len(row3.final_citation_ids_unique) == 1


def test_degraded_remains_t2_t3_not_applicable_but_t1_not_skipped() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["response_mode"] == "DEGRADED"
        # Response mode gate: T2/T3 still N/A
        # Build a minimal observed-shaped payload for classifier reuse
        observed_like = {
            "case_id": rec["case_id"],
            "capture_path_submode": rec["capture_path_submode"],
            "plan_refusal": rec["plan_refusal"],
            "llm_called": False,
            "content": rec["content"],
            "citations": rec["citations"],
        }
        classified = classify_response_mode(observed_like)
        assert classified.response_mode is ResponseMode.DEGRADED
        assert classified.t2_applicability is Applicability.NOT_APPLICABLE
        assert classified.t3_applicability is Applicability.NOT_APPLICABLE
        assert t2_t3_denominator_admits(ResponseMode.DEGRADED) is False

        # T1 still evaluated
        row = evaluate_t1_candidate(rec)
        assert row.candidate_verdict is not T1CandidateVerdict.INELIGIBLE
        assert "degraded_with_citations" in row.edge_cases or not rec["final_citation_ids"]


def test_no_llm_call_observed() -> None:
    manifest = load_companion_manifest()
    assert manifest["llm_called_observed_suite"] is False
    assert manifest["model_backend_identity"] == "none_no_llm"
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["llm_called_observed"] is False
        assert rec["llm_called"] is False


def test_no_formal_result_written() -> None:
    assert FORMAL_T1_RESULT_WRITTEN == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert FORMAL_OBSERVATION == "NOT_STARTED"
    assert_no_formal_result_artifacts()
    summary = candidate_summary()
    assert summary["is_formal_t1_result"] is False
    assert summary["FORMAL_T1_RESULT_WRITTEN"] == "NO"
    for row in summary["per_case"]:
        assert row["is_formal_t1_result"] is False


def test_suite_candidate_readiness_and_gold_not_blocker() -> None:
    rows = evaluate_suite()
    assert len(rows) == 12
    summary = candidate_summary(rows)
    assert summary["eligible_count"] == 11
    assert summary["candidate_compliant_count"] == 11
    assert summary["candidate_violation_count"] == 0
    assert summary["T1_INPUT_BINDING_VALID"] == "YES"
    assert summary["T1_COMPANION_CAPTURE_VALID"] == "YES"
    assert summary["T1_REAL_AFTER_INPUT_READY"] == "YES"
    assert summary["T2_REAL_AFTER_INPUT_READY"] == "NOT_APPLICABLE"
    assert summary["T3_REAL_AFTER_INPUT_READY"] == "NOT_APPLICABLE"
    note = gold_dependency_note()
    assert note["t1_depends_on_synthetic_authored_gold"] is False
    assert note["gold_kind_synthetic_authored_is_t1_blocker"] is False


def test_canonicalize_chunk_id() -> None:
    assert canonicalize_chunk_id(" ABC ") == "abc"
    assert canonicalize_chunk_id(123) == "123"


def test_manifest_companion_run_identity() -> None:
    manifest = load_companion_manifest()
    assert manifest["companion_run"].startswith("w10_showcase_narrow_")
    assert "eb41" in manifest["companion_run"]
    assert manifest["parent_acquisition_run"] == PARENT_ACQUISITION_RUN
    assert manifest["T1_COMPANION_REACQUISITION_EXECUTED"] == "YES"
    assert manifest["T1_COMPANION_CAPTURE_VALID"] == "YES"
    assert manifest["T1_GATED_SCOPE_SIGNAL_AVAILABLE"] == "YES"

"""W10 E-B40 — Degraded response semantics & real-After binding repair tests.

Deterministic only. No LLM / API / LM Studio / NLI / embedding classifier.
Does not write Formal results or enter Formal Observation.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb17_binding_gate import BindingPolicy, validate_binding
from tests.w10_eb18_gold_after_binding_compatibility import COMPAT_PATH
from tests.w10_eb40_real_after_binding import (
    E_B_FORMAL_READY as BIND_FORMAL,
    FORBIDS_EB18_COMPAT_FOR_PRODUCT_AFTER,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW as BIND_MAY_ENTER,
    REAL_AFTER_BINDING_V2_IMPLEMENTED,
    RealAfterBindingError,
    assert_not_eb18_compat_pack,
    bind_eb38_suite,
    build_real_after_binding_v2,
    gold_labels_snapshot,
    reacquisition_feasibility,
    t1_companion_status,
)
from tests.w10_eb40_response_mode_gate import (
    DEGRADED_SCORER_PATH_DEFINED,
    E_B_FORMAL_READY,
    EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH,
    FORMAL_OBSERVATION,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    RESPONSE_MODE_GATE_IMPLEMENTED,
    SCORER_APPLICABILITY_GAP,
    Applicability,
    DegradedBpPolicy,
    ResponseMode,
    ResponseModeGateError,
    classify_eb38_suite,
    classify_response_mode,
    degraded_bp_policy,
    gate_summary,
    historical_eb39_remains_blocked,
    load_eb38_record,
    metrics_surface_for_mode,
    refuse_perfect_score_for_non_answer,
    response_mode_signal_available,
    t2_t3_denominator_admits,
)


def test_response_mode_gate_implemented_and_formal_locked() -> None:
    summary = gate_summary()
    assert summary["gates"]["RESPONSE_MODE_GATE_IMPLEMENTED"] == "YES"
    assert RESPONSE_MODE_GATE_IMPLEMENTED == "YES"
    assert DEGRADED_SCORER_PATH_DEFINED == "YES"
    assert EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH == "CLOSED"
    assert SCORER_APPLICABILITY_GAP == "RESOLVED_FOR_RESPONSE_MODE"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert FORMAL_OBSERVATION == "NOT_STARTED"
    assert summary["rewrites_historical_result"] is False


def test_degraded_never_enters_t2_or_t3_denominator() -> None:
    assert t2_t3_denominator_admits(ResponseMode.DEGRADED) is False
    assert t2_t3_denominator_admits(ResponseMode.REFUSAL) is False
    assert t2_t3_denominator_admits(ResponseMode.ANSWER) is True
    for row in classify_eb38_suite():
        assert row.response_mode is ResponseMode.DEGRADED
        assert row.t2_applicability is Applicability.NOT_APPLICABLE
        assert row.t3_applicability is Applicability.NOT_APPLICABLE
        assert row.t2_t3_scorer_eligible is False
        assert t2_t3_denominator_admits(row.response_mode) is False


def test_degraded_cannot_receive_perfect_t2_t3_score() -> None:
    with pytest.raises(ResponseModeGateError, match="perfect score"):
        refuse_perfect_score_for_non_answer(ResponseMode.DEGRADED)
    with pytest.raises(ResponseModeGateError, match="perfect score"):
        refuse_perfect_score_for_non_answer(ResponseMode.REFUSAL)
    refuse_perfect_score_for_non_answer(ResponseMode.ANSWER)  # must not raise
    surface = metrics_surface_for_mode(ResponseMode.DEGRADED)
    assert surface["t2_t3_claim_scoring"] == "NOT_APPLICABLE"
    assert surface["counts_as_model_quality"] is False


def test_refusal_and_degraded_remain_distinct() -> None:
    degraded = {
        "case_id": "X-degraded",
        "capture_path_submode": "product_stream_degraded",
        "plan_refusal": False,
        "llm_called": False,
        "citations": [{"chunk_id": "c1", "excerpt": "x"}],
    }
    refusal = {
        "case_id": "X-refusal",
        "capture_path_submode": "product_stream_refusal",
        "plan_refusal": True,
        "llm_called": False,
        "citations": [],
    }
    d = classify_response_mode(degraded)
    r = classify_response_mode(refusal)
    assert d.response_mode is ResponseMode.DEGRADED
    assert r.response_mode is ResponseMode.REFUSAL
    assert d.response_mode != r.response_mode
    assert d.bp_class_v2 == "BP_D_DEGRADED_PRODUCT_AFTER"
    assert r.bp_class_v2 == "BP_C_REFUSAL_EXCLUDE"
    assert r.t2_applicability is Applicability.ROUTE_REFUSAL_T4


def test_answer_remains_potentially_scorer_eligible() -> None:
    answer = {
        "case_id": "X-answer",
        "capture_mode": "product_stream",
        "plan_refusal": False,
        "llm_called": True,
        "citations": [{"chunk_id": "c1", "excerpt": "x"}],
    }
    assert response_mode_signal_available(answer) is True
    row = classify_response_mode(answer)
    assert row.response_mode is ResponseMode.ANSWER
    assert row.t2_applicability is Applicability.POTENTIALLY_ELIGIBLE
    assert row.t3_applicability is Applicability.POTENTIALLY_ELIGIBLE
    assert t2_t3_denominator_admits(row.response_mode) is True


def test_citations_nonempty_do_not_force_answer() -> None:
    record = load_eb38_record("C01")
    assert record["citations"]  # nonempty
    row = classify_response_mode(record)
    assert row.response_mode is ResponseMode.DEGRADED


def test_eb38_classifies_only_from_allowed_deterministic_signal() -> None:
    rows = classify_eb38_suite()
    assert len(rows) == 11
    for row in rows:
        assert row.signal_available is True
        assert row.classification_signal.startswith("capture_path_submode=")
        assert row.llm_called is False
        assert row.capture_submode == "product_stream_degraded"
        assert row.response_mode is ResponseMode.DEGRADED


def test_historical_eb39_remains_blocked_under_old_protocol() -> None:
    blocked = historical_eb39_remains_blocked()
    assert blocked["REAL_AFTER_BINDING_COMPLETE"] == "NO"
    assert blocked["SCORER_APPLICABILITY_GAP"] == "YES"
    assert blocked["BLOCKED_PENDING_PROTOCOL_REPAIR"] == "YES"
    assert blocked["rewrites_historical_result"] == "NO"

    # Old E-B17 BP-A gate still INCOMPATIBLE on unrebounded synthetic gold.
    ledger = load_claim_gold_ledger()
    gold = next(c for c in ledger["cases"] if c["case_id"].startswith("C01-"))
    record = load_eb38_record("C01")
    result = validate_binding(
        after_case_id=str(record["case_id"]),
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content_hash=str(record["observed_content_hash"]),
    )
    assert result.verdict.value == "INCOMPATIBLE"
    assert result.t2_t3_eligible is False


def test_real_after_hash_binding_does_not_rewrite_gold_labels() -> None:
    ledger = load_claim_gold_ledger()
    gold = deepcopy(next(c for c in ledger["cases"] if c["case_id"].startswith("C01-")))
    before = gold_labels_snapshot(gold)
    record = load_eb38_record("C01")
    binding = build_real_after_binding_v2(observed_record=record, gold_case=gold)
    assert binding.gold_labels_preserved is True
    assert gold_labels_snapshot(gold) == before
    assert binding.response_mode == ResponseMode.DEGRADED.value
    assert binding.t2_t3_scorer_eligible is False
    assert binding.t2_applicability == Applicability.NOT_APPLICABLE.value
    assert binding.t3_applicability == Applicability.NOT_APPLICABLE.value
    assert binding.provenance_bound is True
    assert REAL_AFTER_BINDING_V2_IMPLEMENTED == "YES"
    assert BIND_FORMAL == "NO"
    assert BIND_MAY_ENTER == "NO"


def test_synthetic_eb18_compat_pack_forbidden_for_product_after() -> None:
    assert FORBIDS_EB18_COMPAT_FOR_PRODUCT_AFTER == "YES"
    assert COMPAT_PATH.is_file()
    with pytest.raises(RealAfterBindingError, match="E-B18"):
        assert_not_eb18_compat_pack(COMPAT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(RealAfterBindingError, match="E-B18"):
        assert_not_eb18_compat_pack({"notes": "author_owned claim embedding"})


def test_no_formal_result_written() -> None:
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert FORMAL_OBSERVATION == "NOT_STARTED"
    bindings = bind_eb38_suite()
    assert len(bindings) == 11
    assert all(b.t2_t3_scorer_eligible is False for b in bindings)
    assert all(b.response_mode == ResponseMode.DEGRADED.value for b in bindings)
    for b in bindings:
        payload = b.to_dict()
        assert "unsupported_rate" not in payload
        assert "grounded_rate" not in payload
        assert "formal_score" not in payload


def test_degraded_bp_policy_is_versioned_bp_d() -> None:
    assert degraded_bp_policy() is DegradedBpPolicy.VERSIONED_BP_D


def test_t1_requires_companion_reacquisition() -> None:
    record = load_eb38_record("C01")
    status = t1_companion_status(record)
    assert status["T1_REAL_AFTER_INPUT_READY"] == "NO"
    assert status["T1_REQUIRES_COMPANION_REACQUISITION"] == "YES"
    feas = reacquisition_feasibility()
    assert feas["REACQUISITION_WITH_SAME_FROZEN_BASELINE_FEASIBLE"] == "YES"
    assert feas["requires_backend_app_change"] == "NO"
    assert feas["t1_scope_companion_reacquisition_needed"] == "YES"
    assert feas["response_mode_signal_reacquisition_needed"] == "NO"


def test_signal_insufficient_does_not_nlp_guess() -> None:
    bare = {"case_id": "X-bare", "content": "看起来像答案", "citations": []}
    assert response_mode_signal_available(bare) is False
    row = classify_response_mode(bare)
    assert row.response_mode is None
    assert row.signal_available is False
    assert row.t2_applicability is Applicability.SIGNAL_INSUFFICIENT

"""W10 E-B19 — T2/T3 Scorer Contract Design tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb17_binding_gate import BindingPolicy, BindingVerdict
from tests.w10_eb18_gold_after_binding_compatibility import (
    load_compatibility_pack,
    materialize_compatibility_case,
)
from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb19_t2_t3_scorer_contract import (
    ARTIFACT_KIND,
    E_B_FORMAL_READY,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PROTOCOL_VERSION,
    T2_T3_SCORER_CONTRACT_DESIGNED,
    T2_T3_SCORER_IMPLEMENTED,
    ScorerContractError,
    ScorerStatus,
    edge_case_fixtures,
    evaluate_g1,
    evaluate_g2,
    readiness_summary,
    remaining_blockers,
    score_t2,
    score_t3,
    scorer_contract_schema,
    validate_t2_case_result_shape,
    validate_t3_case_result_shape,
)


def test_contract_schema_frozen() -> None:
    schema = scorer_contract_schema()
    assert schema["protocol_version"] == PROTOCOL_VERSION
    assert schema["artifact_kind"] == ARTIFACT_KIND
    assert schema["inputs"]["t2"] == ["observed_after", "claim_gold", "binding_policy"]
    assert "unsupported_rate" in schema["outputs"]["t2"]
    assert "g1" in schema["formulas"]
    assert "g2" in schema["formulas"]
    assert schema["matching"]["no_fuzzy"] is True
    assert schema["matching"]["no_nli"] is True
    assert schema["matching"]["no_llm_judge"] is True
    assert schema["matching"]["no_critic_oracle"] is True
    assert schema["gates"]["T2_T3_SCORER_CONTRACT_DESIGNED"] == "YES"
    assert schema["gates"]["T2_T3_SCORER_IMPLEMENTED"] == "NO"
    assert schema["gates"]["E-B_FORMAL_READY"] == "NO"


def test_readiness_keeps_formal_and_implemented_no() -> None:
    summary = readiness_summary()
    assert summary["T2_T3_SCORER_CONTRACT_DESIGNED"] == "YES"
    assert summary["T2_T3_SCORER_IMPLEMENTED"] == "NO"
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["MAY_ENTER_FORMAL_OBSERVATION_WINDOW"] == "NO"
    assert summary["claims"]["scorer_contract_designed"] is True
    assert summary["claims"]["scorer_implemented"] is False
    assert summary["claims"]["formal_observation"] is False
    assert T2_T3_SCORER_CONTRACT_DESIGNED == "YES"
    assert T2_T3_SCORER_IMPLEMENTED == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"


def test_remaining_blockers_list_scorer_contract_only() -> None:
    blockers = {b["id"]: b for b in remaining_blockers()}
    assert blockers["AG-3"]["status"] == "PARTIAL"
    assert "CONTRACT" in blockers["SCORER"]["status"]
    assert blockers["GATE"]["status"] == "NO"


def test_t2_unsupported_rate_formula_on_mixed_labels() -> None:
    """C03-style: 1 supported + 1 unsupported → rate 0.5; unverifiable not numerator."""
    fixtures = edge_case_fixtures()
    # Build mixed from F1 content + extra unverifiable on same bind body
    after = deepcopy(fixtures["F1"]["after"])
    gold = deepcopy(fixtures["F1"]["gold"])
    gold["asserted_claims"] = [
        {
            "claim_id": "mix::u",
            "text": "备份保留 999 天。",
            "label": "unsupported",
            "supporting_evidence_ids": [],
            "support_span_notes": "u",
        },
        {
            "claim_id": "mix::s",
            "text": "备份保留 999 天。",
            "label": "supported",
            "supporting_evidence_ids": ["E1"],
            "support_span_notes": "forced for formula smoke",
        },
        {
            "claim_id": "mix::v",
            "text": "备份保留 999 天。",
            "label": "unverifiable",
            "supporting_evidence_ids": [],
            "support_span_notes": "v",
        },
    ]
    result = score_t2(
        observed_after=after,
        claim_gold=gold,
        binding_policy=BindingPolicy.BP_A,
    )
    assert result.status is ScorerStatus.OBSERVED_SLOT
    assert result.asserted_claim_count == 3
    assert result.unsupported_claim_count == 1
    assert result.unsupported_rate == pytest.approx(1 / 3)
    assert result.label_counts["unverifiable"] == 1
    assert result.formal_measurement is False
    assert result.contract_only is True
    validate_t2_case_result_shape(result.to_dict())


def test_t2_not_applicable_on_empty_claims() -> None:
    fx = edge_case_fixtures()["F6"]
    result = score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_A,
    )
    assert result.status is ScorerStatus.NOT_APPLICABLE
    assert result.unsupported_rate is None
    validate_t2_case_result_shape(result.to_dict())


def test_t2_not_observed_when_target_excluded() -> None:
    fx = edge_case_fixtures()["S1"]
    result = score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        targets_include_t2=False,
    )
    assert result.status is ScorerStatus.NOT_OBSERVED
    assert result.unsupported_rate is None


def test_t2_invalid_on_pool_drift() -> None:
    fx = edge_case_fixtures()["F8"]
    result = score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_A,
    )
    assert result.status is ScorerStatus.INVALID
    assert result.unsupported_rate is None
    assert result.binding_verdict == BindingVerdict.INVALID.value


def test_t2_bp_c_excluded() -> None:
    fx = edge_case_fixtures()["S1"]
    result = score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_C,
    )
    assert result.status is ScorerStatus.NOT_APPLICABLE
    assert result.binding_verdict == BindingVerdict.EXCLUDED_T4.value


@pytest.mark.parametrize(
    "fid",
    ["F1", "F2", "F3", "F4", "F5", "F7", "S1"],
)
def test_edge_f_table_t2_rates(fid: str) -> None:
    fx = edge_case_fixtures()[fid]
    result = score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_A,
    )
    assert result.status is ScorerStatus.OBSERVED_SLOT
    assert result.unsupported_rate == pytest.approx(fx["expect_t2_rate"])


@pytest.mark.parametrize(
    "fid",
    ["F1", "F2", "F3", "F4", "F5", "F7", "S1"],
)
def test_edge_f_table_t3_g1_g2(fid: str) -> None:
    fx = edge_case_fixtures()[fid]
    result = score_t3(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_A,
        final_citations=fx["final_citations"],
        gated_chunks_ordered=fx["gated_chunks_ordered"],
        align_bucket=fx["align_bucket"],
    )
    assert result.status is ScorerStatus.OBSERVED_SLOT
    assert len(result.per_claim) == 1
    row = result.per_claim[0]
    assert row.g1 is fx["expect_g1"]
    assert row.g2 is fx["expect_g2"]
    assert row.grounded is fx["expect_grounded"]
    assert row.grounded == (row.g1 and row.g2)
    if "expect_grounded_rate" in fx:
        assert result.grounded_rate == pytest.approx(fx["expect_grounded_rate"])
    validate_t3_case_result_shape(result.to_dict())


def test_f6_f8_status_paths() -> None:
    f6 = edge_case_fixtures()["F6"]
    t2 = score_t2(observed_after=f6["after"], claim_gold=f6["gold"])
    t3 = score_t3(
        observed_after=f6["after"],
        claim_gold=f6["gold"],
        final_citations=f6["final_citations"],
        gated_chunks_ordered=f6["gated_chunks_ordered"],
        align_bucket=f6["align_bucket"],
    )
    assert t2.status is ScorerStatus.NOT_APPLICABLE
    assert t3.status is ScorerStatus.NOT_APPLICABLE

    f8 = edge_case_fixtures()["F8"]
    t2b = score_t2(observed_after=f8["after"], claim_gold=f8["gold"])
    t3b = score_t3(
        observed_after=f8["after"],
        claim_gold=f8["gold"],
        final_citations=f8["final_citations"],
        gated_chunks_ordered=f8["gated_chunks_ordered"],
        align_bucket=f8["align_bucket"],
    )
    assert t2b.status is ScorerStatus.INVALID
    assert t3b.status is ScorerStatus.INVALID


def test_g2_fragment_mark_resolves_exact_id() -> None:
    claim = {
        "claim_id": "x",
        "label": "supported",
        "supporting_evidence_ids": ["E1"],
    }
    g2, hits, _ = evaluate_g2(
        claim,
        final_citations=[],
        after_content="事实。[片段1]",
        gated_chunks_ordered=[{"chunk_id": "E1"}],
        align_bucket="shrink",
    )
    assert g2 is True
    assert hits == ("E1",)


def test_g2_keep_all_alone_not_true() -> None:
    claim = {
        "claim_id": "x",
        "label": "supported",
        "supporting_evidence_ids": ["E1"],
    }
    g2, hits, note = evaluate_g2(
        claim,
        final_citations=[{"chunk_id": "E2"}, {"chunk_id": "E3"}],
        after_content="无标记正文",
        gated_chunks_ordered=[{"chunk_id": "E1"}, {"chunk_id": "E2"}, {"chunk_id": "E3"}],
        align_bucket="keep_all",
    )
    assert g2 is False
    assert hits == ()
    assert "keep-all" in note


def test_g1_false_for_unsupported_and_unverifiable() -> None:
    observed = ["E1"]
    ok, _ = evaluate_g1(
        {"label": "unsupported", "supporting_evidence_ids": []},
        observed_evidence_ids=observed,
    )
    assert ok is False
    ok2, _ = evaluate_g1(
        {"label": "unverifiable", "supporting_evidence_ids": []},
        observed_evidence_ids=observed,
    )
    assert ok2 is False
    ok3, _ = evaluate_g1(
        {"label": "supported", "supporting_evidence_ids": ["E1"]},
        observed_evidence_ids=observed,
    )
    assert ok3 is True


def test_score_against_eb18_bp_a_compatibility_pack() -> None:
    """Contract smoke on E-B18 rebound pack (protocol wiring only)."""
    pack = load_compatibility_pack()
    case = next(c for c in pack["cases"] if str(c["after_snapshot"]["case_id"]).startswith("C01"))
    after = dict(case["after_snapshot"])
    gold = case["rebound_gold"]
    # Attach citations for G2 success path (exact id)
    eids = list(gold["gated_pool_binding"]["evidence_ids"])
    after["final_citations"] = [{"chunk_id": eids[0]}]
    t2 = score_t2(observed_after=after, claim_gold=gold, binding_policy=BindingPolicy.BP_A)
    t3 = score_t3(
        observed_after=after,
        claim_gold=gold,
        binding_policy=BindingPolicy.BP_A,
        final_citations=after["final_citations"],
        gated_chunks_ordered=[{"chunk_id": eid} for eid in eids],
        align_bucket="shrink",
    )
    assert t2.status is ScorerStatus.OBSERVED_SLOT
    assert t2.binding_verdict == BindingVerdict.BOUND.value
    assert t2.unsupported_rate == pytest.approx(0.0)
    assert t3.status is ScorerStatus.OBSERVED_SLOT
    assert t3.grounded_rate == pytest.approx(1.0)
    assert t3.per_claim[0].g1 is True
    assert t3.per_claim[0].g2 is True
    assert t2.formal_measurement is False
    assert t3.contract_only is True


def test_c03_unsupported_rate_from_materialized_compat() -> None:
    ledger = load_claim_gold_ledger()
    human = next(c for c in ledger["cases"] if str(c["case_id"]).startswith("C03"))
    case = materialize_compatibility_case(human)
    after = dict(case.after_snapshot)
    gold = case.rebound_gold
    t2 = score_t2(observed_after=after, claim_gold=gold)
    assert t2.status is ScorerStatus.OBSERVED_SLOT
    # C03: one supported + one unsupported
    assert t2.asserted_claim_count == 2
    assert t2.unsupported_claim_count == 1
    assert t2.unsupported_rate == pytest.approx(0.5)


def test_shape_validator_rejects_fake_formal() -> None:
    fx = edge_case_fixtures()["S1"]
    result = score_t2(observed_after=fx["after"], claim_gold=fx["gold"])
    payload = result.to_dict()
    payload["formal_measurement"] = True
    with pytest.raises(ScorerContractError, match="formal_measurement"):
        validate_t2_case_result_shape(payload)


def test_shape_validator_rejects_grounded_not_g1_and_g2() -> None:
    fx = edge_case_fixtures()["S1"]
    result = score_t3(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        final_citations=fx["final_citations"],
        gated_chunks_ordered=fx["gated_chunks_ordered"],
        align_bucket=fx["align_bucket"],
    )
    payload = result.to_dict()
    payload["per_claim"][0]["grounded"] = True
    payload["per_claim"][0]["g2"] = False
    with pytest.raises(ScorerContractError, match="g1"):
        validate_t3_case_result_shape(payload)


def test_forbidden_keys_rejected_on_gold() -> None:
    fx = edge_case_fixtures()["S1"]
    gold = deepcopy(fx["gold"])
    gold["llm_judge"] = True
    with pytest.raises(ScorerContractError, match="forbidden"):
        score_t2(observed_after=fx["after"], claim_gold=gold)

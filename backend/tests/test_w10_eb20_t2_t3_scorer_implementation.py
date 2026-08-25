"""W10 E-B20 — T2/T3 Scorer Implementation tests (deterministic · zero LLM)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb17_binding_gate import BindingPolicy, BindingVerdict
from tests.w10_eb18_gold_after_binding_compatibility import load_compatibility_pack
from tests.w10_eb19_t2_t3_scorer_contract import (
    T2_T3_SCORER_IMPLEMENTED as EB19_IMPLEMENTED,
    ScorerStatus,
)
from tests.w10_eb2_generation_observation_contract import (
    STATUS_INELIGIBLE,
    STATUS_NOT_OBSERVED,
    STATUS_OBSERVED_SLOT,
)
from tests.w10_eb20_t2_t3_scorer_implementation import (
    ARTIFACT_KIND,
    E_B_FORMAL_READY,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PROTOCOL_VERSION,
    T2_T3_SCORER_CONTRACT_DESIGNED,
    T2_T3_SCORER_IMPLEMENTED,
    ScorerImplementationError,
    build_implementation_artifact,
    edge_case_fixtures,
    execute_score_t2,
    execute_score_t3,
    map_scorer_status_to_grounding_observation,
    readiness_summary,
    remaining_blockers,
    score_compat_case,
    validate_implementation_artifact,
    validate_implementation_t2_shape,
    validate_implementation_t3_shape,
)


def test_gates_flip_implemented_keep_formal_no() -> None:
    summary = readiness_summary()
    assert summary["T2_T3_SCORER_CONTRACT_DESIGNED"] == "YES"
    assert summary["T2_T3_SCORER_IMPLEMENTED"] == "YES"
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["MAY_ENTER_FORMAL_OBSERVATION_WINDOW"] == "NO"
    assert summary["claims"]["scorer_implemented"] is True
    assert summary["claims"]["scorer_implementation_tests_only"] is True
    assert summary["claims"]["formal_observation"] is False
    assert summary["claims"]["product_faithfulness_proven"] is False
    assert T2_T3_SCORER_IMPLEMENTED == "YES"
    assert T2_T3_SCORER_CONTRACT_DESIGNED == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    # E-B19 historical freeze remains contract-only
    assert EB19_IMPLEMENTED == "NO"


def test_remaining_blockers_scorer_implemented_tests_only() -> None:
    blockers = {b["id"]: b for b in remaining_blockers()}
    assert blockers["SCORER"]["status"] == "IMPLEMENTED_TESTS_ONLY"
    assert blockers["GATE"]["status"] == "NO"
    assert blockers["FORMAL_WIREUP"]["status"] == "OPEN"
    assert blockers["AG-3"]["status"] == "PARTIAL"
    assert "IMPLEMENTED" in blockers["AG-3"]["detail"]


def test_status_map_to_eb2_honesty() -> None:
    assert (
        map_scorer_status_to_grounding_observation(ScorerStatus.OBSERVED_SLOT)
        == STATUS_OBSERVED_SLOT
    )
    assert (
        map_scorer_status_to_grounding_observation(ScorerStatus.NOT_APPLICABLE)
        == STATUS_NOT_OBSERVED
    )
    assert (
        map_scorer_status_to_grounding_observation(ScorerStatus.INVALID)
        == STATUS_INELIGIBLE
    )
    assert (
        map_scorer_status_to_grounding_observation(ScorerStatus.INCOMPATIBLE)
        == STATUS_INELIGIBLE
    )


def test_execute_t2_t3_on_edge_fixtures_deterministic() -> None:
    fixtures = edge_case_fixtures()

    f1 = fixtures["F1"]
    t2 = execute_score_t2(observed_after=f1["after"], claim_gold=f1["gold"])
    assert t2["status"] == ScorerStatus.OBSERVED_SLOT.value
    assert t2["unsupported_rate"] == pytest.approx(1.0)
    assert t2["protocol_version"] == PROTOCOL_VERSION
    assert t2["artifact_kind"] == ARTIFACT_KIND
    assert t2["formal_measurement"] is False
    assert t2["implementation_only"] is True
    assert t2["contract_only"] is False
    validate_implementation_t2_shape(t2)

    s1 = fixtures["S1"]
    t3 = execute_score_t3(
        observed_after=s1["after"],
        claim_gold=s1["gold"],
        final_citations=s1["final_citations"],
        gated_chunks_ordered=s1["gated_chunks_ordered"],
        align_bucket=s1["align_bucket"],
    )
    assert t3["status"] == ScorerStatus.OBSERVED_SLOT.value
    assert t3["grounded_rate"] == pytest.approx(1.0)
    assert t3["per_claim"][0]["g1"] is True
    assert t3["per_claim"][0]["g2"] is True
    assert t3["per_claim"][0]["grounded"] is True
    validate_implementation_t3_shape(t3)

    f6 = fixtures["F6"]
    t2_na = execute_score_t2(observed_after=f6["after"], claim_gold=f6["gold"])
    assert t2_na["status"] == ScorerStatus.NOT_APPLICABLE.value
    assert t2_na["unsupported_rate"] is None

    f8 = fixtures["F8"]
    t2_inv = execute_score_t2(observed_after=f8["after"], claim_gold=f8["gold"])
    assert t2_inv["status"] == ScorerStatus.INVALID.value


def test_labels_only_from_gold_never_relabel() -> None:
    fx = edge_case_fixtures()["F1"]
    gold = deepcopy(fx["gold"])
    # Scorer must trust gold label even if text looks "supported"
    gold["asserted_claims"][0]["label"] = "unsupported"
    t2 = execute_score_t2(observed_after=fx["after"], claim_gold=gold)
    assert t2["unsupported_rate"] == pytest.approx(1.0)
    assert t2["label_counts"]["unsupported"] == 1


def test_exact_citation_grounding_no_fuzzy() -> None:
    fx = edge_case_fixtures()["F4"]
    t3 = execute_score_t3(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        final_citations=fx["final_citations"],
        gated_chunks_ordered=fx["gated_chunks_ordered"],
        align_bucket=fx["align_bucket"],
    )
    assert t3["per_claim"][0]["g1"] is True
    assert t3["per_claim"][0]["g2"] is False
    assert t3["per_claim"][0]["grounded"] is False


def test_forbidden_oracle_keys_rejected() -> None:
    fx = edge_case_fixtures()["S1"]
    gold = deepcopy(fx["gold"])
    gold["expected_action"] = "answer"
    with pytest.raises(ScorerImplementationError, match="forbidden"):
        execute_score_t2(observed_after=fx["after"], claim_gold=gold)


def test_score_compat_pack_wires_observed_slot_honesty() -> None:
    pack = load_compatibility_pack()
    case = next(
        c for c in pack["cases"] if str(c["after_snapshot"]["case_id"]).startswith("C01")
    )
    # Honest empty citations on author-owned After → G2 false, still OBSERVED_SLOT
    record = score_compat_case(case, attach_gold_supporting_pointers=False)
    assert record.grounding_observation_status == STATUS_OBSERVED_SLOT
    assert record.refusal_observation_status == STATUS_NOT_OBSERVED
    assert record.t2["status"] == ScorerStatus.OBSERVED_SLOT.value
    assert record.t2["binding_verdict"] == BindingVerdict.BOUND.value
    assert record.t2["unsupported_rate"] == pytest.approx(0.0)
    assert record.t3["status"] == ScorerStatus.OBSERVED_SLOT.value
    assert record.t3["per_claim"][0]["g1"] is True
    assert record.t3["per_claim"][0]["g2"] is False
    assert record.honesty["product_faithfulness_proven"] is False
    assert record.honesty["t3_pointer_source"] == "after_final_citations"

    # Wiring-only gold pointers → G2 true (still not product faithfulness)
    wired = score_compat_case(case, attach_gold_supporting_pointers=True)
    assert wired.t3["per_claim"][0]["g2"] is True
    assert wired.t3["grounded_rate"] == pytest.approx(1.0)
    assert wired.honesty["t3_pointer_source"] == "gold_supporting_ids_wiring_only"
    assert wired.honesty["product_faithfulness_proven"] is False


def test_c03_unsupported_rate_from_compat_pack() -> None:
    pack = load_compatibility_pack()
    case = next(
        c for c in pack["cases"] if str(c["after_snapshot"]["case_id"]).startswith("C03")
    )
    record = score_compat_case(case)
    assert record.t2["asserted_claim_count"] == 2
    assert record.t2["unsupported_claim_count"] == 1
    assert record.t2["unsupported_rate"] == pytest.approx(0.5)
    assert record.grounding_observation_status == STATUS_OBSERVED_SLOT


def test_build_and_validate_implementation_artifact() -> None:
    artifact = build_implementation_artifact(attach_gold_supporting_pointers=False)
    assert artifact["protocol_version"] == PROTOCOL_VERSION
    assert artifact["artifact_kind"] == ARTIFACT_KIND
    assert artifact["formal_measurement"] is False
    assert artifact["implementation_only"] is True
    assert artifact["gates"]["T2_T3_SCORER_IMPLEMENTED"] == "YES"
    assert artifact["gates"]["E-B_FORMAL_READY"] == "NO"
    assert artifact["honesty"]["product_faithfulness_proven"] is False
    assert artifact["summary"]["case_count"] >= 11
    assert artifact["summary"]["grounding_observed_slot_count"] >= 1
    for case in artifact["cases"]:
        assert case["grounding_observation_status"] in {
            STATUS_OBSERVED_SLOT,
            STATUS_NOT_OBSERVED,
            STATUS_INELIGIBLE,
        }
        assert case["honesty"]["product_faithfulness_proven"] is False
    validate_implementation_artifact(artifact)


def test_artifact_rejects_formal_flip() -> None:
    artifact = build_implementation_artifact()
    artifact["gates"]["E-B_FORMAL_READY"] = "YES"
    with pytest.raises(ScorerImplementationError, match="E-B_FORMAL_READY"):
        validate_implementation_artifact(artifact)


def test_artifact_rejects_fake_formal_measurement() -> None:
    artifact = build_implementation_artifact()
    artifact["formal_measurement"] = True
    with pytest.raises(ScorerImplementationError, match="formal_measurement"):
        validate_implementation_artifact(artifact)


def test_t2_shape_rejects_contract_only_true() -> None:
    fx = edge_case_fixtures()["S1"]
    payload = execute_score_t2(observed_after=fx["after"], claim_gold=fx["gold"])
    payload["contract_only"] = True
    with pytest.raises(ScorerImplementationError, match="contract_only"):
        validate_implementation_t2_shape(payload)


def test_bp_a_default_binding_policy() -> None:
    fx = edge_case_fixtures()["S1"]
    t2 = execute_score_t2(
        observed_after=fx["after"],
        claim_gold=fx["gold"],
        binding_policy=BindingPolicy.BP_A,
    )
    assert t2["binding_verdict"] == BindingVerdict.BOUND.value

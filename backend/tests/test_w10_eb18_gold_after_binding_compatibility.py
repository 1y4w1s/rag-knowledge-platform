"""W10 E-B18 — Gold↔After Binding Compatibility Materialization tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb17_binding_gate import (
    BindingPolicy,
    BindingVerdict,
    HashSpace,
    format_observed_content_hash,
    gold_ledger_digest_from_case,
    normalize_digest,
    observed_content_digest,
    refuse_naive_cross_space_compare,
    validate_binding,
)
from tests.w10_eb18_gold_after_binding_compatibility import (
    AFTER_SOURCE,
    ARTIFACT_KIND,
    COMPATIBILITY_MATERIALIZED,
    E_B_FORMAL_READY,
    GOLD_AFTER_BINDING_COMPATIBLE,
    LIVE_EB15_X_EB12B_COMPATIBLE,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PROTOCOL_VERSION,
    T2_T3_SCORER_IMPLEMENTED,
    CompatibilityError,
    assert_live_eb12b_still_incompatible_with_unrebounded_after,
    author_owned_after_body,
    hash_generation_rules,
    load_compatibility_pack,
    materialize_compatibility_case,
    materialize_compatibility_pack,
    materialize_from_human_gold,
    readiness_summary,
    remaining_blockers,
    validate_compatibility_case,
    validate_compatibility_pack,
    verify_bp_a_gold_content_hash,
    verify_evidence_pool_hash,
    verify_observed_content_hash,
)


def _c01(ledger: dict) -> dict:
    return next(c for c in ledger["cases"] if str(c["case_id"]).startswith("C01"))


def test_hash_rules_cover_three_spaces() -> None:
    rules = hash_generation_rules()
    assert set(rules) == {
        HashSpace.GOLD_LEDGER.value,
        HashSpace.OBSERVED_CONTENT.value,
        HashSpace.EVIDENCE_POOL.value,
    }
    assert "generate_bp_a" in rules[HashSpace.GOLD_LEDGER.value]
    assert "generate_bp_b" in rules[HashSpace.GOLD_LEDGER.value]
    assert "sha256:" in rules[HashSpace.OBSERVED_CONTENT.value]["wire"]


def test_hash_verify_helpers_agree_on_codec() -> None:
    content = "生产环境备份的保留期限为 30 天。"
    wire = format_observed_content_hash(content)
    bare = observed_content_digest(content)
    assert verify_observed_content_hash(content, wire)
    assert verify_bp_a_gold_content_hash(content, bare)
    assert normalize_digest(wire) == bare
    assert verify_evidence_pool_hash("a" * 64, "a" * 64)
    assert not verify_evidence_pool_hash("a" * 64, "b" * 64)


def test_materialize_single_case_binds_case_ids_and_bp_a() -> None:
    ledger = load_claim_gold_ledger()
    human = _c01(ledger)
    case = materialize_compatibility_case(human)
    assert case.after_snapshot["case_id"] == human["case_id"]
    assert case.rebound_gold["case_id"] == human["case_id"]
    assert case.binding_artifact["after_case_id"] == case.binding_artifact["gold_case_id"]
    assert case.binding_artifact["binding_policy"] == BindingPolicy.BP_A.value
    assert case.rebound_gold["content_binding"]["kind"] == BindingPolicy.BP_A.value
    assert case.binding_verdict == BindingVerdict.BOUND.value
    assert case.after_snapshot["after_source"] == AFTER_SOURCE
    assert case.after_snapshot["llm_called"] is False
    assert case.details["compatibility_proof_only"] is True
    assert case.details["product_faithfulness_proven"] is False

    # AG-1: parent BP-B payload digest ≠ rebound observed content digest
    parent_digest = gold_ledger_digest_from_case(human)
    rebound_digest = case.rebound_gold["content_binding"]["content_sha256"]
    assert parent_digest != rebound_digest
    assert verify_bp_a_gold_content_hash(
        case.after_snapshot["after_content"],
        rebound_digest,
    )


def test_validate_compatibility_case_roundtrip() -> None:
    ledger = load_claim_gold_ledger()
    case = materialize_compatibility_case(_c01(ledger)).to_dict()
    report = validate_compatibility_case(case)
    assert report["verdict"] == BindingVerdict.BOUND.value
    assert report["case_id"] == case["after_snapshot"]["case_id"]


def test_pack_materializes_all_claim_denominator_cases() -> None:
    pack = materialize_compatibility_pack()
    validate_compatibility_pack(pack)
    assert pack["protocol_version"] == PROTOCOL_VERSION
    assert pack["artifact_kind"] == ARTIFACT_KIND
    assert pack["gates"]["GOLD_AFTER_BINDING_COMPATIBLE"] == "YES"
    assert pack["gates"]["E-B_FORMAL_READY"] == "NO"
    assert pack["gates"]["LIVE_EB15_X_EB12B_COMPATIBLE"] == "NO"
    # C01–C11 have claims; C12 excluded
    assert len(pack["cases"]) == 11
    assert "C12-out-of-scope-provenance" in pack["excluded_case_ids"]
    ids = {c["after_snapshot"]["case_id"] for c in pack["cases"]}
    assert all(not cid.startswith("C12") for cid in ids)
    for case in pack["cases"]:
        validate_compatibility_case(case)


def test_case_id_mismatch_rejected() -> None:
    ledger = load_claim_gold_ledger()
    case = materialize_compatibility_case(_c01(ledger)).to_dict()
    case["rebound_gold"] = deepcopy(case["rebound_gold"])
    case["rebound_gold"]["case_id"] = "OTHER"
    with pytest.raises(CompatibilityError, match="case_id"):
        validate_compatibility_case(case)


def test_unrebounded_human_gold_still_incompatible_under_bp_a() -> None:
    assert_live_eb12b_still_incompatible_with_unrebounded_after()
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    body = author_owned_after_body(gold)
    # Even with claim texts present, unrebounded kind blocks BP-A.
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content=body,
        after_content_hash=format_observed_content_hash(body),
        observed_evidence_ids=list(gold["gated_pool_binding"]["evidence_ids"]),
        observed_pool_sha256=gold["gated_pool_binding"]["pool_sha256"],
    )
    assert result.verdict == BindingVerdict.INCOMPATIBLE
    assert refuse_naive_cross_space_compare(
        format_observed_content_hash(body),
        gold["content_binding"]["content_sha256"],
    ) == BindingVerdict.INCOMPATIBLE


def test_forbidden_formal_keys_rejected() -> None:
    pack = materialize_compatibility_pack()
    bad = deepcopy(pack)
    bad["unsupported_rate"] = 0.0
    with pytest.raises(CompatibilityError, match="forbidden key"):
        validate_compatibility_pack(bad)


def test_readiness_and_blockers() -> None:
    summary = readiness_summary()
    assert summary["COMPATIBILITY_MATERIALIZED"] == "YES"
    assert summary["GOLD_AFTER_BINDING_COMPATIBLE"] == "YES"
    assert summary["LIVE_EB15_X_EB12B_COMPATIBLE"] == "NO"
    assert summary["T2_T3_SCORER_IMPLEMENTED"] == "NO"
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["MAY_ENTER_FORMAL_OBSERVATION_WINDOW"] == "NO"
    assert COMPATIBILITY_MATERIALIZED == "YES"
    assert GOLD_AFTER_BINDING_COMPATIBLE == "YES"
    assert LIVE_EB15_X_EB12B_COMPATIBLE == "NO"
    assert T2_T3_SCORER_IMPLEMENTED == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert summary["claims"]["bp_a_codec_compatibility"] is True
    assert summary["claims"]["product_faithfulness_proven"] is False

    blockers = {b["id"]: b["status"] for b in remaining_blockers()}
    assert blockers["AG-1"] == "CLEARED_FOR_BP_A_REBOUND"
    assert blockers["AG-3"] == "PARTIAL"
    assert blockers["AG-5"] == "PARTIAL"
    assert blockers["GATE"] == "NO"
    assert blockers["SCORER"] == "NO"


def test_on_disk_pack_matches_materializer() -> None:
    # Ensure fixture is present and validates (written by materialize_from_human_gold).
    materialize_from_human_gold(write=True)
    on_disk = load_compatibility_pack()
    fresh = materialize_compatibility_pack()
    assert on_disk["protocol_version"] == fresh["protocol_version"]
    assert len(on_disk["cases"]) == len(fresh["cases"])
    for a, b in zip(on_disk["cases"], fresh["cases"], strict=True):
        assert a["after_snapshot"]["case_id"] == b["after_snapshot"]["case_id"]
        assert (
            a["rebound_gold"]["content_binding"]["content_sha256"]
            == b["rebound_gold"]["content_binding"]["content_sha256"]
        )
        assert a["binding_verdict"] == BindingVerdict.BOUND.value

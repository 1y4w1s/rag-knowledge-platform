"""W10 E-B17 — Binding Gate tests (deterministic · zero LLM · no formal score)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb17_binding_gate import (
    ARTIFACT_KIND,
    BINDING_GATE_IMPLEMENTED,
    E_B_FORMAL_READY,
    GOLD_AFTER_BINDING_COMPATIBLE,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PROTOCOL_VERSION,
    T2_T3_SCORER_IMPLEMENTED,
    BindingGateError,
    BindingPolicy,
    BindingVerdict,
    HashSpace,
    assert_formal_gates_remain_locked,
    assert_same_hash_space,
    build_binding_artifact,
    digests_equal,
    evidence_pool_digest,
    format_observed_content_hash,
    gold_claim_texts_digest,
    gold_ledger_digest_from_case,
    normalize_digest,
    observed_content_digest,
    policy_capabilities,
    readiness_summary,
    refuse_naive_cross_space_compare,
    remaining_blockers,
    validate_binding,
    validate_binding_artifact_shape,
)


def _c01(ledger: dict) -> dict:
    return next(c for c in ledger["cases"] if str(c["case_id"]).startswith("C01"))


def test_hash_spaces_are_separated() -> None:
    content = "生产环境备份的保留期限为 30 天。"
    observed = observed_content_digest(content)
    wire = format_observed_content_hash(content)
    assert wire == f"sha256:{observed}"
    assert normalize_digest(wire) == observed

    ledger_hash = gold_claim_texts_digest(
        "C01-fully-supported-exact",
        ["生产环境备份的保留期限为 30 天。"],
    )
    pool_hash = evidence_pool_digest(
        [{"chunk_id": "E1", "content": "backup retention 30 days"}]
    )

    assert observed != ledger_hash
    assert observed != pool_hash
    assert ledger_hash != pool_hash
    assert HashSpace.GOLD_LEDGER != HashSpace.OBSERVED_CONTENT
    assert HashSpace.EVIDENCE_POOL != HashSpace.GOLD_LEDGER


def test_refuse_cross_space_assert() -> None:
    with pytest.raises(BindingGateError, match="cross-space"):
        assert_same_hash_space(HashSpace.OBSERVED_CONTENT, HashSpace.GOLD_LEDGER)
    assert (
        refuse_naive_cross_space_compare("sha256:" + "a" * 64, "b" * 64)
        == BindingVerdict.INCOMPATIBLE
    )


def test_bp_a_bound_when_rebound_gold_matches_content() -> None:
    content = "正式产品 After 正文，含命题。"
    digest = observed_content_digest(content)
    gold = {
        "case_id": "CASE-A",
        "content_binding": {
            "kind": BindingPolicy.BP_A.value,
            "content_sha256": digest,
        },
        "gated_pool_binding": {
            "evidence_ids": ["E1"],
            "pool_sha256": evidence_pool_digest(
                [{"chunk_id": "E1", "content": "excerpt"}]
            ),
        },
        "asserted_claims": [
            {
                "claim_id": "CASE-A::c01",
                "text": "含命题",
                "label": "supported",
                "supporting_evidence_ids": ["E1"],
            }
        ],
    }
    pool = evidence_pool_digest([{"chunk_id": "E1", "content": "excerpt"}])
    result = validate_binding(
        after_case_id="CASE-A",
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content=content,
        after_content_hash=format_observed_content_hash(content),
        observed_evidence_ids=["E1", "E2"],
        observed_pool_sha256=pool,
    )
    assert result.verdict == BindingVerdict.BOUND
    assert result.t2_t3_eligible is True
    assert "product_path_faithfulness" in result.measurement_claims_allowed
    assert result.details["formal_candidate"] is True


def test_bp_a_incompatible_when_gold_still_synthetic() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content="anything",
        observed_evidence_ids=list(gold["gated_pool_binding"]["evidence_ids"]),
    )
    assert result.verdict == BindingVerdict.INCOMPATIBLE
    assert result.t2_t3_eligible is False
    assert any("observed_after" in r for r in result.reasons)


def test_bp_b_bound_with_author_owned_body_embedding_claims() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    claim_text = gold["asserted_claims"][0]["text"]
    body = f"Author-owned protocol body.\n{claim_text}\n(end)"
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_B,
        after_content=body,
        after_content_hash=format_observed_content_hash(body),
        observed_evidence_ids=list(gold["gated_pool_binding"]["evidence_ids"]),
        observed_pool_sha256=gold["gated_pool_binding"]["pool_sha256"],
    )
    assert result.verdict == BindingVerdict.BOUND
    assert result.t2_t3_eligible is True
    assert result.details["protocol_only"] is True
    assert result.details["formal_candidate"] is False
    assert "protocol_scorability_wiring_only" in result.measurement_claims_allowed
    # Ledger digest self-check matches on-disk gold.
    assert digests_equal(
        gold_ledger_digest_from_case(gold),
        gold["content_binding"]["content_sha256"],
        space=HashSpace.GOLD_LEDGER,
    )


def test_bp_b_invalid_when_eb15_style_body_lacks_claim_texts() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    degraded = "（系统暂时无法生成完整回答，请稍后重试。）"
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_B,
        after_content=degraded,
        after_content_hash=format_observed_content_hash(degraded),
        observed_evidence_ids=list(gold["gated_pool_binding"]["evidence_ids"]),
        observed_pool_sha256=gold["gated_pool_binding"]["pool_sha256"],
    )
    assert result.verdict == BindingVerdict.INVALID
    assert result.t2_t3_eligible is False
    assert any("presence fail" in r for r in result.reasons)


def test_bp_b_naive_hash_equality_is_not_a_bind_signal() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    after_hash = format_observed_content_hash("unrelated body")
    gold_hash = gold["content_binding"]["content_sha256"]
    # Cross-space compare is explicitly INCOMPATIBLE as a bind proof.
    assert refuse_naive_cross_space_compare(after_hash, gold_hash) == BindingVerdict.INCOMPATIBLE
    # Live material digests differ after normalize (expected under AG-1).
    assert normalize_digest(after_hash) != normalize_digest(gold_hash)

def test_bp_c_excludes_t2_t3() -> None:
    gold = {
        "case_id": "EB8-EMPTY-GATE-zh",
        "content_binding": {"kind": "synthetic_authored", "content_sha256": "a" * 64},
        "gated_pool_binding": {"evidence_ids": []},
        "asserted_claims": [],
    }
    result = validate_binding(
        after_case_id="EB8-EMPTY-GATE-zh",
        gold_case=gold,
        binding_policy=BindingPolicy.BP_C,
        after_content="知识库中未找到相关内容。",
    )
    assert result.verdict == BindingVerdict.EXCLUDED_T4
    assert result.t2_t3_eligible is False
    assert "refusal_behavior_t4" in result.measurement_claims_allowed


def test_case_id_mismatch_invalid() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    result = validate_binding(
        after_case_id="OTHER-CASE",
        gold_case=gold,
        binding_policy=BindingPolicy.BP_B,
        after_content=gold["asserted_claims"][0]["text"],
    )
    assert result.verdict == BindingVerdict.INVALID
    assert any("case_id mismatch" in r for r in result.reasons)


def test_pool_drift_invalidates_bp_b() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    claim_text = gold["asserted_claims"][0]["text"]
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_B,
        after_content=claim_text,
        observed_evidence_ids=["NOT-IN-GOLD"],
        observed_pool_sha256=gold["gated_pool_binding"]["pool_sha256"],
    )
    assert result.verdict == BindingVerdict.INVALID
    assert any("pool drift" in r for r in result.reasons)


def test_binding_artifact_shape_and_build() -> None:
    ledger = load_claim_gold_ledger()
    gold = _c01(ledger)
    artifact = build_binding_artifact(
        after_case_id=gold["case_id"],
        gold_case_id=gold["case_id"],
        binding_policy=BindingPolicy.BP_B,
        after_content_hash=format_observed_content_hash("x"),
        gold_case=gold,
        observed_evidence_ids=gold["gated_pool_binding"]["evidence_ids"],
        notes="protocol wiring probe",
    )
    validate_binding_artifact_shape(artifact)
    payload = artifact.to_dict()
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert payload["artifact_kind"] == ARTIFACT_KIND
    assert payload["after_case_id"] == payload["gold_case_id"]
    assert payload["binding_policy"] == BindingPolicy.BP_B.value

    bad = deepcopy(payload)
    bad["unsupported_rate"] = 0.1
    with pytest.raises(BindingGateError, match="forbidden key"):
        validate_binding_artifact_shape(bad)


def test_live_material_still_incompatible_summary() -> None:
    assert_formal_gates_remain_locked()
    summary = readiness_summary()
    assert summary["BINDING_GATE_IMPLEMENTED"] == "YES"
    assert summary["GOLD_AFTER_BINDING_COMPATIBLE"] == "NO"
    assert summary["T2_T3_SCORER_IMPLEMENTED"] == "NO"
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["MAY_ENTER_FORMAL_OBSERVATION_WINDOW"] == "NO"
    assert BINDING_GATE_IMPLEMENTED == "YES"
    assert GOLD_AFTER_BINDING_COMPATIBLE == "NO"
    assert T2_T3_SCORER_IMPLEMENTED == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"

    caps = policy_capabilities()
    assert caps["BP-A"]["role"] == "formal_candidate"
    assert caps["BP-B"]["role"] == "test_only"
    assert caps["BP-C"]["role"] == "t4_exclusion"

    blockers = {b["id"]: b["status"] for b in remaining_blockers()}
    assert blockers["AG-1"] == "OPEN"
    assert blockers["AG-3"] == "PARTIAL"
    assert blockers["AG-5"] == "OPEN"
    assert blockers["GATE"] == "NO"

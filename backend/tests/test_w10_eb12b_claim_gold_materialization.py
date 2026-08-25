"""W10 E-B12B — claim gold materialization tests (deterministic only)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb_generation_claim_gold_contract import (
    ARTIFACT_KIND,
    PARENT_OBSERVATION_PROTOCOL,
    PROTOCOL_VERSION,
    validate_claim_gold_ledger,
)
from tests.w10_eb12b_claim_gold_materialization import (
    ANNOTATION_STATUS_ANNOTATED,
    C12_CASE_ID,
    CREATED_BY,
    E_B_CLAIM_GOLD_ANNOTATED,
    E_B_FORMAL_READY,
    FORMAL_GOLD_PATH,
    ClaimGoldMaterializationError,
    assert_claim_gold_present_and_valid,
    claim_denominator_case_ids,
    contract_module_imports_are_llm_free,
    load_annotation_draft,
    load_claim_gold_ledger,
    materialization_status,
    materialize_claim_gold_ledger,
    sha256_hex,
    validate_annotated_draft_ready,
)


def test_formal_gold_present_valid_and_identity_frozen() -> None:
    ledger = assert_claim_gold_present_and_valid()
    assert FORMAL_GOLD_PATH.is_file()
    assert ledger["protocol_version"] == PROTOCOL_VERSION
    assert ledger["parent_observation_protocol"] == PARENT_OBSERVATION_PROTOCOL
    assert ledger["artifact_kind"] == ARTIFACT_KIND
    assert ledger["created_by"] == CREATED_BY
    assert "ANNOTATED" in str(ledger.get("notes", ""))
    assert E_B_CLAIM_GOLD_ANNOTATED == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert ANNOTATION_STATUS_ANNOTATED == "ANNOTATED"


def test_materialize_matches_on_disk_and_passes_eb9a() -> None:
    draft = load_annotation_draft()
    validate_annotated_draft_ready(draft)
    rebuilt = materialize_claim_gold_ledger(draft)
    on_disk = load_claim_gold_ledger()
    assert rebuilt == on_disk
    validate_claim_gold_ledger(on_disk)


def test_content_and_pool_hashes_bound() -> None:
    ledger = load_claim_gold_ledger()
    for case in ledger["cases"]:
        binding = case["content_binding"]
        assert binding["kind"] == "synthetic_authored"
        assert len(binding["content_sha256"]) == 64
        assert all(c in "0123456789abcdefABCDEF" for c in binding["content_sha256"])
        pool = case["gated_pool_binding"]
        assert isinstance(pool["pool_sha256"], str)
        assert len(pool["pool_sha256"]) == 64
        assert all(c in "0123456789abcdefABCDEF" for c in pool["pool_sha256"])
        assert "exclude_refusal_boilerplate" in case["denominator_policy"]


def test_c12_excluded_from_claim_denominator() -> None:
    ledger = load_claim_gold_ledger()
    denom = claim_denominator_case_ids(ledger)
    assert C12_CASE_ID not in denom
    assert len(denom) == 11
    c12 = next(case for case in ledger["cases"] if case["case_id"] == C12_CASE_ID)
    assert c12["asserted_claims"] == []
    assert "EXCLUDED_FROM_CLAIM_DENOMINATOR" in str(c12.get("notes", ""))


def test_eligible_cases_have_claims() -> None:
    ledger = load_claim_gold_ledger()
    total = 0
    for case in ledger["cases"]:
        if case["case_id"] == C12_CASE_ID:
            continue
        assert len(case["asserted_claims"]) >= 1
        total += len(case["asserted_claims"])
    assert total == 17


def test_no_forbidden_oracle_or_judge_keys() -> None:
    ledger = load_claim_gold_ledger()
    blob = str(ledger)
    for banned in (
        "expected_action",
        "oracle_cases",
        "llm_judge",
        "auto_label",
        "nli_label",
        "critic_score",
    ):
        assert banned not in blob


def test_status_report_gates() -> None:
    status = materialization_status()
    assert status["gates"]["E_B_CLAIM_GOLD_ANNOTATED"] == "YES"
    assert status["gates"]["E_B_FORMAL_READY"] == "NO"
    assert status["identities"]["annotation_status"] == ANNOTATION_STATUS_ANNOTATED
    assert status["c12"]["in_claim_denominator"] is False
    assert status["claims"]["llm"] is False
    assert status["claims"]["generation_observation"] is False
    assert status["claims"]["generation_result"] is False
    assert status["claims"]["formal_measurement"] is False


def test_c12_claims_rejected() -> None:
    draft = deepcopy(load_annotation_draft())
    for case in draft["cases"]:
        if case["case_id"] == C12_CASE_ID:
            case["claims"] = [
                {
                    "claim_id": f"{C12_CASE_ID}::c01",
                    "claim_text": "should not enter denominator",
                    "label": "supported",
                    "supporting_evidence_ids": ["E-OUT"],
                    "annotation_notes": "bad",
                }
            ]
            break
    with pytest.raises(ClaimGoldMaterializationError, match="claims=\\[\\]"):
        validate_annotated_draft_ready(draft)


def test_empty_eligible_claim_rejected() -> None:
    draft = deepcopy(load_annotation_draft())
    for case in draft["cases"]:
        if case["case_id"].startswith("C01-"):
            case["claims"] = []
            break
    with pytest.raises(ClaimGoldMaterializationError, match="≥1 human-annotated"):
        validate_annotated_draft_ready(draft)


def test_sha256_helper_deterministic() -> None:
    assert sha256_hex({"a": 1}) == sha256_hex({"a": 1})
    assert sha256_hex({"a": 1}) != sha256_hex({"a": 2})
    assert len(sha256_hex("x")) == 64


def test_no_llm_hooks_in_materialization_module() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb12b_claim_gold_materialization as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")

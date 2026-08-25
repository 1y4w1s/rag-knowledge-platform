"""W10 E-B9a — claim gold ledger schema/validator tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_generation_claim_gold_contract import (
    ARTIFACT_KIND,
    E_B_FORMAL_READY,
    FORBIDDEN_CRITIC_ORACLE_KEYS,
    FORBIDDEN_KEYS,
    FORBIDDEN_LLM_JUDGE_KEYS,
    GOLD_FILENAME,
    GOLD_PATH,
    PARENT_OBSERVATION_PROTOCOL,
    PROTOCOL_VERSION,
    SCHEMA_FILENAME,
    SCHEMA_PATH,
    ClaimGoldContractError,
    build_schema_example_ledger,
    clone_schema_example,
    contract_module_imports_are_llm_free,
    load_claim_gold_if_present,
    load_schema_document,
    validate_claim_gold_ledger,
)


def test_schema_example_passes_validation() -> None:
    payload = build_schema_example_ledger()
    validate_claim_gold_ledger(payload)
    assert payload["artifact_kind"] == ARTIFACT_KIND
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert len(payload["cases"]) == 1
    assert len(payload["cases"][0]["asserted_claims"]) == 3


def test_identity_constants_and_schema_file_frozen() -> None:
    assert PROTOCOL_VERSION == "w10_eb_generation_claim_gold_v1"
    assert PARENT_OBSERVATION_PROTOCOL == "w10_eb1_generation_observation_v1"
    assert ARTIFACT_KIND == "CLAIM_GOLD_LEDGER"
    assert E_B_FORMAL_READY == "NO"
    assert SCHEMA_PATH.is_file()
    assert SCHEMA_PATH.name == SCHEMA_FILENAME
    schema = load_schema_document()
    assert schema["properties"]["protocol_version"]["const"] == PROTOCOL_VERSION
    assert schema["properties"]["artifact_kind"]["const"] == ARTIFACT_KIND
    assert schema["properties"]["parent_observation_protocol"]["const"] == (
        PARENT_OBSERVATION_PROTOCOL
    )
    assert set(schema["required"]) >= {
        "protocol_version",
        "parent_observation_protocol",
        "artifact_kind",
        "created_by",
        "cases",
    }


def test_gold_annotation_file_present_and_valid() -> None:
    assert GOLD_FILENAME == "w10-eb-generation-claim-gold-v1.json"
    assert GOLD_PATH.name == GOLD_FILENAME
    assert GOLD_PATH.is_file()
    payload = load_claim_gold_if_present()
    assert payload is not None
    validate_claim_gold_ledger(payload)
    assert payload["artifact_kind"] == ARTIFACT_KIND
    assert payload["created_by"] == "human_annotator"
    assert E_B_FORMAL_READY == "NO"


def test_missing_header_fields_rejected() -> None:
    for field in (
        "protocol_version",
        "parent_observation_protocol",
        "artifact_kind",
        "created_by",
        "cases",
    ):
        payload = clone_schema_example()
        del payload[field]
        with pytest.raises(ClaimGoldContractError, match="missing fields"):
            validate_claim_gold_ledger(payload)


def test_missing_case_and_claim_fields_rejected() -> None:
    payload = clone_schema_example()
    del payload["cases"][0]["content_binding"]
    with pytest.raises(ClaimGoldContractError, match="missing fields"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    del payload["cases"][0]["asserted_claims"][0]["supporting_evidence_ids"]
    with pytest.raises(ClaimGoldContractError, match="missing fields"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    del payload["cases"][0]["asserted_claims"][0]["support_span_notes"]
    with pytest.raises(ClaimGoldContractError, match="missing fields"):
        validate_claim_gold_ledger(payload)


def test_content_hash_binding_required() -> None:
    payload = clone_schema_example()
    del payload["cases"][0]["content_binding"]["content_sha256"]
    with pytest.raises(ClaimGoldContractError, match="missing fields"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["cases"][0]["content_binding"]["content_sha256"] = "not-a-hash"
    with pytest.raises(ClaimGoldContractError, match="content hash"):
        validate_claim_gold_ledger(payload)


def test_supported_requires_evidence_ids() -> None:
    payload = clone_schema_example()
    claim = payload["cases"][0]["asserted_claims"][0]
    assert claim["label"] == "supported"
    claim["supporting_evidence_ids"] = []
    with pytest.raises(ClaimGoldContractError, match="supported requires"):
        validate_claim_gold_ledger(payload)


def test_evidence_ids_must_belong_to_gated_pool() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["asserted_claims"][0]["supporting_evidence_ids"] = [
        "foreign-evidence-id"
    ]
    with pytest.raises(ClaimGoldContractError, match="not in declared gated pool"):
        validate_claim_gold_ledger(payload)


def test_critic_oracle_fields_rejected() -> None:
    assert "expected_action" in FORBIDDEN_CRITIC_ORACLE_KEYS
    assert "oracle_cases" in FORBIDDEN_CRITIC_ORACLE_KEYS

    payload = clone_schema_example()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(ClaimGoldContractError, match="forbidden claim-gold"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["oracle_cases"] = [{"case_id": "C01"}]
    with pytest.raises(ClaimGoldContractError, match="forbidden claim-gold"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["cases"][0]["expected_action"] = "ACCEPT"
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["cases"][0]["asserted_claims"][0]["oracle_case"] = {"x": 1}
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)


def test_llm_judge_fields_rejected() -> None:
    assert "llm_judge" in FORBIDDEN_LLM_JUDGE_KEYS
    assert "nli_label" in FORBIDDEN_LLM_JUDGE_KEYS
    assert "judge_model" in FORBIDDEN_LLM_JUDGE_KEYS

    for key in ("llm_judge", "nli_label", "judge_model", "auto_label"):
        payload = clone_schema_example()
        payload[key] = "forbidden"
        with pytest.raises(ClaimGoldContractError, match="forbidden"):
            validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["cases"][0]["asserted_claims"][0]["llm_judge_label"] = "supported"
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["created_by"] = "llm_annotator"
    with pytest.raises(ClaimGoldContractError, match="forbidden as formal gold"):
        validate_claim_gold_ledger(payload)


def test_lexical_only_label_source_rejected() -> None:
    assert "label_source" in FORBIDDEN_KEYS
    payload = clone_schema_example()
    payload["cases"][0]["asserted_claims"][0]["label_source"] = "lexical_overlap"
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["cases"][0]["label_source"] = "token_overlap"
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)

    payload = clone_schema_example()
    payload["lexical_overlap_label"] = True
    with pytest.raises(ClaimGoldContractError, match="forbidden"):
        validate_claim_gold_ledger(payload)


def test_invalid_label_rejected() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["asserted_claims"][0]["label"] = "grounded"
    with pytest.raises(ClaimGoldContractError, match="label must be one of"):
        validate_claim_gold_ledger(payload)


def test_denominator_policy_must_exclude_refusal_boilerplate() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["denominator_policy"] = "include_everything"
    with pytest.raises(ClaimGoldContractError, match="denominator_policy"):
        validate_claim_gold_ledger(payload)


def test_eb_formal_ready_remains_no() -> None:
    assert E_B_FORMAL_READY == "NO"
    payload = load_claim_gold_if_present()
    assert payload is not None
    validate_claim_gold_ledger(payload)
    validate_claim_gold_ledger(build_schema_example_ledger())


def test_no_llm_hooks_in_contract_module() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb_generation_claim_gold_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")


def test_clone_does_not_mutate_builder() -> None:
    a = build_schema_example_ledger()
    b = clone_schema_example()
    b["created_by"] = "mutated"
    assert a["created_by"] != b["created_by"]
    validate_claim_gold_ledger(a)

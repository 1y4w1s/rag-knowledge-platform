"""W10 E-B9b — empty-gate companion suite contract tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_empty_gate_suite_contract import (
    ARTIFACT_KIND,
    CASE_COUNT,
    CASE_ID_PREFIX,
    CASES_FILENAME,
    CASES_PATH,
    E_B_EMPTY_GATE_CONTRACT_READY,
    E_B_FORMAL_READY,
    FORBIDDEN_CRITIC_ORACLE_KEYS,
    FORBIDDEN_KEYS,
    FORMAL_RESULT_FILENAME,
    FORMAL_RESULT_PATH,
    PARENT_OBSERVATION_PROTOCOL,
    PROTOCOL_VERSION,
    PURPOSE,
    REFUSAL_GOLD_EN,
    REFUSAL_GOLD_ZH,
    SCHEMA_FILENAME,
    SCHEMA_PATH,
    SUITE_ID,
    SUITE_STRATEGY,
    W9_CRITIC_SUITE_ID,
    EmptyGateSuiteContractError,
    assert_eb2_v1_identity_untouched,
    assert_formal_result_absent,
    assert_real_cases_file_present_and_valid,
    assert_refusal_gold_mirrors_product,
    build_schema_example_suite,
    clone_schema_example,
    contract_module_imports_are_llm_free,
    expected_no_context_reply_for,
    load_schema_document,
    validate_empty_gate_suite,
)


def test_schema_example_passes_validation() -> None:
    payload = build_schema_example_suite()
    validate_empty_gate_suite(payload)
    assert payload["suite_id"] == SUITE_ID
    assert payload["case_count"] == CASE_COUNT
    assert payload["purpose"] == PURPOSE
    assert len(payload["cases"]) == CASE_COUNT
    assert all(c["case_id"].startswith(CASE_ID_PREFIX) for c in payload["cases"])


def test_identity_constants_and_schema_file_frozen() -> None:
    assert PROTOCOL_VERSION == "w10_eb_empty_gate_v1"
    assert SUITE_ID == "w10_eb_empty_gate_v1"
    assert CASE_COUNT == 2
    assert PURPOSE == "empty_gate_refuse_ok"
    assert PARENT_OBSERVATION_PROTOCOL == "w10_eb1_generation_observation_v1"
    assert SUITE_STRATEGY == "S2_companion"
    assert ARTIFACT_KIND == "EMPTY_GATE_SUITE_SCHEMA_EXAMPLE"
    assert E_B_EMPTY_GATE_CONTRACT_READY == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert SUITE_ID != W9_CRITIC_SUITE_ID
    assert SCHEMA_PATH.is_file()
    assert SCHEMA_PATH.name == SCHEMA_FILENAME
    schema = load_schema_document()
    assert schema["properties"]["suite_id"]["const"] == SUITE_ID
    assert schema["properties"]["case_count"]["const"] == CASE_COUNT
    assert schema["properties"]["purpose"]["const"] == PURPOSE
    assert schema["properties"]["suite_strategy"]["const"] == SUITE_STRATEGY
    assert set(schema["required"]) >= {
        "protocol_version",
        "suite_id",
        "case_count",
        "purpose",
        "parent_observation_protocol",
        "suite_strategy",
        "artifact_kind",
        "cases",
    }


def test_real_cases_present_and_formal_result_absent() -> None:
    assert CASES_FILENAME == "w10-eb-empty-gate-cases.json"
    assert FORMAL_RESULT_FILENAME == "w10-eb-empty-gate-formal-result.json"
    assert CASES_PATH.name == CASES_FILENAME
    assert FORMAL_RESULT_PATH.name == FORMAL_RESULT_FILENAME
    assert_real_cases_file_present_and_valid()
    assert_formal_result_absent()
    assert CASES_PATH.exists()
    assert not FORMAL_RESULT_PATH.exists()


def test_missing_header_fields_rejected() -> None:
    for field in (
        "protocol_version",
        "suite_id",
        "case_count",
        "purpose",
        "parent_observation_protocol",
        "suite_strategy",
        "artifact_kind",
        "cases",
    ):
        payload = clone_schema_example()
        del payload[field]
        with pytest.raises(EmptyGateSuiteContractError, match="missing fields"):
            validate_empty_gate_suite(payload)


def test_missing_case_fields_rejected() -> None:
    for field in (
        "case_id",
        "query",
        "retrieval_result_state",
        "evidence_count",
        "expected_refusal",
        "no_context_reply_for",
    ):
        payload = clone_schema_example()
        del payload["cases"][0][field]
        with pytest.raises(EmptyGateSuiteContractError, match="missing fields"):
            validate_empty_gate_suite(payload)


def test_case_count_must_match_cases_length_and_n() -> None:
    payload = clone_schema_example()
    payload["case_count"] = 3
    with pytest.raises(EmptyGateSuiteContractError, match="case_count must be 2"):
        validate_empty_gate_suite(payload)

    payload = clone_schema_example()
    payload["cases"] = payload["cases"][:1]
    with pytest.raises(EmptyGateSuiteContractError, match="cases length must equal"):
        validate_empty_gate_suite(payload)


def test_w9_critic_suite_identity_rejected() -> None:
    payload = clone_schema_example()
    payload["suite_id"] = W9_CRITIC_SUITE_ID
    with pytest.raises(EmptyGateSuiteContractError, match="suite_id mismatch"):
        validate_empty_gate_suite(payload)


def test_critic_oracle_and_expected_action_rejected() -> None:
    assert "expected_action" in FORBIDDEN_CRITIC_ORACLE_KEYS
    assert "oracle_cases" in FORBIDDEN_CRITIC_ORACLE_KEYS
    assert "expected_action" in FORBIDDEN_KEYS

    payload = clone_schema_example()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(EmptyGateSuiteContractError, match="forbidden empty-gate"):
        validate_empty_gate_suite(payload)

    payload = clone_schema_example()
    payload["oracle_cases"] = [{"case_id": "C01"}]
    with pytest.raises(EmptyGateSuiteContractError, match="forbidden empty-gate"):
        validate_empty_gate_suite(payload)

    payload = clone_schema_example()
    payload["cases"][0]["expected_action"] = "ACCEPT"
    with pytest.raises(EmptyGateSuiteContractError, match="forbidden"):
        validate_empty_gate_suite(payload)

    payload = clone_schema_example()
    payload["w9_critic_oracle"] = {"x": 1}
    with pytest.raises(EmptyGateSuiteContractError, match="forbidden"):
        validate_empty_gate_suite(payload)


def test_formal_measurement_claim_keys_rejected() -> None:
    for key in (
        "measurement_validity",
        "formal_observation_result",
        "targets_measured",
        "formal_ready",
    ):
        payload = clone_schema_example()
        payload[key] = True
        with pytest.raises(EmptyGateSuiteContractError, match="forbidden"):
            validate_empty_gate_suite(payload)


def test_evidence_count_must_be_zero() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["evidence_count"] = 1
    with pytest.raises(EmptyGateSuiteContractError, match="evidence_count must be 0"):
        validate_empty_gate_suite(payload)


def test_expected_refusal_must_be_true() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["expected_refusal"] = False
    with pytest.raises(EmptyGateSuiteContractError, match="expected_refusal must be true"):
        validate_empty_gate_suite(payload)


def test_retrieval_result_state_enum() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["retrieval_result_state"] = "nonempty_weak_evidence"
    with pytest.raises(EmptyGateSuiteContractError, match="retrieval_result_state"):
        validate_empty_gate_suite(payload)


def test_case_id_prefix_and_no_w9_reuse() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["case_id"] = "C07-correct-insufficiency-refusal"
    with pytest.raises(EmptyGateSuiteContractError, match="prefix pattern"):
        validate_empty_gate_suite(payload)

    payload = clone_schema_example()
    payload["cases"][0]["case_id"] = "EB4-EMPTY-GATE-zh"
    with pytest.raises(EmptyGateSuiteContractError, match="prefix pattern"):
        validate_empty_gate_suite(payload)


def test_no_context_reply_for_must_match_language_band() -> None:
    payload = clone_schema_example()
    # Force ZH gold onto EN-band query.
    payload["cases"][1]["no_context_reply_for"] = REFUSAL_GOLD_ZH
    with pytest.raises(EmptyGateSuiteContractError, match="language band"):
        validate_empty_gate_suite(payload)

    assert expected_no_context_reply_for("中文问题") == REFUSAL_GOLD_ZH
    assert expected_no_context_reply_for("English question only") == REFUSAL_GOLD_EN


def test_purpose_must_be_empty_gate_refuse_ok() -> None:
    payload = clone_schema_example()
    payload["purpose"] = "false_refuse_rate"
    with pytest.raises(EmptyGateSuiteContractError, match="purpose must be"):
        validate_empty_gate_suite(payload)


def test_eb2_v1_isolation_untouched() -> None:
    assert_eb2_v1_identity_untouched()
    from tests import w10_eb2_generation_observation_contract as eb2

    assert eb2.SUITE_ID == W9_CRITIC_SUITE_ID
    assert eb2.FROZEN_CASE_COUNT == 12
    assert eb2.PROTOCOL_VERSION == "w10_eb2_generation_observation_v1"
    assert SUITE_ID != eb2.SUITE_ID
    assert CASE_COUNT != eb2.FROZEN_CASE_COUNT


def test_refusal_gold_mirrors_product() -> None:
    assert_refusal_gold_mirrors_product()


def test_eb_gates() -> None:
    assert E_B_EMPTY_GATE_CONTRACT_READY == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert_real_cases_file_present_and_valid()
    assert_formal_result_absent()
    validate_empty_gate_suite(build_schema_example_suite())


def test_no_llm_hooks_in_contract_module() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb_empty_gate_suite_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")
    assert not hasattr(mod, "stream_deepseek_tokens")


def test_clone_does_not_mutate_builder() -> None:
    a = build_schema_example_suite()
    b = clone_schema_example()
    b["notes"] = "mutated"
    assert a["notes"] != b["notes"]
    validate_empty_gate_suite(a)

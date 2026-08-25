"""W10 empty-gate cases artifact contract tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_empty_gate_cases_contract import (
    ARTIFACT_KIND_REAL,
    ARTIFACT_KIND_SCHEMA_EXAMPLE,
    CASE_COUNT,
    CASES_FILENAME,
    CASES_MATERIAL_STATUS_REAL,
    CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE,
    CASES_PATH,
    E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY,
    E_B_EMPTY_GATE_CASES_MATERIAL_READY,
    E_B_FORMAL_READY,
    FORMAL_RESULT_PATH,
    PREP_STATUS_PATH,
    PROTOCOL_VERSION,
    SCHEMA_PATH,
    SUITE_ID,
    EmptyGateCasesContractError,
    assert_eb9b_suite_identity_aligned,
    assert_formal_result_absent,
    assert_prep_status_present,
    assert_real_cases_present_and_valid,
    build_prep_status_document,
    build_real_eligible_cases,
    build_schema_example_cases,
    clone_schema_example,
    contract_module_imports_are_llm_free,
    load_prep_status_document,
    load_real_cases,
    load_schema_document,
    validate_empty_gate_cases_artifact,
    validate_prep_status_document,
)


def test_schema_example_passes_validation() -> None:
    payload = build_schema_example_cases()
    validate_empty_gate_cases_artifact(payload)
    assert payload["artifact_kind"] == ARTIFACT_KIND_SCHEMA_EXAMPLE
    assert payload["cases_material_status"] == CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE
    assert payload["case_count"] == CASE_COUNT
    assert len(payload["cases"]) == CASE_COUNT


def test_real_eligible_builder_passes_validation() -> None:
    payload = build_real_eligible_cases()
    validate_empty_gate_cases_artifact(payload)
    assert payload["artifact_kind"] == ARTIFACT_KIND_REAL
    assert payload["cases_material_status"] == CASES_MATERIAL_STATUS_REAL


def test_identity_and_schema_frozen() -> None:
    assert PROTOCOL_VERSION == "w10_eb_empty_gate_cases_v1"
    assert SUITE_ID == "w10_eb_empty_gate_v1"
    assert E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY == "YES"
    assert E_B_EMPTY_GATE_CASES_MATERIAL_READY == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert SCHEMA_PATH.is_file()
    schema = load_schema_document()
    assert schema["properties"]["suite_id"]["const"] == SUITE_ID
    assert schema["properties"]["case_count"]["const"] == CASE_COUNT


def test_real_cases_present_prep_status_aligned() -> None:
    assert CASES_FILENAME == "w10-eb-empty-gate-cases.json"
    assert_real_cases_present_and_valid()
    assert CASES_PATH.is_file()
    on_disk = load_real_cases()
    assert on_disk["artifact_kind"] == ARTIFACT_KIND_REAL
    assert on_disk["cases_material_status"] == CASES_MATERIAL_STATUS_REAL
    assert_formal_result_absent()
    assert not FORMAL_RESULT_PATH.exists()
    assert_prep_status_present()
    assert PREP_STATUS_PATH.is_file()
    status = load_prep_status_document()
    assert status["cases_material_status"] == CASES_MATERIAL_STATUS_REAL
    assert status["E_B_EMPTY_GATE_CASES_MATERIAL_READY"] == "YES"
    assert status["E_B_FORMAL_READY"] == "NO"
    validate_prep_status_document(build_prep_status_document())


def test_schema_example_cannot_claim_real_eligible() -> None:
    payload = clone_schema_example()
    payload["cases_material_status"] = CASES_MATERIAL_STATUS_REAL
    with pytest.raises(EmptyGateCasesContractError, match="cannot claim REAL_ELIGIBLE"):
        validate_empty_gate_cases_artifact(payload)


def test_real_artifact_kind_requires_real_eligible() -> None:
    payload = clone_schema_example()
    payload["artifact_kind"] = ARTIFACT_KIND_REAL
    payload["cases_material_status"] = CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE
    with pytest.raises(EmptyGateCasesContractError, match="REAL_ELIGIBLE"):
        validate_empty_gate_cases_artifact(payload)


def test_critic_oracle_and_llm_judge_rejected() -> None:
    payload = clone_schema_example()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(EmptyGateCasesContractError, match="forbidden"):
        validate_empty_gate_cases_artifact(payload)

    payload = clone_schema_example()
    payload["llm_judge"] = True
    with pytest.raises(EmptyGateCasesContractError, match="forbidden"):
        validate_empty_gate_cases_artifact(payload)

    payload = clone_schema_example()
    payload["cases"][0]["auto_label"] = "refuse"
    with pytest.raises(EmptyGateCasesContractError, match="forbidden"):
        validate_empty_gate_cases_artifact(payload)


def test_c04_c07_and_w9_ids_rejected() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["case_id"] = "C07-correct-insufficiency-refusal"
    with pytest.raises(EmptyGateCasesContractError, match="prefix pattern"):
        validate_empty_gate_cases_artifact(payload)


def test_evidence_count_and_refusal_rules() -> None:
    payload = clone_schema_example()
    payload["cases"][0]["evidence_count"] = 1
    with pytest.raises(EmptyGateCasesContractError, match="evidence_count must be 0"):
        validate_empty_gate_cases_artifact(payload)

    payload = clone_schema_example()
    payload["cases"][0]["expected_refusal"] = False
    with pytest.raises(EmptyGateCasesContractError, match="expected_refusal must be true"):
        validate_empty_gate_cases_artifact(payload)


def test_eb9b_alignment_and_gates() -> None:
    assert_eb9b_suite_identity_aligned()
    assert E_B_FORMAL_READY == "NO"
    assert E_B_EMPTY_GATE_CASES_MATERIAL_READY == "YES"
    assert_real_cases_present_and_valid()
    assert_formal_result_absent()
    validate_empty_gate_cases_artifact(build_schema_example_cases())
    validate_empty_gate_cases_artifact(build_real_eligible_cases())


def test_no_llm_hooks() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb_empty_gate_cases_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")


def test_clone_isolation() -> None:
    a = build_schema_example_cases()
    b = clone_schema_example()
    b["notes"] = "mutated"
    assert a["notes"] != b["notes"]
    validate_empty_gate_cases_artifact(a)

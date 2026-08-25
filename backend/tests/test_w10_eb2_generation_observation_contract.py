"""W10 E-B2 — generation observation schema freeze tests (structure only; no run)."""

from __future__ import annotations

import json

import pytest

from tests.w10_eb2_generation_observation_contract import (
    ALLOWED_CLAIM,
    ARTIFACT_SCHEMA_VERSION,
    EA5_OBSERVATION_POINT,
    EA5_RESULT_PATH,
    FORBIDDEN_CLAIMS,
    FORBIDDEN_RUNNER_IDS,
    FROZEN_CASE_COUNT,
    OBSERVATION_POINT,
    PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    RUNNER_MODULE,
    TOP_LEVEL_REQUIRED,
    GenerationObservationContractError,
    assert_reserved_result_absent,
    build_schema_example_artifact,
    clone_schema_example,
    contract_module_imports_are_llm_free,
    json_schema_document,
    validate_reserved_artifact,
)


def test_schema_example_passes_structural_validation_as_non_run() -> None:
    payload = build_schema_example_artifact()
    validate_reserved_artifact(payload)
    assert payload["artifact_kind"] == "SCHEMA_EXAMPLE_NOT_A_RUN"
    assert payload["measurement_validity"]["measurement_valid"] is False
    assert "SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN" in payload["measurement_validity"][
        "invalid_reasons"
    ]
    assert payload["run_id"].startswith("SCHEMA_EXAMPLE_")
    assert payload["case_count"] == FROZEN_CASE_COUNT
    assert len(payload["per_case_observation"]) == FROZEN_CASE_COUNT
    assert payload["observation_point"] == OBSERVATION_POINT
    assert payload["measurement_validity"]["llm_called"] is False


def test_protocol_version_and_identity_constants_frozen() -> None:
    assert PROTOCOL_VERSION == "w10_eb2_generation_observation_v1"
    assert ARTIFACT_SCHEMA_VERSION == "w10-eb2-generation-observation-v1"
    assert RUNNER_ID == "w10_eb2_generation_observation_runner"
    assert RUNNER_MODULE == "tests.w10_eb2_generation_observation_contract"
    assert OBSERVATION_POINT == "generation_final_content_and_citations"
    schema = json_schema_document()
    assert schema["properties"]["protocol_version"]["const"] == PROTOCOL_VERSION
    assert schema["properties"]["observation_point"]["const"] == OBSERVATION_POINT
    assert set(TOP_LEVEL_REQUIRED) <= set(schema["required"])


def test_missing_required_top_level_field_rejected() -> None:
    for field in (
        "protocol_version",
        "run_id",
        "base_sha",
        "suite_id",
        "observation_point",
        "per_case_observation",
        "measurement_validity",
    ):
        payload = clone_schema_example()
        del payload[field]
        with pytest.raises(GenerationObservationContractError, match="missing fields"):
            validate_reserved_artifact(payload)


def test_missing_required_per_case_field_rejected() -> None:
    for field in (
        "case_id",
        "eligibility",
        "classification",
        "input_hash",
        "gen_plan_reference",
        "final_content_observation",
        "final_citations",
        "scope_compliance_result",
        "grounding_observation_status",
        "refusal_observation_status",
    ):
        payload = clone_schema_example()
        del payload["per_case_observation"][0][field]
        with pytest.raises(GenerationObservationContractError, match="missing fields"):
            validate_reserved_artifact(payload)


def test_protocol_version_drift_rejected() -> None:
    payload = clone_schema_example()
    payload["protocol_version"] = "1.0.0"
    with pytest.raises(GenerationObservationContractError, match="protocol_version"):
        validate_reserved_artifact(payload)


def test_observation_point_must_be_generation_final() -> None:
    payload = clone_schema_example()
    payload["observation_point"] = EA5_OBSERVATION_POINT
    with pytest.raises(GenerationObservationContractError, match="E-A5 artifact reuse"):
        validate_reserved_artifact(payload)


def test_ea5_artifact_reuse_rejected_by_schema_version() -> None:
    payload = clone_schema_example()
    payload["artifact_schema_version"] = "w10-ea4-formal-window-v1"
    with pytest.raises(GenerationObservationContractError, match="E-A5 artifact reuse"):
        validate_reserved_artifact(payload)


def test_ea5_formal_result_file_fails_eb2_validation() -> None:
    assert EA5_RESULT_PATH.exists(), "E-A5 result fixture must exist for isolation test"
    ea5 = json.loads(EA5_RESULT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(GenerationObservationContractError):
        validate_reserved_artifact(ea5)


def test_p2_r3_runner_identity_rejected() -> None:
    payload = clone_schema_example()
    payload["runner_id"] = "w9_critic_p2_r3_formal_runner"
    with pytest.raises(GenerationObservationContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["runner_module"] = "tests.w9_critic_p2_r3_formal_runner"
    with pytest.raises(GenerationObservationContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)

    assert "w9_critic_p2_r3_formal_runner" in FORBIDDEN_RUNNER_IDS
    assert "execute_frozen_case" in FORBIDDEN_RUNNER_IDS
    assert "w10_ea4_formal_window_runner" in FORBIDDEN_RUNNER_IDS


def test_p2_r3_shaped_payload_with_per_case_result_rejected() -> None:
    payload = clone_schema_example()
    payload["per_case_result"] = payload["per_case_observation"]
    with pytest.raises(GenerationObservationContractError, match="critic/E-A5 top-level"):
        validate_reserved_artifact(payload)


def test_critic_oracle_fields_rejected_top_level() -> None:
    payload = clone_schema_example()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(GenerationObservationContractError, match="critic/E-A5 top-level"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["oracle_cases"] = [{"case_id": "C01"}]
    with pytest.raises(GenerationObservationContractError, match="critic/E-A5 top-level"):
        validate_reserved_artifact(payload)


def test_critic_oracle_fields_rejected_per_case() -> None:
    payload = clone_schema_example()
    payload["per_case_observation"][0]["expected_action"] = "ACCEPT"
    with pytest.raises(GenerationObservationContractError, match="critic/E-A5 per-case"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["per_case_observation"][1]["scope_compliance_pass"] = True
    with pytest.raises(GenerationObservationContractError, match="critic/E-A5 per-case"):
        validate_reserved_artifact(payload)


def test_forbidden_measurement_claims_rejected() -> None:
    assert ALLOWED_CLAIM == "generation observation artifact produced"
    assert FORBIDDEN_CLAIMS == (
        "generation quality proven",
        "grounding proven",
        "Critic validated",
    )
    for claim in FORBIDDEN_CLAIMS:
        payload = clone_schema_example()
        payload["measurement_claims"]["asserted"] = [claim]
        with pytest.raises(
            GenerationObservationContractError, match="forbidden measurement claim"
        ):
            validate_reserved_artifact(payload)


def test_forbidden_claim_in_notes_rejected() -> None:
    payload = clone_schema_example()
    payload["notes"] = "This run has grounding proven somehow"
    with pytest.raises(GenerationObservationContractError, match="forbidden measurement claim"):
        validate_reserved_artifact(payload)


def test_p2_r1_unblock_flags_rejected() -> None:
    payload = clone_schema_example()
    payload["p2_r1_status"] = "PASS"
    with pytest.raises(GenerationObservationContractError, match="BLOCKED"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["does_not_unblock_p2_r1"] = False
    with pytest.raises(GenerationObservationContractError, match="does_not_unblock_p2_r1"):
        validate_reserved_artifact(payload)


def test_c12_must_stay_ineligible() -> None:
    payload = clone_schema_example()
    c12 = next(
        item
        for item in payload["per_case_observation"]
        if item["case_id"] == "C12-out-of-scope-provenance"
    )
    c12["eligibility"] = True
    with pytest.raises(GenerationObservationContractError, match="C12"):
        validate_reserved_artifact(payload)


def test_schema_example_cannot_claim_measurement_valid() -> None:
    payload = clone_schema_example()
    payload["measurement_validity"]["measurement_valid"] = True
    payload["measurement_validity"]["invalid_reasons"] = []
    with pytest.raises(GenerationObservationContractError, match="SCHEMA_EXAMPLE"):
        validate_reserved_artifact(payload)


def test_reserved_result_absent_during_eb2_freeze() -> None:
    assert RESERVED_RESULT_FILENAME == "w10-eb2-generation-observation-result.json"
    assert RESERVED_RESULT_PATH.name == RESERVED_RESULT_FILENAME
    assert_reserved_result_absent()
    assert not RESERVED_RESULT_PATH.exists()


def test_no_llm_and_no_ea5_or_p2_execution_hooks() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb2_generation_observation_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    validate_reserved_artifact(build_schema_example_artifact())


def test_clone_does_not_mutate_builder() -> None:
    a = build_schema_example_artifact()
    b = clone_schema_example()
    b["run_id"] = "SCHEMA_EXAMPLE_mutated"
    assert a["run_id"] != b["run_id"]
    validate_reserved_artifact(a)

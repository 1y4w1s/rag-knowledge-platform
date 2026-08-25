"""W10 E-A4 — formal window contract freeze tests (schema only; no formal run)."""

from __future__ import annotations

import pytest

from tests.w10_ea4_formal_window_contract import (
    ADAPTER_PROTOCOL_VERSION,
    ALLOWED_CLAIM,
    ARTIFACT_SCHEMA_VERSION,
    ELIGIBILITY_PROTOCOL_ID,
    FORBIDDEN_CLAIMS,
    FORBIDDEN_RUNNER_IDS,
    FROZEN_CASE_COUNT,
    PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    RUNNER_MODULE,
    TOP_LEVEL_REQUIRED,
    FormalWindowContractError,
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
    assert len(payload["per_case_result"]) == FROZEN_CASE_COUNT


def test_protocol_version_and_identity_constants_frozen() -> None:
    assert PROTOCOL_VERSION == "1.0.0"
    assert ARTIFACT_SCHEMA_VERSION == "w10-ea4-formal-window-v1"
    assert RUNNER_ID == "w10_ea4_formal_window_runner"
    assert RUNNER_MODULE == "tests.w10_ea4_formal_window_contract"
    assert ADAPTER_PROTOCOL_VERSION == "w10_ea2_scope_eligibility_v1"
    assert ELIGIBILITY_PROTOCOL_ID == "w10_ea1_scope_eligibility"
    schema = json_schema_document()
    assert schema["properties"]["protocol_version"]["const"] == PROTOCOL_VERSION
    assert set(TOP_LEVEL_REQUIRED) <= set(schema["required"])


def test_missing_required_field_rejected() -> None:
    for field in (
        "protocol_version",
        "run_id",
        "base_sha",
        "suite_id",
        "case_count",
        "eligibility_summary",
        "per_case_result",
        "measurement_validity",
    ):
        payload = clone_schema_example()
        del payload[field]
        with pytest.raises(FormalWindowContractError, match="missing fields"):
            validate_reserved_artifact(payload)


def test_protocol_version_drift_rejected() -> None:
    payload = clone_schema_example()
    payload["protocol_version"] = "1.0.1"
    with pytest.raises(FormalWindowContractError, match="protocol_version"):
        validate_reserved_artifact(payload)


def test_wrong_runner_identity_p2_r1_rejected() -> None:
    payload = clone_schema_example()
    payload["runner_id"] = "execute_frozen_case"
    with pytest.raises(FormalWindowContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["runner_module"] = "w9_critic_p2_r1_harness.execute_frozen_case"
    with pytest.raises(FormalWindowContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)


def test_wrong_runner_identity_p2_r3_substitution_rejected() -> None:
    payload = clone_schema_example()
    payload["runner_id"] = "w9_critic_p2_r3_formal_runner"
    with pytest.raises(FormalWindowContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["runner_module"] = "tests.w9_critic_p2_r3_formal_runner"
    with pytest.raises(FormalWindowContractError, match="wrong runner identity"):
        validate_reserved_artifact(payload)

    assert "w9_critic_p2_r3_formal_runner" in FORBIDDEN_RUNNER_IDS
    assert "execute_frozen_case" in FORBIDDEN_RUNNER_IDS
    assert "FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN" in FORBIDDEN_RUNNER_IDS


def test_executor_path_cannot_be_execute_frozen_case() -> None:
    payload = clone_schema_example()
    payload["per_case_result"][0]["executor_path"] = "execute_frozen_case"
    with pytest.raises(FormalWindowContractError, match="forbids P2-R1/P2-R3"):
        validate_reserved_artifact(payload)


def test_forbidden_measurement_claims_rejected() -> None:
    assert ALLOWED_CLAIM == "plan-construction citation scope compliance"
    assert FORBIDDEN_CLAIMS == (
        "generation-final safety",
        "Critic oracle capability",
        "P2-R1 unblocked",
    )
    for claim in FORBIDDEN_CLAIMS:
        payload = clone_schema_example()
        payload["measurement_claims"]["asserted"] = [claim]
        with pytest.raises(FormalWindowContractError, match="forbidden measurement claim"):
            validate_reserved_artifact(payload)


def test_forbidden_claim_in_notes_rejected() -> None:
    payload = clone_schema_example()
    payload["notes"] = "This proves P2-R1 unblocked somehow"
    with pytest.raises(FormalWindowContractError, match="forbidden measurement claim"):
        validate_reserved_artifact(payload)


def test_p2_r1_unblock_flags_rejected() -> None:
    payload = clone_schema_example()
    payload["p2_r1_status"] = "PASS"
    with pytest.raises(FormalWindowContractError, match="BLOCKED"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["does_not_unblock_p2_r1"] = False
    with pytest.raises(FormalWindowContractError, match="does_not_unblock_p2_r1"):
        validate_reserved_artifact(payload)


def test_c12_must_stay_invalid_and_out_of_denominator() -> None:
    payload = clone_schema_example()
    c12 = next(
        item
        for item in payload["per_case_result"]
        if item["case_id"] == "C12-out-of-scope-provenance"
    )
    c12["product_path_eligible"] = True
    with pytest.raises(FormalWindowContractError, match="C12"):
        validate_reserved_artifact(payload)


def test_schema_example_cannot_claim_measurement_valid() -> None:
    payload = clone_schema_example()
    payload["measurement_validity"]["measurement_valid"] = True
    payload["measurement_validity"]["invalid_reasons"] = []
    with pytest.raises(FormalWindowContractError, match="SCHEMA_EXAMPLE"):
        validate_reserved_artifact(payload)


def test_reserved_result_filename_frozen() -> None:
    assert RESERVED_RESULT_FILENAME == "w10-ea4-formal-window-result.json"
    assert RESERVED_RESULT_PATH.name == RESERVED_RESULT_FILENAME
    # E-A4 freeze forbade writing this file. E-A5 is the authorized writer.
    # If present, it must be a FORMAL_RUN_RESULT, not a schema example.
    if RESERVED_RESULT_PATH.exists():
        import json

        payload = json.loads(RESERVED_RESULT_PATH.read_text(encoding="utf-8"))
        validate_reserved_artifact(payload)
        assert payload["artifact_kind"] == "FORMAL_RUN_RESULT"
        assert payload["measurement_validity"]["measurement_valid"] is True
        assert payload["p2_r1_status"] == "BLOCKED"


def test_no_llm_and_no_execute_frozen_case_call() -> None:
    assert contract_module_imports_are_llm_free() is True
    # Ensure validation itself does not import harness execute path.
    import tests.w10_ea4_formal_window_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    validate_reserved_artifact(build_schema_example_artifact())


def test_adapter_and_eligibility_binds_required() -> None:
    payload = clone_schema_example()
    payload["adapter_protocol_version"] = "w9_critic_p2_r2_protocol_vX"
    with pytest.raises(FormalWindowContractError, match="adapter_protocol_version"):
        validate_reserved_artifact(payload)

    payload = clone_schema_example()
    payload["eligibility_protocol_id"] = "p2_r3_eligibility"
    with pytest.raises(FormalWindowContractError, match="eligibility_protocol_id"):
        validate_reserved_artifact(payload)


def test_clone_does_not_mutate_builder() -> None:
    a = build_schema_example_artifact()
    b = clone_schema_example()
    b["run_id"] = "SCHEMA_EXAMPLE_mutated"
    assert a["run_id"] != b["run_id"]
    # deepcopy import used by clone; ensure original still validates
    validate_reserved_artifact(a)

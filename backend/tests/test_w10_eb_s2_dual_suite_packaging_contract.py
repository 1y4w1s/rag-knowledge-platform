"""W10 E-B11 Lane B — S2 dual-suite packaging contract tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_s2_dual_suite_packaging_contract import (
    ARTIFACT_KIND_AUTHORIZED,
    ARTIFACT_KIND_SCHEMA_EXAMPLE,
    COMPANION_CASE_COUNT,
    COMPANION_SUITE_ID,
    E_B_FORMAL_READY,
    E_B_S2_PACKAGING_AUTHORIZED,
    E_B_S2_PACKAGING_CONTRACT_READY,
    FORMAL_PACKAGING_RESULT_PATH,
    PREP_STATUS_PATH,
    PRIMARY_CASE_COUNT,
    PRIMARY_SUITE_ID,
    PROTOCOL_VERSION,
    SCHEMA_PATH,
    SUITE_STRATEGY,
    S2DualSuitePackagingContractError,
    assert_eb2_and_empty_gate_identities_aligned,
    assert_formal_packaging_result_absent,
    assert_prep_status_present,
    build_prep_status_document,
    build_schema_example_packaging,
    clone_schema_example,
    contract_module_imports_are_llm_free,
    load_prep_status_document,
    load_schema_document,
    validate_prep_status_document,
    validate_s2_dual_suite_packaging,
)


def test_schema_example_passes_validation() -> None:
    payload = build_schema_example_packaging()
    validate_s2_dual_suite_packaging(payload)
    assert payload["suite_strategy"] == SUITE_STRATEGY
    assert payload["artifact_kind"] == ARTIFACT_KIND_SCHEMA_EXAMPLE
    assert payload["primary_suite"]["suite_id"] == PRIMARY_SUITE_ID
    assert payload["companion_suite"]["suite_id"] == COMPANION_SUITE_ID
    assert payload["authorization"]["E_B_FORMAL_READY"] == "NO"
    assert payload["authorization"]["authorized_formal_write"] is False


def test_identity_and_schema_frozen() -> None:
    assert PROTOCOL_VERSION == "w10_eb_s2_dual_suite_packaging_v1"
    assert E_B_S2_PACKAGING_CONTRACT_READY == "YES"
    assert E_B_S2_PACKAGING_AUTHORIZED == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert SCHEMA_PATH.is_file()
    schema = load_schema_document()
    assert schema["properties"]["suite_strategy"]["const"] == SUITE_STRATEGY
    assert schema["properties"]["primary_suite"]["properties"]["case_count"]["const"] == (
        PRIMARY_CASE_COUNT
    )
    assert schema["properties"]["companion_suite"]["properties"]["case_count"][
        "const"
    ] == COMPANION_CASE_COUNT


def test_prep_status_present_formal_result_absent() -> None:
    assert_prep_status_present()
    assert PREP_STATUS_PATH.is_file()
    status = load_prep_status_document()
    assert status["E_B_S2_PACKAGING_AUTHORIZED"] == "NO"
    assert status["formal_packaging_result_status"] == "ABSENT"
    assert_formal_packaging_result_absent()
    assert not FORMAL_PACKAGING_RESULT_PATH.exists()
    validate_prep_status_document(build_prep_status_document())


def test_authorized_packaging_kind_rejected_during_prep() -> None:
    payload = clone_schema_example()
    payload["artifact_kind"] = ARTIFACT_KIND_AUTHORIZED
    with pytest.raises(S2DualSuitePackagingContractError, match="artifact_kind must be"):
        validate_s2_dual_suite_packaging(payload)


def test_w9_case_count_immutable() -> None:
    payload = clone_schema_example()
    payload["primary_suite"]["case_count"] = 13
    with pytest.raises(S2DualSuitePackagingContractError, match="case_count must remain 12"):
        validate_s2_dual_suite_packaging(payload)


def test_merge_into_same_suite_id_rejected() -> None:
    payload = clone_schema_example()
    payload["companion_suite"]["suite_id"] = PRIMARY_SUITE_ID
    with pytest.raises(S2DualSuitePackagingContractError, match="suite_id must be"):
        validate_s2_dual_suite_packaging(payload)


def test_composition_rules_must_be_true() -> None:
    payload = clone_schema_example()
    payload["composition_rules"]["forbid_merge_into_w9"] = False
    with pytest.raises(S2DualSuitePackagingContractError, match="forbid_merge_into_w9"):
        validate_s2_dual_suite_packaging(payload)


def test_authorization_cannot_flip_formal_ready() -> None:
    payload = clone_schema_example()
    payload["authorization"]["E_B_FORMAL_READY"] = "YES"
    with pytest.raises(S2DualSuitePackagingContractError, match="E_B_FORMAL_READY must be NO"):
        validate_s2_dual_suite_packaging(payload)

    payload = clone_schema_example()
    payload["authorization"]["authorized_formal_write"] = True
    with pytest.raises(
        S2DualSuitePackagingContractError, match="authorized_formal_write must be false"
    ):
        validate_s2_dual_suite_packaging(payload)


def test_critic_oracle_and_reuse_keys_rejected() -> None:
    payload = clone_schema_example()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(S2DualSuitePackagingContractError, match="forbidden"):
        validate_s2_dual_suite_packaging(payload)

    payload = clone_schema_example()
    payload["ea5_formal_reuse"] = True
    with pytest.raises(S2DualSuitePackagingContractError, match="forbidden"):
        validate_s2_dual_suite_packaging(payload)

    payload = clone_schema_example()
    payload["p2_r3_formal_reuse"] = True
    with pytest.raises(S2DualSuitePackagingContractError, match="forbidden"):
        validate_s2_dual_suite_packaging(payload)

    payload = clone_schema_example()
    payload["llm_judge"] = True
    with pytest.raises(S2DualSuitePackagingContractError, match="forbidden"):
        validate_s2_dual_suite_packaging(payload)


def test_eb2_empty_gate_alignment_and_gates() -> None:
    assert_eb2_and_empty_gate_identities_aligned()
    assert E_B_FORMAL_READY == "NO"
    assert E_B_S2_PACKAGING_AUTHORIZED == "NO"
    assert_formal_packaging_result_absent()
    validate_s2_dual_suite_packaging(build_schema_example_packaging())


def test_no_llm_hooks() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb_s2_dual_suite_packaging_contract as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")


def test_clone_isolation() -> None:
    a = build_schema_example_packaging()
    b = clone_schema_example()
    b["notes"] = "mutated"
    assert a["notes"] != b["notes"]
    validate_s2_dual_suite_packaging(a)

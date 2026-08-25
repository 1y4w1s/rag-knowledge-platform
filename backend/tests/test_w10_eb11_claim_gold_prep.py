"""W10 E-B11 Lane A — claim gold annotation prep tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_generation_claim_gold_contract import (
    build_schema_example_ledger,
)
from tests.w10_eb11_claim_gold_prep import (
    ANNOTATION_STATUS_NOT_ANNOTATED,
    E_B_CLAIM_GOLD_ANNOTATED,
    E_B_CLAIM_GOLD_PREP_READY,
    E_B_FORMAL_READY,
    FORMAL_GOLD_FILENAME,
    FORMAL_GOLD_PATH,
    PREP_ARTIFACT_KIND,
    PREP_FILENAME,
    PREP_PATH,
    PREP_PROTOCOL_VERSION,
    PREP_SCHEMA_FILENAME,
    PREP_SCHEMA_PATH,
    ClaimGoldPrepError,
    assert_prep_artifact_present,
    build_annotation_placeholder,
    claim_gold_preparation_status,
    clone_annotation_placeholder,
    contract_module_imports_are_llm_free,
    load_annotation_placeholder,
    load_prep_schema_document,
    validate_annotation_placeholder,
    validate_future_claim_gold_ledger,
)


def test_placeholder_passes_validation() -> None:
    payload = build_annotation_placeholder()
    validate_annotation_placeholder(payload)
    assert payload["artifact_kind"] == PREP_ARTIFACT_KIND
    assert payload["protocol_version"] == PREP_PROTOCOL_VERSION
    assert payload["annotation_status"] == ANNOTATION_STATUS_NOT_ANNOTATED
    assert payload["annotation_slots"] == []


def test_on_disk_placeholder_and_schema_present() -> None:
    assert_prep_artifact_present()
    assert PREP_PATH.is_file()
    assert PREP_PATH.name == PREP_FILENAME
    assert PREP_SCHEMA_PATH.is_file()
    assert PREP_SCHEMA_PATH.name == PREP_SCHEMA_FILENAME
    loaded = load_annotation_placeholder()
    assert loaded["target_gold_filename"] == FORMAL_GOLD_FILENAME
    schema = load_prep_schema_document()
    assert schema["properties"]["protocol_version"]["const"] == PREP_PROTOCOL_VERSION
    assert schema["properties"]["artifact_kind"]["const"] == PREP_ARTIFACT_KIND


def test_formal_gold_path_established() -> None:
    assert FORMAL_GOLD_FILENAME == "w10-eb-generation-claim-gold-v1.json"
    assert FORMAL_GOLD_PATH.name == FORMAL_GOLD_FILENAME
    # Path reserved since E-B11; may be filled by E-B12B materialization.
    assert FORMAL_GOLD_PATH.parent.is_dir()


def test_gates_remain_prep_only() -> None:
    assert E_B_CLAIM_GOLD_PREP_READY == "YES"
    # Prep-module constant tracks the placeholder artifact (still NOT_ANNOTATED).
    assert E_B_CLAIM_GOLD_ANNOTATED == "NO"
    assert E_B_FORMAL_READY == "NO"
    status = claim_gold_preparation_status()
    assert status["gates"]["E_B_FORMAL_READY"] == "NO"
    assert status["gates"]["E_B_CLAIM_GOLD_ANNOTATED"] == "NO"
    assert status["claims"]["fake_annotations"] is False
    assert status["claims"]["auto_label"] is False
    assert status["claims"]["formal_measurement"] is False


def test_validator_integration_accepts_eb9a_schema_example() -> None:
    """Integration hook only — schema example is not a substitute for on-disk gold."""
    validate_future_claim_gold_ledger(build_schema_example_ledger())
    assert FORMAL_GOLD_PATH.parent.is_dir()


def test_non_empty_slots_rejected() -> None:
    payload = clone_annotation_placeholder()
    payload["annotation_slots"] = [
        {"case_id": "C01", "slot_status": "AWAITING_HUMAN_ANNOTATION"}
    ]
    with pytest.raises(ClaimGoldPrepError, match="annotation_slots must be empty"):
        validate_annotation_placeholder(payload)


def test_fabricated_claim_body_keys_rejected() -> None:
    payload = clone_annotation_placeholder()
    payload["asserted_claims"] = [{"claim_id": "x", "label": "supported"}]
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["cases"] = [{"case_id": "C01"}]
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)


def test_critic_oracle_and_llm_judge_rejected() -> None:
    payload = clone_annotation_placeholder()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["oracle_cases"] = [{"case_id": "C01"}]
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["llm_judge"] = True
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["auto_label"] = True
    with pytest.raises(ClaimGoldPrepError, match="forbidden prep fields"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["created_by"] = "llm_annotator"
    with pytest.raises(ClaimGoldPrepError, match="forbidden"):
        validate_annotation_placeholder(payload)


def test_gate_flip_to_formal_ready_rejected() -> None:
    payload = clone_annotation_placeholder()
    payload["gates"]["E_B_FORMAL_READY"] = "YES"
    with pytest.raises(ClaimGoldPrepError, match="E_B_FORMAL_READY"):
        validate_annotation_placeholder(payload)

    payload = clone_annotation_placeholder()
    payload["gates"]["E_B_CLAIM_GOLD_ANNOTATED"] = "YES"
    with pytest.raises(ClaimGoldPrepError, match="E_B_CLAIM_GOLD_ANNOTATED"):
        validate_annotation_placeholder(payload)


def test_missing_header_fields_rejected() -> None:
    for field in (
        "protocol_version",
        "artifact_kind",
        "target_gold_filename",
        "annotation_slots",
        "gates",
    ):
        payload = clone_annotation_placeholder()
        del payload[field]
        with pytest.raises(ClaimGoldPrepError, match="missing fields"):
            validate_annotation_placeholder(payload)


def test_no_llm_hooks_in_prep_module() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb11_claim_gold_prep as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")
    assert not hasattr(mod, "auto_label")


def test_clone_does_not_mutate_builder() -> None:
    a = build_annotation_placeholder()
    b = clone_annotation_placeholder()
    b["created_by"] = "mutated"
    assert a["created_by"] != b["created_by"]
    validate_annotation_placeholder(a)

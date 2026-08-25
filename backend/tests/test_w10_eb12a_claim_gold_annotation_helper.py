"""W10 E-B12A-0 — claim gold annotation helper tests (deterministic only)."""

from __future__ import annotations

import pytest

from tests.w10_eb_generation_claim_gold_contract import PLACEHOLDER_CONTENT_SHA256
from tests.w10_eb12a_claim_gold_annotation_helper import (
    ANNOTATION_STATUS_AWAITING,
    E_B12A_ANNOTATION_HELPER_READY,
    E_B_CLAIM_GOLD_ANNOTATED,
    E_B_FORMAL_READY,
    FILL_POLICY,
    FROZEN_SOURCE_FILENAME,
    HELPER_ARTIFACT_KIND,
    HELPER_PROTOCOL_VERSION,
    TEMPLATE_FILENAME,
    TEMPLATE_PATH,
    TEMPLATE_SCHEMA_FILENAME,
    TEMPLATE_SCHEMA_PATH,
    ClaimGoldAnnotationHelperError,
    annotation_helper_preparation_status,
    assert_annotation_helper_artifacts_present,
    build_annotation_template,
    build_claim_row_template,
    clone_annotation_template,
    contract_module_imports_are_llm_free,
    load_annotation_template,
    load_frozen_case_evidence_sources,
    load_template_schema_document,
    validate_annotation_template,
    validate_draft_eb9a_schema_compatible,
    validate_human_annotation_draft,
)


def test_template_passes_validation() -> None:
    payload = build_annotation_template()
    validate_annotation_template(payload)
    assert payload["artifact_kind"] == HELPER_ARTIFACT_KIND
    assert payload["protocol_version"] == HELPER_PROTOCOL_VERSION
    assert payload["annotation_status"] == ANNOTATION_STATUS_AWAITING
    assert payload["fill_policy"] == FILL_POLICY
    assert payload["frozen_source_filename"] == FROZEN_SOURCE_FILENAME
    assert all(case["claims"] == [] for case in payload["cases"])


def test_on_disk_template_and_schema_present() -> None:
    assert_annotation_helper_artifacts_present()
    assert TEMPLATE_PATH.is_file()
    assert TEMPLATE_PATH.name == TEMPLATE_FILENAME
    assert TEMPLATE_SCHEMA_PATH.is_file()
    assert TEMPLATE_SCHEMA_PATH.name == TEMPLATE_SCHEMA_FILENAME
    loaded = load_annotation_template()
    schema = load_template_schema_document()
    assert schema["properties"]["protocol_version"]["const"] == HELPER_PROTOCOL_VERSION
    assert schema["properties"]["artifact_kind"]["const"] == HELPER_ARTIFACT_KIND
    assert loaded["gates"]["E_B12A_ANNOTATION_HELPER_READY"] == "YES"


def test_frozen_source_display_has_query_and_chunks_only() -> None:
    cases = load_frozen_case_evidence_sources()
    assert len(cases) == 12
    first = cases[0]
    assert first["case_id"] == "C01-fully-supported-exact"
    assert first["query"] == "生产备份保留多久？"
    assert "answer" not in first
    assert "expected_action" not in first
    assert first["evidence_chunks"] == [
        {
            "chunk_id": "E1",
            "content": "生产环境备份的保留期限为 30 天。",
        }
    ]
    assert first["claims"] == []


def test_helper_output_matches_builder_and_on_disk() -> None:
    built = build_annotation_template()
    loaded = load_annotation_template()
    assert built["protocol_version"] == loaded["protocol_version"]
    assert len(built["cases"]) == len(loaded["cases"])
    assert built["cases"][0]["case_id"] == loaded["cases"][0]["case_id"]


def test_gates_remain_prep_only() -> None:
    assert E_B12A_ANNOTATION_HELPER_READY == "YES"
    assert E_B_CLAIM_GOLD_ANNOTATED == "NO"
    assert E_B_FORMAL_READY == "NO"
    status = annotation_helper_preparation_status()
    assert status["gates"]["E_B12A_ANNOTATION_HELPER_READY"] == "YES"
    assert status["gates"]["E_B_FORMAL_READY"] == "NO"
    assert status["claims"]["auto_label"] is False
    assert status["claims"]["uses_model_answer_as_truth"] is False
    assert status["claims"]["formal_measurement"] is False


def test_prefilled_claims_in_template_rejected() -> None:
    payload = clone_annotation_template()
    payload["cases"][0]["claims"] = [
        {
            "claim_id": "c01",
            "claim_text": "human claim",
            "label": "supported",
            "supporting_evidence_ids": ["E1"],
            "annotation_notes": None,
        }
    ]
    with pytest.raises(ClaimGoldAnnotationHelperError, match="claims must be empty"):
        validate_annotation_template(payload)


def test_forbidden_fields_rejected_on_template() -> None:
    payload = clone_annotation_template()
    payload["expected_action"] = "REFUSE"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_annotation_template(payload)

    payload = clone_annotation_template()
    payload["llm_judge"] = True
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_annotation_template(payload)

    payload = clone_annotation_template()
    payload["auto_label"] = True
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_annotation_template(payload)

    payload = clone_annotation_template()
    payload["cases"][0]["answer"] = "must not appear"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_annotation_template(payload)


def test_auto_label_and_oracle_fields_rejected_on_draft() -> None:
    draft = _minimal_valid_draft()
    draft["label_source"] = "lexical_overlap"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_human_annotation_draft(draft)

    draft = _minimal_valid_draft()
    draft["cases"][0]["claims"][0]["inferred_label"] = "supported"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_human_annotation_draft(draft)

    draft = _minimal_valid_draft()
    draft["cases"][0]["claims"][0]["auto_generated_label"] = True
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden annotation fields"):
        validate_human_annotation_draft(draft)

    draft = _minimal_valid_draft()
    draft["created_by"] = "llm_annotator"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="forbidden"):
        validate_human_annotation_draft(draft)


def test_model_answer_reuse_rejected_as_claim_text() -> None:
    draft = _minimal_valid_draft()
    draft["cases"][0]["claims"][0]["claim_text"] = "生产备份保留 30 天[片段1]。"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="must not reuse frozen model answer"):
        validate_human_annotation_draft(draft)


def test_supported_label_requires_evidence_ids() -> None:
    draft = _minimal_valid_draft()
    draft["cases"][0]["claims"][0]["supporting_evidence_ids"] = []
    with pytest.raises(ClaimGoldAnnotationHelperError, match="label=supported requires"):
        validate_human_annotation_draft(draft)


def test_draft_eb9a_schema_compatible_integration() -> None:
    draft = _minimal_valid_draft()
    validate_draft_eb9a_schema_compatible(
        draft,
        content_sha256=PLACEHOLDER_CONTENT_SHA256,
        created_by="human_annotator_integration_test",
    )


def test_claim_row_template_is_empty_scaffold() -> None:
    row = build_claim_row_template()
    assert row["claim_id"] == ""
    assert row["claim_text"] == ""
    assert row["label"] is None
    assert row["supporting_evidence_ids"] == []
    assert row["annotation_notes"] is None


def test_gate_flip_to_formal_ready_rejected() -> None:
    payload = clone_annotation_template()
    payload["gates"]["E_B_FORMAL_READY"] = "YES"
    with pytest.raises(ClaimGoldAnnotationHelperError, match="E_B_FORMAL_READY"):
        validate_annotation_template(payload)


def test_no_llm_hooks_in_helper_module() -> None:
    assert contract_module_imports_are_llm_free() is True
    import tests.w10_eb12a_claim_gold_annotation_helper as mod

    assert not hasattr(mod, "execute_frozen_case")
    assert not hasattr(mod, "run_formal_window")
    assert not hasattr(mod, "run_generation_observation")
    assert not hasattr(mod, "auto_label")


def _minimal_valid_draft() -> dict:
    return {
        "fill_policy": FILL_POLICY,
        "created_by": "human_annotator_test",
        "cases": [
            {
                "case_id": "C01-fully-supported-exact",
                "evidence_chunks": [
                    {
                        "chunk_id": "E1",
                        "content": "生产环境备份的保留期限为 30 天。",
                    }
                ],
                "claims": [
                    {
                        "claim_id": "C01-fully-supported-exact::c01",
                        "claim_text": "生产环境备份保留 30 天。",
                        "label": "supported",
                        "supporting_evidence_ids": ["E1"],
                        "annotation_notes": "excerpt states 30 days",
                    }
                ],
            }
        ],
    }

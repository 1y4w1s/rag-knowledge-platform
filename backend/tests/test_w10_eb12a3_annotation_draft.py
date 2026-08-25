"""W10 E-B12A-3 — annotation draft workspace (human-filled; formal gold via E-B12B)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.w10_eb_generation_claim_gold_contract import PLACEHOLDER_CONTENT_SHA256
from tests.w10_eb12a_claim_gold_annotation_helper import (
    E_B_FORMAL_READY,
    FILL_POLICY,
    FIXTURES,
    FROZEN_SOURCE_FILENAME,
    load_frozen_case_evidence_sources,
    validate_draft_eb9a_schema_compatible,
    validate_human_annotation_draft,
)
from tests.w10_eb12b_claim_gold_materialization import (
    ANNOTATION_STATUS_ANNOTATED,
    C12_CASE_ID,
    E_B_CLAIM_GOLD_ANNOTATED,
)

DRAFT_FILENAME = "w10-eb-generation-claim-gold-v1.annotation-draft.json"
DRAFT_PATH = FIXTURES / DRAFT_FILENAME
FORMAL_GOLD_PATH = FIXTURES / "w10-eb-generation-claim-gold-v1.json"

FORBIDDEN_CASE_KEYS = frozenset(
    {
        "answer",
        "model_answer",
        "expected_action",
        "oracle_cases",
        "oracle_case",
        "critic_score",
        "critic_actions",
        "labels",
        "auto_label",
        "llm_judge",
    }
)


def _load_draft() -> dict:
    assert DRAFT_PATH.is_file(), f"missing draft workspace: {DRAFT_PATH}"
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def test_annotation_draft_present_and_annotated() -> None:
    draft = _load_draft()
    assert draft["annotation_status"] == ANNOTATION_STATUS_ANNOTATED
    assert draft["created_by"] == "human_annotator"
    assert draft["fill_policy"] == FILL_POLICY
    assert draft["frozen_source_filename"] == FROZEN_SOURCE_FILENAME
    assert draft["gates"]["E_B_CLAIM_GOLD_ANNOTATED"] == E_B_CLAIM_GOLD_ANNOTATED == "YES"
    assert draft["gates"]["E_B_FORMAL_READY"] == E_B_FORMAL_READY == "NO"


def test_annotation_draft_mirrors_frozen_cases_with_human_claims() -> None:
    draft = _load_draft()
    frozen = load_frozen_case_evidence_sources()
    assert len(draft["cases"]) == len(frozen) == 12
    for draft_case, frozen_case in zip(draft["cases"], frozen, strict=True):
        assert draft_case["case_id"] == frozen_case["case_id"]
        assert draft_case["query"] == frozen_case["query"]
        assert draft_case["evidence_chunks"] == frozen_case["evidence_chunks"]
        assert FORBIDDEN_CASE_KEYS.isdisjoint(draft_case.keys())
        if draft_case["case_id"] == C12_CASE_ID:
            assert draft_case["claims"] == []
        else:
            assert len(draft_case["claims"]) >= 1


def test_annotation_draft_passes_human_and_eb9a_validators() -> None:
    draft = _load_draft()
    validate_human_annotation_draft(draft)
    validate_draft_eb9a_schema_compatible(
        draft,
        content_sha256=PLACEHOLDER_CONTENT_SHA256,
        created_by="human_annotator",
    )


def test_formal_gold_materialized_alongside_draft() -> None:
    assert FORMAL_GOLD_PATH.is_file()
    assert DRAFT_PATH.name != FORMAL_GOLD_PATH.name
    assert Path(FORMAL_GOLD_PATH).name == "w10-eb-generation-claim-gold-v1.json"

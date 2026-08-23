"""Deterministic P0 ADVERSARIAL capability contract freeze tests (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.eval.adversarial_capability.freeze import (
    LEGACY_ADV20_CASE_IDS,
    ROUND_START_MASTER_SHA,
    build_p0_contract,
    load_p0_contract,
    validate_p0_contract,
    write_p0_contract,
)
from app.eval.adversarial_capability.taxonomy import (
    ANSWERABILITY_TAXONOMY,
    CAPABILITY_STAGES,
    FORBIDDEN_AUTO_MAPPINGS,
)
from app.eval.contract_validity.golden_contracts import ADVERSARIAL_FORMAL_CONTRACT
from app.eval.contract_validity.metric_validity import metric_validity_by_name


def test_p0_contract_build_validates() -> None:
    payload = build_p0_contract()
    validate_p0_contract(payload)
    assert payload["round_start_master_sha"] == ROUND_START_MASTER_SHA
    assert payload["success_class"] == "PARTIAL"
    assert payload["legacy_adv20"]["status"] == "INVALID_FOR_CAPABILITY"
    assert payload["proposed_capability_denominator"] == 0


def test_legacy_adv20_remains_invalid_for_capability() -> None:
    assert (
        ADVERSARIAL_FORMAL_CONTRACT["original_metric_validity"]
        == "INVALID_FOR_CAPABILITY"
    )
    entry = metric_validity_by_name()["ADVERSARIAL original pass"]
    assert entry.validity.value == "INVALID_FOR_CAPABILITY"
    payload = build_p0_contract()
    score = payload["legacy_adv20"]["score"]
    assert score["pass_count"] == 1
    assert score["total"] == 20
    assert score["capability_validity"] == "INVALID_FOR_CAPABILITY"


def test_empty_expected_chunk_does_not_auto_map_refuse() -> None:
    payload = build_p0_contract()
    assert payload["answerability_assignment_rules"][
        "cannot_infer_from_expected_chunk_empty"
    ]
    for claim in FORBIDDEN_AUTO_MAPPINGS:
        assert claim in payload["forbidden_claims"]
    assert "expected_chunk_empty_implies_refuse" in payload["forbidden_claims"]


def test_migration_table_covers_exactly_adv20() -> None:
    payload = build_p0_contract()
    rows = payload["case_migration_table"]
    assert [r["case_id"] for r in rows] == list(LEGACY_ADV20_CASE_IDS)
    assert payload["migration_counts"]["VALID_AS_IS"] == 0
    assert payload["migration_counts"]["MIGRATABLE_WITH_CONTRACT"] == 18
    assert payload["migration_counts"]["INVALID_CORPUS"] == 1
    assert payload["migration_counts"]["INVALID_EXPECTATION"] == 1
    by_id = {r["case_id"]: r for r in rows}
    assert by_id["GQ-104"]["migration_class"] == "INVALID_CORPUS"
    assert by_id["GQ-110"]["migration_class"] == "INVALID_EXPECTATION"
    assert by_id["GQ-91"]["answerability"] == "UNSAFE_REQUEST"
    assert by_id["GQ-92"]["answerability"] == "OUT_OF_SCOPE"


def test_stages_and_taxonomy_frozen() -> None:
    payload = build_p0_contract()
    assert [s["stage"] for s in payload["stage_contract"]] == list(CAPABILITY_STAGES)
    assert payload["answerability_taxonomy"] == list(ANSWERABILITY_TAXONOMY)
    assert len(payload["hard_controls"]) == 7


def test_artifact_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.eval.adversarial_capability.freeze as freeze_mod

    target = tmp_path / "backend" / freeze_mod.ARTIFACT_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        freeze_mod,
        "artifact_path",
        lambda repo_root=None: target,
    )
    written = write_p0_contract(repo_root=tmp_path)
    assert written == target
    loaded = load_p0_contract(repo_root=tmp_path)
    assert loaded["proposed_capability_denominator"] == 0


def test_committed_artifact_loads_if_present() -> None:
    from app.eval.adversarial_capability.freeze import artifact_path

    path = artifact_path()
    if not path.is_file():
        pytest.skip("artifact not yet written")
    payload = load_p0_contract()
    assert payload["proposed_capability_denominator"] == 0
    assert payload["success_class"] == "PARTIAL"

"""Offline harness for ADVERSARIAL P3 real retrieval artifact."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.adversarial_capability.p2_design import PRIMARY_CAPABILITY_CASE_IDS
from app.eval.adversarial_capability.p3_runner import SCHEMA_VERSION, STAGE


def test_p3_artifact_schema_if_present() -> None:
    path = (
        Path(__file__).resolve().parent
        / "fixtures/l4_adversarial_capability/w8-adversarial-p3-real-retrieval.json"
    )
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stage"] == STAGE
    assert data["corpus_identity"]["CAPABILITY_VALID_DENOMINATOR"] == 4
    assert len(data["cases"]) == 4
    assert {c["case_id"] for c in data["cases"]} == set(PRIMARY_CAPABILITY_CASE_IDS)
    for case in data["cases"]:
        assert "retrieval_observation_class" in case
        assert case["corpus_truth"] == case["answerability_class"]

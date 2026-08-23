"""Offline harness for ADVERSARIAL P4 real local capability artifact."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.adversarial_capability.p2_design import PRIMARY_CAPABILITY_CASE_IDS
from app.eval.adversarial_capability.p4_runner import SCHEMA_VERSION, STAGE, TRIALS_PER_CASE


def test_p4_artifact_schema_if_present() -> None:
    path = (
        Path(__file__).resolve().parent
        / "fixtures/l4_adversarial_capability/w8-adversarial-p4-real-local.json"
    )
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stage"] == STAGE
    assert data["metrics_c17"]["CAPABILITY_VALID_DENOMINATOR"] == 4
    assert data.get("product_remediation") is False
    expected_trials = len(PRIMARY_CAPABILITY_CASE_IDS) * TRIALS_PER_CASE
    assert len(data.get("schedule") or []) == expected_trials
    trajectories = data.get("trajectories") or []
    if data.get("measurement_validity") == "VALID" and data.get("ready_for_p5"):
        assert len(trajectories) == expected_trials
        assert not data.get("errors")
        assert data.get("probe_only") is False

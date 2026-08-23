"""Offline harness checks for MEMORY P3 freeze (no LM Studio)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.eval.memory_capability.p3_flags import (
    apply_memory_p3_flags,
    assert_production_exposure_default,
    restore_memory_p3_flags,
)
from app.eval.memory_capability.p3_freeze import (
    L3_SCORE,
    L4_SCORE,
    L5_SCORE,
    MEMORY_P3_REAL_RUN_LINEAGE,
    assert_artifact_matches_freeze,
    assert_manifest_matches_constants,
    load_p3_freeze_manifest,
)
from app.eval.memory_capability.p3_runner import CASE_IDS, EMPTY_IDS, SEEDED_IDS, _case_hash
from tests.golden_agent_qa_loader import load_golden_agent_cases


def test_production_exposure_trace_default_remains_false() -> None:
    assert assert_production_exposure_default() is True
    assert settings.model_fields["agent_memory_exposure_trace_enabled"].default is False


def test_benchmark_flags_enable_trace_without_changing_default() -> None:
    saved = apply_memory_p3_flags(memory_enabled=True)
    try:
        assert settings.agent_memory_enabled is True
        assert settings.agent_memory_exposure_trace_enabled is True
    finally:
        restore_memory_p3_flags(saved)
    assert settings.model_fields["agent_memory_exposure_trace_enabled"].default is False


def test_frozen_ga_memory_case_ids_and_hashes() -> None:
    cases = {c.case_id: c for c in load_golden_agent_cases() if c.case_id in CASE_IDS}
    assert set(cases) == set(CASE_IDS)
    assert set(SEEDED_IDS) == {"GA-9", "GA-10"}
    assert set(EMPTY_IDS) == {"GA-11", "GA-12"}
    assert cases["GA-9"].pre_seed_memories
    assert cases["GA-10"].pre_seed_memories
    assert cases["GA-11"].pre_seed_memories == ()
    assert cases["GA-12"].pre_seed_memories == ()
    # Stable intent hashes (Golden not mutated)
    assert len(_case_hash(cases["GA-9"])) == 64
    assert _case_hash(cases["GA-9"]) != _case_hash(cases["GA-10"])


def test_p3_freeze_manifest_invariants() -> None:
    manifest = load_p3_freeze_manifest()
    assert_manifest_matches_constants(manifest)
    assert manifest["frozen_seeded_cases"] == ["GA-9", "GA-10"]
    assert manifest["L3_EXPOSED"]["score"] == L3_SCORE
    assert manifest["L4_UTILIZED"]["score"] == L4_SCORE
    assert manifest["L5_TASK_BENEFIT"]["score"] == L5_SCORE
    assert MEMORY_P3_REAL_RUN_LINEAGE == "VALID"
    assert manifest["memory_p3_real_run_lineage"] == "VALID"
    # Causal separation locked
    assert manifest["lifecycle"]["L3_exposed"] is True
    assert manifest["lifecycle"]["L4_utilized"] is False
    assert manifest["lifecycle"]["L5_benefit"] is False
    assert "EXPOSURE != UTILIZATION" in manifest["causal_separation"]["proof"]
    assert "UTILIZATION != BENEFIT" in manifest["causal_separation"]["proof"]


def test_p3_freeze_denominator_upgrade_from_p1() -> None:
    """L3 valid measured denom; L4/L5 cannot remain P1 denom 0."""
    manifest = load_p3_freeze_manifest()
    dens = manifest["denominators"]
    assert dens["L3"] == 10
    assert dens["L4_utilization"] == 10
    assert dens["L5_task_benefit"] == 10
    assert dens["p1_superseded"]["L4_utilization"] == 0
    assert dens["p1_superseded"]["L5_task_benefit"] == 0
    assert dens["L4_utilization"] != dens["p1_superseded"]["L4_utilization"]
    assert dens["L5_task_benefit"] != dens["p1_superseded"]["L5_task_benefit"]


def test_p3_freeze_privacy_and_safety_zeros() -> None:
    privacy = load_p3_freeze_manifest()["privacy_safety"]
    assert privacy["plaintext_leakage"] == 0
    assert privacy["wrong_run_step_memory_acceptance"] == 0
    assert privacy["empty_memory_fake_exposure"] == 0
    assert privacy["false_utilization"] == 0


def test_real_capability_artifact_schema_if_present() -> None:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        Path(__file__).resolve().parent
        / "fixtures/l4_memory_capability/w8-memory-p3-real-capability.json",
        root / "artifacts/benchmarks/tmp/reports/w8-memory-p3-real-capability.json",
        Path(__file__).resolve().parents[1]
        / "artifacts/benchmarks/tmp/reports/w8-memory-p3-real-capability.json",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "w8-memory-p3-real-capability-v1"
    assert_artifact_matches_freeze(data)

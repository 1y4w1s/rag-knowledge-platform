"""Offline harness checks for MEMORY P3 (no LM Studio)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.eval.memory_capability.p3_flags import (
    apply_memory_p3_flags,
    assert_production_exposure_default,
    restore_memory_p3_flags,
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
    assert data["l3_proven"] is True
    assert data["scored_model_trajectories"] == 30
    assert data["privacy_audit"]["plaintext_in_trace"] == 0
    assert data["product_remediation"] is False
    assert data["runtime_rollout"] is False

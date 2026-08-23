"""Offline harness checks for MEMORY C1 real revalidation (no LM Studio)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.eval.memory_capability.c1_flags import (
    apply_memory_c1_flags,
    assert_production_c1_default,
    restore_memory_c1_flags,
)
from app.eval.memory_capability.c1_runner import (
    CONDITIONS,
    SEEDED_IDS,
    TRIALS_PER_CASE,
    _classify,
    build_interleaved_schedule,
)
from app.eval.memory_utilization_ablation.evaluator_audit import (
    audit_l4_semantics,
    build_hard_negatives,
    score_hard_negative,
)


def test_production_c1_default_remains_false() -> None:
    assert assert_production_c1_default() is True
    assert settings.model_fields["agent_memory_relevance_label_enabled"].default is False


def test_c1_flags_toggle_without_changing_default() -> None:
    saved = apply_memory_c1_flags(memory_enabled=True, c1_enabled=True)
    try:
        assert settings.agent_memory_relevance_label_enabled is True
        assert settings.agent_memory_exposure_trace_enabled is True
    finally:
        restore_memory_c1_flags(saved)
    assert settings.model_fields["agent_memory_relevance_label_enabled"].default is False


def test_interleaved_schedule_contract() -> None:
    schedule = build_interleaved_schedule()
    assert len(schedule) == 30
    assert schedule[0]["condition"] == "OFF_WITH_MEMORY"
    assert schedule[0]["case_id"] == "GA-9"
    assert schedule[1]["condition"] == "ON_WITH_MEMORY"
    assert schedule[2]["condition"] == "WITHOUT_MEMORY"
    assert schedule[3]["case_id"] == "GA-10"
    assert schedule[3]["condition"] == "OFF_WITH_MEMORY"
    # Never run all ON then all OFF: within each round, OFF precedes ON for same case
    for round_idx in range(1, TRIALS_PER_CASE + 1):
        round_slots = [s for s in schedule if s["round"] == round_idx]
        assert [s["condition"] for s in round_slots] == [
            "OFF_WITH_MEMORY",
            "ON_WITH_MEMORY",
            "WITHOUT_MEMORY",
            "OFF_WITH_MEMORY",
            "ON_WITH_MEMORY",
            "WITHOUT_MEMORY",
        ]
        assert [s["case_id"] for s in round_slots] == [
            "GA-9",
            "GA-9",
            "GA-9",
            "GA-10",
            "GA-10",
            "GA-10",
        ]
    assert set(SEEDED_IDS) == {"GA-9", "GA-10"}
    assert CONDITIONS == ("OFF_WITH_MEMORY", "ON_WITH_MEMORY", "WITHOUT_MEMORY")


def test_classification_helpers() -> None:
    assert (
        _classify(
            l3_off=10,
            l3_on=10,
            l4_off=0,
            l4_on=3,
            l5_on=1,
            false_util=0,
            privacy_leaks=0,
            empty_fake=0,
            wrong_scope=0,
            wrong_run=0,
            hn_false=0,
            model_residency_break=False,
        )
        == "REAL_VALIDATED"
    )
    assert (
        _classify(
            l3_off=10,
            l3_on=10,
            l4_off=0,
            l4_on=2,
            l5_on=0,
            false_util=0,
            privacy_leaks=0,
            empty_fake=0,
            wrong_scope=0,
            wrong_run=0,
            hn_false=0,
            model_residency_break=False,
        )
        == "REAL_VALIDATED_FOR_L4_ONLY"
    )
    assert (
        _classify(
            l3_off=10,
            l3_on=10,
            l4_off=0,
            l4_on=0,
            l5_on=0,
            false_util=0,
            privacy_leaks=0,
            empty_fake=0,
            wrong_scope=0,
            wrong_run=0,
            hn_false=0,
            model_residency_break=False,
        )
        == "NO_MEASURABLE_GAIN"
    )
    assert (
        _classify(
            l3_off=10,
            l3_on=8,
            l4_off=0,
            l4_on=0,
            l5_on=0,
            false_util=0,
            privacy_leaks=0,
            empty_fake=0,
            wrong_scope=0,
            wrong_run=0,
            hn_false=0,
            model_residency_break=False,
        )
        == "REGRESSION"
    )
    assert (
        _classify(
            l3_off=10,
            l3_on=10,
            l4_off=0,
            l4_on=1,
            l5_on=0,
            false_util=0,
            privacy_leaks=0,
            empty_fake=0,
            wrong_scope=0,
            wrong_run=0,
            hn_false=0,
            model_residency_break=True,
        )
        == "INCONCLUSIVE"
    )


def test_p4_hard_negatives_still_zero_false_util() -> None:
    for sample in build_hard_negatives():
        assert score_hard_negative(sample) is False, sample.sample_id
    audit = audit_l4_semantics()
    assert audit["blind_spot"] == "PARTIAL"


def test_artifact_schema_if_present() -> None:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        Path(__file__).resolve().parent
        / "fixtures/l4_memory_capability/w8-memory-c1-real-revalidation.json",
        root / "artifacts/benchmarks/tmp/reports/w8-memory-c1-real-revalidation.json",
        Path(__file__).resolve().parents[1]
        / "artifacts/benchmarks/tmp/reports/w8-memory-c1-real-revalidation.json",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    assert path is not None, "expected C1 real-revalidation artifact fixture"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "w8-memory-c1-real-revalidation-v1"
    assert data["metrics"]["scored_trajectories"] == 30
    assert "L3_EXPOSED" in data["metrics"]
    assert "L4_UTILIZED" in data["metrics"]
    assert "L5_TASK_BENEFIT" in data["metrics"]
    assert data["runtime_rollout"] is False
    assert data["model_config"]["thinking"] == "OFF"
    assert data["model_config"]["model"] == "zai-org/glm-4.6v-flash"
    assert data["classification"] == "NO_MEASURABLE_GAIN"
    assert data["metrics"]["L3_EXPOSED"]["OFF_WITH_MEMORY"]["passed"] == 10
    assert data["metrics"]["L3_EXPOSED"]["ON_WITH_MEMORY"]["passed"] == 10
    assert data["metrics"]["L4_UTILIZED"]["OFF_WITH_MEMORY"]["passed"] == 0
    assert data["metrics"]["L4_UTILIZED"]["ON_WITH_MEMORY"]["passed"] == 0
    assert data["privacy_audit"]["false_utilization"] == 0
    assert data["memory_c1_base_sha"].startswith("f4d1e7c")

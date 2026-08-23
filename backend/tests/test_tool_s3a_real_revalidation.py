"""Offline harness checks for TOOL S3A real revalidation (no LM Studio)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.eval.tool_capability.s3a_flags import (
    apply_s3a_isolation_flags,
    assert_production_s3a_default,
    force_production_defaults,
    restore_s3a_isolation_flags,
)
from app.eval.tool_capability.s3a_runner import (
    CASE_ID,
    CONDITIONS,
    TRIALS_PER_ARM,
    _interpret,
    build_paired_schedule,
)
from app.eval.tool_capability.s3a_telemetry import (
    build_s3a_telemetry,
    score_deterministic_hard_negatives,
    selection_bucket,
)


def test_production_s3a_default_remains_false() -> None:
    from app.core.config import Settings

    assert assert_production_s3a_default() is True
    assert Settings.model_fields["agent_l4_tool_contrastive_selection_enabled"].default is False
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False


def test_s3a_isolation_flags_keep_s2_t2_off() -> None:
    saved = apply_s3a_isolation_flags(s3a_enabled=True)
    try:
        assert settings.agent_l4_tool_contrastive_selection_enabled is True
        assert settings.agent_l4_tool_preferred_hint_enabled is False
        assert settings.agent_l4_task_satisfied_hint_enabled is False
    finally:
        restore_s3a_isolation_flags(saved)
        force_production_defaults()
    assert settings.agent_l4_tool_contrastive_selection_enabled is False


def test_paired_schedule_contract() -> None:
    schedule = build_paired_schedule()
    assert len(schedule) == 20
    assert schedule[0]["condition"] == "S3A_OFF"
    assert schedule[0]["case_id"] == CASE_ID
    assert schedule[1]["condition"] == "S3A_ON"
    assert schedule[0]["s2_enabled"] is False
    assert schedule[1]["t2_enabled"] is False
    for round_idx in range(1, TRIALS_PER_ARM + 1):
        round_slots = [s for s in schedule if s["round"] == round_idx]
        assert [s["condition"] for s in round_slots] == list(CONDITIONS)
        assert all(s["case_id"] == "GQ-131" for s in round_slots)
    assert CONDITIONS == ("S3A_OFF", "S3A_ON")


def test_selection_bucket() -> None:
    assert selection_bucket("search_documents") == "search_documents"
    assert selection_bucket("semantic_search") == "semantic_search"
    assert selection_bucket("list_knowledge_bases") == "other_tool"
    assert selection_bucket(None) == "invalid_decision"


def test_s3a_telemetry_off_no_guidance() -> None:
    tel = build_s3a_telemetry(
        query="How to search documents across knowledge bases?",
        s3a_enabled=False,
        captures=[
            {
                "planner_decision": {"action": "tool", "tool_name": "semantic_search"},
                "parsed_tool": "semantic_search",
                "raw_excerpt": '{"action":"tool","tool_name":"semantic_search"}',
            }
        ],
        outcome={"steps": [{"tool_name": "semantic_search", "ok": True}]},
    )
    assert tel["s3a_enabled"] is False
    assert tel["guidance_emitted"] is False
    assert tel["description_variant"] == "baseline_product"
    assert tel["selection_correct"] is False
    assert tel["s2_enabled"] is False
    assert tel["t2_enabled"] is False


def test_s3a_telemetry_on_emits_for_gq131() -> None:
    tel = build_s3a_telemetry(
        query="How to search documents across knowledge bases?",
        s3a_enabled=True,
        captures=[
            {
                "planner_decision": {"action": "tool", "tool_name": "search_documents"},
                "parsed_tool": "search_documents",
                "raw_excerpt": '{"action":"tool","tool_name":"search_documents"}',
            }
        ],
        outcome={"steps": [{"tool_name": "search_documents", "ok": True}]},
    )
    assert tel["contrastive_guidance_eligible"] is True
    assert tel["guidance_emitted"] is True
    assert tel["description_variant"] == "contrastive_s3a"
    assert tel["selection_correct"] is True
    assert tel["intent_classification"] == "catalog_search"


def test_hard_negatives_zero_regression() -> None:
    hn = score_deterministic_hard_negatives()
    assert hn["classes_complete"] is True
    assert hn["pass"] is True
    assert hn["regression_count"] == 0
    assert hn["proxy_s3a"]["hard_negative_regressions"] == 0
    classes = {r["intent_class"] for r in hn["product_rows"]}
    assert "non_retrieval" in classes
    assert "semantic_qa" in classes
    assert "both_reasonable" in classes


def test_interpret_no_gain_marks_model_boundary() -> None:
    result = _interpret(
        off_sel=0,
        on_sel=0,
        off_pass=0,
        on_pass=0,
        safety_totals={
            "out_of_scope_accept": 0,
            "invalid_args_accept": 0,
            "exposed_set_mutation": 0,
            "unsafe_terminal": 0,
            "premature_finish": 0,
            "unrecovered_schema": 0,
            "s3a_false_force_on_ineligible": 0,
        },
        hn_pass=True,
        model_residency_break=False,
        measurement_valid=True,
        n_trials=20,
    )
    assert result["capability_label"] == "NO_MEASURABLE_GAIN"
    assert result["possible_model_selection_boundary"] is True
    assert result["runtime_rollout"] is False


def test_interpret_real_validated() -> None:
    result = _interpret(
        off_sel=0,
        on_sel=7,
        off_pass=0,
        on_pass=2,
        safety_totals={
            "out_of_scope_accept": 0,
            "invalid_args_accept": 0,
            "exposed_set_mutation": 0,
            "unsafe_terminal": 0,
            "premature_finish": 0,
            "unrecovered_schema": 0,
            "s3a_false_force_on_ineligible": 0,
        },
        hn_pass=True,
        model_residency_break=False,
        measurement_valid=True,
        n_trials=20,
    )
    assert result["capability_label"] == "REAL_VALIDATED"
    assert result["runtime_rollout"] is False


def test_artifact_schema_if_present() -> None:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        Path(__file__).resolve().parent
        / "fixtures/l4_tool_capability/w8-tool-s3a-real-revalidation.json",
        root / "artifacts/benchmarks/tmp/reports/w8-tool-s3a-real-revalidation.json",
        Path(__file__).resolve().parents[1]
        / "artifacts/benchmarks/tmp/reports/w8-tool-s3a-real-revalidation.json",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    assert path is not None, "expected S3A real-revalidation artifact fixture"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "w8-tool-s3a-real-revalidation-v1"
    assert data["scored_trials"] == 20
    assert data["frozen_case"]["case_id"] == "GQ-131"
    assert data["runtime_rollout"] is False
    assert data["model_config"]["thinking"] == "OFF"
    assert data["model_config"]["model"] == "zai-org/glm-4.6v-flash"
    assert data["isolation"]["s2"] == "OFF"
    assert data["isolation"]["t2"] == "OFF"
    assert "S3A_OFF" in data["selection_metrics"]
    assert "S3A_ON" in data["selection_metrics"]
    assert data["hard_negatives"]["pass"] is True
    assert data["capability_label"] == "NO_MEASURABLE_GAIN"
    assert data["POSSIBLE_MODEL_SELECTION_BOUNDARY"] is True
    assert data["selection_metrics"]["S3A_OFF"]["counts"]["selection_correct"] == 0
    assert data["selection_metrics"]["S3A_ON"]["counts"]["selection_correct"] == 0
    assert data["tool_s3a_base_sha"].startswith("838bb03")

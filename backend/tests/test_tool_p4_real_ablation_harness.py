"""Deterministic TOOL P4 harness tests (no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.p4_freeze import (
    assert_manifest_matches_constants,
    load_p4_manifest,
)
from app.eval.tool_capability.p4_runner import (
    CASE_ORDER,
    CONDITIONS,
    SCHEDULE_SEED,
    STABILITY_TRIALS,
    _interpret,
    build_interleaved_schedule,
)
from app.eval.tool_capability.p4_telemetry import (
    build_p4_safety,
    build_s2_telemetry,
    build_t2_telemetry,
)


def test_interleaved_schedule_60_slots() -> None:
    schedule = build_interleaved_schedule()
    assert len(schedule) == len(CASE_ORDER) * len(CONDITIONS) * STABILITY_TRIALS
    assert schedule[0]["case_id"] == "GQ-131"
    assert schedule[0]["condition"] == "00"
    assert schedule[1]["condition"] == "10"
    assert schedule[2]["condition"] == "01"
    assert schedule[3]["condition"] == "11"
    # After four conditions of GQ-131, next case begins.
    assert schedule[4]["case_id"] == "GQ-132"
    assert schedule[4]["condition"] == "00"
    # Round 2 starts after 12 slots.
    assert schedule[12]["round"] == 2
    assert schedule[12]["panel"] == "stability"
    assert all(s["panel"] == "primary" for s in schedule[:12])
    assert SCHEDULE_SEED == "tool-p4-interleaved-v1"


def test_s2_telemetry_gq131_eligible_without_emission_when_off() -> None:
    tel = build_s2_telemetry(
        case_id="GQ-131",
        s2_enabled=False,
        captures=[
            {
                "planner_decision": {"action": "tool", "tool_name": "semantic_search"},
                "parsed_tool": "semantic_search",
            }
        ],
        outcome={"steps": [{"tool_name": "semantic_search", "ok": True}]},
        hint_emissions=[],
    )
    assert tel["preferred_tool_hint_eligible"] is True
    assert tel["preferred_tool_hint_emitted"] is False
    assert tel["preferred_tool_hint_expected"] == "search_documents"
    assert tel["gq131_historical_wrong_tool"] is True
    assert tel["gq131_selection_improved"] is False


def test_t2_telemetry_marks_termination_improved() -> None:
    obs = {
        "total": 2,
        "summary": "可见库",
        "items": [{"kb_id": "k1", "name": "A", "document_count": 1}],
    }
    tel = build_t2_telemetry(
        case_id="GQ-132",
        t2_enabled=True,
        captures=[],
        outcome={
            "steps": [
                {
                    "tool_name": "list_knowledge_bases",
                    "ok": True,
                    "observation": obs,
                }
            ],
            "terminal_action": "finish",
            "capped": False,
        },
        trajectory={
            "terminal_action": "finish",
            "budget_exhausted": False,
            "safe": True,
        },
        hint_emissions=[{"task_contract_satisfied": True}],
    )
    assert tel["task_contract_satisfied_eligible"] is True
    assert tel["task_contract_satisfied_emitted"] is True
    assert tel["observation_contract_satisfied"] is True
    assert tel["termination_improved"] is True


def test_p4_safety_flags_false_task_satisfied_hint() -> None:
    safety = build_p4_safety(
        base_safety={
            "unsafe_terminal": 0,
            "out_of_scope_accept": 0,
            "invalid_args_accept": 0,
            "false_observation_success": 0,
            "failed_tool_marked_success": 0,
            "schema_unrecovered": 0,
        },
        s2={"preferred_tool_hint_false_positive": False},
        t2={
            "premature_terminal": False,
            "task_contract_satisfied_emitted": True,
            "observation_contract_satisfied": False,
        },
        task_completion=False,
        trajectory={"terminal_action": None, "budget_exhausted": True},
    )
    assert safety["false_task_satisfied_hint"] == 1
    assert safety["wrong_preferred_tool_hint"] == 0


def test_p4_freeze_manifest_matches_measured_panel() -> None:
    assert_manifest_matches_constants(load_p4_manifest())
    data = load_p4_manifest()
    assert data["s2_selection_improvement_gq131"]["10"] == "0/5"
    assert data["t2_termination_improvement_gq132_149"]["01"] == "10/10"
    assert data["s2_validation"] == "NO_MEASURABLE_GAIN"
    assert data["t2_validation"] == "REAL_VALIDATED_ON_FROZEN_SUBSET"
    assert data["interaction"]["condition_11"] == "NO_INTERACTION/T2-DOMINANT"
    assert data["safety_metrics"]["unsafe_terminal"] == 0
    assert data["safety_metrics"]["premature_finish"] == 0
    assert data["safety_metrics"]["false_task_satisfied_hint"] == 0
    assert data["safety_metrics"]["wrong_preferred_tool_hint"] == 0
    assert data["safety_metrics"]["out_of_scope_tool_accept"] == 0
    assert data["safety_metrics"]["schema_unrecovered"] == 0
    assert data["tna_tracking"]["unrecovered_tool_name_as_action"] == 0
    assert data["ready_for_runtime_rollout"] is False
    assert data["feature_flag_defaults"]["agent_l4_tool_preferred_hint_enabled"] is False
    assert data["feature_flag_defaults"]["agent_l4_task_satisfied_hint_enabled"] is False


def test_interpret_t2_dominant_no_interaction() -> None:
    """00=0, 10=0, 01=10, 11=10 → T2-only gain; not ADDITIVE."""
    by = {
        "00": {
            "stability_pass": 0,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 0, "GQ-149": 0},
        },
        "10": {
            "stability_pass": 0,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 0, "GQ-149": 0},
        },
        "01": {
            "stability_pass": 10,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 5, "GQ-149": 5},
        },
        "11": {
            "stability_pass": 10,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 5, "GQ-149": 5},
        },
    }
    out = _interpret(
        by_condition=by,
        safety_totals={
            "unsafe_terminal": 0,
            "premature_finish": 0,
            "false_task_satisfied_hint": 0,
            "wrong_preferred_tool_hint": 0,
            "out_of_scope_tool_accept": 0,
            "invalid_args_accept": 0,
            "failed_tool_marked_success": 0,
            "matcher_false_positive": 0,
            "failed_tool_coverage_pollution": 0,
            "schema_unrecovered": 0,
        },
        unrecovered_tna=0,
        measurement_valid=True,
    )
    ix = out["interaction"]
    assert ix["condition_11"] == "NO_INTERACTION/T2-DOMINANT"
    assert ix["s2_effect"] == 0
    assert ix["t2_effect"] == 10
    assert ix["s2_x_t2_interaction"] == 0
    assert out["case"] == "Case1"
    assert out["s2_validation"] == "NO_MEASURABLE_GAIN"
    assert out["t2_validation"] == "REAL_VALIDATED_ON_FROZEN_SUBSET"


def test_interpret_regression_on_safety() -> None:
    by = {
        "00": {
            "stability_pass": 0,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 0, "GQ-149": 0},
        },
        "10": {
            "stability_pass": 5,
            "per_case_pass": {"GQ-131": 5, "GQ-132": 0, "GQ-149": 0},
        },
        "01": {
            "stability_pass": 0,
            "per_case_pass": {"GQ-131": 0, "GQ-132": 0, "GQ-149": 0},
        },
        "11": {
            "stability_pass": 5,
            "per_case_pass": {"GQ-131": 5, "GQ-132": 0, "GQ-149": 0},
        },
    }
    out = _interpret(
        by_condition=by,
        safety_totals={"unsafe_terminal": 1, "schema_unrecovered": 0},
        unrecovered_tna=0,
        measurement_valid=True,
    )
    assert out["case"] == "Case4"
    assert out["ready_for_runtime_rollout"] is False

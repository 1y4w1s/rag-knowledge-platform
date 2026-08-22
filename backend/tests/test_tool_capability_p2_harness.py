"""Deterministic TOOL P2 harness tests (no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.p2_freeze import (
    assert_manifest_matches_constants,
    load_p2_freeze_manifest,
    measurement_ready_for_freeze,
)
from app.eval.tool_capability.taxonomy import classify_tna, is_raw_tool_name_as_action


def test_tna_tool_name_as_action_detected_and_recovered() -> None:
    raw = '{"action":"search_documents","args":{"query":"q"},"reason_code":"initial_retrieval"}'
    assert is_raw_tool_name_as_action(raw) is True
    row = classify_tna(raw)
    assert row["raw_tool_name_as_action"] is True
    assert row["recovered"] is True
    assert row["unrecovered"] is False


def test_tna_canonical_action_not_counted() -> None:
    raw = '{"action":"tool","tool_name":"search_documents","args":{"query":"q"}}'
    assert is_raw_tool_name_as_action(raw) is False


def test_freeze_ready_without_passing_score() -> None:
    """Trustworthy 0/N measurement must still be freeze-eligible."""
    assert measurement_ready_for_freeze(
        safety_totals={"unsafe_terminal": 0, "schema_unrecovered": 0},
        unrecovered_tna=0,
        product_issues=[],
    )


def test_p2_freeze_manifest_matches_constants() -> None:
    assert_manifest_matches_constants(load_p2_freeze_manifest())

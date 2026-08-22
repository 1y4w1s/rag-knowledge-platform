"""Deterministic TOOL P2 harness tests (no LM Studio)."""

from __future__ import annotations

from app.eval.tool_capability.taxonomy import classify_tna, is_raw_tool_name_as_action


def test_tna_tool_name_as_action_detected_and_recovered() -> None:
    raw = '{"action":"search_documents","reason_code":"initial_retrieval"}'
    assert is_raw_tool_name_as_action(raw) is True
    row = classify_tna(raw)
    assert row["raw_tool_name_as_action"] is True
    assert row["recovered"] is True
    assert row["unrecovered"] is False


def test_tna_canonical_action_not_counted() -> None:
    raw = '{"action":"tool","tool_name":"search_documents","args":{"query":"q"}}'
    assert is_raw_tool_name_as_action(raw) is False

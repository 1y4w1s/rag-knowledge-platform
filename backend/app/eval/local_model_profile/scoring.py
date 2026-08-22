"""Strict scoring helpers for local model probes.

``repair_required`` and ``schema_success`` are intentionally separate:
fence-stripping / lenient extraction may set ``repair_required=True`` but
must **not** flip ``schema_success`` to True unless raw JSON parses cleanly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProbeDecisionAction(str, Enum):
    """Independent mini-schema (mirrors AgentActionKind; not imported from runtime)."""

    tool = "tool"
    finish = "finish"
    clarify = "clarify"
    refuse = "refuse"


ALLOWED_PROBE_TOOLS = frozenset(
    {
        "semantic_search",
        "search_documents",
        "get_chunk_excerpt",
        "list_knowledge_bases",
    }
)


@dataclass(slots=True)
class JsonScore:
    schema_success: bool
    repair_required: bool
    parsed: dict[str, Any] | None
    error: str | None = None


@dataclass(slots=True)
class DecisionScore:
    ok: bool
    action: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] | None = None
    error: str | None = None
    schema_success: bool = False
    repair_required: bool = False


def score_strict_json(raw: str, *, required_keys: set[str] | None = None) -> JsonScore:
    """Strict JSON object parse. Fence stripping ⇒ repair_required, not schema_success."""
    if raw is None or not str(raw).strip():
        return JsonScore(
            schema_success=False,
            repair_required=False,
            parsed=None,
            error="empty_output",
        )

    text = str(raw)
    try:
        parsed = json.loads(text.strip())
        if not isinstance(parsed, dict):
            return JsonScore(
                schema_success=False,
                repair_required=False,
                parsed=None,
                error="not_object",
            )
        if required_keys and not required_keys.issubset(parsed.keys()):
            return JsonScore(
                schema_success=False,
                repair_required=False,
                parsed=parsed,
                error="missing_keys",
            )
        return JsonScore(
            schema_success=True, repair_required=False, parsed=parsed, error=None
        )
    except json.JSONDecodeError:
        pass

    repaired = _strip_fence(text)
    repair_required = repaired != text.strip()
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError:
        return JsonScore(
            schema_success=False,
            repair_required=repair_required or True,
            parsed=None,
            error="parse_error",
        )
    if not isinstance(parsed, dict):
        return JsonScore(
            schema_success=False,
            repair_required=True,
            parsed=None,
            error="not_object",
        )
    if required_keys and not required_keys.issubset(parsed.keys()):
        return JsonScore(
            schema_success=False,
            repair_required=True,
            parsed=parsed,
            error="missing_keys",
        )
    # Parsed only after repair → schema_success stays False.
    return JsonScore(
        schema_success=False,
        repair_required=True,
        parsed=parsed,
        error="repair_required",
    )


def score_agent_decision(raw: str) -> DecisionScore:
    js = score_strict_json(raw, required_keys={"action"})
    if js.parsed is None:
        return DecisionScore(
            ok=False,
            error=js.error or "parse_error",
            schema_success=js.schema_success,
            repair_required=js.repair_required,
        )
    # Strict schema PASS requires schema_success (no repair).
    if not js.schema_success:
        return DecisionScore(
            ok=False,
            error=js.error or "repair_required",
            schema_success=False,
            repair_required=js.repair_required,
        )

    action_raw = js.parsed.get("action")
    if not isinstance(action_raw, str):
        return DecisionScore(
            ok=False,
            error="invalid_action",
            schema_success=True,
            repair_required=False,
        )
    try:
        action = ProbeDecisionAction(action_raw)
    except ValueError:
        return DecisionScore(
            ok=False,
            error="invalid_action_enum",
            schema_success=True,
            repair_required=False,
        )

    tool_name = js.parsed.get("tool_name")
    if tool_name is not None and not isinstance(tool_name, str):
        return DecisionScore(
            ok=False,
            error="invalid_tool_name",
            schema_success=True,
            repair_required=False,
        )
    args = js.parsed.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return DecisionScore(
            ok=False,
            error="invalid_args",
            schema_success=True,
            repair_required=False,
        )

    if action == ProbeDecisionAction.tool:
        if not tool_name:
            return DecisionScore(
                ok=False,
                error="missing_tool_name",
                schema_success=True,
                repair_required=False,
            )
        if tool_name not in ALLOWED_PROBE_TOOLS:
            return DecisionScore(
                ok=False,
                error="unknown_tool",
                schema_success=True,
                repair_required=False,
                action=action.value,
                tool_name=tool_name,
                args=args,
            )
    else:
        tool_name = None
        args = {}

    return DecisionScore(
        ok=True,
        action=action.value,
        tool_name=tool_name,
        args=args,
        schema_success=True,
        repair_required=False,
    )


def score_evidence_selection(
    raw: str,
    *,
    allowed_ids: set[str],
) -> DecisionScore:
    """Expect ``{"selected_ids": [...]}`` with ids ⊆ allowed_ids."""
    js = score_strict_json(raw, required_keys={"selected_ids"})
    if not js.schema_success or js.parsed is None:
        return DecisionScore(
            ok=False,
            error=js.error or "parse_error",
            schema_success=js.schema_success,
            repair_required=js.repair_required,
        )
    selected = js.parsed.get("selected_ids")
    if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
        return DecisionScore(
            ok=False,
            error="invalid_selected_ids",
            schema_success=True,
            repair_required=False,
        )
    hallucinated = [x for x in selected if x not in allowed_ids]
    if hallucinated:
        return DecisionScore(
            ok=False,
            error="evidence_id_hallucination",
            schema_success=True,
            repair_required=False,
            args={"selected_ids": selected, "hallucinated": hallucinated},
        )
    return DecisionScore(
        ok=True,
        schema_success=True,
        repair_required=False,
        args={"selected_ids": selected},
    )


def score_native_tool_call(
    tool_calls: list[dict[str, Any]],
    *,
    expected_name: str,
    required_arg_keys: set[str],
) -> DecisionScore:
    if not tool_calls:
        return DecisionScore(ok=False, error="no_tool_calls")
    first = tool_calls[0]
    fn = first.get("function") if isinstance(first, dict) else None
    if not isinstance(fn, dict):
        return DecisionScore(ok=False, error="invalid_tool_call_shape")
    name = fn.get("name")
    if name != expected_name:
        return DecisionScore(
            ok=False,
            error="unexpected_tool",
            tool_name=str(name) if name is not None else None,
        )
    raw_args = fn.get("arguments", "{}")
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError:
        return DecisionScore(ok=False, error="invalid_tool_args_json", tool_name=name)
    if not isinstance(args, dict):
        return DecisionScore(ok=False, error="invalid_tool_args", tool_name=name)
    if not required_arg_keys.issubset(args.keys()):
        return DecisionScore(ok=False, error="missing_tool_args", tool_name=name, args=args)
    return DecisionScore(ok=True, tool_name=name, args=args)


_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    if stripped.startswith("```"):
        start = stripped.find("\n")
        end = stripped.rfind("```")
        if start != -1 and end != -1 and end > start:
            return stripped[start:end].strip()
    if stripped.startswith("json"):
        return stripped[4:].strip()
    return stripped

"""W8 P7 eval-only schema repair candidates (STRICT / NARROW / BROAD)."""

from __future__ import annotations

import copy
import json
from enum import Enum
from typing import Any

from app.eval.schema_ablation.models import CandidateKind, CandidateOutcome
from app.eval.schema_ablation.tool_inventory import ToolInventorySnapshot
from app.services.agent.planners import _strip_llm_json_fence, parse_agent_decision
from app.services.agent.types import AgentDecision


class RepairLayer(str, Enum):
    """Where TOOL_NAME_AS_ACTION repair would attach in product (analysis only)."""

    json_parsing = "json_parsing"
    agent_decision_validation = "agent_decision_validation"
    tool_name_canonicalization = "tool_name_canonicalization"


RECOMMENDED_REPAIR_LAYER = RepairLayer.tool_name_canonicalization


def decode_llm_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Mirror product JSON decode step (includes fence strip)."""
    if not raw or not raw.strip():
        return None, "empty_output"
    try:
        parsed = json.loads(_strip_llm_json_fence(raw))
    except json.JSONDecodeError:
        return None, "parse_error"
    if isinstance(parsed, list):
        return None, "not_single_object"
    if not isinstance(parsed, dict):
        return None, "parse_error"
    return parsed, None


def _decision_to_dict(decision: AgentDecision) -> dict[str, Any]:
    return {
        "action": decision.action.value,
        "tool_name": decision.tool_name,
        "args": dict(decision.args or {}),
        "reason_code": decision.reason_code,
        "user_message": decision.user_message,
    }


def _decisions_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if a is None or b is None:
        return a is b
    return (
        a.get("action") == b.get("action")
        and a.get("tool_name") == b.get("tool_name")
        and a.get("args") == b.get("args")
        and a.get("reason_code") == b.get("reason_code")
        and a.get("user_message") == b.get("user_message")
    )


def evaluate_strict(raw: str) -> CandidateOutcome:
    parsed = parse_agent_decision(raw)
    decision = _decision_to_dict(parsed.decision) if parsed.decision else None
    return CandidateOutcome(
        parse_ok=parsed.ok,
        error=parsed.error,
        decision=decision,
        repair_applied=False,
        semantic_mutation=False,
        false_repair=False,
    )


def _tool_name_missing_or_null(obj: dict[str, Any]) -> bool:
    if "tool_name" not in obj:
        return True
    return obj.get("tool_name") is None


def _tool_names_conflict(action_as_tool: str, tool_name: str | None) -> bool:
    if tool_name is None:
        return False
    return tool_name != action_as_tool


def apply_narrow_canonicalization(
    obj: dict[str, Any],
    inventory: ToolInventorySnapshot,
) -> tuple[dict[str, Any], bool]:
    """Candidate A — narrow tool-name canonicalization (eval-only).

    When and only when:
    1. action is str
    2. action exactly equals an allowed/exposed tool name
    3. tool_name missing or null
    4. no conflicting tool_name
    Transform: action→tool, tool_name→original action. No other field changes.
    """
    patched = copy.deepcopy(obj)
    action_raw = patched.get("action")
    if not isinstance(action_raw, str):
        return patched, False
    if action_raw not in inventory.allowed_tool_names:
        return patched, False
    if not _tool_name_missing_or_null(patched):
        existing = patched.get("tool_name")
        if isinstance(existing, str) and _tool_names_conflict(action_raw, existing):
            return patched, False
        if existing is not None:
            return patched, False
    patched["action"] = "tool"
    patched["tool_name"] = action_raw
    return patched, True


def apply_duplicate_consistent_canonicalization(
    obj: dict[str, Any],
    inventory: ToolInventorySnapshot,
) -> tuple[dict[str, Any], bool]:
    """Candidate A2 — duplicate-consistent tool-name canonicalization (eval-only).

    When and only when:
    1. action is str
    2. action exactly equals an allowed/exposed tool name
    3. tool_name missing/null OR tool_name == action (exact duplicate)
    Transform: action→tool; if tool_name missing/null set tool_name→original action.
    If tool_name == action, preserve tool_name value.
    """
    patched = copy.deepcopy(obj)
    action_raw = patched.get("action")
    if not isinstance(action_raw, str):
        return patched, False
    if action_raw not in inventory.allowed_tool_names:
        return patched, False

    if _tool_name_missing_or_null(patched):
        patched["action"] = "tool"
        patched["tool_name"] = action_raw
        return patched, True

    existing = patched.get("tool_name")
    if isinstance(existing, str) and existing == action_raw:
        patched["action"] = "tool"
        return patched, True

    return patched, False


def apply_broad_canonicalization(
    obj: dict[str, Any],
    inventory: ToolInventorySnapshot,
) -> tuple[dict[str, Any], bool]:
    """Candidate B — unsafe control: canonicalize any allowed tool name in action.

    Ignores existing tool_name and scope nuance. Must not be recommended for product.
    """
    patched = copy.deepcopy(obj)
    action_raw = patched.get("action")
    if not isinstance(action_raw, str):
        return patched, False
    if action_raw not in inventory.allowed_tool_names:
        return patched, False
    patched["action"] = "tool"
    patched["tool_name"] = action_raw
    return patched, True


def _parse_from_dict(obj: dict[str, Any], *, repair_applied: bool) -> CandidateOutcome:
    raw = json.dumps(obj, ensure_ascii=False)
    parsed = parse_agent_decision(raw)
    decision = _decision_to_dict(parsed.decision) if parsed.decision else None
    return CandidateOutcome(
        parse_ok=parsed.ok,
        error=parsed.error,
        decision=decision,
        repair_applied=repair_applied,
        semantic_mutation=False,
        false_repair=False,
    )


def evaluate_candidate(
    raw: str,
    *,
    kind: CandidateKind,
    inventory: ToolInventorySnapshot,
    strict_baseline: CandidateOutcome | None = None,
) -> CandidateOutcome:
    if kind == CandidateKind.strict:
        return evaluate_strict(raw)

    obj, decode_err = decode_llm_json(raw)
    if obj is None:
        out = CandidateOutcome(
            parse_ok=False,
            error=decode_err,
            decision=None,
            repair_applied=False,
            semantic_mutation=False,
            false_repair=False,
        )
        return out

    if kind == CandidateKind.narrow:
        patched, applied = apply_narrow_canonicalization(obj, inventory)
    elif kind == CandidateKind.duplicate_consistent:
        patched, applied = apply_duplicate_consistent_canonicalization(obj, inventory)
    elif kind == CandidateKind.broad:
        patched, applied = apply_broad_canonicalization(obj, inventory)
    else:
        msg = f"unsupported candidate kind: {kind}"
        raise ValueError(msg)

    if not applied:
        strict = strict_baseline or evaluate_strict(raw)
        return CandidateOutcome(
            parse_ok=strict.parse_ok,
            error=strict.error,
            decision=strict.decision,
            repair_applied=False,
            semantic_mutation=False,
            false_repair=False,
        )

    out = _parse_from_dict(patched, repair_applied=applied)
    return out


def _args_pass_ablation_safety_contract(tool_name: str | None, args: dict[str, Any]) -> bool:
    """Eval-only stricter args check for hard-negative false-repair detection."""
    if not tool_name:
        return False
    if tool_name in ("semantic_search", "search_documents"):
        query = args.get("query")
        return isinstance(query, str) and bool(query.strip())
    if tool_name == "get_chunk_excerpt":
        chunk_id = args.get("chunk_id")
        return isinstance(chunk_id, str) and bool(chunk_id)
    if tool_name == "grep_in_document":
        doc = args.get("document_id")
        pattern = args.get("pattern")
        return isinstance(doc, str) and bool(doc) and isinstance(pattern, str) and bool(pattern)
    if tool_name == "compare_chunks":
        ids = args.get("chunk_ids")
        return isinstance(ids, list) and len(ids) >= 2 and all(isinstance(x, str) for x in ids)
    return True


def classify_hard_negative_accept(
    outcome: CandidateOutcome,
    *,
    dimension: str,
    inventory: ToolInventorySnapshot,
    strict_outcome: CandidateOutcome | None = None,
) -> dict[str, int]:
    """Return counters for specialized false-repair dimensions."""
    counts = {
        "false_repair": 0,
        "unknown_tool_accept": 0,
        "conflict_accept": 0,
        "invalid_arguments_accept": 0,
        "out_of_scope_tool_accept": 0,
    }
    if dimension in {
        "finish_action",
        "clarify_action",
        "refuse_action",
        "duplicate_finish",
        "duplicate_clarify",
        "duplicate_refuse",
    }:
        if (
            outcome.parse_ok
            and outcome.decision
            and outcome.decision.get("action") == "tool"
        ):
            counts["false_repair"] = 1
        return counts
    if dimension == "json_with_fence_valid_under_strict":
        if strict_outcome and strict_outcome.parse_ok and outcome.parse_ok:
            if outcome.repair_applied or outcome.decision != strict_outcome.decision:
                counts["false_repair"] = 1
        return counts
    if not outcome.parse_ok:
        return counts
    if outcome.repair_applied and outcome.decision:
        tool_name = outcome.decision.get("tool_name")
        args = outcome.decision.get("args") or {}
        args_ok = _args_pass_ablation_safety_contract(
            tool_name if isinstance(tool_name, str) else None,
            args if isinstance(args, dict) else {},
        )
        if not args_ok:
            counts["false_repair"] = 1
            if dimension in {
                "missing_required_args",
                "wrong_arg_type",
                "illegal_argument_structure",
                "duplicate_missing_required_args",
                "duplicate_wrong_arg_type",
                "duplicate_malformed_args",
            }:
                counts["invalid_arguments_accept"] = 1
            return counts
        if dimension == "illegal_argument_structure":
            return counts
    counts["false_repair"] = 1
    if dimension.startswith("unknown"):
        counts["unknown_tool_accept"] = 1
    if dimension == "conflicting_tool_name":
        counts["conflict_accept"] = 1
    if dimension in {
        "missing_required_args",
        "wrong_arg_type",
        "illegal_argument_structure",
        "duplicate_missing_required_args",
        "duplicate_wrong_arg_type",
        "duplicate_malformed_args",
    }:
        counts["invalid_arguments_accept"] = 1
    if dimension == "out_of_scope_dependent_tool":
        counts["out_of_scope_tool_accept"] = 1
    return counts

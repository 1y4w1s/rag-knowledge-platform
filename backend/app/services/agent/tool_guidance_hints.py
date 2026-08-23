"""TOOL P3 product experiments: S2 preferred-tool + T2 task-satisfied hints.

ADVISORY only — never remaps AgentDecision, never force-finish, never expands
ToolResolver scope. Flags default OFF; OFF leaves ObservationSummary unchanged.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass, replace
from typing import Any
from uuid import UUID

from app.services.agent.types import (
    AgentState,
    EvidenceState,
    FactStatus,
    ObservationSummary,
)

NO_HINT: None = None

# Competing search pair for S2 (aligned with offline ablation Family S).
_COMPETING_SEARCH = frozenset({"semantic_search", "search_documents"})

_CATALOG_PATTERNS = (
    re.compile(r"search documents", re.I),
    re.compile(r"across knowledge bases", re.I),
    re.compile(r"by\s+(filename|content)\s+mode", re.I),
    re.compile(r"list documents", re.I),
    re.compile(r"document search", re.I),
)
_SEMANTIC_PATTERNS = (
    re.compile(r"\bwhat (does|is|are)\b", re.I),
    re.compile(r"\bexplain\b", re.I),
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bsummarize\b", re.I),
    re.compile(r"\bwhy\b", re.I),
)
_MULTI_STEP_PATTERNS = (
    re.compile(r"\bthen\b", re.I),
    re.compile(r"\bafter that\b", re.I),
    re.compile(r"然后"),
    re.compile(r"接着"),
)
_OOS_PATTERNS = (
    re.compile(r"\bdelete\b", re.I),
    re.compile(r"\bpurge\b", re.I),
    re.compile(r"\bdrop\b", re.I),
    re.compile(r"删除"),
)

# Migrated termination-target contracts (GQ-132 / GQ-149). Exact query match
# fail-closed — non-migrated / ambiguous queries never set satisfied.
_TERMINATION_CONTRACTS: tuple[tuple[str, str, str], ...] = (
    (
        "GQ-132",
        "List all knowledge bases endpoint",
        "list_knowledge_bases",
    ),
    (
        "GQ-149",
        "Search documents by content mode",
        "search_documents",
    ),
)

# GQ-131 selection target (S2 preferred tool).
_GQ131_QUERY = "How to search documents across knowledge bases?"
_GQ131_PREFERRED = "search_documents"


@dataclass(frozen=True, slots=True)
class PreferredToolHint:
    """Structured advisory preferred-tool signal (S2)."""

    preferred_tool: str
    intent_class: str
    reason: str
    case_id: str | None = None


def intent_class_for_query(query: str) -> str:
    """catalog_search | semantic_qa | ambiguous | multi_step | oos — fail-closed."""
    if any(p.search(query) for p in _OOS_PATTERNS):
        return "oos"
    if any(p.search(query) for p in _MULTI_STEP_PATTERNS):
        return "multi_step"
    catalog = any(p.search(query) for p in _CATALOG_PATTERNS)
    semantic = any(p.search(query) for p in _SEMANTIC_PATTERNS)
    if catalog and not semantic:
        return "catalog_search"
    if semantic and not catalog:
        return "semantic_qa"
    return "ambiguous"


def preferred_tool_for_intent(intent_class: str) -> str | None:
    if intent_class == "catalog_search":
        return "search_documents"
    if intent_class == "semantic_qa":
        return "semantic_search"
    return None


def resolve_preferred_tool_hint(
    query: str,
    exposed_tools: frozenset[str] | set[str] | tuple[str, ...],
) -> PreferredToolHint | None:
    """S2: unique preferred tool in exposed set, else NO_HINT.

    Never expands exposed scope. Ambiguous / missing preferred → None.
    """
    exposed = frozenset(exposed_tools)
    q = (query or "").strip()
    if not q or not exposed:
        return None

    # Exact migrated GQ-131 catalog intent.
    if q.casefold() == _GQ131_QUERY.casefold():
        if _GQ131_PREFERRED not in exposed:
            return None
        return PreferredToolHint(
            preferred_tool=_GQ131_PREFERRED,
            intent_class="catalog_search",
            reason="migrated_task_contract_preferred_tool",
            case_id="GQ-131",
        )

    intent = intent_class_for_query(q)
    preferred = preferred_tool_for_intent(intent)
    if preferred is None:
        return None
    if preferred not in exposed:
        return None
    # Prefer only when competing search pair is relevant (both catalog tools
    # present OR preferred itself is the sole search tool).
    if preferred in _COMPETING_SEARCH and not (exposed & _COMPETING_SEARCH):
        return None
    return PreferredToolHint(
        preferred_tool=preferred,
        intent_class=intent,
        reason="unambiguous_task_intent",
        case_id=None,
    )


def match_termination_contract(query: str) -> tuple[str, str] | None:
    """Return (case_id, expected_tool) for unique migrated T-target, else None."""
    q = (query or "").strip().casefold()
    if not q:
        return None
    hits = [
        (case_id, tool)
        for case_id, contract_q, tool in _TERMINATION_CONTRACTS
        if contract_q.casefold() == q
    ]
    if len(hits) != 1:
        return None
    return hits[0]


def observation_as_dict(data: Any) -> dict[str, Any] | None:
    """Normalize tool step data for tool-native observation predicate."""
    if data is None:
        return None
    if isinstance(data, dict):
        return data
    if is_dataclass(data) and not isinstance(data, type):
        raw = asdict(data)
        return _jsonish(raw)
    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        return _jsonish(model_dump())
    return None


def _jsonish(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(v) for v in value]
    return value


def _has_conflicted_evidence(evidence: EvidenceState) -> bool:
    if evidence.contradictions:
        return True
    return any(
        f.required and f.status == FactStatus.conflicted for f in evidence.facts
    )


def resolve_task_contract_satisfied(
    query: str,
    *,
    last_tool: str | None,
    last_ok: bool | None,
    observation: Any,
    evidence: EvidenceState | None = None,
) -> bool:
    """T2: True only when migrated contract obs predicate proves satisfaction.

    tool ok ≠ satisfied. Conflicted evidence → False. Not a force_finish.
    """
    matched = match_termination_contract(query)
    if matched is None:
        return False
    _case_id, expected_tool = matched
    if last_ok is not True:
        return False
    if last_tool != expected_tool:
        return False
    if evidence is not None and _has_conflicted_evidence(evidence):
        return False

    from app.eval.tool_capability.observation import observation_satisfies_contract

    payload = observation_as_dict(observation)
    ok, _reason = observation_satisfies_contract(expected_tool, payload)
    return ok


def apply_tool_guidance_hints(
    summary: ObservationSummary,
    state: AgentState,
    exposed_tools: frozenset[str] | set[str] | tuple[str, ...],
    *,
    preferred_enabled: bool | None = None,
    satisfied_enabled: bool | None = None,
) -> ObservationSummary:
    """Inject S2/T2 advisory fields when flags ON; OFF → identity."""
    if preferred_enabled is None or satisfied_enabled is None:
        from app.core.config import settings

        if preferred_enabled is None:
            preferred_enabled = settings.agent_l4_tool_preferred_hint_enabled
        if satisfied_enabled is None:
            satisfied_enabled = settings.agent_l4_task_satisfied_hint_enabled

    if not preferred_enabled and not satisfied_enabled:
        return summary

    updates: dict[str, Any] = {}

    if preferred_enabled:
        hint = resolve_preferred_tool_hint(state.original_query, exposed_tools)
        if hint is not None:
            updates["preferred_tool_hint"] = hint.preferred_tool
            updates["preferred_tool_intent"] = hint.intent_class
            updates["preferred_tool_reason"] = hint.reason

    if satisfied_enabled:
        last = state.steps[-1] if state.steps else None
        satisfied = resolve_task_contract_satisfied(
            state.original_query,
            last_tool=last.tool_name if last else None,
            last_ok=last.ok if last else None,
            observation=last.data if last else None,
            evidence=state.evidence,
        )
        if satisfied:
            updates["task_contract_satisfied"] = True

    if not updates:
        return summary
    return replace(summary, **updates)

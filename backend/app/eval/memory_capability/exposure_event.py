"""MemoryExposureEvent contract — eval-side schema (no runtime emit).

Privacy: identifiers + content hash only; never store full memory text in events.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class MemoryExposureScope(str, Enum):
    """Counting / isolation scope for unique exposure semantics."""

    user = "user"
    thread = "thread"
    run = "run"
    step = "step"


class MemoryExposureChannel(str, Enum):
    """Which planner path assembled the model-visible prompt."""

    llm_planner = "llm_planner"
    next_action_planner = "next_action_planner"


class MemoryExposureSource(str, Enum):
    """Provenance of the exposure claim (must be prompt-boundary for L3)."""

    planner_prompt_injection = "planner_prompt_injection"
    # Non-authoritative sources — evaluator MUST reject for L3 proof
    load_only = "load_only"
    format_only = "format_only"
    state_assign_only = "state_assign_only"


CONTEXT_SLOT_PLANNER_USER_PROMPT = "planner_user_prompt"


@dataclass(frozen=True, slots=True)
class MemoryExposureEvent:
    """Minimal observability record for model-visible memory exposure.

    Prefer identifiers/hashes over raw memory content.
    """

    run_id: str
    step_id: str
    memory_hash: str
    injected_to_context: bool
    scope: MemoryExposureScope = MemoryExposureScope.run
    source: MemoryExposureSource = MemoryExposureSource.planner_prompt_injection
    context_slot: str = CONTEXT_SLOT_PLANNER_USER_PROMPT
    channel: MemoryExposureChannel = MemoryExposureChannel.next_action_planner
    memory_id: str | None = None
    proposition_id: str | None = None
    memory_key: str | None = None  # stable key id, not payload
    timestamp: str | None = None  # ISO-8601 when required by project traces

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scope"] = self.scope.value
        payload["source"] = self.source.value
        payload["channel"] = self.channel.value
        return payload


def stable_memory_hash(
    *,
    key: str,
    memory_type: str,
    value: Any,
    summary: Any | None = None,
) -> str:
    """SHA-256 of canonical key/type/payload — no raw text stored in event."""
    payload = summary if summary is not None else value
    canonical = json.dumps(
        {"key": key, "memory_type": memory_type, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_proposition_id(*, key: str, kind: str, expected: str) -> str:
    """Stable semantic id for evaluator binding (not DB uuid)."""
    raw = f"{key}|{kind}|{expected}"
    return "prop_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


MEMORY_EXPOSURE_EVENT_FIELDS: tuple[str, ...] = (
    "run_id",
    "step_id",
    "memory_id",
    "proposition_id",
    "memory_hash",
    "memory_key",
    "scope",
    "source",
    "injected_to_context",
    "context_slot",
    "channel",
    "timestamp",
)

PRIVACY_POLICY: dict[str, Any] = {
    "store_raw_memory_content": False,
    "preferred_identifiers": ["memory_id", "memory_hash", "proposition_id", "memory_key"],
    "hash_algorithm": "sha256",
    "rationale": (
        "Exposure proof needs identity of which memory entered context, "
        "not a second copy of preference text in telemetry."
    ),
}

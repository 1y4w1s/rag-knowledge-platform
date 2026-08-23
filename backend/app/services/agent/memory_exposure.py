"""Option B: emit MemoryExposureEvent at planner prompt assembly (flag-gated).

LOADED != EXPOSED: emit only after a non-empty memory_block is inserted into the
model-visible prompt. Default OFF — must not alter prompt bytes or memory order.
Privacy: identifiers/hashes only; never put memory plaintext into events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.core.config import settings
from app.eval.memory_capability.exposure_event import (
    CONTEXT_SLOT_PLANNER_USER_PROMPT,
    MemoryExposureChannel,
    MemoryExposureEvent,
    MemoryExposureScope,
    MemoryExposureSource,
    stable_memory_hash,
)

_EVENTS: list[MemoryExposureEvent] = []


@dataclass(frozen=True, slots=True)
class MemoryExposureRecord:
    """Structured identity for a memory that may become model-visible."""

    memory_hash: str
    memory_key: str | None = None
    memory_id: str | None = None
    proposition_id: str | None = None


def clear_memory_exposure_events() -> None:
    _EVENTS.clear()


def get_memory_exposure_events() -> tuple[MemoryExposureEvent, ...]:
    return tuple(_EVENTS)


def memory_exposure_trace_enabled() -> bool:
    """Observability-only flag — not agent_memory_enabled."""
    return bool(settings.agent_memory_exposure_trace_enabled)


def build_memory_exposure_records(
    memories: Sequence[Any],
) -> tuple[MemoryExposureRecord, ...]:
    """Build hash/id records from loaded AgentMemory rows (no plaintext retained)."""
    out: list[MemoryExposureRecord] = []
    for mem in memories:
        key = str(getattr(mem, "key", "") or "")
        memory_type = str(getattr(mem, "memory_type", "") or "")
        value = getattr(mem, "value", None)
        summary = getattr(mem, "summary", None)
        mid = getattr(mem, "id", None)
        out.append(
            MemoryExposureRecord(
                memory_hash=stable_memory_hash(
                    key=key,
                    memory_type=memory_type,
                    value=value,
                    summary=summary,
                ),
                memory_key=key or None,
                memory_id=str(mid) if mid is not None else None,
            )
        )
    return tuple(out)


def emit_memory_exposure_at_prompt_boundary(
    *,
    memory_block: str,
    channel: MemoryExposureChannel,
    run_id: str | None,
    step_id: str | None,
    records: Sequence[MemoryExposureRecord] | None = None,
    scope: MemoryExposureScope = MemoryExposureScope.run,
) -> tuple[MemoryExposureEvent, ...]:
    """Emit structured events only for true prompt-boundary exposure.

    No-ops when:
    - flag is OFF
    - memory_block is empty (nothing model-visible)
    - run_id / step_id missing (cannot bind L3 proof)
    - records empty (no identities to claim)
    """
    if not memory_exposure_trace_enabled():
        return ()
    if not memory_block:
        return ()
    if not run_id or not step_id:
        return ()
    if not records:
        return ()

    emitted: list[MemoryExposureEvent] = []
    seen: set[str] = set()
    for rec in records:
        if rec.memory_hash in seen:
            continue
        seen.add(rec.memory_hash)
        event = MemoryExposureEvent(
            run_id=run_id,
            step_id=step_id,
            memory_hash=rec.memory_hash,
            injected_to_context=True,
            scope=scope,
            source=MemoryExposureSource.planner_prompt_injection,
            context_slot=CONTEXT_SLOT_PLANNER_USER_PROMPT,
            channel=channel,
            memory_id=rec.memory_id,
            proposition_id=rec.proposition_id,
            memory_key=rec.memory_key,
        )
        payload = event.to_dict()
        for banned in (
            "value",
            "content",
            "summary",
            "plaintext",
            "memory_text",
            "prompt",
        ):
            if banned in payload:
                raise RuntimeError(f"privacy violation: {banned} in exposure event")
        _EVENTS.append(event)
        emitted.append(event)
    return tuple(emitted)

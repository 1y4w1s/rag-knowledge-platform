"""Dedup / scope counting semantics for MemoryExposureEvent (eval-only)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.eval.memory_capability.exposure_event import (
    MemoryExposureEvent,
    MemoryExposureScope,
    MemoryExposureSource,
)

AUTHORITATIVE_SOURCES: frozenset[MemoryExposureSource] = frozenset(
    {MemoryExposureSource.planner_prompt_injection}
)

AUTHORITATIVE_SLOTS: frozenset[str] = frozenset({"planner_user_prompt"})


def is_authoritative_exposure(event: MemoryExposureEvent) -> bool:
    """True only for model-visible prompt injection claims."""
    return (
        event.injected_to_context is True
        and event.source in AUTHORITATIVE_SOURCES
        and event.context_slot in AUTHORITATIVE_SLOTS
        and bool(event.memory_hash)
        and bool(event.run_id)
        and bool(event.step_id)
    )


def unique_exposure_key(
    event: MemoryExposureEvent,
    *,
    scope: MemoryExposureScope | None = None,
) -> tuple[str, ...]:
    """Key used to avoid double-counting unique exposure.

    Default scope=run: same memory re-injected on every decide step counts once per run.
    scope=step: each (run, step, hash) is distinct (multi-step audit).
    """
    effective = scope or event.scope
    if effective == MemoryExposureScope.step:
        return (event.run_id, event.step_id, event.memory_hash)
    if effective == MemoryExposureScope.thread:
        # thread id is not a first-class event field; run_id is the run within a thread.
        # Callers that need thread aggregation should pass a synthetic run_id = thread_id.
        return (event.run_id, event.memory_hash)
    if effective == MemoryExposureScope.user:
        return (event.run_id, event.memory_hash)
    # run (default)
    return (event.run_id, event.memory_hash)


def dedupe_unique_exposures(
    events: Sequence[MemoryExposureEvent],
    *,
    scope: MemoryExposureScope = MemoryExposureScope.run,
    authoritative_only: bool = True,
) -> tuple[MemoryExposureEvent, ...]:
    """Return first-seen authoritative events under unique_exposure_key."""
    seen: set[tuple[str, ...]] = set()
    out: list[MemoryExposureEvent] = []
    for event in events:
        if authoritative_only and not is_authoritative_exposure(event):
            continue
        key = unique_exposure_key(event, scope=scope)
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    return tuple(out)


def count_unique_exposures(
    events: Sequence[MemoryExposureEvent],
    *,
    scope: MemoryExposureScope = MemoryExposureScope.run,
) -> int:
    return len(dedupe_unique_exposures(events, scope=scope))


def filter_events_for_run_step(
    events: Iterable[MemoryExposureEvent],
    *,
    run_id: str,
    step_id: str | None = None,
) -> tuple[MemoryExposureEvent, ...]:
    matched: list[MemoryExposureEvent] = []
    for event in events:
        if event.run_id != run_id:
            continue
        if step_id is not None and event.step_id != step_id:
            continue
        matched.append(event)
    return tuple(matched)


DEDUP_SEMANTICS: dict[str, str] = {
    "multi_step_repeat_injection": (
        "Same memory_hash re-injected on steps 1..N within one run → "
        "unique count = 1 under scope=run; = N under scope=step."
    ),
    "thread_or_user_aggregation": (
        "For thread/user rollups, callers set run_id to the aggregate id or "
        "group events externally; event schema stays run/step granular."
    ),
    "loaded_without_event": "Does not contribute to unique exposure count.",
    "non_authoritative_source": "load_only / format_only / state_assign_only are ignored.",
}

"""L3_EXPOSED via MemoryExposureEvent — evaluator interface (fixtures only).

Makes L3 PROVABLE when trajectories supply structured exposure events.
Does not emit runtime events; does not change product behavior.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.eval.memory_capability.exposure_event import MemoryExposureEvent
from app.eval.memory_capability.exposure_semantics import (
    dedupe_unique_exposures,
    filter_events_for_run_step,
    is_authoritative_exposure,
)
from app.eval.memory_capability.schema import LevelResult, MeasurementLevel


def _level(
    *,
    eligible: bool,
    attempted: bool,
    passed: bool,
    reason: str = "",
) -> LevelResult:
    return LevelResult(
        level=MeasurementLevel.L3_EXPOSED,
        eligible=eligible,
        attempted=attempted,
        passed=passed,
        reason=reason,
    )


def validate_exposure_event(event: MemoryExposureEvent) -> tuple[bool, str]:
    """Structural validity for an L3-proof event (not merely loaded)."""
    if not event.run_id:
        return False, "missing run_id"
    if not event.step_id:
        return False, "missing step_id"
    if not event.memory_hash:
        return False, "missing memory_hash"
    if event.injected_to_context is not True:
        return False, "injected_to_context must be True for exposure proof"
    if not is_authoritative_exposure(event):
        return False, "non-authoritative source/slot (loaded≠exposed)"
    return True, ""


def l3_exposed_from_events(
    *,
    run_id: str,
    expected_memory_hashes: Sequence[str],
    events: Sequence[MemoryExposureEvent],
    step_id: str | None = None,
    require_all_expected: bool = True,
    empty_memory_case: bool = False,
) -> LevelResult:
    """Prove L3_EXPOSED from MemoryExposureEvent stream.

    Rules:
    - empty_memory_case: pass iff no authoritative exposures for run
    - loaded-but-no-event: fail (expected hashes with zero matching events)
    - wrong run_id / step_id / memory_hash: do not count
    - duplicates: unique semantics under scope=run
    - event with injected_to_context=False: invalid for L3
    """
    if empty_memory_case:
        scoped = filter_events_for_run_step(events, run_id=run_id, step_id=step_id)
        authoritative = [e for e in scoped if is_authoritative_exposure(e)]
        passed = len(authoritative) == 0
        return _level(
            eligible=True,
            attempted=True,
            passed=passed,
            reason="" if passed else "empty memory must not emit exposure events",
        )

    if not expected_memory_hashes:
        return _level(
            eligible=True,
            attempted=True,
            passed=False,
            reason="no expected memory hashes (not an empty-memory case)",
        )

    scoped = filter_events_for_run_step(events, run_id=run_id, step_id=step_id)
    if not scoped:
        return _level(
            eligible=True,
            attempted=True,
            passed=False,
            reason="no exposure events for run/step (loaded≠exposed)",
        )

    # Reject any scoped event that claims exposure but fails validity
    invalid = [e for e in scoped if e.injected_to_context and not is_authoritative_exposure(e)]
    if invalid:
        return _level(
            eligible=True,
            attempted=True,
            passed=False,
            reason="invalid exposure event (source/slot before true injection)",
        )

    unique = dedupe_unique_exposures(scoped)
    exposed_hashes = {e.memory_hash for e in unique}
    expected_set = set(expected_memory_hashes)

    if require_all_expected:
        missing = expected_set - exposed_hashes
        if missing:
            return _level(
                eligible=True,
                attempted=True,
                passed=False,
                reason=f"missing exposure for hashes: {sorted(missing)}",
            )
        # Extra exposures allowed (other active memories) — L3 cares about expected ones
        return _level(eligible=True, attempted=True, passed=True, reason="")

    if exposed_hashes & expected_set:
        return _level(eligible=True, attempted=True, passed=True, reason="")
    return _level(
        eligible=True,
        attempted=True,
        passed=False,
        reason="no expected memory_hash found in unique exposures",
    )


def unique_exposed_hashes(
    events: Sequence[MemoryExposureEvent],
    *,
    run_id: str,
) -> frozenset[str]:
    scoped = filter_events_for_run_step(events, run_id=run_id)
    unique = dedupe_unique_exposures(scoped)
    return frozenset(e.memory_hash for e in unique)


EVALUATOR_INTERFACE_READY: dict[str, object] = {
    "status": "READY",
    "consumes": "MemoryExposureEvent",
    "proves": "L3_EXPOSED",
    "runtime_emit": False,
    "note": (
        "MEMORY P0 evaluate_trajectory still uses exposed_context string fixtures; "
        "l3_exposed_from_events is the machine-provable path once instrumentation emits events."
    ),
}

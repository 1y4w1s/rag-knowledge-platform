"""L3 observability recommendation (design only — no product implementation)."""

from __future__ import annotations

from typing import Any

NEED_L3_PRODUCT_INSTRUMENTATION = True

MINIMAL_L3_TRACE_FIELDS: tuple[str, ...] = (
    "memory_id",
    "memory_hash",
    "injected_to_context",
    "scope",
    "position_or_source",
    "run_id",
    "step_id",
)

L3_OBSERVABILITY_RECOMMENDATION: dict[str, Any] = {
    "need_product_instrumentation": NEED_L3_PRODUCT_INSTRUMENTATION,
    "gap_id": "L3_OBSERVABILITY_GAP",
    "minimal_fields": list(MINIMAL_L3_TRACE_FIELDS),
    "rationale": (
        "L4/L5 capability measurement requires machine-observable proof that seeded "
        "memories entered model context; planner._memory_context string injection alone "
        "is not emitted as structured telemetry in production trajectories."
    ),
    "product_remediation_in_this_task": False,
}


def l3_observability_recommendation() -> dict[str, Any]:
    return L3_OBSERVABILITY_RECOMMENDATION

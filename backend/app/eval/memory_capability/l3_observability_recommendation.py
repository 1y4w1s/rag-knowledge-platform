"""L3 observability recommendation (design only — no product implementation)."""

from __future__ import annotations

from typing import Any

from app.eval.memory_capability.exposure_audit import TRUE_EXPOSURE_BOUNDARY
from app.eval.memory_capability.exposure_event import MEMORY_EXPOSURE_EVENT_FIELDS
from app.eval.memory_capability.instrumentation_options import (
    PRODUCT_PATCH_BUDGET,
    RECOMMENDED_OPTION,
)

NEED_L3_PRODUCT_INSTRUMENTATION = True

MINIMAL_L3_TRACE_FIELDS: tuple[str, ...] = tuple(MEMORY_EXPOSURE_EVENT_FIELDS)

L3_OBSERVABILITY_RECOMMENDATION: dict[str, Any] = {
    "need_product_instrumentation": NEED_L3_PRODUCT_INSTRUMENTATION,
    "gap_id": "L3_OBSERVABILITY_GAP",
    "gap_status": "CONFIRMED",
    "minimal_fields": list(MINIMAL_L3_TRACE_FIELDS),
    "true_exposure_boundary": TRUE_EXPOSURE_BOUNDARY,
    "recommended_instrumentation_option": RECOMMENDED_OPTION,
    "product_patch_budget": PRODUCT_PATCH_BUDGET,
    "rationale": (
        "L4/L5 capability measurement requires machine-observable proof that seeded "
        "memories entered model context at the planner prompt boundary "
        "(LLMPlanner._call_llm_for_plan / NextActionPlanner._call_llm); "
        "planner._memory_context assignment alone is not structured telemetry."
    ),
    "product_remediation_in_this_task": False,
    "evaluator_interface": "READY",
    "ready_for_instrumentation_implementation": True,
}


def l3_observability_recommendation() -> dict[str, Any]:
    return L3_OBSERVABILITY_RECOMMENDATION

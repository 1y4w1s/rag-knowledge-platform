"""Future instrumentation options A/B/C — design only, DO NOT implement."""

from __future__ import annotations

from typing import Any

INSTRUMENTATION_OPTIONS: dict[str, dict[str, Any]] = {
    "A": {
        "name": "Emit at load/format/assign",
        "hook_points": [
            "memory.load_active_memories",
            "memory.format_memory_context",
            "runtime planner._memory_context = …",
        ],
        "correctness": "LOW — violates loaded≠exposed; false L3 positives",
        "intrusiveness": "LOW",
        "privacy": "GOOD if hash-only",
        "testability": "EASY but wrong signal",
        "trace_consistency": "POOR vs model-visible prompt",
        "recommend": False,
    },
    "B": {
        "name": "Emit at planner prompt assembly (recommended)",
        "hook_points": [
            "planners.LLMPlanner._call_llm_for_plan (memory_block non-empty)",
            "planners.NextActionPlanner._call_llm (memory_block non-empty)",
        ],
        "correctness": "HIGH — coincides with true exposure boundary",
        "intrusiveness": "MEDIUM — two call sites + thin helper; flag-gated",
        "privacy": "GOOD — emit memory_id/hash/key only",
        "testability": "HIGH — unit-testable with fake LLM",
        "trace_consistency": "HIGH — same moment as llm_complete_with_usage",
        "recommend": True,
    },
    "C": {
        "name": "Wrap llm_complete_with_usage and parse prompt",
        "hook_points": [
            "rag.chat_llm.complete_chat_with_usage wrapper / monkeypatch",
        ],
        "correctness": "MEDIUM-HIGH if marker parsing robust",
        "intrusiveness": "HIGH — global LLM path; risk of unrelated callers",
        "privacy": "WEAK — may touch full prompt content",
        "testability": "MEDIUM — brittle string markers",
        "trace_consistency": "MEDIUM — after assembly, harder to bind memory_id",
        "recommend": False,
    },
}

RECOMMENDED_OPTION = "B"

PRODUCT_PATCH_BUDGET: dict[str, Any] = {
    "ideal": "observability-only",
    "behavior_change": "NONE",
    "files_estimated": [
        "backend/app/services/agent/planners.py",
        "backend/app/services/agent/memory_exposure.py (new thin helper, optional)",
        "backend/app/core/config.py (flag)",
        "backend/tests/test_agent_memory_exposure_trace.py (new)",
    ],
    "loc_estimated": "80–150",
    "new_event": "MemoryExposureEvent (or dict-compatible emit)",
    "tests_estimated": "6–12 unit/integration",
    "migration": False,
    "feature_flag": "agent_memory_exposure_trace_enabled",
    "flag_default": False,
    "rollout": "off by default; eval harness may enable",
    "notes": (
        "No change to which memories load/format/inject; only structured side-channel "
        "emit when memory_block is appended. Empty _memory_context → no events."
    ),
}


def instrumentation_design() -> dict[str, Any]:
    return {
        "options": INSTRUMENTATION_OPTIONS,
        "recommended": RECOMMENDED_OPTION,
        "preferred_instrumentation_point": INSTRUMENTATION_OPTIONS[RECOMMENDED_OPTION][
            "hook_points"
        ],
        "product_patch_budget": PRODUCT_PATCH_BUDGET,
        "implemented_in_this_task": False,
    }

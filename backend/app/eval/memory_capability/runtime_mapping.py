"""Runtime mapping audit — characterization only (no instrumentation changes)."""

from __future__ import annotations

from typing import Any

RUNTIME_MEMORY_PIPELINE: tuple[dict[str, str], ...] = (
    {
        "stage": "L1_SEED",
        "location": "backend/tests/test_agent_golden.py · golden_benchmark/harness.py",
        "mechanism": "upsert_memory(db, user_id, memory_type, key, value) per pre_seed_memories",
        "observable": "DB row in agent_memories after commit",
    },
    {
        "stage": "L2_LOAD",
        "location": "backend/app/services/agent/memory.py::load_active_memories",
        "mechanism": "SQL SELECT active memories with decay/confidence/governance filters",
        "observable": "list[AgentMemory] returned to runtime",
    },
    {
        "stage": "L3_EXPOSE_PREP",
        "location": "backend/app/services/agent/memory.py::format_memory_context + runtime assign",
        "mechanism": (
            "Formatted bullet list stored on planner._memory_context / "
            "init_agent_state(memory_context=...) — NOT yet model-visible"
        ),
        "observable": "planner._memory_context string; AgentState.memory_context",
    },
    {
        "stage": "L3_EXPOSE_BOUNDARY",
        "location": (
            "backend/app/services/agent/planners.py::"
            "LLMPlanner._call_llm_for_plan / NextActionPlanner._call_llm"
        ),
        "mechanism": (
            "Non-empty _memory_context appended as memory_block into prompt, "
            "then passed to llm_complete_with_usage — TRUE model-visible exposure"
        ),
        "observable": (
            "prompt content at LLM call; currently NO structured MemoryExposureEvent "
            "(see exposure_audit.py / MemoryExposureEvent contract)"
        ),
    },
    {
        "stage": "L4_CONSUME",
        "location": "backend/app/services/agent/planners.py (LLMPlanner / NextActionPlanner)",
        "mechanism": "Memory block appended to system/user prompt; no dedicated memory tool",
        "observable": "Model output / tool args only — no structured utilization trace",
    },
)

L3_OBSERVABILITY_GAP: dict[str, Any] = {
    "gap_id": "L3_OBSERVABILITY_GAP",
    "status": "CONFIRMED",
    "description": (
        "Runtime exposes memory at planner prompt assembly but does not "
        "emit a structured MemoryExposureEvent confirming which memory hashes reached "
        "the model context at each decide step."
    ),
    "impact": (
        "L3_EXPOSED can be verified in unit/integration tests that inspect planner state "
        "or fixture exposed_context strings, but trajectories lack a first-class "
        "observability hook for machine-provable exposure audit."
    ),
    "workaround_for_eval": (
        "Deterministic evaluator accepts explicit exposed_context OR MemoryExposureEvent "
        "fixtures (l3_exposed_from_events) — no product instrumentation in this task."
    ),
    "true_boundary": (
        "planners.py LLMPlanner._call_llm_for_plan / NextActionPlanner._call_llm"
    ),
    "no_memory_tool": True,
    "forbidden_taxonomy": "MODEL_IGNORES_MEMORY_TOOL",
}

RUNTIME_MAPPING_AUDIT: dict[str, Any] = {
    "pipeline": list(RUNTIME_MEMORY_PIPELINE),
    "l3_observability_gap": L3_OBSERVABILITY_GAP,
    "memory_loaded_not_memory_used": True,
    "keyword_overlap_not_semantic_utilization": True,
    "product_code_modified": False,
}


def runtime_mapping_audit() -> dict[str, Any]:
    return RUNTIME_MAPPING_AUDIT

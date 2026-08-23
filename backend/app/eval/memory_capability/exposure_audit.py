"""Static runtime audit of the MEMORY exposure pipeline (eval-only).

Read-only characterization of product code paths. No instrumentation.
Invariant: loaded ≠ exposed — assigning planner._memory_context is NOT exposure.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Pipeline stages (verified against product source — no guessing)
# ---------------------------------------------------------------------------

EXPOSURE_PIPELINE_STAGES: tuple[dict[str, Any], ...] = (
    {
        "stage": "L1_SEED",
        "file": "backend/app/services/agent/memory.py",
        "function": "upsert_memory",
        "data_shape": "DB row agent_memories(id, user_id, key, value, memory_type, …)",
        "notes": "Eval/golden harness calls upsert_memory before run; not model-visible.",
    },
    {
        "stage": "L2_LOAD",
        "file": "backend/app/services/agent/memory.py",
        "function": "load_active_memories",
        "data_shape": "list[AgentMemory] after status/suppress/decay filters, limit=20",
        "call_sites": (
            "backend/app/services/agent/runtime.py::_run_l3_next_action_loop "
            "(when settings.agent_memory_enabled)",
            "backend/app/services/agent/runtime.py::_run_agent_loop "
            "(when isinstance(planner, LLMPlanner) and agent_memory_enabled)",
            "backend/app/api/agent.py (admin/debug list path — not planner injection)",
        ),
        "notes": "Loaded rows alone are NOT model-visible.",
    },
    {
        "stage": "L2b_FORMAT",
        "file": "backend/app/services/agent/memory.py",
        "function": "format_memory_context",
        "data_shape": (
            "str bullet list: '- [{tier}] {key}: {summary|value} ({memory_type}) "
            "importance=…' with header; empty list → ''"
        ),
        "notes": "Produces prompt text; still not exposure until LLM prompt assembly.",
    },
    {
        "stage": "L2c_ASSIGN",
        "file": "backend/app/services/agent/runtime.py",
        "function": (
            "_run_l3_next_action_loop / _run_agent_loop → planner._memory_context = …; "
            "init_agent_state(memory_context=…)"
        ),
        "data_shape": "planner._memory_context: str; AgentState.memory_context: str",
        "notes": (
            "Side-channel assignment for later prompt build. "
            "NOT the model-visible exposure boundary."
        ),
    },
    {
        "stage": "L3_EXPOSE_BOUNDARY",
        "file": "backend/app/services/agent/planners.py",
        "functions": (
            "LLMPlanner._call_llm_for_plan",
            "NextActionPlanner._call_llm",
        ),
        "mechanism": (
            "memory_block = '\\n\\n用户长期偏好…\\n' + self._memory_context "
            "if self._memory_context else ''; "
            "concatenated into prompt; then llm_complete_with_usage([{role, content}])"
        ),
        "data_shape": (
            "list[dict] chat messages with role='user' and content containing memory_block"
        ),
        "notes": (
            "THIS is the real exposure boundary: memories become model-visible only when "
            "non-empty _memory_context is appended into the prompt passed to the LLM."
        ),
    },
)

TRUE_EXPOSURE_BOUNDARY: dict[str, Any] = {
    "file": "backend/app/services/agent/planners.py",
    "functions": [
        "LLMPlanner._call_llm_for_plan",
        "NextActionPlanner._call_llm",
    ],
    "condition": "bool(self._memory_context) before llm_complete_with_usage",
    "context_slot": "planner_user_prompt",
    "channels": ["llm_planner", "next_action_planner"],
    "not_exposure": [
        "load_active_memories return value",
        "format_memory_context return value alone",
        "planner._memory_context assignment",
        "AgentState.memory_context field alone",
        "AgentMemory DB rows",
    ],
}

L3_OBSERVABILITY_GAP_CONFIRMED: dict[str, Any] = {
    "gap_id": "L3_OBSERVABILITY_GAP",
    "status": "CONFIRMED",
    "description": (
        "Product injects memory into planner prompts but emits no structured "
        "MemoryExposureEvent; benchmarks cannot machine-prove which memories were "
        "model-visible on a specific (run_id, step_id) trajectory."
    ),
    "blocked_capability": ["GA-9", "GA-10", "L4_UTILIZATION_DENOM", "L5_TASK_BENEFIT_DENOM"],
    "product_instrumentation_in_this_task": False,
}

LOADED_NE_EXPOSED_INVARIANT: dict[str, str] = {
    "rule": "loaded != exposed",
    "meaning": (
        "A memory present in load_active_memories / format_memory_context output "
        "does not imply L3_EXPOSED unless a valid MemoryExposureEvent records "
        "injected_to_context=True at the planner prompt boundary."
    ),
}


def exposure_boundary_audit() -> dict[str, Any]:
    return {
        "pipeline": list(EXPOSURE_PIPELINE_STAGES),
        "true_exposure_boundary": TRUE_EXPOSURE_BOUNDARY,
        "l3_gap": L3_OBSERVABILITY_GAP_CONFIRMED,
        "invariant": LOADED_NE_EXPOSED_INVARIANT,
        "product_code_modified": False,
        "runtime_emit": False,
    }

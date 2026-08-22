"""W8 P0 research trajectory schema (eval-only; not product runtime)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = "1.0.0"
RAW_EXCERPT_CHARS = 240


class FailureClass(str, Enum):
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_MALFORMED_JSON = "MODEL_MALFORMED_JSON"
    MODEL_SCHEMA_FAILURE = "MODEL_SCHEMA_FAILURE"
    MODEL_TOOL_MAPPING_FAILURE = "MODEL_TOOL_MAPPING_FAILURE"
    MODEL_WRONG_ACTION = "MODEL_WRONG_ACTION"
    MODEL_PREMATURE_FINISH = "MODEL_PREMATURE_FINISH"
    MODEL_HALLUCINATED_TOOL = "MODEL_HALLUCINATED_TOOL"
    TOOL_EXECUTION_FAILURE = "TOOL_EXECUTION_FAILURE"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    SYSTEM_STOP_BLOCK = "SYSTEM_STOP_BLOCK"
    SYSTEM_RECOVERY = "SYSTEM_RECOVERY"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    SAFE_REFUSAL = "SAFE_REFUSAL"
    SAFE_PARTIAL = "SAFE_PARTIAL"
    UNKNOWN = "UNKNOWN"


class TrajectoryCategory(str, Enum):
    direct = "direct"
    missing_fact = "missing_fact"
    multi_fact = "multi_fact"
    conflict = "conflict"
    tool_failure = "tool_failure"
    budget = "budget"
    clarify = "clarify"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    return uuid4().hex[:12]


def excerpt_raw(raw: str | None, *, limit: int = RAW_EXCERPT_CHARS) -> str:
    text = (raw or "").replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


@dataclass(slots=True)
class StepTrace:
    step_index: int
    planner_raw_response_excerpt: str
    planner_parse_success: bool
    planner_decision: dict[str, Any]
    decision_valid: bool
    stop_policy_effect: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_success: bool | None = None
    observation_summary: str = ""
    fact_status_before: dict[str, str] = field(default_factory=dict)
    fact_status_after: dict[str, str] = field(default_factory=dict)
    evidence_coverage: float = 0.0
    conflicts: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None
    events: list[str] = field(default_factory=list)
    recoverable_if_repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrajectoryResult:
    case_id: str
    category: str
    query: str
    model_id: str
    thinking_mode: str
    started_at: str
    duration_ms: float
    terminal_action: str | None
    terminal_reason: str | None
    steps_used: int
    steps: list[StepTrace]
    task_success: bool
    safe_termination: bool
    evidence_complete: bool
    premature_finish: bool
    model_failure_count: int
    system_intervention_count: int
    timeout: bool
    failure_class: list[str]
    model_decision_success: bool
    system_safety_success: bool
    end_to_end_success: bool
    system_saved: bool
    unrecovered_model_failure: bool
    events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [s.to_dict() for s in self.steps]
        return payload


@dataclass(slots=True)
class SuiteSummary:
    trajectory_count: int
    end_to_end_success_rate: float
    safe_termination_rate: float
    premature_finish_rate: float
    planner_parse_success_rate: float
    planner_decision_valid_rate: float
    tool_selection_accuracy: float
    tool_execution_success_rate: float
    evidence_completion_rate: float
    system_intervention_rate: float
    system_recovery_success_rate: float
    system_saved_count: int
    system_saved_rate: float
    unrecovered_model_failure_rate: float
    timeout_rate: float
    budget_exhaustion_rate: float
    mean_steps: float
    median_steps: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_max_ms: float | None
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

"""L4 TOOL capability evaluator schema (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ContractStage(str, Enum):
    planner_tool_selected = "planner_tool_selected"
    tool_args_valid = "tool_args_valid"
    tool_resolver_accepted = "tool_resolver_accepted"
    tool_execution_succeeded = "tool_execution_succeeded"
    expected_observation_present = "expected_observation_present"
    post_observation_decision_valid = "post_observation_decision_valid"
    safe_terminal = "safe_terminal"


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: ContractStage
    eligible: bool
    attempted: bool
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


@dataclass(slots=True)
class ToolStepInput:
    planner_action: str
    selected_tool: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    resolver_accepted: bool | None = None
    execution_succeeded: bool | None = None
    execution_error: str | None = None
    observation: Any = None
    post_observation_action: str | None = None
    post_observation_decision_valid: bool | None = None


@dataclass(frozen=True, slots=True)
class ToolCapabilityCase:
    case_id: str
    query: str
    expected_tool: str
    required_arg_keys: tuple[str, ...] = ("query",)
    optional_mode: str | None = None


@dataclass(slots=True)
class ToolTrajectoryInput:
    case: ToolCapabilityCase
    steps: list[ToolStepInput]
    terminal_action: str | None
    terminal_reason: str | None = None
    budget_exhausted: bool = False
    safe: bool = True


@dataclass(slots=True)
class CaseEvaluation:
    case_id: str
    stages: tuple[StageResult, ...]
    task_completion: bool
    safe_termination: bool
    budget_exhausted: bool
    terminal_only_would_succeed: bool
    false_task_success_from_terminal: bool

    def stage_map(self) -> dict[str, StageResult]:
        return {s.stage.value: s for s in self.stages}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "stages": [s.to_dict() for s in self.stages],
            "task_completion": self.task_completion,
            "safe_termination": self.safe_termination,
            "budget_exhausted": self.budget_exhausted,
            "terminal_only_would_succeed": self.terminal_only_would_succeed,
            "false_task_success_from_terminal": self.false_task_success_from_terminal,
        }


@dataclass(frozen=True, slots=True)
class MetricCount:
    metric: str
    eligible: int
    attempted: int
    passed: int

    @property
    def rate(self) -> float:
        if self.attempted <= 0:
            return 0.0
        return round(self.passed / self.attempted, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "eligible": self.eligible,
            "attempted": self.attempted,
            "passed": self.passed,
            "rate": self.rate,
        }


@dataclass(slots=True)
class SuiteMetrics:
    case_count: int
    metrics: tuple[MetricCount, ...]
    task_completion_count: int
    false_task_success_count: int

    def metric_map(self) -> dict[str, MetricCount]:
        return {m.metric: m for m in self.metrics}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "metrics": [m.to_dict() for m in self.metrics],
            "task_completion_count": self.task_completion_count,
            "false_task_success_count": self.false_task_success_count,
        }

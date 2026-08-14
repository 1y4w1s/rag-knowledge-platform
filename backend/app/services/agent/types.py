"""Agent 领域类型（G3 runtime / finalize 共享）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


class ToolFailureKind(str, Enum):
    infra = "infra"
    denied = "denied"
    disabled = "disabled"
    invalid_args = "invalid_args"
    not_found = "not_found"
    quota = "quota"


@dataclass(frozen=True, slots=True)
class ToolFailure:
    kind: ToolFailureKind
    tool_name: str
    summary: str
    reason: str | None = None
    breaker_open: bool = False


@dataclass(frozen=True, slots=True)
class ToolCallPlan:
    tool_name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolStartEvent:
    step: int
    tool: str
    args_summary: str


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    step: int
    tool: str
    ok: bool
    summary: str
    latency_ms: int
    capped: bool = False


@dataclass(frozen=True, slots=True)
class AgentBudgetEvent:
    steps_used: int
    max_steps: int
    capped: bool


@dataclass(frozen=True, slots=True)
class AgentStepRecord:
    step_index: int
    tool_name: str
    args: dict[str, Any]
    ok: bool
    summary: str
    latency_ms: int
    step_id: UUID | None = None
    data: Any = None


@dataclass(frozen=True, slots=True)
class StepExecution:
    ok: bool
    summary: str
    latency_ms: int
    data: Any
    failure: ToolFailure | None = None


@dataclass(frozen=True, slots=True)
class AgentRunOutcome:
    run_id: UUID
    steps_used: int
    max_steps: int
    capped: bool
    timed_out: bool
    steps: tuple[AgentStepRecord, ...]
    low_confidence: bool = False
    tool_fallback_count: int = 0
    tool_replanned: int = 0


@dataclass(frozen=True, slots=True)
class ParseResult:
    ok: bool
    plan: list[ToolCallPlan] | None = None
    error: str | None = None
    llm_raw: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedPlan:
    ok: bool
    plan: list[ToolCallPlan] | None = None
    violations: list[str] | None = None

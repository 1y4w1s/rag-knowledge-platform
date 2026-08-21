"""Agent 领域类型（G3 runtime / finalize 共享 · L3 状态契约）。"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    # L3：显式终态 decision（finish/clarify/refuse）；legacy 路径保持 None
    terminal_decision: AgentDecision | None = None


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


# ── L3 Observation-driven 状态契约（W1；旧类型保留双轨）──────────────


class AgentActionKind(str, Enum):
    tool = "tool"
    finish = "finish"
    clarify = "clarify"
    refuse = "refuse"


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """L3 Planner 单步输出（替代整条 tool 序列）。"""

    action: AgentActionKind
    tool_name: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    reason_code: str = ""
    user_message: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionParseResult:
    """L3 单步 decision 解析结果（非 tool 序列）。"""

    ok: bool
    decision: AgentDecision | None = None
    error: str | None = None
    llm_raw: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedDecision:
    """L3 SafetyFrame 单步 decision 校验结果。"""

    ok: bool
    decision: AgentDecision | None = None
    violations: list[str] | None = None


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    """证据冲突摘要（无完整正文）。"""

    fact_a: str
    fact_b: str
    chunk_ids: tuple[UUID, ...] = ()
    note: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceState:
    required_facts: tuple[str, ...] = ()
    covered_facts: tuple[str, ...] = ()
    missing_facts: tuple[str, ...] = ()
    chunk_ids: tuple[UUID, ...] = ()
    document_ids: tuple[UUID, ...] = ()
    contradictions: tuple[EvidenceConflict, ...] = ()
    sufficient: bool = False
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class ObservationSummary:
    """供 Planner prompt 的压缩观察（禁止完整 chunk / web 正文）。"""

    original_query: str = ""
    active_query: str = ""
    steps_used: int = 0
    max_steps: int = 0
    last_tool: str | None = None
    last_ok: bool | None = None
    last_summary: str = ""
    chunk_ids: tuple[UUID, ...] = ()
    document_ids: tuple[UUID, ...] = ()
    doc_names: tuple[str, ...] = ()
    top_scores: tuple[float, ...] = ()
    evidence_sufficient: bool = False
    confidence: float = 0.0
    covered_facts: tuple[str, ...] = ()
    missing_facts: tuple[str, ...] = ()
    last_failure_kind: str | None = None
    last_failure_summary: str | None = None
    reflection_count: int = 0


@dataclass(frozen=True, slots=True)
class AgentState:
    """L3 loop 单一状态源。"""

    original_query: str
    active_query: str
    steps: tuple[AgentStepRecord, ...]
    evidence: EvidenceState
    steps_used: int
    max_steps: int
    reflection_count: int
    last_failure: ToolFailure | None = None
    memory_context: str = ""

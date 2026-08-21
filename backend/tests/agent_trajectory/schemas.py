"""Trajectory eval 数据契约（acceptable-set · 非 exact path）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.agent.types import AgentActionKind, AgentDecision


@dataclass(frozen=True, slots=True)
class AcceptableAction:
    """单步可接受动作（tool_name=None 表示任意/不适用）。"""

    action: AgentActionKind
    tool_name: str | None = None
    reason_codes: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryCase:
    """一条 trajectory 题：逐步 acceptable set + 终态集合。"""

    case_id: str
    category: str
    description: str
    # 0-based decide 序号 → 可接受集合；缺省步用 default_acceptable
    acceptable_by_step: dict[int, tuple[AcceptableAction, ...]] = field(
        default_factory=dict
    )
    default_acceptable: tuple[AcceptableAction, ...] = ()
    acceptable_terminals: tuple[AgentActionKind, ...] = (
        AgentActionKind.finish,
    )
    max_steps_soft: int | None = None  # Steps per Success 软上限（None=不检）


@dataclass(frozen=True, slots=True)
class StepScore:
    step_index: int
    decision: AgentDecision
    in_acceptable_set: bool


@dataclass(frozen=True, slots=True)
class TrajectoryScore:
    case_id: str
    category: str
    tool_selection_ok: bool
    stop_accuracy_ok: bool
    dependency_ok: bool
    steps_used: int
    redundant_tool_count: int
    task_success: bool
    details: tuple[StepScore, ...]
    terminal_action: AgentActionKind | None = None

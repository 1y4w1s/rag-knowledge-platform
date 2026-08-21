"""Trajectory 评分：acceptable-set / stop / dependency / redundant。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.agent.types import AgentActionKind, AgentDecision

from tests.agent_trajectory.schemas import (
    AcceptableAction,
    StepScore,
    TrajectoryCase,
    TrajectoryScore,
)

# dependent tools：无前序 ID 时不得作为「正确依赖」
_DEPENDENT_TOOLS = frozenset(
    {"get_chunk_excerpt", "grep_in_document", "compare_chunks"}
)


def matches_acceptable(
    decision: AgentDecision,
    acceptable: AcceptableAction,
) -> bool:
    if decision.action != acceptable.action:
        return False
    if acceptable.tool_name is not None and decision.tool_name != acceptable.tool_name:
        return False
    if acceptable.reason_codes is not None:
        if decision.reason_code not in acceptable.reason_codes:
            return False
    return True


def in_acceptable_set(
    decision: AgentDecision,
    acceptables: tuple[AcceptableAction, ...],
) -> bool:
    return any(matches_acceptable(decision, a) for a in acceptables)


def _acceptable_for_step(
    case: TrajectoryCase,
    step_index: int,
) -> tuple[AcceptableAction, ...]:
    if step_index in case.acceptable_by_step:
        return case.acceptable_by_step[step_index]
    return case.default_acceptable


def _redundant_tool_count(decisions: list[AgentDecision]) -> int:
    """同 tool_name + 同 args 重复计为冗余（成本信号）。"""
    keys: list[tuple[str, str]] = []
    for d in decisions:
        if d.action != AgentActionKind.tool or not d.tool_name:
            continue
        # args 规范化：仅用稳定 repr（测试侧可控）
        args_key = repr(sorted((d.args or {}).items()))
        keys.append((d.tool_name, args_key))
    counts = Counter(keys)
    return sum(c - 1 for c in counts.values() if c > 1)


def _dependency_ok(
    decisions: list[AgentDecision],
    *,
    had_chunk_ids_before_dependent: bool | None,
) -> bool:
    """若调用 dependent tool，须声明「此前已有 chunk/doc ID」。

    had_chunk_ids_before_dependent:
      - True / False：用例显式告知
      - None：无 dependent 调用则通过；有调用则默认 Fail（须用例声明）
    """
    used_dependent = any(
        d.action == AgentActionKind.tool and d.tool_name in _DEPENDENT_TOOLS
        for d in decisions
    )
    if not used_dependent:
        return True
    if had_chunk_ids_before_dependent is None:
        return False
    return bool(had_chunk_ids_before_dependent)


def score_trajectory(
    case: TrajectoryCase,
    *,
    decisions: list[AgentDecision],
    terminal: AgentDecision | None,
    steps_used: int,
    had_chunk_ids_before_dependent: bool | None = None,
) -> TrajectoryScore:
    """对一次轨迹打分（不要求唯一 exact path）。"""
    details: list[StepScore] = []
    selection_ok = True
    for i, decision in enumerate(decisions):
        acceptables = _acceptable_for_step(case, i)
        ok = bool(acceptables) and in_acceptable_set(decision, acceptables)
        if not acceptables:
            # 未声明的步：宽松跳过（避免 exact-path 强迫）
            ok = True
        if not ok:
            selection_ok = False
        details.append(
            StepScore(step_index=i, decision=decision, in_acceptable_set=ok)
        )

    terminal_action = terminal.action if terminal is not None else None
    stop_ok = (
        terminal_action in case.acceptable_terminals
        if case.acceptable_terminals
        else terminal_action is not None
    )
    if case.max_steps_soft is not None and steps_used > case.max_steps_soft:
        stop_ok = False

    dep_ok = _dependency_ok(
        decisions, had_chunk_ids_before_dependent=had_chunk_ids_before_dependent
    )
    redundant = _redundant_tool_count(decisions)
    task_ok = selection_ok and stop_ok and dep_ok

    return TrajectoryScore(
        case_id=case.case_id,
        category=case.category,
        tool_selection_ok=selection_ok,
        stop_accuracy_ok=stop_ok,
        dependency_ok=dep_ok,
        steps_used=steps_used,
        redundant_tool_count=redundant,
        task_success=task_ok,
        details=tuple(details),
        terminal_action=terminal_action,
    )


def summarize_scores(scores: list[TrajectoryScore]) -> dict[str, Any]:
    """离线/CI 摘要（成功率 · stop · recovery 占位字段）。"""
    n = len(scores)
    if n == 0:
        return {
            "n": 0,
            "task_success_rate": 0.0,
            "stop_accuracy_rate": 0.0,
            "tool_selection_rate": 0.0,
            "avg_steps_per_success": 0.0,
            "redundant_tool_total": 0,
        }
    successes = [s for s in scores if s.task_success]
    return {
        "n": n,
        "task_success_rate": sum(1 for s in scores if s.task_success) / n,
        "stop_accuracy_rate": sum(1 for s in scores if s.stop_accuracy_ok) / n,
        "tool_selection_rate": sum(1 for s in scores if s.tool_selection_ok) / n,
        "avg_steps_per_success": (
            sum(s.steps_used for s in successes) / len(successes) if successes else 0.0
        ),
        "redundant_tool_total": sum(s.redundant_tool_count for s in scores),
        "by_category": {
            cat: sum(1 for s in scores if s.category == cat and s.task_success)
            / max(1, sum(1 for s in scores if s.category == cat))
            for cat in sorted({s.category for s in scores})
        },
    }

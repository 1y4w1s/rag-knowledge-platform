"""Deterministic seven-stage TOOL capability evaluator."""

from __future__ import annotations

from app.eval.tool_capability.args_validation import validate_tool_args
from app.eval.tool_capability.contract import CURRENT_L3_TOOL_CAPABILITY_STAGES
from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.tool_capability.schema import (
    CaseEvaluation,
    ContractStage,
    StageResult,
    ToolStepInput,
    ToolTrajectoryInput,
)

_VALID_POST_OBSERVATION_ACTIONS = frozenset({"finish", "refuse", "clarify", "tool"})


def _first_tool_step(steps: list[ToolStepInput]) -> ToolStepInput | None:
    for step in steps:
        if step.planner_action == "tool":
            return step
    return None


def _terminal_only_success(trajectory: ToolTrajectoryInput) -> bool:
    return trajectory.terminal_action == "finish" and trajectory.safe and not trajectory.budget_exhausted


def evaluate_trajectory(trajectory: ToolTrajectoryInput) -> CaseEvaluation:
    case = trajectory.case
    tool_step = _first_tool_step(trajectory.steps)
    stage_results: list[StageResult] = []

    # Stage 1 — planner_tool_selected
    s1_passed = bool(
        tool_step is not None
        and tool_step.selected_tool == case.expected_tool
    )
    s1 = StageResult(
        stage=ContractStage.planner_tool_selected,
        eligible=True,
        attempted=True,
        passed=s1_passed,
        reason="" if s1_passed else "wrong or missing tool selection",
    )
    stage_results.append(s1)

    # Stage 2 — tool_args_valid
    s2_attempted = s1_passed and tool_step is not None
    if s2_attempted:
        args_ok, args_reason = validate_tool_args(case.expected_tool, tool_step.tool_args)
        if case.optional_mode and tool_step.tool_args.get("mode") != case.optional_mode:
            args_ok = False
            args_reason = f"expected mode={case.optional_mode}"
    else:
        args_ok, args_reason = False, "skipped: tool not selected"
    s2 = StageResult(
        stage=ContractStage.tool_args_valid,
        eligible=True,
        attempted=s2_attempted,
        passed=bool(s2_attempted and args_ok),
        reason=args_reason,
    )
    stage_results.append(s2)

    # Stage 3 — tool_resolver_accepted
    s3_attempted = s2.passed and tool_step is not None
    if s3_attempted:
        resolver_ok = tool_step.resolver_accepted is True
        resolver_reason = "" if resolver_ok else "resolver rejected tool call"
    else:
        resolver_ok = False
        resolver_reason = "skipped: invalid args"
    s3 = StageResult(
        stage=ContractStage.tool_resolver_accepted,
        eligible=True,
        attempted=s3_attempted,
        passed=bool(s3_attempted and resolver_ok),
        reason=resolver_reason,
    )
    stage_results.append(s3)

    # Stage 4 — tool_execution_succeeded
    s4_attempted = s3.passed and tool_step is not None
    if s4_attempted:
        exec_ok = tool_step.execution_succeeded is True
        exec_reason = "" if exec_ok else (tool_step.execution_error or "execution failed")
    else:
        exec_ok = False
        exec_reason = "skipped: resolver did not accept"
    s4 = StageResult(
        stage=ContractStage.tool_execution_succeeded,
        eligible=True,
        attempted=s4_attempted,
        passed=bool(s4_attempted and exec_ok),
        reason=exec_reason,
    )
    stage_results.append(s4)

    # Stage 5 — expected_observation_present
    s5_attempted = s4.passed and tool_step is not None
    if s5_attempted:
        obs_ok, obs_reason = observation_satisfies_contract(
            case.expected_tool,
            tool_step.observation,
        )
    else:
        obs_ok = False
        obs_reason = "skipped: execution did not succeed"
    s5 = StageResult(
        stage=ContractStage.expected_observation_present,
        eligible=True,
        attempted=s5_attempted,
        passed=bool(s5_attempted and obs_ok),
        reason=obs_reason,
    )
    stage_results.append(s5)

    # Stage 6 — post_observation_decision_valid
    s6_attempted = s5.passed
    post_action = tool_step.post_observation_action if tool_step else None
    if s6_attempted and tool_step is not None:
        if tool_step.post_observation_decision_valid is not None:
            post_ok = tool_step.post_observation_decision_valid
            post_reason = "" if post_ok else "explicit invalid post-observation decision"
        elif post_action in {"finish", "refuse", "clarify"}:
            post_ok = True
            post_reason = ""
        elif post_action == "tool":
            post_ok = False
            post_reason = "premature re-tool without task completion"
        else:
            post_ok = False
            post_reason = "missing post-observation decision"
    else:
        post_ok = False
        post_reason = "skipped: expected observation absent"
    s6 = StageResult(
        stage=ContractStage.post_observation_decision_valid,
        eligible=True,
        attempted=s6_attempted,
        passed=bool(s6_attempted and post_ok),
        reason=post_reason,
    )
    stage_results.append(s6)

    # Stage 7 — safe_terminal
    s7_attempted = s6.passed
    terminal_ok = (
        trajectory.safe
        and trajectory.terminal_action in {"finish", "refuse", "clarify"}
        and not trajectory.budget_exhausted
    )
    s7 = StageResult(
        stage=ContractStage.safe_terminal,
        eligible=True,
        attempted=s7_attempted,
        passed=bool(s7_attempted and terminal_ok),
        reason="" if terminal_ok else "unsafe or budget-exhausted terminal",
    )
    stage_results.append(s7)

    all_stages_pass = all(s.passed for s in stage_results)
    task_completion = all_stages_pass and not trajectory.budget_exhausted
    terminal_only = _terminal_only_success(trajectory)
    false_from_terminal = terminal_only and not task_completion

    return CaseEvaluation(
        case_id=case.case_id,
        stages=tuple(stage_results),
        task_completion=task_completion,
        safe_termination=trajectory.safe and not trajectory.budget_exhausted,
        budget_exhausted=trajectory.budget_exhausted,
        terminal_only_would_succeed=terminal_only,
        false_task_success_from_terminal=false_from_terminal,
    )


def all_contract_stages() -> tuple[str, ...]:
    return tuple(s.value for s in CURRENT_L3_TOOL_CAPABILITY_STAGES)

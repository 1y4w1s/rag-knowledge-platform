"""CURRENT_L3_TOOL_CAPABILITY_CONTRACT — seven deterministic evaluation stages."""

from __future__ import annotations

from app.eval.tool_capability.schema import ContractStage

CURRENT_L3_TOOL_CAPABILITY_STAGES: tuple[ContractStage, ...] = (
    ContractStage.planner_tool_selected,
    ContractStage.tool_args_valid,
    ContractStage.tool_resolver_accepted,
    ContractStage.tool_execution_succeeded,
    ContractStage.expected_observation_present,
    ContractStage.post_observation_decision_valid,
    ContractStage.safe_terminal,
)

STAGE_ORDER: tuple[str, ...] = tuple(s.value for s in CURRENT_L3_TOOL_CAPABILITY_STAGES)

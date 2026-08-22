"""Deterministic fixtures for ADAPT TOOL cases (GQ-131, GQ-132, GQ-149)."""

from __future__ import annotations

from app.eval.tool_capability.schema import (
    ToolCapabilityCase,
    ToolStepInput,
    ToolTrajectoryInput,
)

GQ131_CASE = ToolCapabilityCase(
    case_id="GQ-131",
    query="How to search documents across knowledge bases?",
    expected_tool="search_documents",
    required_arg_keys=("query",),
)

GQ132_CASE = ToolCapabilityCase(
    case_id="GQ-132",
    query="List all knowledge bases endpoint",
    expected_tool="list_knowledge_bases",
    required_arg_keys=(),
)

GQ149_CASE = ToolCapabilityCase(
    case_id="GQ-149",
    query="Search documents by content mode",
    expected_tool="search_documents",
    required_arg_keys=("query",),
    optional_mode="content",
)

_SEARCH_OBSERVATION = {
    "total": 2,
    "summary": "正文匹配 2 篇",
    "items": [
        {
            "document_id": "doc-001",
            "kb_id": "kb-001",
            "kb_name": "Engineering",
            "filename": "api_guide.md",
            "snippet": "search documents across knowledge bases",
        }
    ],
}

_KB_OBSERVATION = {
    "total": 3,
    "scope_label": "personal",
    "summary": "可见库 3 个 · personal",
    "items": [
        {
            "kb_id": "kb-001",
            "name": "Engineering",
            "document_count": 12,
        },
        {
            "kb_id": "kb-002",
            "name": "HR Policies",
            "document_count": 5,
        },
    ],
}


def gq131_success_trajectory() -> ToolTrajectoryInput:
    return ToolTrajectoryInput(
        case=GQ131_CASE,
        steps=[
            ToolStepInput(
                planner_action="tool",
                selected_tool="search_documents",
                tool_args={"query": "search documents across knowledge bases"},
                resolver_accepted=True,
                execution_succeeded=True,
                observation=_SEARCH_OBSERVATION,
                post_observation_action="finish",
                post_observation_decision_valid=True,
            )
        ],
        terminal_action="finish",
        terminal_reason="tool_task_complete",
        safe=True,
    )


def gq132_success_trajectory() -> ToolTrajectoryInput:
    return ToolTrajectoryInput(
        case=GQ132_CASE,
        steps=[
            ToolStepInput(
                planner_action="tool",
                selected_tool="list_knowledge_bases",
                tool_args={"q": "List all knowledge bases endpoint"},
                resolver_accepted=True,
                execution_succeeded=True,
                observation=_KB_OBSERVATION,
                post_observation_action="finish",
                post_observation_decision_valid=True,
            )
        ],
        terminal_action="finish",
        terminal_reason="tool_task_complete",
        safe=True,
    )


def gq149_success_trajectory() -> ToolTrajectoryInput:
    return ToolTrajectoryInput(
        case=GQ149_CASE,
        steps=[
            ToolStepInput(
                planner_action="tool",
                selected_tool="search_documents",
                tool_args={"query": "content search query", "mode": "content"},
                resolver_accepted=True,
                execution_succeeded=True,
                observation={
                    **_SEARCH_OBSERVATION,
                    "summary": "正文匹配 1 篇",
                    "mode": "content",
                },
                post_observation_action="finish",
                post_observation_decision_valid=True,
            )
        ],
        terminal_action="finish",
        terminal_reason="tool_task_complete",
        safe=True,
    )


ADAPT_FIXTURE_TRAJECTORIES: dict[str, ToolTrajectoryInput] = {
    "GQ-131": gq131_success_trajectory(),
    "GQ-132": gq132_success_trajectory(),
    "GQ-149": gq149_success_trajectory(),
}

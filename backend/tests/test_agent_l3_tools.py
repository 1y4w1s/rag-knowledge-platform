"""L3-W4：ToolSpec requires/produces + ToolResolver dependent tools 解锁。"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.agent.planners import SafetyFrame
from app.services.agent.state import init_agent_state
from app.services.agent.tool_resolver import (
    DEPENDENT_TOOL_NAMES,
    DEPENDENT_TOOL_SPECS,
    INDEPENDENT_TOOL_SPECS,
    RESOURCE_CHUNK_ID,
    RESOURCE_DOCUMENT_ID,
    ToolResolver,
    ToolSpec,
    is_dependent_unlocked,
    resources_from_state,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    EvidenceState,
)


def test_critic_and_dynamic_tools_flags_default_false() -> None:
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.rag_critic_enabled is False


def test_tool_spec_requires_produces_on_catalog() -> None:
    by_name = {s.name: s for s in (*INDEPENDENT_TOOL_SPECS, *DEPENDENT_TOOL_SPECS)}
    assert RESOURCE_CHUNK_ID in by_name["semantic_search"].produces
    assert RESOURCE_DOCUMENT_ID in by_name["semantic_search"].produces
    assert by_name["semantic_search"].requires == frozenset()

    excerpt = by_name["get_chunk_excerpt"]
    assert excerpt.requires == frozenset({RESOURCE_CHUNK_ID})
    assert RESOURCE_CHUNK_ID in excerpt.produces

    grep = by_name["grep_in_document"]
    assert grep.requires == frozenset({RESOURCE_DOCUMENT_ID})

    compare = by_name["compare_chunks"]
    assert compare.requires == frozenset({RESOURCE_CHUNK_ID})


def test_resolver_flag_off_only_independent() -> None:
    state = init_agent_state(original_query="q", max_steps=5)
    # 即使已有 ID，flag 关也不解锁
    state = replace(
        state,
        evidence=EvidenceState(
            chunk_ids=(uuid4(), uuid4()),
            document_ids=(uuid4(),),
        ),
    )
    names = ToolResolver.available_names(
        state, dynamic_enabled=False, external_tools_enabled=True
    )
    assert names == frozenset(s.name for s in INDEPENDENT_TOOL_SPECS)
    assert names.isdisjoint(DEPENDENT_TOOL_NAMES)


def test_resolver_flag_on_empty_state_no_dependent() -> None:
    state = init_agent_state(original_query="q", max_steps=5)
    names = ToolResolver.available_names(
        state, dynamic_enabled=True, external_tools_enabled=True
    )
    assert names == frozenset(s.name for s in INDEPENDENT_TOOL_SPECS)
    assert names.isdisjoint(DEPENDENT_TOOL_NAMES)


def test_resolver_unlocks_excerpt_and_grep_with_ids() -> None:
    chunk_id = uuid4()
    doc_id = uuid4()
    state = init_agent_state(original_query="q", max_steps=5)
    state = replace(
        state,
        evidence=EvidenceState(chunk_ids=(chunk_id,), document_ids=(doc_id,)),
    )
    assert resources_from_state(state) == frozenset(
        {RESOURCE_CHUNK_ID, RESOURCE_DOCUMENT_ID}
    )
    names = ToolResolver.available_names(
        state, dynamic_enabled=True, external_tools_enabled=True
    )
    assert "get_chunk_excerpt" in names
    assert "grep_in_document" in names
    # 仅 1 个 chunk → compare 仍锁
    assert "compare_chunks" not in names


def test_resolver_unlocks_compare_with_two_chunks() -> None:
    state = init_agent_state(original_query="q", max_steps=5)
    state = replace(
        state,
        evidence=EvidenceState(chunk_ids=(uuid4(), uuid4())),
    )
    names = ToolResolver.available_names(
        state, dynamic_enabled=True, external_tools_enabled=True
    )
    assert "get_chunk_excerpt" in names
    assert "compare_chunks" in names
    assert "grep_in_document" not in names  # 无 document_id


def test_is_dependent_unlocked_compare_needs_two() -> None:
    compare = next(s for s in DEPENDENT_TOOL_SPECS if s.name == "compare_chunks")
    state = init_agent_state(original_query="q", max_steps=5)
    state_one = replace(state, evidence=EvidenceState(chunk_ids=(uuid4(),)))
    state_two = replace(
        state, evidence=EvidenceState(chunk_ids=(uuid4(), uuid4()))
    )
    assert is_dependent_unlocked(compare, state_one) is False
    assert is_dependent_unlocked(compare, state_two) is True


def test_validate_decision_rejects_locked_dependent_tool() -> None:
    frame = SafetyFrame("复杂对比问题以及分别是多少？")
    state = init_agent_state(original_query="q", max_steps=5)
    available = ToolResolver.available_names(
        state, dynamic_enabled=True, external_tools_enabled=True
    )
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="get_chunk_excerpt",
        args={"chunk_id": str(uuid4())},
        reason_code="need_excerpt",
    )
    result = frame.validate_decision(
        decision, state, available_tools=available
    )
    assert result.ok is False
    assert any("not currently available" in v for v in (result.violations or []))


def test_validate_decision_allows_unlocked_excerpt() -> None:
    frame = SafetyFrame("复杂对比问题以及分别是多少？")
    chunk_id = uuid4()
    state = init_agent_state(original_query="q", max_steps=5)
    state = replace(state, evidence=EvidenceState(chunk_ids=(chunk_id,)))
    available = ToolResolver.available_names(
        state, dynamic_enabled=True, external_tools_enabled=True
    )
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="get_chunk_excerpt",
        args={"chunk_id": str(chunk_id)},
        reason_code="need_excerpt",
    )
    result = frame.validate_decision(
        decision, state, available_tools=available
    )
    assert result.ok is True


def test_tool_spec_default_requires_produces_empty() -> None:
    spec = ToolSpec(name="x", description="d", parameters={})
    assert spec.requires == frozenset()
    assert spec.produces == frozenset()


@pytest.mark.asyncio
async def test_next_action_planner_uses_resolver_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """flag 开 + 有 chunk → decide_next 可见面含 excerpt（mock LLM）。"""
    from app.services.agent.planners import NextActionPlanner, parse_agent_decision

    monkeypatch.setattr(settings, "agent_l3_dynamic_tools_enabled", True)
    monkeypatch.setattr(settings, "external_tools_enabled", False)

    frame = SafetyFrame("复杂对比问题以及分别是多少？")
    planner = NextActionPlanner(
        "复杂对比问题以及分别是多少？",
        safety_frame=frame,
        tool_specs=list(INDEPENDENT_TOOL_SPECS),
    )
    state = init_agent_state(original_query="q", max_steps=5)
    state = replace(
        state,
        evidence=EvidenceState(chunk_ids=(uuid4(),)),
    )
    available = planner._available_tools(state)
    names = {s.name for s in available}
    assert "get_chunk_excerpt" in names
    assert "web_search" not in names  # external 关

    raw = (
        '{"action":"tool","tool_name":"get_chunk_excerpt",'
        f'"args":{{"chunk_id":"{state.evidence.chunk_ids[0]}"}},'
        '"reason_code":"need_excerpt"}'
    )

    async def _fake_llm(summary, tool_specs):  # noqa: ANN001
        del summary, tool_specs
        return parse_agent_decision(raw)

    monkeypatch.setattr(planner, "_call_llm", _fake_llm)
    decision = await planner.decide_next(state)
    assert decision.action == AgentActionKind.tool
    assert decision.tool_name == "get_chunk_excerpt"

"""TOOL P3 product experiments ? S2 preferred-tool + T2 task-satisfied hints.

Deterministic safety tests. Flags default OFF; OFF must not change L3 baseline.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.eval.tool_capability.fixtures import (
    GQ132_CASE,
    GQ149_CASE,
    gq132_success_trajectory,
    gq149_success_trajectory,
)
from app.services.agent.planners import _build_next_action_prompt
from app.services.agent.state import init_agent_state, summarize_state_for_planner
from app.services.agent.tool_guidance_hints import (
    apply_tool_guidance_hints,
    intent_class_for_query,
    resolve_preferred_tool_hint,
    resolve_task_contract_satisfied,
)
from app.services.agent.types import (
    AgentStepRecord,
    EvidenceConflict,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
)

_EXPOSED = frozenset(
    {"semantic_search", "search_documents", "list_knowledge_bases"}
)
_GQ131_QUERY = "How to search documents across knowledge bases?"


def _state(query: str, *, max_steps: int = 5):
    return init_agent_state(original_query=query, max_steps=max_steps)


def test_tool_guidance_flags_default_off() -> None:
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False


def test_s2_gq131_emits_preferred_search_documents() -> None:
    hint = resolve_preferred_tool_hint(_GQ131_QUERY, _EXPOSED)
    assert hint is not None
    assert hint.preferred_tool == "search_documents"
    assert hint.intent_class == "catalog_search"
    assert hint.case_id == "GQ-131"


def test_s2_hard_negatives_no_false_preferred() -> None:
    sem = resolve_preferred_tool_hint(
        "What does the leave policy say about sick days according to the handbook?",
        _EXPOSED,
    )
    assert sem is not None
    assert sem.preferred_tool == "semantic_search"

    cat = resolve_preferred_tool_hint(
        "Search documents by filename for leave-policy.pdf",
        _EXPOSED,
    )
    assert cat is not None
    assert cat.preferred_tool == "search_documents"

    assert (
        resolve_preferred_tool_hint(
            "Search documents and explain what the policy means",
            _EXPOSED,
        )
        is None
    )
    assert (
        intent_class_for_query("Search documents and explain what the policy means")
        == "ambiguous"
    )

    assert (
        resolve_preferred_tool_hint(
            "Delete all knowledge bases and purge storage",
            _EXPOSED,
        )
        is None
    )
    assert (
        resolve_preferred_tool_hint(
            "List knowledge bases then summarize onboarding docs",
            _EXPOSED,
        )
        is None
    )
    assert (
        intent_class_for_query("List knowledge bases then summarize onboarding docs")
        == "multi_step"
    )


def test_s2_non_exposed_preferred_is_no_hint() -> None:
    exposed = frozenset({"semantic_search", "list_knowledge_bases"})
    assert resolve_preferred_tool_hint(_GQ131_QUERY, exposed) is None


def test_s2_off_leaves_summary_and_prompt_identical() -> None:
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    state = _state(_GQ131_QUERY)
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base,
        state,
        _EXPOSED,
        preferred_enabled=False,
        satisfied_enabled=False,
    )
    assert out is base
    assert out.preferred_tool_hint is None
    assert out.task_contract_satisfied is False

    prompt_off = _build_next_action_prompt("- semantic_search: x", out)
    prompt_base = _build_next_action_prompt("- semantic_search: x", base)
    assert "preferred_tool_hint" not in prompt_off
    assert "task_contract_satisfied" not in prompt_off
    assert prompt_off == prompt_base


def test_s2_on_injects_advisory_without_forcing_decision() -> None:
    state = _state(_GQ131_QUERY)
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base,
        state,
        _EXPOSED,
        preferred_enabled=True,
        satisfied_enabled=False,
    )
    assert out is not base
    assert out.preferred_tool_hint == "search_documents"
    assert out.preferred_tool_intent == "catalog_search"
    prompt = _build_next_action_prompt(
        "- semantic_search: a\n- search_documents: b",
        out,
    )
    assert "preferred_tool_hint" in prompt
    assert "search_documents" in prompt
    assert "advisory" in prompt.lower()


def test_ablation_matrix_flags_independent() -> None:
    """00 / 10 / 01 / 11 ? flags gate independently."""
    state = _state(_GQ131_QUERY)
    base = summarize_state_for_planner(state)

    off = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=False, satisfied_enabled=False
    )
    s2 = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=True, satisfied_enabled=False
    )
    t2 = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=False, satisfied_enabled=True
    )
    both = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=True, satisfied_enabled=True
    )
    assert off.preferred_tool_hint is None and off.task_contract_satisfied is False
    assert s2.preferred_tool_hint == "search_documents"
    assert s2.task_contract_satisfied is False
    assert t2.preferred_tool_hint is None
    assert t2.task_contract_satisfied is False
    assert both.preferred_tool_hint == "search_documents"
    assert both.task_contract_satisfied is False


def _step(
    tool: str,
    *,
    ok: bool,
    data: object,
    args: dict | None = None,
) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=0,
        tool_name=tool,
        args=args or {},
        ok=ok,
        summary="ok" if ok else "fail",
        latency_ms=1,
        step_id=uuid4(),
        data=data,
    )


def test_t2_gq132_and_gq149_satisfied_when_obs_complete() -> None:
    for case, traj in (
        (GQ132_CASE, gq132_success_trajectory()),
        (GQ149_CASE, gq149_success_trajectory()),
    ):
        step = traj.steps[0]
        assert resolve_task_contract_satisfied(
            case.query,
            last_tool=step.selected_tool,
            last_ok=True,
            observation=step.observation,
        )


def test_t2_partial_wrong_failed_conflict_false() -> None:
    q132 = GQ132_CASE.query
    q149 = GQ149_CASE.query

    assert not resolve_task_contract_satisfied(
        q132,
        last_tool="list_knowledge_bases",
        last_ok=True,
        observation={"total": 0, "items": [], "summary": "empty"},
    )

    assert not resolve_task_contract_satisfied(
        q149,
        last_tool="search_documents",
        last_ok=True,
        observation={"hits": [{"chunk_id": "c1", "score": 0.9}]},
    )

    assert not resolve_task_contract_satisfied(
        q149,
        last_tool="search_documents",
        last_ok=False,
        observation=None,
    )

    assert not resolve_task_contract_satisfied(
        q132,
        last_tool="semantic_search",
        last_ok=True,
        observation={
            "hits": [
                {
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "score": 0.9,
                    "excerpt": "policy",
                }
            ]
        },
    )

    conflicted = EvidenceState(
        facts=(
            FactGoal(
                id="F1",
                text="conflict",
                kind=FactKind.condition,
                status=FactStatus.conflicted,
                required=True,
            ),
        ),
        contradictions=(
            EvidenceConflict(fact_a="A", fact_b="B", note="disagree"),
        ),
    )
    good_kb = gq132_success_trajectory().steps[0].observation
    assert not resolve_task_contract_satisfied(
        q132,
        last_tool="list_knowledge_bases",
        last_ok=True,
        observation=good_kb,
        evidence=conflicted,
    )


def test_t2_off_identical_to_baseline() -> None:
    assert settings.agent_l4_task_satisfied_hint_enabled is False
    traj = gq132_success_trajectory()
    step = traj.steps[0]
    state = _state(GQ132_CASE.query)
    state = replace(
        state,
        steps=(
            _step(
                step.selected_tool,
                ok=True,
                data=step.observation,
                args=dict(step.tool_args),
            ),
        ),
        steps_used=1,
    )
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base,
        state,
        _EXPOSED,
        preferred_enabled=False,
        satisfied_enabled=False,
    )
    assert out is base
    assert out.task_contract_satisfied is False
    prompt = _build_next_action_prompt("- list_knowledge_bases: x", out)
    assert "task_contract_satisfied" not in prompt


def test_t2_on_injects_satisfied_advisory_only() -> None:
    traj = gq132_success_trajectory()
    step = traj.steps[0]
    state = _state(GQ132_CASE.query)
    state = replace(
        state,
        steps=(
            _step(
                step.selected_tool,
                ok=True,
                data=step.observation,
                args=dict(step.tool_args),
            ),
        ),
        steps_used=1,
    )
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base,
        state,
        _EXPOSED,
        preferred_enabled=False,
        satisfied_enabled=True,
    )
    assert out.task_contract_satisfied is True
    assert out.preferred_tool_hint is None
    prompt = _build_next_action_prompt("- list_knowledge_bases: x", out)
    assert "task_contract_satisfied" in prompt
    assert "NOT force_finish" in prompt
    assert "StopPolicy" in prompt


def test_t2_tool_ok_alone_is_not_satisfied() -> None:
    assert not resolve_task_contract_satisfied(
        GQ149_CASE.query,
        last_tool="search_documents",
        last_ok=True,
        observation={"total": 1, "items": [{"document_id": "d1"}]},
    )


@pytest.mark.parametrize(
    ("preferred", "satisfied"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_apply_respects_explicit_flag_matrix(
    preferred: bool, satisfied: bool
) -> None:
    state = _state(GQ132_CASE.query)
    step = gq132_success_trajectory().steps[0]
    state = replace(
        state,
        steps=(_step(step.selected_tool, ok=True, data=step.observation),),
        steps_used=1,
    )
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base,
        state,
        _EXPOSED,
        preferred_enabled=preferred,
        satisfied_enabled=satisfied,
    )
    if preferred:
        assert out.preferred_tool_hint is None or out.preferred_tool_hint in _EXPOSED
    else:
        assert out.preferred_tool_hint is None
    if satisfied:
        assert out.task_contract_satisfied is True
    else:
        assert out.task_contract_satisfied is False

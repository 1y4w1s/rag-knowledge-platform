"""TOOL S3A product experiment ? contrastive tool-description selection.

Deterministic safety tests. Flag default OFF; OFF must be identity.
Never remaps AgentDecision / exposed set / ToolResolver.
"""

from __future__ import annotations

from app.core.config import settings
from app.eval.tool_selection_p5.candidates import S3A_DESCRIPTIONS as FROZEN_S3A
from app.services.agent.planners import _build_next_action_prompt, _build_tool_descriptions
from app.services.agent.state import init_agent_state, summarize_state_for_planner
from app.services.agent.tool_contrastive_selection import (
    S3A_DESCRIPTIONS,
    apply_contrastive_tool_descriptions,
    contrastive_selection_eligible,
    s3a_intent_class,
)
from app.services.agent.tool_guidance_hints import (
    apply_tool_guidance_hints,
    resolve_preferred_tool_hint,
    resolve_task_contract_satisfied,
)
from app.services.agent.tool_resolver import INDEPENDENT_TOOL_SPECS, ToolSpec
from app.services.agent.types import ObservationSummary

_EXPOSED = frozenset({"semantic_search", "search_documents", "list_knowledge_bases"})
_GQ131 = "How to search documents across knowledge bases?"


def _specs(*names: str) -> list[ToolSpec]:
    by_name = {s.name: s for s in INDEPENDENT_TOOL_SPECS}
    return [by_name[n] for n in names]


def test_s3a_flag_default_off() -> None:
    assert settings.agent_l4_tool_contrastive_selection_enabled is False
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False


def test_s3a_descriptions_match_frozen_p5() -> None:
    assert S3A_DESCRIPTIONS == FROZEN_S3A


def test_s3a_off_is_identity() -> None:
    specs = _specs("semantic_search", "search_documents", "list_knowledge_bases")
    out = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=False)
    assert out is specs
    for a, b in zip(out, specs):
        assert a.description == b.description
        assert a.name == b.name
        assert a.parameters == b.parameters


def test_s3a_on_rewrites_competing_descriptions_for_catalog() -> None:
    specs = _specs("semantic_search", "search_documents", "list_knowledge_bases")
    out = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    assert [s.name for s in out] == [s.name for s in specs]
    assert out is not specs
    by = {s.name: s for s in out}
    assert by["semantic_search"].description == S3A_DESCRIPTIONS["semantic_search"]
    assert by["search_documents"].description == S3A_DESCRIPTIONS["search_documents"]
    assert by["list_knowledge_bases"].description == S3A_DESCRIPTIONS["list_knowledge_bases"]
    assert by["search_documents"].parameters == specs[1].parameters


def test_s3a_on_rewrites_for_true_semantic() -> None:
    q = "What does the leave policy say about sick days according to the handbook?"
    assert s3a_intent_class(q) == "semantic_qa"
    specs = _specs("semantic_search", "search_documents")
    out = apply_contrastive_tool_descriptions(specs, q, enabled=True)
    assert out[0].description == S3A_DESCRIPTIONS["semantic_search"]
    assert out[1].description == S3A_DESCRIPTIONS["search_documents"]


def test_s3a_hard_negatives_fail_closed_no_rewrite() -> None:
    specs = _specs("semantic_search", "search_documents", "list_knowledge_bases")
    cases = [
        ("Search documents and explain what the policy means", "ambiguous"),
        ("List knowledge bases then summarize onboarding docs", "multi_tool"),
        ("Delete all knowledge bases and purge storage", "oos"),
        ("Find materials about onboarding across knowledge bases", "ambiguous"),
    ]
    for query, intent in cases:
        assert s3a_intent_class(query) == intent, query
        assert contrastive_selection_eligible(query, _EXPOSED) is False
        out = apply_contrastive_tool_descriptions(specs, query, enabled=True)
        assert out is specs


def test_s3a_true_catalog_eligible() -> None:
    q = "Search documents by filename for leave-policy.pdf"
    assert s3a_intent_class(q) == "catalog_search"
    assert contrastive_selection_eligible(q, _EXPOSED) is True


def test_s3a_missing_competitor_fails_closed() -> None:
    specs = _specs("semantic_search", "list_knowledge_bases")
    out = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    assert out is specs
    assert contrastive_selection_eligible(_GQ131, frozenset(s.name for s in specs)) is False


def test_s3a_does_not_mutate_exposed_set_or_order() -> None:
    specs = _specs("list_knowledge_bases", "search_documents", "semantic_search")
    out = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    assert [s.name for s in out] == [s.name for s in specs]


def test_s3a_prompt_contains_contrastive_text_when_on() -> None:
    specs = _specs("semantic_search", "search_documents")
    rewritten = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    desc = _build_tool_descriptions(rewritten)
    assert "passage" in desc.lower() or "chunk" in desc.lower() or "Top-N" in desc
    assert "filename" in desc or "document_id" in desc
    summary = ObservationSummary(original_query=_GQ131)
    prompt = _build_next_action_prompt(desc, summary)
    assert "search_documents" in prompt
    assert "semantic_search" in prompt


def test_s3a_does_not_emit_preferred_hint() -> None:
    state = init_agent_state(original_query=_GQ131, max_steps=5)
    base = summarize_state_for_planner(state)
    out = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=False, satisfied_enabled=False
    )
    assert out.preferred_tool_hint is None
    specs = _specs("semantic_search", "search_documents")
    apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    assert out.preferred_tool_hint is None


def test_s2_historical_semantics_preserved() -> None:
    hint = resolve_preferred_tool_hint(_GQ131, _EXPOSED)
    assert hint is not None
    assert hint.preferred_tool == "search_documents"
    assert hint.intent_class == "catalog_search"
    assert hint.case_id == "GQ-131"
    assert (
        resolve_preferred_tool_hint(
            "Search documents and explain what the policy means", _EXPOSED
        )
        is None
    )


def test_t2_unaffected_by_s3a_module() -> None:
    assert (
        resolve_task_contract_satisfied(
            _GQ131,
            last_tool="search_documents",
            last_ok=True,
            observation={"documents": [{"document_id": "x"}]},
        )
        is False
    )
    assert settings.agent_l4_task_satisfied_hint_enabled is False


def test_s2_s3a_compatibility_matrix() -> None:
    specs = _specs("semantic_search", "search_documents", "list_knowledge_bases")
    state = init_agent_state(original_query=_GQ131, max_steps=5)
    base = summarize_state_for_planner(state)

    off_specs = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=False)
    off_sum = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=False, satisfied_enabled=False
    )
    assert off_specs is specs
    assert off_sum.preferred_tool_hint is None

    s2_specs = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=False)
    s2_sum = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=True, satisfied_enabled=False
    )
    assert s2_specs is specs
    assert s2_sum.preferred_tool_hint == "search_documents"

    s3_specs = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    s3_sum = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=False, satisfied_enabled=False
    )
    assert s3_specs is not specs
    assert s3_sum.preferred_tool_hint is None
    assert s3_specs[0].description == S3A_DESCRIPTIONS["semantic_search"]

    both_specs = apply_contrastive_tool_descriptions(specs, _GQ131, enabled=True)
    both_sum = apply_tool_guidance_hints(
        base, state, _EXPOSED, preferred_enabled=True, satisfied_enabled=False
    )
    assert both_specs[1].description == S3A_DESCRIPTIONS["search_documents"]
    assert both_sum.preferred_tool_hint == "search_documents"


def test_non_retrieval_and_multi_tool_no_deterministic_override() -> None:
    specs = _specs("semantic_search", "search_documents", "list_knowledge_bases")
    for q in (
        "List knowledge bases then summarize onboarding docs",
        "Delete all knowledge bases and purge storage",
    ):
        out = apply_contrastive_tool_descriptions(specs, q, enabled=True)
        assert out is specs

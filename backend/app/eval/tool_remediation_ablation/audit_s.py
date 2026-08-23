"""Family S audit — why semantic_search wins over search_documents (frozen P2)."""

from __future__ import annotations

from typing import Any

from app.eval.tool_remediation_ablation.corpus import first_tool_name, reconstruct_trials
from app.eval.tool_remediation_ablation.models import FAMILY_S_CASE, FailureFamily

# Frozen product description snapshot (read-only audit; not patched here).
PRODUCT_DESCRIPTIONS: dict[str, str] = {
    "semantic_search": "语义搜索，根据查询语义检索相关文档片段（返回 Top-N 命中）",
    "search_documents": "文档搜索，按文件名或内容搜索文档元信息",
    "list_knowledge_bases": "列出用户当前可见的知识库列表",
}

# Inventory order as exposed to planner (INDEPENDENT_TOOL_SPECS order).
EXPOSED_ORDER: tuple[str, ...] = (
    "semantic_search",
    "search_documents",
    "list_knowledge_bases",
)

# NextAction prompt example leads with semantic_search.
PROMPT_EXAMPLE_LEAD_TOOL = "semantic_search"

PARAM_SCHEMA_SIMILARITY = {
    "both_require_query": True,
    "semantic_search_params": ("query",),
    "search_documents_params": ("query", "mode"),
    "overlap": ("query",),
}


def audit_family_s(trials: tuple[Any, ...] | None = None) -> dict[str, Any]:
    """Return structured root-cause audit for Family S (GQ-131 × 5)."""
    trials = trials or reconstruct_trials()
    s_trials = [t for t in trials if t.family == FailureFamily.S_TOOL_SELECTION]
    assert len(s_trials) == 5
    assert all(t.case_id == FAMILY_S_CASE for t in s_trials)
    assert all(first_tool_name(t) == "semantic_search" for t in s_trials)

    query = s_trials[0].query
    factors = {
        "descriptions": {
            "semantic_search": PRODUCT_DESCRIPTIONS["semantic_search"],
            "search_documents": PRODUCT_DESCRIPTIONS["search_documents"],
            "bias": (
                "search_documents is framed as metadata (元信息) while the user asks "
                "how to search documents; semantic_search is framed as content retrieval, "
                "so the model treats a 'how to search' question as RAG passage search."
            ),
        },
        "name_semantics": {
            "query_tokens": ["search", "documents", "knowledge", "bases"],
            "tool_name_overlap": {
                "search_documents": ["search", "documents"],
                "semantic_search": ["search"],
            },
            "note": (
                "Lexical overlap favors search_documents, yet first action is still "
                "semantic_search — ordering + description framing dominate name match."
            ),
        },
        "ordering": {
            "exposed_order": list(EXPOSED_ORDER),
            "first_listed": EXPOSED_ORDER[0],
            "prompt_example_lead_tool": PROMPT_EXAMPLE_LEAD_TOOL,
            "bias": "semantic_search is listed first and used in the JSON example.",
        },
        "schema_similarity": PARAM_SCHEMA_SIMILARITY,
        "query_wording": {
            "query": query,
            "catalog_cues": ["search documents", "across knowledge bases"],
            "semantic_qa_cues": [],
            "note": (
                "Query is catalog/capability how-to, not a content question needing "
                "chunk evidence; contract expects search_documents."
            ),
        },
        "planner_hints": {
            "reason_code_observed": "initial_retrieval",
            "finish_rules_irrelevant_at_step0": True,
            "no_preferred_tool_hint": True,
        },
        "observation_history": {
            "step0_has_prior_obs": False,
            "later_switch": (
                "All 5 trials switch to search_documents only on final budget step "
                "after empty semantic_search hits — late correction, not first-action fix."
            ),
        },
    }

    root = (
        "PLANNER_WRONG_TOOL: competing independent tools with overlapping query schemas; "
        "semantic_search wins via inventory/example ordering + content-retrieval framing, "
        "while search_documents is under-described as metadata-only — not model stupidity."
    )
    return {
        "family": FailureFamily.S_TOOL_SELECTION.value,
        "case_id": FAMILY_S_CASE,
        "trials": 5,
        "actual_first_tool": "semantic_search",
        "expected_tool": "search_documents",
        "both_exposed": True,
        "root_cause": root,
        "factors": factors,
        "not_root_causes": [
            "model is dumb",
            "ToolResolver rejection",
            "args schema invalid",
            "unsafe terminal",
        ],
    }

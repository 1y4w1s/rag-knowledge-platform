"""Family S offline selection candidates (S0–S4) — eval-only, no product wiring."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.eval.tool_remediation_ablation.audit_s import PRODUCT_DESCRIPTIONS
from app.eval.tool_remediation_ablation.models import SelectionSample, Verdict

# S1: description disambiguation only (eval snapshot, not product patch).
S1_DESCRIPTIONS: dict[str, str] = {
    "semantic_search": (
        "Retrieve Top-N passage/chunk hits by meaning to answer content questions. "
        "Do NOT use for listing documents, filename lookup, or 'how to search documents' "
        "catalog/capability questions."
    ),
    "search_documents": (
        "Find documents across knowledge bases by filename or content mode; returns "
        "document_id/filename metadata. Prefer this for document search / catalog / "
        "cross-KB document lookup questions (including 'how to search documents')."
    ),
    "list_knowledge_bases": PRODUCT_DESCRIPTIONS["list_knowledge_bases"],
}

_CATALOG_PATTERNS = (
    re.compile(r"search documents", re.I),
    re.compile(r"across knowledge bases", re.I),
    re.compile(r"by\s+(filename|content)\s+mode", re.I),
    re.compile(r"list documents", re.I),
    re.compile(r"document search", re.I),
)
_SEMANTIC_PATTERNS = (
    re.compile(r"\bwhat (does|is|are)\b", re.I),
    re.compile(r"\bexplain\b", re.I),
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bsummarize\b", re.I),
    re.compile(r"\bwhy\b", re.I),
)


def intent_class_for_query(query: str) -> str:
    catalog = any(p.search(query) for p in _CATALOG_PATTERNS)
    semantic = any(p.search(query) for p in _SEMANTIC_PATTERNS)
    if catalog and not semantic:
        return "catalog_search"
    if semantic and not catalog:
        return "semantic_qa"
    if catalog and semantic:
        return "ambiguous"
    return "ambiguous"


def intent_unambiguous_catalog(query: str) -> bool:
    return intent_class_for_query(query) == "catalog_search"


def _token_overlap_score(query: str, text: str) -> float:
    q_tokens = {t for t in re.findall(r"[a-z0-9_\u4e00-\u9fff]+", query.lower()) if len(t) > 1}
    d_tokens = {t for t in re.findall(r"[a-z0-9_\u4e00-\u9fff]+", text.lower()) if len(t) > 1}
    if not q_tokens or not d_tokens:
        return 0.0
    return len(q_tokens & d_tokens) / len(q_tokens)


def lexical_select(
    query: str,
    exposed: tuple[str, ...],
    descriptions: dict[str, str],
) -> str:
    """Deterministic proxy for description-driven selection (offline stand-in for LLM)."""
    best_tool = exposed[0]
    best_score = -1.0
    for idx, name in enumerate(exposed):
        desc = descriptions.get(name, name)
        # Prefer stronger description match; tiny tie-break favors later tools to
        # counteract first-position bias when scores equal.
        score = _token_overlap_score(query, f"{name} {desc}") + idx * 1e-6
        # Boost explicit catalog intent toward search_documents when desc mentions it.
        if name == "search_documents" and intent_unambiguous_catalog(query):
            if "document" in desc.lower() or "catalog" in desc.lower() or "filename" in desc.lower():
                score += 0.35
        if name == "semantic_search" and intent_class_for_query(query) == "semantic_qa":
            if "passage" in desc.lower() or "chunk" in desc.lower() or "语义" in desc:
                score += 0.35
        if score > best_score:
            best_score = score
            best_tool = name
    return best_tool


def apply_s0(sample: SelectionSample) -> str:
    return sample.selected_tool


def apply_s1(sample: SelectionSample) -> str:
    """Description disambiguation via lexical proxy over S1 descriptions."""
    return lexical_select(sample.query, sample.exposed_tools, S1_DESCRIPTIONS)


def apply_s0_lexical_baseline(sample: SelectionSample) -> str:
    return lexical_select(sample.query, sample.exposed_tools, PRODUCT_DESCRIPTIONS)


NO_HINT = "NO_HINT"


def s2_preferred_tool_hint(sample: SelectionSample) -> str:
    """Advisory structured preferred_tool_hint (freeze S2).

    Returns a tool name only when task intent/contract is unambiguous for the
    competing search pair; otherwise NO_HINT. Never a deterministic override.
    """
    competing = frozenset({"semantic_search", "search_documents"})
    if sample.selected_tool not in competing:
        return NO_HINT
    if intent_unambiguous_catalog(sample.query) and "search_documents" in sample.exposed_tools:
        return "search_documents"
    if intent_class_for_query(sample.query) == "semantic_qa" and "semantic_search" in sample.exposed_tools:
        return "semantic_search"
    return NO_HINT


def apply_s2(sample: SelectionSample) -> str:
    """Offline apply of S2 advisory hint (if NO_HINT, keep planner selection)."""
    hint = s2_preferred_tool_hint(sample)
    if hint == NO_HINT:
        return sample.selected_tool
    return hint


def apply_s3(sample: SelectionSample) -> str:
    """Deterministic narrow selection guard — only if intent unambiguous."""
    if (
        intent_unambiguous_catalog(sample.query)
        and sample.selected_tool == "semantic_search"
        and "search_documents" in sample.exposed_tools
    ):
        return "search_documents"
    if (
        intent_class_for_query(sample.query) == "semantic_qa"
        and sample.selected_tool == "search_documents"
        and "semantic_search" in sample.exposed_tools
    ):
        return "semantic_search"
    return sample.selected_tool


def apply_s4(sample: SelectionSample) -> str:
    """Remove competing tool (DIAGNOSTIC ONLY) — drop semantic_search from inventory."""
    remaining = tuple(t for t in sample.exposed_tools if t != "semantic_search")
    if not remaining:
        return sample.selected_tool
    if sample.selected_tool == "semantic_search":
        # Reselect with disambiguated descriptions (diagnostic inventory ablation).
        return lexical_select(sample.query, remaining, S1_DESCRIPTIONS)
    if sample.selected_tool not in remaining:
        return remaining[0]
    return sample.selected_tool


S_CANDIDATES: dict[str, Callable[[SelectionSample], str]] = {
    "S0": apply_s0,
    "S1": apply_s1,
    "S2": apply_s2,
    "S3": apply_s3,
    "S4": apply_s4,
}

S_META: dict[str, dict[str, Any]] = {
    "S0": {
        "label": "baseline",
        "complexity": "none",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "none",
        "default_verdict": Verdict.REJECT,
        "rationale": "Frozen first-action remains semantic_search; no remediation.",
    },
    "S1": {
        "label": "description_disambiguation_only",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "low_prompt_drift",
        "default_verdict": Verdict.ACCEPT,
        "rationale": (
            "Rewrites competing tool descriptions so catalog vs passage intent diverge; "
            "no inventory/resolver change."
        ),
    },
    "S2": {
        "label": "task_intent_preferred_tool_hint",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": False,  # advisory hint only; not a deterministic selection override
        "deterministic_override": False,
        "product_mode": "advisory_preferred_tool_hint",
        "safety_risk": "medium_if_intent_overfires",
        "default_verdict": Verdict.ACCEPT,
        "rationale": (
            "Advisory structured preferred_tool_hint from unambiguous task intent/contract; "
            "ambiguous → NO_HINT; planner retains legal selection (no deterministic override)."
        ),
    },
    "S3": {
        "label": "deterministic_narrow_selection_guard",
        "complexity": "medium",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "medium_false_remap",
        "default_verdict": Verdict.ACCEPT,
        "rationale": "Remaps semantic_search→search_documents only when catalog intent unambiguous.",
    },
    "S4": {
        "label": "remove_competing_tool_diagnostic",
        "complexity": "high",
        "scope_expansion": True,
        "deterministic": True,
        "safety_risk": "high_capability_loss",
        "default_verdict": Verdict.DIAGNOSTIC_ONLY,
        "rationale": (
            "Hiding semantic_search recovers catalog cases but expands product scope "
            "negatively (drops a primary RAG tool) — diagnostic only, not a product rec."
        ),
    },
}


def _s_hard_negative_regression(sample: SelectionSample, chosen: str) -> bool:
    """True when candidate introduces unsafe/incorrect selection pressure."""
    if sample.expected_tool is not None:
        return chosen != sample.expected_tool
    # Ambiguous / OOS: any active remap is a regression; especially toward must_not_force.
    if chosen != sample.selected_tool:
        return True
    return False


def score_selection_candidate(
    candidate_id: str,
    targets: list[SelectionSample],
    hard_negatives: list[SelectionSample],
) -> dict[str, Any]:
    fn = S_CANDIDATES[candidate_id]
    meta = S_META[candidate_id]
    details: list[dict[str, Any]] = []
    recovered = 0
    for sample in targets:
        chosen = fn(sample)
        ok = chosen == sample.expected_tool
        if ok:
            recovered += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "source": sample.source,
                "chosen": chosen,
                "expected": sample.expected_tool,
                "recovered": ok,
            }
        )

    regressions = 0
    false_behavior = 0
    for sample in hard_negatives:
        chosen = fn(sample)
        bad = _s_hard_negative_regression(sample, chosen)
        if bad:
            regressions += 1
            if sample.must_not_force_tool and chosen == sample.must_not_force_tool:
                false_behavior += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "source": sample.source,
                "intent_class": sample.intent_class,
                "chosen": chosen,
                "expected": sample.expected_tool,
                "must_not_force": sample.must_not_force_tool,
                "regression": bad,
            }
        )

    if candidate_id == "S0":
        verdict = Verdict.REJECT
    elif candidate_id == "S4":
        verdict = Verdict.DIAGNOSTIC_ONLY
    elif recovered == 0:
        verdict = Verdict.REJECT
    elif regressions > 0:
        verdict = Verdict.REJECT
    elif meta["scope_expansion"]:
        verdict = Verdict.DIAGNOSTIC_ONLY
    else:
        verdict = Verdict.ACCEPT

    return {
        "candidate_id": candidate_id,
        "family": "S",
        "target_count": len(targets),
        "target_recovered": recovered,
        "hard_negative_count": len(hard_negatives),
        "hard_negative_regressions": regressions,
        "new_false_behavior": false_behavior,
        "safety_risk": meta["safety_risk"],
        "scope_expansion": meta["scope_expansion"],
        "deterministic": meta["deterministic"],
        "complexity": meta["complexity"],
        "verdict": verdict,
        "rationale": meta["rationale"],
        "details": details,
        "label": meta["label"],
    }

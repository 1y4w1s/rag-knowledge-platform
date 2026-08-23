"""Offline S3A–S3F candidates — deterministic proxies only (no LM Studio)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Tuple

from app.eval.tool_selection_p5.models import (
    EXPECTED_TOOL,
    STUBBORN_TOOL,
    CandidateScore,
    SelectionSample,
    Verdict,
)

S3A_DESCRIPTIONS: Dict[str, str] = {
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
    "list_knowledge_bases": "List knowledge bases currently visible to the user.",
}

# Strong catalog cues only — "across knowledge bases" alone is insufficient
# (avoids classifying both-reasonable retrieval as hard catalog_search).
_CATALOG = (
    re.compile(r"search documents", re.I),
    re.compile(r"by\s+(filename|content)\s+mode", re.I),
    re.compile(r"list documents", re.I),
    re.compile(r"document search", re.I),
    re.compile(r"\bfilename\b", re.I),
    re.compile(r"how to search documents", re.I),
)
_SEMANTIC = (
    re.compile(r"\bwhat (does|is|are)\b", re.I),
    re.compile(r"\bexplain\b", re.I),
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bsummarize\b", re.I),
    re.compile(r"\bwhy\b", re.I),
    re.compile(r"\bsay about\b", re.I),
)
_MULTI = (re.compile(r"\bthen\b", re.I), re.compile("然后"), re.compile("接着"))
_OOS = (re.compile(r"\bdelete\b", re.I), re.compile(r"\bpurge\b", re.I), re.compile("删除"))


def intent_class(query: str) -> str:
    if any(p.search(query) for p in _OOS):
        return "oos"
    if any(p.search(query) for p in _MULTI):
        return "multi_tool"
    catalog = any(p.search(query) for p in _CATALOG)
    semantic = any(p.search(query) for p in _SEMANTIC)
    if catalog and not semantic:
        return "catalog_search"
    if semantic and not catalog:
        return "semantic_qa"
    return "ambiguous"


def _tok_overlap(query: str, text: str) -> float:
    q = {t for t in re.findall(r"[a-z0-9_\u4e00-\u9fff]+", query.lower()) if len(t) > 1}
    d = {t for t in re.findall(r"[a-z0-9_\u4e00-\u9fff]+", text.lower()) if len(t) > 1}
    if not q or not d:
        return 0.0
    return len(q & d) / float(len(q))


def lexical_select(
    query: str,
    exposed: Tuple[str, ...],
    descriptions: Dict[str, str],
    order_bias: float = 0.0,
) -> str:
    best = exposed[0]
    best_score = -1.0
    intent = intent_class(query)
    for idx, name in enumerate(exposed):
        desc = descriptions.get(name, name)
        score = _tok_overlap(query, "%s %s" % (name, desc)) + idx * 1e-6
        score += max(0, len(exposed) - idx) * order_bias
        if name == "search_documents" and intent == "catalog_search":
            if any(k in desc.lower() for k in ("document", "catalog", "filename", "meta")):
                score += 0.4
        if name == "semantic_search" and intent == "semantic_qa":
            if any(k in desc.lower() for k in ("passage", "chunk", "meaning", "语义")):
                score += 0.4
        if score > best_score:
            best_score = score
            best = name
    return best


def apply_s0(sample: SelectionSample) -> str:
    return sample.selected_tool


def apply_s3a(sample: SelectionSample) -> str:
    # Only rewrite descriptions' influence when intent is unambiguous.
    # Ambiguous / both-reasonable / multi / oos keep planner autonomy (no hard remap).
    intent = intent_class(sample.query)
    if intent not in ("catalog_search", "semantic_qa"):
        return sample.selected_tool
    return lexical_select(sample.query, sample.exposed_tools, S3A_DESCRIPTIONS)


def apply_s3b(sample: SelectionSample) -> str:
    intent = intent_class(sample.query)
    hint = sample.preferred_hint
    if hint and intent == "catalog_search" and hint in sample.exposed_tools:
        return hint
    if hint and intent == "semantic_qa" and hint in sample.exposed_tools:
        return hint
    return sample.selected_tool


def apply_s3c(sample: SelectionSample) -> str:
    intent = intent_class(sample.query)
    if (
        sample.preferred_hint
        and intent == "catalog_search"
        and sample.selected_tool != sample.preferred_hint
        and sample.preferred_hint in sample.exposed_tools
    ):
        return sample.preferred_hint
    return sample.selected_tool


def apply_s3d(sample: SelectionSample) -> str:
    intent = intent_class(sample.query)
    if intent == "catalog_search" and "search_documents" in sample.exposed_tools:
        return "search_documents"
    if intent == "semantic_qa" and "semantic_search" in sample.exposed_tools:
        return "semantic_search"
    return sample.selected_tool


def apply_s3e(sample: SelectionSample) -> str:
    intent = intent_class(sample.query)
    if (
        intent == "catalog_search"
        and sample.selected_tool == STUBBORN_TOOL
        and EXPECTED_TOOL in sample.exposed_tools
    ):
        return EXPECTED_TOOL
    if (
        intent == "semantic_qa"
        and sample.selected_tool == EXPECTED_TOOL
        and STUBBORN_TOOL in sample.exposed_tools
    ):
        return STUBBORN_TOOL
    return sample.selected_tool


def apply_s3f(sample: SelectionSample) -> str:
    productish = {
        "semantic_search": "语义搜索，根据查询语义检索相关文档片段（返回 Top-N 命中）",
        "search_documents": "文档搜索，按文件名或内容搜索文档元信息",
        "list_knowledge_bases": "列出用户当前可见的知识库列表",
    }
    exposed = tuple(
        sorted(sample.exposed_tools, key=lambda n: 0 if n == "search_documents" else 1)
    )
    return lexical_select(sample.query, exposed, productish, order_bias=0.05)


CANDIDATES: Dict[str, Callable[[SelectionSample], str]] = {
    "S0": apply_s0,
    "S3A": apply_s3a,
    "S3B": apply_s3b,
    "S3C": apply_s3c,
    "S3D": apply_s3d,
    "S3E": apply_s3e,
    "S3F": apply_s3f,
}

# B4/B5 freeze — offline proxies only. Status is READY_FOR_PRODUCT_EXPERIMENT (B6).
META: Dict[str, Dict[str, Any]] = {
    "S0": {
        "label": "frozen_baseline",
        "complexity": "none",
        "scope_change": "none",
        "autonomy_impact": "none",
        "status": "BASELINE",
        "rationale": "Frozen first-action remains semantic_search; S2 already failed in P4.",
    },
    "S3A": {
        "label": "contrastive_tool_description_clarification",
        "complexity": "low",
        "scope_change": "prompt_descriptions_only",
        "autonomy_impact": "low",
        "status": "READY_FOR_PRODUCT_EXPERIMENT",
        "exact_semantics": (
            "For unambiguous catalog_search / semantic_qa intents only, replace competing "
            "tool description text with contrastive S3A_DESCRIPTIONS and re-score via "
            "lexical_select. Ambiguous / both_reasonable / multi_tool / oos keep the "
            "planner's original selected_tool (no hard remap)."
        ),
        "target_mechanism": (
            "Attacks contributing D (description framing) and C (order/description coupling) "
            "so the planner's own selection contract can prefer search_documents on catalog "
            "how-to queries without a binding preferred_tool override."
        ),
        "why_differs_from_s2": (
            "S2 injects an advisory preferred_tool_hint beside unchanged descriptions; "
            "S3A changes the tool-identity evidence the planner reads (descriptions), "
            "not a side-channel recommendation. Addresses A/E by removing reliance on "
            "non-binding hint compliance."
        ),
        "hard_negatives": "0/6 offline regressions required",
        "target_recovery": "10/10 offline proxy on frozen GQ-131 targets",
        "regressions": "must remain 0 on hard-negative strata",
        "rationale": (
            "Clarify competing tool descriptions without forcing selection; "
            "preserves planner autonomy; addresses D/C contribution."
        ),
    },
    "S3B": {
        "label": "preferred_plus_explicit_discouraged_competitor",
        "complexity": "low",
        "scope_change": "prompt_advisory_strengthening",
        "autonomy_impact": "low",
        "status": "READY_FOR_PRODUCT_EXPERIMENT",
        "role": "FALLBACK",
        "mechanism": (
            "When intent is unambiguous catalog_search or semantic_qa AND a preferred_hint "
            "is present and exposed, follow the hint (offline optimistic compliance bound). "
            "Otherwise keep selected_tool. Product form would strengthen advisory text: "
            "preferred + explicitly discourage the competing stubborn tool — still not a "
            "hard runtime guard."
        ),
        "safety_tradeoff": (
            "Stronger advice raises compliance odds but still can be ignored by the model; "
            "if mis-applied on ambiguous strata it risks false preferred selections — hence "
            "fallback-only and HN gate of 0 regressions."
        ),
        "why_fallback_only": (
            "Does not fix root A/E (hint remains advisory semantics); depends on hint "
            "emission + intent gate; S3A is preferred because it changes description "
            "evidence without re-centering on the failed S2 side-channel."
        ),
        "hard_negatives": "0/6 offline regressions required",
        "rationale": (
            "Strengthen advisory: preferred + discourage competing tool; still non-hard-guard. "
            "Targets E without killing autonomy. Optimistic offline compliance upper bound."
        ),
    },
    "S3C": {
        "label": "structured_tool_choice_rationale_slot",
        "complexity": "medium",
        "scope_change": "prompt_schema",
        "autonomy_impact": "low",
        "status": "REJECT",
        "rationale": "Forces rationale comparing tools; higher complexity than S3A/B.",
    },
    "S3D": {
        "label": "two_stage_intent_then_planner",
        "complexity": "high",
        "scope_change": "architecture",
        "autonomy_impact": "medium",
        "status": "REJECT",
        "rationale": "Extra stage expands scope/complexity; intent remap risks HN overfire.",
    },
    "S3E": {
        "label": "deterministic_routing_guard",
        "complexity": "medium",
        "scope_change": "runtime_guard",
        "autonomy_impact": "kills_autonomy",
        "status": "DIAGNOSTIC_ONLY",
        "rationale": "DIAGNOSTIC ONLY per D5 — never product-implement in P5.",
    },
    "S3F": {
        "label": "tool_order_permutation_bias_control",
        "complexity": "low",
        "scope_change": "inventory_order_only",
        "autonomy_impact": "none",
        "status": "DIAGNOSTIC_ONLY",
        "rationale": "Bias control / diagnostic for ordering contribution — not a product fix alone.",
    },
}


def _entropy(tools: List[str]) -> float:
    if not tools:
        return 0.0
    counts = Counter(tools)
    n = len(tools)
    ent = 0.0
    for c in counts.values():
        p = c / float(n)
        ent -= p * math.log(p, 2)
    return ent


def _hn_regression(sample: SelectionSample, chosen: str) -> bool:
    if sample.expected_tool is not None:
        return chosen != sample.expected_tool
    if sample.must_not_force_tool and chosen == sample.must_not_force_tool:
        return True
    return chosen != sample.selected_tool


def score_candidate(
    candidate_id: str,
    targets: List[SelectionSample],
    hard_negatives: List[SelectionSample],
) -> CandidateScore:
    fn = CANDIDATES[candidate_id]
    meta = META[candidate_id]
    details: List[Dict[str, Any]] = []
    recovered = 0
    chosen_targets: List[str] = []
    for sample in targets:
        chosen = fn(sample)
        chosen_targets.append(chosen)
        ok = chosen == sample.expected_tool
        if ok:
            recovered += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "panel": sample.panel,
                "chosen": chosen,
                "expected": sample.expected_tool,
                "recovered": ok,
            }
        )

    regressions = 0
    false_preferred = 0
    for sample in hard_negatives:
        chosen = fn(sample)
        bad = _hn_regression(sample, chosen)
        if bad:
            regressions += 1
        if sample.must_not_force_tool and chosen == sample.must_not_force_tool:
            false_preferred += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "panel": sample.panel,
                "intent_class": sample.intent_class,
                "chosen": chosen,
                "expected": sample.expected_tool,
                "must_not_force": sample.must_not_force_tool,
                "regression": bad,
            }
        )

    if candidate_id == "S0":
        verdict = Verdict.REJECT
    elif candidate_id in ("S3E", "S3F"):
        verdict = Verdict.DIAGNOSTIC_ONLY
    elif recovered == 0:
        verdict = Verdict.REJECT
    elif regressions > 0:
        verdict = Verdict.REJECT
    elif meta["complexity"] == "high":
        verdict = Verdict.REJECT
    elif candidate_id == "S3A":
        verdict = Verdict.PRIMARY
    elif candidate_id == "S3B":
        verdict = Verdict.FALLBACK
    else:
        verdict = Verdict.REJECT

    return CandidateScore(
        candidate_id=candidate_id,
        label=meta["label"],
        target_count=len(targets),
        target_recovered=recovered,
        hard_negative_count=len(hard_negatives),
        hard_negative_regressions=regressions,
        false_preferred_selections=false_preferred,
        tool_choice_entropy=_entropy(chosen_targets),
        scope_change=meta["scope_change"],
        complexity=meta["complexity"],
        autonomy_impact=meta["autonomy_impact"],
        verdict=verdict,
        rationale=meta["rationale"],
        status=str(meta.get("status") or "UNSPECIFIED"),
        details=details,
    )


def score_all(
    targets: List[SelectionSample],
    hard_negatives: List[SelectionSample],
) -> List[CandidateScore]:
    return [score_candidate(cid, targets, hard_negatives) for cid in CANDIDATES]

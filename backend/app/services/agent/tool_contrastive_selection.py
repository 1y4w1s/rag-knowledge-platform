"""TOOL S3A: gated contrastive tool-description selection experiment.

Product form of frozen P5 candidate S3A (READY_FOR_PRODUCT_EXPERIMENT only).
Rewrites competing tool *descriptions* in the planner prompt when safe.

ADVISORY / model-decided -- never remaps AgentDecision, never forces a tool,
never mutates the exposed tool set, never bypasses ToolResolver / args validation.
Flag default OFF. Capability NOT_YET_REAL_VALIDATED. Runtime rollout NO.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Sequence

from app.services.agent.tool_resolver import ToolSpec

# Frozen P5 S3A_DESCRIPTIONS -- keep identical to eval.tool_selection_p5.candidates.
S3A_DESCRIPTIONS: dict[str, str] = {
    'semantic_search': "Retrieve Top-N passage/chunk hits by meaning to answer content questions. Do NOT use for listing documents, filename lookup, or 'how to search documents' catalog/capability questions.",
    'search_documents': "Find documents across knowledge bases by filename or content mode; returns document_id/filename metadata. Prefer this for document search / catalog / cross-KB document lookup questions (including 'how to search documents').",
    'list_knowledge_bases': 'List knowledge bases currently visible to the user.',
}

_COMPETING_PAIR = frozenset({"semantic_search", "search_documents"})

# Strong catalog cues only -- "across knowledge bases" alone is insufficient
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
_MULTI = (re.compile(r"\bthen\b", re.I), re.compile('然后'), re.compile('接着'))
_OOS = (re.compile(r"\bdelete\b", re.I), re.compile(r"\bpurge\b", re.I), re.compile('删除'))


def s3a_intent_class(query: str) -> str:
    """catalog_search | semantic_qa | ambiguous | multi_tool | oos -- fail-closed."""
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


def contrastive_selection_eligible(
    query: str,
    exposed_tools: frozenset[str] | set[str] | tuple[str, ...] | Sequence[str],
) -> bool:
    """True only when S3A may safely rewrite competing descriptions."""
    exposed = frozenset(exposed_tools)
    q = (query or "").strip()
    if not q:
        return False
    if not _COMPETING_PAIR.issubset(exposed):
        return False
    for key in _COMPETING_PAIR:
        if not (S3A_DESCRIPTIONS.get(key) or "").strip():
            return False
    intent = s3a_intent_class(q)
    return intent in ("catalog_search", "semantic_qa")


def apply_contrastive_tool_descriptions(
    tool_specs: list[ToolSpec],
    query: str,
    *,
    enabled: bool | None = None,
) -> list[ToolSpec]:
    """Rewrite tool descriptions for planner prompt when S3A flag ON and eligible.

    OFF / ineligible -> identity (same list object when unchanged).
    Never drops, adds, or reorders tools; parameters untouched.
    """
    if enabled is None:
        from app.core.config import settings

        enabled = bool(settings.agent_l4_tool_contrastive_selection_enabled)

    if not enabled:
        return tool_specs

    exposed = tuple(spec.name for spec in tool_specs)
    if not contrastive_selection_eligible(query, exposed):
        return tool_specs

    out: list[ToolSpec] = []
    changed = False
    for spec in tool_specs:
        new_desc = S3A_DESCRIPTIONS.get(spec.name)
        if new_desc is None or new_desc == spec.description:
            out.append(spec)
            continue
        out.append(replace(spec, description=new_desc))
        changed = True
    return out if changed else tool_specs

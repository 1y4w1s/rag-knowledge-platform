"""L4 EvidenceMatcher → L3 runtime tool observation 薄接线（默认关）。

``snippets_from_tool_data`` / ``maybe_apply_evidence_match_after_tool``；
算法与 flag 门控仍在 ``matcher.EvidenceMatcher``。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from app.services.agent.matcher import EvidenceMatcher, EvidenceSnippet
from app.services.agent.types import AgentState, StepExecution


def snippets_from_tool_data(data: Any) -> tuple[EvidenceSnippet, ...]:
    """从只读 tool 产出抽 EvidenceSnippet（duck-typed；无正文则空）。"""
    if data is None:
        return ()
    out: list[EvidenceSnippet] = []
    hits = getattr(data, "hits", None)
    if hits is not None:
        for i, hit in enumerate(hits):
            text = (getattr(hit, "excerpt", None) or "").strip()
            if not text:
                continue
            cid = getattr(hit, "chunk_id", None)
            page = getattr(hit, "page", None)
            out.append(
                EvidenceSnippet(
                    evidence_id=str(cid) if cid is not None else f"hit-{i}",
                    text=text,
                    chunk_id=cid if isinstance(cid, UUID) else None,
                    page=str(page) if page is not None else None,
                    provenance=str(getattr(hit, "doc_name", "") or ""),
                    confidence=float(getattr(hit, "score", 1.0) or 1.0),
                )
            )
        return tuple(out)

    items = getattr(data, "items", None)
    if items is not None:
        for i, item in enumerate(items):
            text = (getattr(item, "snippet", None) or "").strip()
            if not text:
                continue
            did = getattr(item, "document_id", None)
            out.append(
                EvidenceSnippet(
                    evidence_id=str(did) if did is not None else f"doc-{i}",
                    text=text,
                    document_id=did if isinstance(did, UUID) else None,
                    provenance=str(getattr(item, "filename", "") or ""),
                )
            )
        return tuple(out)

    excerpt = getattr(data, "excerpt", None)
    if isinstance(excerpt, str) and excerpt.strip():
        cid = getattr(data, "chunk_id", None)
        did = getattr(data, "document_id", None)
        page = getattr(data, "page", None)
        return (
            EvidenceSnippet(
                evidence_id=str(cid) if cid is not None else "excerpt",
                text=excerpt.strip(),
                chunk_id=cid if isinstance(cid, UUID) else None,
                document_id=did if isinstance(did, UUID) else None,
                page=str(page) if page is not None else None,
                provenance=str(getattr(data, "doc_name", "") or ""),
            ),
        )

    matches = getattr(data, "matches", None)
    if matches is not None:
        for i, m in enumerate(matches):
            text = (getattr(m, "content", None) or "").strip()
            if not text:
                continue
            cid = getattr(m, "chunk_id", None)
            page = getattr(m, "page_number", None)
            out.append(
                EvidenceSnippet(
                    evidence_id=str(cid) if cid is not None else f"grep-{i}",
                    text=text,
                    chunk_id=cid if isinstance(cid, UUID) else None,
                    page=str(page) if page is not None else None,
                    provenance=str(getattr(m, "doc_name", "") or ""),
                )
            )
        return tuple(out)

    chunks = getattr(data, "chunks", None)
    if chunks is not None:
        for i, ch in enumerate(chunks):
            text = (getattr(ch, "content", None) or "").strip()
            if not text:
                continue
            cid = getattr(ch, "chunk_id", None)
            did = getattr(ch, "document_id", None)
            page = getattr(ch, "page_number", None)
            out.append(
                EvidenceSnippet(
                    evidence_id=str(cid) if cid is not None else f"cmp-{i}",
                    text=text,
                    chunk_id=cid if isinstance(cid, UUID) else None,
                    document_id=did if isinstance(did, UUID) else None,
                    page=str(page) if page is not None else None,
                    provenance=str(getattr(ch, "doc_name", "") or ""),
                )
            )
        return tuple(out)
    return ()


def maybe_apply_evidence_match_after_tool(
    state: AgentState,
    execution: StepExecution,
) -> AgentState:
    """L3 loop 薄接线：成功 tool observation → Matcher 更新 ledger（默认关 = 原样）。

    空 FactGoal ledger / 失败 step / 无正文 snippet → 不改写。
    """
    if not execution.ok or execution.data is None:
        return state
    if not state.evidence.facts:
        return state
    snippets = snippets_from_tool_data(execution.data)
    if not snippets:
        return state
    updated, result = EvidenceMatcher().match_and_apply(state.evidence, snippets)
    if not result.ok:
        return state
    return replace(state, evidence=updated)

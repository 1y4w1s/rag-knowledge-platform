"""L4-W3 Evidence Matcher：FactGoal ↔ evidence coverage（默认关；fixture + lexical）。

纯函数不读 flag；``EvidenceMatcher`` 仅挂 ``agent_l4_evidence_matcher_enabled``。
Ledger reducer 更新 FactStatus / 方案 A；不接 runtime。
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from app.services.agent.fact_contracts import (
    fact_coverage_ratio,
    reduce_fact_observation,
    sync_evidence_fact_views,
)
from app.services.agent.types import (
    EvidenceItem,
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactObservation,
    FactStatus,
)

_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_NEG = re.compile(r"不(适用|存在|允许|包含)|禁止|无此|并非|相反|不适用")
_AFFIRM = re.compile(r"适用|存在|允许|确认|包含|标准|档位")
_REL_RANK = {
    EvidenceRelation.partial: 1,
    EvidenceRelation.supports: 2,
    EvidenceRelation.resolves: 3,
    EvidenceRelation.contradicts: 4,
}
_SUPPORT_OVERLAP = 0.45
_PARTIAL_OVERLAP = 0.22

@dataclass(frozen=True, slots=True)
class EvidenceSnippet:
    evidence_id: str
    text: str
    source_type: str = "text"
    chunk_id: UUID | None = None
    document_id: UUID | None = None
    page: str | None = None
    provenance: str = ""
    confidence: float = 1.0

@dataclass(frozen=True, slots=True)
class MatchResult:
    ok: bool
    items: tuple[EvidenceItem, ...] = ()
    observation: FactObservation = FactObservation()
    coverage_ratio: float = 0.0
    error: str | None = None
    source: str = ""  # fixture | deterministic | disabled

def evidence_items_to_observation(items: Sequence[EvidenceItem]) -> FactObservation:
    best: dict[str, EvidenceRelation] = {}
    for item in items:
        for fact_id, rel in _item_relations(item):
            prev = best.get(fact_id)
            if prev is None or _REL_RANK[rel] > _REL_RANK[prev]:
                best[fact_id] = rel
    return FactObservation(relations=tuple(sorted(best.items(), key=lambda kv: kv[0])))

def match_from_fixture(
    facts: Sequence[FactGoal],
    fixture: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> MatchResult:
    if not facts:
        return MatchResult(ok=False, error="empty_facts", source="fixture")
    rows = _coerce_fixture_rows(fixture)
    if not rows:
        return MatchResult(ok=False, error="empty_fixture", source="fixture")
    known = {g.id for g in facts}
    items: list[EvidenceItem] = []
    for row in rows:
        eid = str(row.get("evidence_id") or row.get("id") or "").strip()
        if not eid:
            return MatchResult(ok=False, error="missing_evidence_id", source="fixture")
        supports = _fact_ids(row.get("supports"), known)
        contradicts = _fact_ids(row.get("contradicts"), known)
        partials = _fact_ids(row.get("partials") or row.get("partial"), known)
        resolves = _fact_ids(row.get("resolves"), known)
        if not (supports or contradicts or partials or resolves):
            continue
        text = str(row.get("text") or "")
        items.append(
            EvidenceItem(
                evidence_id=eid,
                source_type=str(row.get("source_type") or "fixture"),
                excerpt_hash=_hash_excerpt(text) if text else "",
                supports=supports,
                contradicts=contradicts,
                partials=partials,
                resolves=resolves,
                confidence=float(row.get("confidence", 1.0)),
                provenance=str(row.get("provenance") or "fixture"),
            )
        )
    if not items:
        return MatchResult(ok=False, error="no_relations", source="fixture")
    return MatchResult(
        ok=True,
        items=tuple(items),
        observation=evidence_items_to_observation(items),
        source="fixture",
    )

def deterministic_match(
    facts: Sequence[FactGoal],
    snippets: Sequence[EvidenceSnippet],
    *,
    only_uncovered: bool = True,
) -> MatchResult:
    if not facts:
        return MatchResult(ok=False, error="empty_facts", source="deterministic")
    if not snippets:
        return MatchResult(ok=False, error="empty_evidence", source="deterministic")
    targets = [
        g
        for g in facts
        if not only_uncovered
        or g.status in (FactStatus.missing, FactStatus.partial, FactStatus.conflicted)
    ]
    if not targets:
        return MatchResult(ok=True, source="deterministic")

    items: list[EvidenceItem] = []
    for snip in snippets:
        text = (snip.text or "").strip()
        if not text:
            continue
        supports: list[str] = []
        partials: list[str] = []
        contradicts: list[str] = []
        for goal in targets:
            rel = _lexical_relation(goal.text, text)
            if rel == EvidenceRelation.contradicts:
                contradicts.append(goal.id)
            elif rel == EvidenceRelation.partial:
                partials.append(goal.id)
            elif rel == EvidenceRelation.supports:
                supports.append(goal.id)
        if not (supports or partials or contradicts):
            continue
        items.append(
            EvidenceItem(
                evidence_id=snip.evidence_id,
                source_type=snip.source_type,
                chunk_id=snip.chunk_id,
                document_id=snip.document_id,
                page=snip.page,
                excerpt_hash=_hash_excerpt(text),
                supports=tuple(supports),
                contradicts=tuple(contradicts),
                partials=tuple(partials),
                confidence=snip.confidence,
                provenance=snip.provenance or snip.evidence_id,
            )
        )
    if not items:
        return MatchResult(ok=False, error="no_match", source="deterministic")
    return MatchResult(
        ok=True,
        items=tuple(items),
        observation=evidence_items_to_observation(items),
        source="deterministic",
    )

def apply_evidence_match(evidence: EvidenceState, match: MatchResult) -> EvidenceState:
    """Ledger reducer：合并 evidence_items + 应用 observation → 方案 A。"""
    if not match.ok or (not match.observation.relations and not match.items):
        return evidence
    merged = _merge_items(evidence.evidence_items, match.items)
    updated = reduce_fact_observation(evidence, match.observation)
    updated = replace(updated, evidence_items=merged)
    updated = sync_evidence_fact_views(updated)
    conf = max((i.confidence for i in match.items), default=0.0)
    return replace(updated, confidence=max(updated.confidence, conf))

def apply_and_score(
    evidence: EvidenceState, match: MatchResult
) -> tuple[EvidenceState, MatchResult]:
    updated = apply_evidence_match(evidence, match)
    return updated, replace(match, coverage_ratio=fact_coverage_ratio(updated))

class EvidenceMatcher:
    """Flag 门控：关 → disabled；开 → fixture 或 deterministic。"""

    def match(
        self,
        facts: Sequence[FactGoal],
        snippets: Sequence[EvidenceSnippet] = (),
        *,
        fixture: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
        only_uncovered: bool = True,
    ) -> MatchResult:
        from app.core.config import settings

        if not settings.agent_l4_evidence_matcher_enabled:
            return MatchResult(ok=False, error="disabled", source="disabled")
        if fixture is not None:
            return match_from_fixture(facts, fixture)
        return deterministic_match(facts, snippets, only_uncovered=only_uncovered)

    def match_and_apply(
        self,
        evidence: EvidenceState,
        snippets: Sequence[EvidenceSnippet] = (),
        *,
        fixture: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
        only_uncovered: bool = True,
    ) -> tuple[EvidenceState, MatchResult]:
        result = self.match(
            evidence.facts, snippets, fixture=fixture, only_uncovered=only_uncovered
        )
        if not result.ok:
            return evidence, result
        return apply_and_score(evidence, result)

def _item_relations(item: EvidenceItem) -> list[tuple[str, EvidenceRelation]]:
    return (
        [(f, EvidenceRelation.contradicts) for f in item.contradicts]
        + [(f, EvidenceRelation.resolves) for f in item.resolves]
        + [(f, EvidenceRelation.supports) for f in item.supports]
        + [(f, EvidenceRelation.partial) for f in item.partials]
    )

def _lexical_relation(fact_text: str, evidence_text: str) -> EvidenceRelation | None:
    ft, et = _tokens(fact_text), _tokens(evidence_text)
    if not ft or not et:
        return None
    overlap = len(ft & et) / len(ft)
    if overlap < _PARTIAL_OVERLAP:
        return None
    if _NEG.search(evidence_text) and (
        _AFFIRM.search(fact_text) or overlap >= _SUPPORT_OVERLAP
    ):
        return EvidenceRelation.contradicts
    if overlap >= _SUPPORT_OVERLAP:
        return EvidenceRelation.supports
    return EvidenceRelation.partial

def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN.finditer(text) if m.group(0).strip()}

def _hash_excerpt(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def _fact_ids(raw: Any, known: set[str]) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return ()
    out: list[str] = []
    for item in raw:
        fid = str(item).strip()
        if fid and fid in known and fid not in out:
            out.append(fid)
    return tuple(out)

def _coerce_fixture_rows(
    fixture: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(fixture, Mapping):
        if "items" in fixture and isinstance(fixture["items"], list):
            return [dict(x) for x in fixture["items"] if isinstance(x, Mapping)]
        rows: list[dict[str, Any]] = []
        for key, val in fixture.items():
            if key == "items" or not isinstance(val, Mapping):
                continue
            row = dict(val)
            row.setdefault("evidence_id", key)
            rows.append(row)
        return rows
    return [dict(x) for x in fixture if isinstance(x, Mapping)]

def _merge_items(
    existing: tuple[EvidenceItem, ...], incoming: tuple[EvidenceItem, ...]
) -> tuple[EvidenceItem, ...]:
    by_id = {item.evidence_id: item for item in existing}
    for item in incoming:
        by_id[item.evidence_id] = item
    return tuple(by_id.values())

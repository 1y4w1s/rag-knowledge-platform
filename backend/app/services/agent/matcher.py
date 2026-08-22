"""L4-W3 Evidence Matcher：FactGoal ↔ evidence coverage（默认关；fixture + lexical）。

纯函数不读 flag；``EvidenceMatcher`` 仅挂 ``agent_l4_evidence_matcher_enabled``。
Ledger reducer 更新 FactStatus / 方案 A。
Runtime 薄接线见 ``matcher_runtime``。
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
_YEAR = re.compile(r"(?:19|20)\d{2}")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_CN_AMOUNT = re.compile(
    r"[零一二三四五六七八九十百千万两]+(?:元|块|钱|块钱)?|"
    r"[零一二三四五六七八九十百千万两]+"
)
_TOPIC_ONLY = re.compile(
    r"按照|有关|规定|执行|讨论|涉及|另行|管理|确认.*调整|"
    r"由.*制定|可纳入|流程"
)
_NEG_EXTENDED = re.compile(
    r"不(?:可以|得|能|适用|存在|允许|包含)|禁止|无此|并非|相反|不适用|无法"
)
_DEFINITIVE = re.compile(
    r"标准为|为每人|每人每天|上限|下限|不得|必须|可以报销|"
    r"允许|禁止|不适用|是\s*\d"
)
_ENTITY_GROUPS: tuple[tuple[str, ...], ...] = (
    ("北京", "上海", "广州", "深圳"),
    ("国内", "国际"),
    ("教授", "普通工作"),
    ("教授级", "普通工作"),
)
_DEPT = re.compile(r"[\u4e00-\u9fff]{2,10}部")
_CN_DIGIT = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
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
            rel = _hardened_relation(goal.text, text)
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
    """Legacy Gate C frozen baseline — do not change thresholds or semantics."""
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


def _extract_years(text: str) -> set[str]:
    return set(_YEAR.findall(text))


def _cn_simple_to_int(token: str) -> int | None:
    """Best-effort for paraphrase cases (e.g. 五百 -> 500); known I1 boundary."""
    token = token.strip().replace("块钱", "").replace("块", "").replace("钱", "").replace("元", "")
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if token.startswith("十") and len(token) == 2 and token[1] in _CN_DIGIT:
        return 10 + _CN_DIGIT[token[1]]
    if token.endswith("十") and len(token) == 2 and token[0] in _CN_DIGIT:
        return _CN_DIGIT[token[0]] * 10
    if "百" in token:
        parts = token.split("百", 1)
        head = parts[0]
        tail = parts[1] if len(parts) > 1 else ""
        base = _CN_DIGIT.get(head, 1 if head == "" else None)
        if base is None:
            return None
        value = base * 100
        if tail:
            if tail == "十":
                value += 10
            elif tail.startswith("十") and len(tail) == 2:
                value += 10 + _CN_DIGIT.get(tail[1], 0)
            elif tail in _CN_DIGIT:
                value += _CN_DIGIT[tail]
        return value
    if len(token) == 1 and token in _CN_DIGIT:
        return _CN_DIGIT[token]
    return None


def _extract_values(text: str) -> set[int]:
    values: set[int] = set()
    for m in _NUM.finditer(text):
        raw = m.group(0)
        if raw.isdigit() and len(raw) == 4 and raw.startswith(("19", "20")):
            continue
        try:
            values.add(int(float(raw)))
        except ValueError:
            continue
    for m in _CN_AMOUNT.finditer(text):
        parsed = _cn_simple_to_int(m.group(0))
        if parsed is not None and parsed < 1900:
            values.add(parsed)
    return values


def _asks_for_value(fact: str) -> bool:
    return bool(re.search(r"多少|几\b|是否", fact)) or fact.rstrip().endswith("?")


def _asks_for_lookup(fact: str) -> bool:
    return "找到" in fact


def _years_conflict(fact: str, evidence: str) -> bool:
    fact_years = _extract_years(fact)
    ev_years = _extract_years(evidence)
    if not fact_years or not ev_years:
        return False
    return fact_years.isdisjoint(ev_years)


def _values_conflict(fact: str, evidence: str) -> bool:
    fact_vals = _extract_values(fact)
    ev_vals = _extract_values(evidence)
    if not fact_vals or not ev_vals:
        return False
    ft, et = _tokens(fact), _tokens(evidence)
    overlap = len(ft & et) / len(ft) if ft else 0.0
    if overlap < _PARTIAL_OVERLAP:
        return False
    if fact_vals == ev_vals:
        return False
    return True


def _entity_scope_conflict(fact: str, evidence: str) -> bool:
    for group in _ENTITY_GROUPS:
        fact_hits = [item for item in group if item in fact]
        ev_hits = [item for item in group if item in evidence]
        if fact_hits and ev_hits and set(fact_hits) != set(ev_hits):
            return True
    fact_depts = set(_DEPT.findall(fact))
    ev_depts = set(_DEPT.findall(evidence))
    if fact_depts and ev_depts and fact_depts.isdisjoint(ev_depts):
        return True
    return False


def _has_negation_marker(text: str) -> bool:
    return bool(_NEG.search(text) or _NEG_EXTENDED.search(text))


def _explicit_polarity_conflict(fact: str, evidence: str) -> bool:
    ft, et = _tokens(fact), _tokens(evidence)
    if not ft or not et:
        return False
    overlap = len(ft & et) / len(ft)
    if overlap < _PARTIAL_OVERLAP:
        return False
    if "不可以" in evidence and "可以" in fact and "不可以" not in fact:
        return True
    if "禁止" in evidence and "允许" in fact:
        return True
    if "不得" in evidence and ("可以" in fact or "允许" in fact):
        return True
    return False


def _negation_conflict(fact: str, evidence: str) -> bool:
    if _explicit_polarity_conflict(fact, evidence):
        return True
    fact_neg = _has_negation_marker(fact)
    ev_neg = _has_negation_marker(evidence)
    if fact_neg == ev_neg:
        return False
    ft, et = _tokens(fact), _tokens(evidence)
    if not ft or not et:
        return False
    overlap = len(ft & et) / len(ft)
    return overlap >= _PARTIAL_OVERLAP


def _comparison_incomplete(fact: str, evidence: str) -> bool:
    fact_years = _extract_years(fact)
    ev_years = _extract_years(evidence)
    if len(fact_years) >= 2 and ev_years and len(ev_years) < len(fact_years):
        return True
    if "比较" in fact and ("A" in fact or "B" in fact):
        needed = {label for label in ("A", "B") if label in fact}
        if needed and not needed.issubset(set(evidence)):
            return True
    if "分别" in fact and len(fact_years) >= 2:
        if not ev_years or len(ev_years) < len(fact_years):
            return True
    return False


def _apply_structural_guards(
    fact: str, evidence: str, base: EvidenceRelation | None
) -> EvidenceRelation | None:
    """A — structural guards on legacy lexical baseline."""
    if base is None:
        return None
    if base == EvidenceRelation.contradicts:
        return base
    if _negation_conflict(fact, evidence) or _values_conflict(fact, evidence):
        return EvidenceRelation.contradicts
    if base == EvidenceRelation.supports and (
        _years_conflict(fact, evidence)
        or _entity_scope_conflict(fact, evidence)
        or _comparison_incomplete(fact, evidence)
    ):
        return EvidenceRelation.partial
    return base


def _has_answer_bearing_content(fact: str, evidence: str) -> bool:
    """B — claim-level answer-bearing validation."""
    ft, et = _tokens(fact), _tokens(evidence)
    if not ft or not et:
        return False
    overlap = len(ft & et) / len(ft)
    if overlap < _PARTIAL_OVERLAP:
        return False

    fact_years = _extract_years(fact)
    ev_years = _extract_years(evidence)
    ev_vals = _extract_values(evidence)
    has_definitive = bool(ev_vals) or bool(_DEFINITIVE.search(evidence))
    topic_only = bool(_TOPIC_ONLY.search(evidence)) and not has_definitive

    if _asks_for_value(fact) and not has_definitive:
        return False

    if fact_years:
        if fact_years.isdisjoint(ev_years):
            return False
        if (_asks_for_lookup(fact) or _asks_for_value(fact)) and not has_definitive:
            return False

    if _asks_for_lookup(fact):
        if topic_only or not has_definitive:
            return False

    if topic_only and (_asks_for_value(fact) or _asks_for_lookup(fact) or fact_years):
        return False

    if _comparison_incomplete(fact, evidence):
        return False

    return True


def _overlap_partial(fact: str, evidence: str) -> bool:
    ft, et = _tokens(fact), _tokens(evidence)
    if not ft or not et:
        return False
    return len(ft & et) / len(ft) >= _PARTIAL_OVERLAP


def _has_strong_support(fact: str, evidence: str) -> bool:
    base = _lexical_relation(fact, evidence)
    if base != EvidenceRelation.supports:
        return False
    guarded = _apply_structural_guards(fact, evidence, base)
    if guarded != EvidenceRelation.supports:
        return False
    return _has_answer_bearing_content(fact, evidence)


def _hardened_relation(fact_text: str, evidence_text: str) -> EvidenceRelation | None:
    """A+B+C product relation: guards + claim validation + conservative full-cover."""
    guarded = _apply_structural_guards(
        fact_text, evidence_text, _lexical_relation(fact_text, evidence_text)
    )
    if guarded is None or guarded == EvidenceRelation.contradicts:
        return guarded
    if guarded in (EvidenceRelation.supports, EvidenceRelation.partial):
        if not _has_answer_bearing_content(fact_text, evidence_text):
            if guarded == EvidenceRelation.supports:
                return EvidenceRelation.partial
            return EvidenceRelation.partial if _overlap_partial(fact_text, evidence_text) else None
    if guarded == EvidenceRelation.supports and not _has_strong_support(fact_text, evidence_text):
        return EvidenceRelation.partial
    return guarded


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

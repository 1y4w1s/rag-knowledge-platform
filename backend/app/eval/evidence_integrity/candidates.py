"""Gate C remediation — eval-only candidate matchers (do not wire to product).

All candidates call product ``deterministic_match`` / ``_lexical_relation`` as the
lexical baseline and apply offline guards or claim heuristics on top.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.services.agent.matcher import (
    EvidenceSnippet,
    MatchResult,
    _AFFIRM,
    _NEG,
    _PARTIAL_OVERLAP,
    _hash_excerpt,
    _lexical_relation,
    _tokens,
    deterministic_match,
    evidence_items_to_observation,
)
from app.services.agent.types import EvidenceRelation, FactGoal, FactStatus

RelationFn = Callable[[str, str], EvidenceRelation | None]

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


def _extract_years(text: str) -> set[str]:
    return set(_YEAR.findall(text))


def _cn_simple_to_int(token: str) -> int | None:
    """Best-effort for Gate C paraphrase cases (e.g. 五百 -> 500)."""
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


def _guard_downgrade(fact: str, evidence: str, base: EvidenceRelation | None) -> EvidenceRelation | None:
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


def _lexical_with_threshold(
    fact_text: str,
    evidence_text: str,
    *,
    support_threshold: float,
    partial_threshold: float = _PARTIAL_OVERLAP,
) -> EvidenceRelation | None:
    ft, et = _tokens(fact_text), _tokens(evidence_text)
    if not ft or not et:
        return None
    overlap = len(ft & et) / len(ft)
    if overlap < partial_threshold:
        return None
    if _NEG.search(evidence_text) and (
        _AFFIRM.search(fact_text) or overlap >= support_threshold
    ):
        return EvidenceRelation.contradicts
    if overlap >= support_threshold:
        return EvidenceRelation.supports
    return EvidenceRelation.partial


def candidate_a_relation(fact: str, evidence: str) -> EvidenceRelation | None:
    """Deterministic structural guards on lexical baseline."""
    return _guard_downgrade(fact, evidence, _lexical_relation(fact, evidence))


def candidate_b_relation(fact: str, evidence: str) -> EvidenceRelation | None:
    """Claim-level answer-bearing validation on guarded lexical baseline."""
    guarded = candidate_a_relation(fact, evidence)
    if guarded is None or guarded == EvidenceRelation.contradicts:
        return guarded
    if guarded in (EvidenceRelation.supports, EvidenceRelation.partial):
        if not _has_answer_bearing_content(fact, evidence):
            if guarded == EvidenceRelation.supports:
                return EvidenceRelation.partial
            return EvidenceRelation.partial if overlap_partial(fact, evidence) else None
    return guarded


def candidate_c_relation(fact: str, evidence: str) -> EvidenceRelation | None:
    """Conservative coverage: lexical support capped unless strong support passes."""
    base = _lexical_relation(fact, evidence)
    if base is None:
        return None
    if base == EvidenceRelation.contradicts:
        return base
    guarded = _guard_downgrade(fact, evidence, base)
    if guarded == EvidenceRelation.contradicts:
        return guarded
    if guarded == EvidenceRelation.supports:
        if _strong_support(fact, evidence):
            return EvidenceRelation.supports
        return EvidenceRelation.partial
    return guarded


def candidate_ab_relation(fact: str, evidence: str) -> EvidenceRelation | None:
    """Combined A guards + B claim validation."""
    return candidate_b_relation(fact, evidence)


def candidate_abc_relation(fact: str, evidence: str) -> EvidenceRelation | None:
    """A+B guards with conservative full-cover policy."""
    rel = candidate_b_relation(fact, evidence)
    if rel == EvidenceRelation.supports and not _strong_support(fact, evidence):
        return EvidenceRelation.partial
    return rel


def overlap_partial(fact: str, evidence: str) -> bool:
    ft, et = _tokens(fact), _tokens(evidence)
    if not ft or not et:
        return False
    return len(ft & et) / len(ft) >= _PARTIAL_OVERLAP


def _strong_support(fact: str, evidence: str) -> bool:
    base = _lexical_relation(fact, evidence)
    if base != EvidenceRelation.supports:
        return False
    guarded = _guard_downgrade(fact, evidence, base)
    if guarded != EvidenceRelation.supports:
        return False
    return _has_answer_bearing_content(fact, evidence)


def threshold_relation(support_threshold: float) -> RelationFn:
    def _fn(fact: str, evidence: str) -> EvidenceRelation | None:
        return _lexical_with_threshold(
            fact,
            evidence,
            support_threshold=support_threshold,
        )

    return _fn


def eval_match(
    facts: Sequence[FactGoal],
    snippets: Sequence[EvidenceSnippet],
    relation_fn: RelationFn,
    *,
    only_uncovered: bool = True,
    source: str = "eval_candidate",
) -> MatchResult:
    """Build MatchResult from a per-pair relation function (eval-only)."""
    if not facts:
        return MatchResult(ok=False, error="empty_facts", source=source)
    if not snippets:
        return MatchResult(ok=False, error="empty_evidence", source=source)

    targets = [
        g
        for g in facts
        if not only_uncovered
        or g.status in (FactStatus.missing, FactStatus.partial, FactStatus.conflicted)
    ]
    if not targets:
        return MatchResult(ok=True, source=source)

    items: list = []
    for snip in snippets:
        text = (snip.text or "").strip()
        if not text:
            continue
        supports: list[str] = []
        partials: list[str] = []
        contradicts: list[str] = []
        for goal in targets:
            rel = relation_fn(goal.text, text)
            if rel == EvidenceRelation.contradicts:
                contradicts.append(goal.id)
            elif rel == EvidenceRelation.partial:
                partials.append(goal.id)
            elif rel == EvidenceRelation.supports:
                supports.append(goal.id)
        if not (supports or partials or contradicts):
            continue
        from app.services.agent.types import EvidenceItem

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
        return MatchResult(ok=False, error="no_match", source=source)
    return MatchResult(
        ok=True,
        items=tuple(items),
        observation=evidence_items_to_observation(items),
        source=source,
    )


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    candidate_id: str
    description: str
    relation_fn: RelationFn | None = None
    use_product_deterministic: bool = False


def baseline_match(
    facts: Sequence[FactGoal],
    snippets: Sequence[EvidenceSnippet],
    *,
    only_uncovered: bool = True,
) -> MatchResult:
    return deterministic_match(facts, snippets, only_uncovered=only_uncovered)


CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        candidate_id="BASELINE",
        description="Product deterministic_match (Gate C frozen baseline)",
        use_product_deterministic=True,
    ),
    CandidateSpec(
        candidate_id="A",
        description="Lexical baseline + deterministic guards (value/year/entity/negation)",
        relation_fn=candidate_a_relation,
    ),
    CandidateSpec(
        candidate_id="B",
        description="A guards + claim-level answer-bearing validation",
        relation_fn=candidate_b_relation,
    ),
    CandidateSpec(
        candidate_id="C",
        description="Conservative coverage: lexical support capped unless strong support",
        relation_fn=candidate_c_relation,
    ),
    CandidateSpec(
        candidate_id="A+B",
        description="Combined deterministic guards and claim validation",
        relation_fn=candidate_ab_relation,
    ),
    CandidateSpec(
        candidate_id="A+B+C",
        description="A+B with conservative full-cover cap",
        relation_fn=candidate_abc_relation,
    ),
)

THRESHOLD_DIAGNOSTICS: tuple[tuple[str, float], ...] = (
    ("THRESHOLD_0.45", 0.45),
    ("THRESHOLD_0.55", 0.55),
    ("THRESHOLD_0.60", 0.60),
    ("THRESHOLD_0.70", 0.70),
)

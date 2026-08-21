"""L4 FactGoal contracts：派生视图 + deterministic observation reducer（纯函数）。"""

from __future__ import annotations

from dataclasses import replace

from app.services.agent.types import (
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactKind,
    FactObservation,
    FactStatus,
)

_MAX_FACT_CHARS = 80
_MAX_FACT_GOALS = 6


def derive_fact_views(
    facts: tuple[FactGoal, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """方案 A：FactGoal[] → required / covered / missing 字符串视图。"""
    required = tuple(g.text for g in facts if g.required)
    covered = tuple(
        g.text for g in facts if g.required and g.status == FactStatus.covered
    )
    missing = tuple(
        g.text
        for g in facts
        if g.required and g.status in (FactStatus.missing, FactStatus.partial)
    )
    return required, covered, missing


def sync_evidence_fact_views(evidence: EvidenceState) -> EvidenceState:
    """有 facts 时重算三元组；conflicted required → sufficient 强制 False。"""
    if not evidence.facts:
        return evidence
    required, covered, missing = derive_fact_views(evidence.facts)
    has_conflict = any(
        g.required and g.status == FactStatus.conflicted for g in evidence.facts
    )
    return replace(
        evidence,
        required_facts=required,
        covered_facts=covered,
        missing_facts=missing,
        sufficient=False if has_conflict else evidence.sufficient,
    )


def facts_ready_for_stop(evidence: EvidenceState) -> bool:
    """Stop 可消费信号：全部 required covered 且无 conflicted（见 stop_policy.evaluate_stop）。"""
    required = [g for g in evidence.facts if g.required]
    if not required:
        return False
    if any(g.status == FactStatus.conflicted for g in required):
        return False
    return all(g.status == FactStatus.covered for g in required)


def fact_coverage_ratio(evidence: EvidenceState) -> float:
    """required ∧ covered / required；无 required → 0.0。"""
    required = [g for g in evidence.facts if g.required]
    if not required:
        return 0.0
    covered = sum(1 for g in required if g.status == FactStatus.covered)
    return covered / len(required)


def _next_fact_status(current: FactStatus, relation: EvidenceRelation) -> FactStatus:
    if relation == EvidenceRelation.contradicts:
        return FactStatus.conflicted
    if relation == EvidenceRelation.resolves:
        return FactStatus.covered
    if relation == EvidenceRelation.partial:
        if current in (FactStatus.conflicted, FactStatus.covered):
            return current
        return FactStatus.partial
    if current == FactStatus.conflicted:
        return FactStatus.conflicted
    return FactStatus.covered


def reduce_fact_observation(
    evidence: EvidenceState,
    observation: FactObservation,
) -> EvidenceState:
    """Deterministic fixture matcher：按 fact_id 应用 supports/partial/contradicts/resolves。"""
    if not evidence.facts or not observation.relations:
        return evidence
    by_id = {fact_id: rel for fact_id, rel in observation.relations}
    updated = tuple(
        replace(goal, status=_next_fact_status(goal.status, by_id[goal.id]))
        if goal.id in by_id
        else goal
        for goal in evidence.facts
    )
    return sync_evidence_fact_views(replace(evidence, facts=updated))


def seed_fact_goals(
    *,
    fact_goals: tuple[FactGoal, ...] = (),
    required_facts: tuple[str, ...] = (),
) -> tuple[FactGoal, ...]:
    if fact_goals:
        return tuple(
            replace(g, text=_clip_fact(g.text))
            for g in fact_goals
            if g.text.strip()
        )[:_MAX_FACT_GOALS]
    texts = tuple(_clip_fact(f) for f in required_facts if f)[:_MAX_FACT_GOALS]
    return tuple(
        FactGoal(
            id=f"F{i + 1}",
            text=text,
            kind=FactKind.lookup,
            required=True,
            status=FactStatus.missing,
        )
        for i, text in enumerate(texts)
    )


def _clip_fact(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_FACT_CHARS:
        return text
    return text[: _MAX_FACT_CHARS - 1] + "…"

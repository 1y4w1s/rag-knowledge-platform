"""L4-W5：Planner 消费 missing / conflicted（prompt 摘要 · 默认关）。

纯函数不读 flag；``apply_observation_fact_hints`` 挂 ``agent_l4_stop_policy_enabled``。
不接 StopPolicy / runtime 主循环；不抬默认。
"""

from __future__ import annotations

from dataclasses import replace

from app.services.agent.types import (
    EvidenceState,
    FactGoal,
    FactStatus,
    ObservationSummary,
)

_MAX_FACT_HINTS = 16
_MAX_FACT_CHARS = 80


def conflicted_fact_texts(facts: tuple[FactGoal, ...]) -> tuple[str, ...]:
    """required ∧ conflicted → 文本视图（供 ObservationSummary）。"""
    return tuple(
        _clip(g.text)
        for g in facts
        if g.required and g.status == FactStatus.conflicted and g.text.strip()
    )[:_MAX_FACT_HINTS]


def missing_fact_texts(facts: tuple[FactGoal, ...]) -> tuple[str, ...]:
    """required ∧ (missing|partial) → 文本视图。"""
    return tuple(
        _clip(g.text)
        for g in facts
        if g.required
        and g.status in (FactStatus.missing, FactStatus.partial)
        and g.text.strip()
    )[:_MAX_FACT_HINTS]


def apply_observation_fact_hints(
    summary: ObservationSummary,
    evidence: EvidenceState,
    *,
    enabled: bool | None = None,
) -> ObservationSummary:
    """Flag 开且有 FactGoal → 注入 missing_facts / conflicted_facts；关 → 原样。"""
    if enabled is None:
        from app.core.config import settings

        enabled = settings.agent_l4_stop_policy_enabled
    if not enabled or not evidence.facts:
        return summary

    missing = missing_fact_texts(evidence.facts)
    conflicted = conflicted_fact_texts(evidence.facts)
    return replace(
        summary,
        missing_facts=missing if missing else summary.missing_facts,
        conflicted_facts=conflicted,
    )


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_FACT_CHARS:
        return text
    return text[: _MAX_FACT_CHARS - 1] + "…"

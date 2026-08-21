"""L4-W6 Reflection/Recovery：FactGoal 感知的恢复策略（默认关）。

纯函数不读 flag；``ReflectionRecovery`` 挂 ``agent_l4_reflection_recovery_enabled``。
矛盾支路另需 ``agent_l4_contradiction_enabled``。
W6b：``maybe_l3_recovery_decision`` 薄挂 L3 loop（仍默认关）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.services.agent.fact_contracts import fact_coverage_ratio
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    EvidenceState,
    FactStatus,
    ToolFailure,
)

if TYPE_CHECKING:
    from app.services.agent.types import AgentState

_MAX_QUERY_CHARS = 120
_DEFAULT_MAX_REFLECTIONS = 1
_DEFAULT_TOOL = "semantic_search"


class RecoveryKind(str, Enum):
    """恢复动作种类（非 AgentActionKind）。"""

    resolve_conflict = "resolve_conflict"
    fallback_tool = "fallback_tool"
    rewrite_retrieve = "rewrite_retrieve"
    fill_gap = "fill_gap"
    none = "none"


@dataclass(frozen=True, slots=True)
class RecoverySignal:
    """可测恢复信号。ok=False 表示 disabled / 无效输入。"""

    ok: bool
    kind: RecoveryKind | None = None
    reason_code: str = ""
    target_fact_ids: tuple[str, ...] = ()
    suggested_query: str = ""
    suggested_tool: str | None = None
    coverage_ratio: float = 0.0
    error: str | None = None
    source: str = ""  # deterministic | disabled


def evaluate_recovery(
    evidence: EvidenceState,
    *,
    reflection_signal: str | None = None,
    last_failure: ToolFailure | None = None,
    steps_used: int = 0,
    max_steps: int = 0,
    reflection_count: int = 0,
    max_reflections: int = _DEFAULT_MAX_REFLECTIONS,
    contradiction_enabled: bool = False,
) -> RecoverySignal:
    """Fact-aware Recovery：纯函数。

    优先级：预算尽 → 矛盾 resolve → 工具失败 fallback → low_recall rewrite → fill_gap。
    ``complex_query`` 不单独开支路（映射为忽略）。
    """
    coverage = fact_coverage_ratio(evidence)
    base = dict(coverage_ratio=coverage, source="deterministic")

    budget_exhausted = max_steps > 0 and steps_used >= max_steps
    reflection_exhausted = (
        max_reflections > 0 and reflection_count >= max_reflections
    )
    if budget_exhausted:
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.none,
            reason_code="budget_exhausted",
            **base,
        )
    if reflection_exhausted:
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.none,
            reason_code="reflection_budget_exhausted",
            **base,
        )

    conflicted = tuple(
        g for g in evidence.facts if g.required and g.status == FactStatus.conflicted
    )
    if conflicted and contradiction_enabled:
        goal = conflicted[0]
        query = _clip_query(f"核实冲突：{goal.text}")
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.resolve_conflict,
            reason_code="facts_conflicted_resolve",
            target_fact_ids=(goal.id,),
            suggested_query=query,
            suggested_tool=_DEFAULT_TOOL,
            **base,
        )

    missing = tuple(
        g
        for g in evidence.facts
        if g.required and g.status in (FactStatus.missing, FactStatus.partial)
    )

    if last_failure is not None:
        query, fact_ids = _query_from_missing(missing, evidence)
        if not query:
            return RecoverySignal(
                ok=True,
                kind=RecoveryKind.none,
                reason_code="empty_recovery_query",
                **base,
            )
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.fallback_tool,
            reason_code="tool_failure_fallback",
            target_fact_ids=fact_ids,
            suggested_query=query,
            suggested_tool=_DEFAULT_TOOL,
            **base,
        )

    signal = (reflection_signal or "").strip()
    if signal == "complex_query":
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.none,
            reason_code="no_recovery_needed",
            **base,
        )

    if signal == "low_recall" or missing:
        query, fact_ids = _query_from_missing(missing, evidence)
        if not query:
            return RecoverySignal(
                ok=True,
                kind=RecoveryKind.none,
                reason_code="empty_recovery_query",
                **base,
            )
        if signal == "low_recall":
            return RecoverySignal(
                ok=True,
                kind=RecoveryKind.rewrite_retrieve,
                reason_code="low_recall_rewrite",
                target_fact_ids=fact_ids,
                suggested_query=query,
                suggested_tool=_DEFAULT_TOOL,
                **base,
            )
        return RecoverySignal(
            ok=True,
            kind=RecoveryKind.fill_gap,
            reason_code="facts_fill_gap",
            target_fact_ids=fact_ids,
            suggested_query=query,
            suggested_tool=_DEFAULT_TOOL,
            **base,
        )

    return RecoverySignal(
        ok=True,
        kind=RecoveryKind.none,
        reason_code="no_recovery_needed",
        **base,
    )


def recovery_to_decision(signal: RecoverySignal) -> AgentDecision | None:
    """RecoverySignal → 可执行 AgentDecision；none / disabled / 无 query → None。"""
    if (
        not signal.ok
        or signal.kind is None
        or signal.kind == RecoveryKind.none
        or not signal.suggested_query.strip()
    ):
        return None
    tool = signal.suggested_tool or _DEFAULT_TOOL
    return AgentDecision(
        action=AgentActionKind.tool,
        tool_name=tool,
        args={"query": signal.suggested_query.strip()},
        reason_code=signal.reason_code,
    )


class ReflectionRecovery:
    """Flag 门控：关 → disabled；开 → ``evaluate_recovery``。"""

    def evaluate(
        self,
        evidence: EvidenceState,
        *,
        reflection_signal: str | None = None,
        last_failure: ToolFailure | None = None,
        steps_used: int = 0,
        max_steps: int = 0,
        reflection_count: int = 0,
        max_reflections: int = _DEFAULT_MAX_REFLECTIONS,
    ) -> RecoverySignal:
        from app.core.config import settings

        if not settings.agent_l4_reflection_recovery_enabled:
            return RecoverySignal(ok=False, error="disabled", source="disabled")
        return evaluate_recovery(
            evidence,
            reflection_signal=reflection_signal,
            last_failure=last_failure,
            steps_used=steps_used,
            max_steps=max_steps,
            reflection_count=reflection_count,
            max_reflections=max_reflections,
            contradiction_enabled=settings.agent_l4_contradiction_enabled,
        )


def derive_l3_reflection_signal(state: AgentState) -> str | None:
    """L3 薄派生：最近一步检索空命中 → low_recall；不派生 complex_query。"""
    if not state.steps:
        return None
    last = state.steps[-1]
    if last.tool_name not in ("semantic_search", "search_documents"):
        return None
    if not last.ok or last.data is None:
        return None
    data = last.data
    hits = getattr(data, "hits", None)
    if hits is not None:
        return "low_recall" if len(hits) == 0 else None
    items = getattr(data, "items", None)
    if items is not None:
        return "low_recall" if len(items) == 0 else None
    return None


def maybe_l3_recovery_decision(state: AgentState) -> AgentDecision | None:
    """L3 loop 钩子：flag 关 / 无恢复动作 → None；否则 → tool AgentDecision。"""
    from app.core.config import settings

    max_reflections = settings.agent_max_reflections
    if max_reflections <= 0:
        max_reflections = _DEFAULT_MAX_REFLECTIONS
    signal = ReflectionRecovery().evaluate(
        state.evidence,
        reflection_signal=derive_l3_reflection_signal(state),
        last_failure=state.last_failure,
        steps_used=state.steps_used,
        max_steps=state.max_steps,
        reflection_count=state.reflection_count,
        max_reflections=max_reflections,
    )
    return recovery_to_decision(signal)


def _query_from_missing(
    missing: tuple,
    evidence: EvidenceState,
) -> tuple[str, tuple[str, ...]]:
    if missing:
        goal = missing[0]
        return _clip_query(goal.text), (goal.id,)
    # 无 FactGoal 时兼容派生 missing 视图（纯 L3 字符串槽）
    if evidence.missing_facts:
        return _clip_query(evidence.missing_facts[0]), ()
    return "", ()


def _clip_query(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= _MAX_QUERY_CHARS:
        return text
    return text[: _MAX_QUERY_CHARS - 1] + "…"

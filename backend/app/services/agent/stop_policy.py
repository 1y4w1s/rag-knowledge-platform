"""L4-W4 Stop policy：fact coverage 驱动 finish / partial / refuse（默认关）。

纯函数不读 flag；``StopPolicy`` 挂 ``agent_l4_stop_policy_enabled``。
W5.5a：``apply_stop_policy_decision`` / ``maybe_stop_terminal`` 薄挂 L3 loop。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.services.agent.fact_contracts import fact_coverage_ratio, facts_ready_for_stop
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    EvidenceState,
    FactStatus,
)

if TYPE_CHECKING:
    from app.services.agent.types import AgentState


class StopKind(str, Enum):
    """终态 / 覆盖信号（非 AgentActionKind；partial 为 L4 专用）。"""

    finish = "finish"
    partial = "partial"
    refuse = "refuse"


@dataclass(frozen=True, slots=True)
class StopSignal:
    """可测停止信号。ok=False 表示 disabled / 无效输入。"""

    ok: bool
    kind: StopKind | None = None
    reason_code: str = ""
    coverage_ratio: float = 0.0
    ready: bool = False
    budget_exhausted: bool = False
    conflicted_ids: tuple[str, ...] = ()
    missing_ids: tuple[str, ...] = ()
    error: str | None = None
    source: str = ""  # deterministic | disabled


def evaluate_stop(
    evidence: EvidenceState,
    *,
    steps_used: int = 0,
    max_steps: int = 0,
) -> StopSignal:
    """Fact coverage Stop：纯函数。

    - required 全 covered 且无 conflicted → finish
    - conflicted → refuse
    - 缺证 + 预算尽 + 有部分覆盖 → partial
    - 缺证 + 预算尽 + 零覆盖 → refuse
    - 缺证 + 仍有预算 → partial（未就绪信号，不得 finish）
    """
    required = [g for g in evidence.facts if g.required]
    conflicted_ids = tuple(
        g.id for g in required if g.status == FactStatus.conflicted
    )
    missing_ids = tuple(
        g.id
        for g in required
        if g.status in (FactStatus.missing, FactStatus.partial)
    )
    coverage = fact_coverage_ratio(evidence)
    ready = facts_ready_for_stop(evidence)
    budget_exhausted = max_steps > 0 and steps_used >= max_steps

    base = dict(
        coverage_ratio=coverage,
        ready=ready,
        budget_exhausted=budget_exhausted,
        conflicted_ids=conflicted_ids,
        missing_ids=missing_ids,
        source="deterministic",
    )

    if ready:
        return StopSignal(
            ok=True,
            kind=StopKind.finish,
            reason_code="facts_covered",
            **base,
        )

    if conflicted_ids:
        return StopSignal(
            ok=True,
            kind=StopKind.refuse,
            reason_code=(
                "facts_conflicted_budget" if budget_exhausted else "facts_conflicted"
            ),
            **base,
        )

    if not required:
        return StopSignal(
            ok=True,
            kind=StopKind.refuse if budget_exhausted else StopKind.partial,
            reason_code=(
                "no_required_facts_budget" if budget_exhausted else "no_required_facts"
            ),
            **base,
        )

    if budget_exhausted:
        if coverage > 0.0:
            return StopSignal(
                ok=True,
                kind=StopKind.partial,
                reason_code="facts_partial_budget",
                **base,
            )
        return StopSignal(
            ok=True,
            kind=StopKind.refuse,
            reason_code="facts_missing_budget",
            **base,
        )

    return StopSignal(
        ok=True,
        kind=StopKind.partial,
        reason_code="facts_incomplete",
        **base,
    )


class StopPolicy:
    """Flag 门控：关 → disabled；开 → ``evaluate_stop``。"""

    def evaluate(
        self,
        evidence: EvidenceState,
        *,
        steps_used: int = 0,
        max_steps: int = 0,
    ) -> StopSignal:
        from app.core.config import settings

        if not settings.agent_l4_stop_policy_enabled:
            return StopSignal(ok=False, error="disabled", source="disabled")
        return evaluate_stop(
            evidence, steps_used=steps_used, max_steps=max_steps
        )


def _has_required_facts(evidence: EvidenceState) -> bool:
    return any(g.required for g in evidence.facts)


def _retrieve_for_incomplete(
    state: AgentState,
    *,
    reason_code: str,
) -> AgentDecision:
    query = (
        (state.active_query or state.original_query).strip() or state.original_query
    )
    return AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": query},
        reason_code=reason_code,
    )


def _decision_from_stop_signal(signal: StopSignal) -> AgentDecision:
    """StopSignal 终态 → AgentDecision（partial → finish + 非完整 reason）。"""
    if signal.kind == StopKind.finish:
        return AgentDecision(
            action=AgentActionKind.finish,
            reason_code=signal.reason_code or "facts_covered",
        )
    if signal.kind == StopKind.refuse:
        return AgentDecision(
            action=AgentActionKind.refuse,
            reason_code=signal.reason_code or "facts_missing_budget",
        )
    # partial：无 AgentActionKind.partial → finish + stop reason（非 evidence-complete）
    return AgentDecision(
        action=AgentActionKind.finish,
        reason_code=signal.reason_code or "facts_partial_budget",
    )


def apply_stop_policy_decision(
    state: AgentState,
    decision: AgentDecision,
) -> AgentDecision:
    """L3 loop 薄接线：StopPolicy 改写 decision（默认关 = 原样）。

    Runtime 边界：无 required FactGoal 时不改写（空 ledger 不误杀 L3 finish；
    Decomposer flag 关或分解失败时仍为空 ledger，evaluate_stop 不强制进 control flow）。
    """
    signal = StopPolicy().evaluate(
        state.evidence,
        steps_used=state.steps_used,
        max_steps=state.max_steps,
    )
    if not signal.ok or not _has_required_facts(state.evidence):
        return decision

    # 合法澄清放行（与 evidence_gate 一致）
    if decision.action == AgentActionKind.clarify:
        return decision

    if signal.kind == StopKind.finish:
        # 已覆盖：允许 / 强制 finish，避免无意义 tool
        if decision.action == AgentActionKind.finish:
            return AgentDecision(
                action=AgentActionKind.finish,
                reason_code=decision.reason_code or signal.reason_code,
            )
        return _decision_from_stop_signal(signal)

    if signal.kind == StopKind.refuse:
        return _decision_from_stop_signal(signal)

    # partial
    if signal.budget_exhausted:
        return _decision_from_stop_signal(signal)

    # 有预算但未就绪：拦截过早 finish → 再检；tool / refuse 原样放行
    if decision.action == AgentActionKind.finish:
        return _retrieve_for_incomplete(
            state, reason_code="facts_incomplete_retrieve"
        )
    return decision


def maybe_stop_terminal(state: AgentState) -> AgentDecision | None:
    """预算耗尽且无 terminal 时，用 StopPolicy 收敛终态（默认关 → None）。"""
    signal = StopPolicy().evaluate(
        state.evidence,
        steps_used=state.steps_used,
        max_steps=state.max_steps,
    )
    if not signal.ok or not _has_required_facts(state.evidence):
        return None
    if not signal.budget_exhausted and signal.kind != StopKind.finish:
        return None
    if signal.kind is None:
        return None
    return _decision_from_stop_signal(signal)

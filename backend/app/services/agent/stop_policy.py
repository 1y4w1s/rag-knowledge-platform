"""L4-W4 Stop policy：fact coverage 驱动 finish / partial / refuse（默认关）。

纯函数不读 flag；``StopPolicy`` 仅挂 ``agent_l4_stop_policy_enabled``。
不接 runtime / Planner。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.agent.fact_contracts import fact_coverage_ratio, facts_ready_for_stop
from app.services.agent.types import EvidenceState, FactStatus


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

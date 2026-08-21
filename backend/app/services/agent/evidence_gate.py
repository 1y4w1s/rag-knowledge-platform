"""L3-W5 · EvidenceState → finish/retrieve 决策映射（不重造 sufficiency 算法）。

sufficient 由 `state.update_evidence_state` → `check_evidence_sufficiency` 写入；
本模块只消费布尔结果做 stop/retrieve 门控。`agent_l3_evidence_state_enabled` 默认 False。
"""

from __future__ import annotations

from app.services.agent.types import AgentActionKind, AgentDecision, AgentState


def maybe_finish_from_evidence(
    state: AgentState,
    *,
    enabled: bool | None = None,
) -> AgentDecision | None:
    """flag 开且 EvidenceState.sufficient → 短路 finish（省 LLM）。"""
    if enabled is None:
        from app.core.config import settings

        enabled = settings.agent_l3_evidence_state_enabled
    if not enabled or not state.evidence.sufficient:
        return None
    return AgentDecision(
        action=AgentActionKind.finish,
        reason_code="evidence_sufficient",
    )


def apply_evidence_stop_retrieve(
    state: AgentState,
    decision: AgentDecision,
    *,
    enabled: bool | None = None,
) -> AgentDecision:
    """把 EvidenceState.sufficient 映射进 stop/retrieve。

    - sufficient → finish（覆盖 LLM 继续 tool，对应 stop-now）
    - insufficient + finish → semantic_search 再检（有预算）或 refuse（无预算）
    - clarify / refuse / tool：原样放行（不杀死合法澄清/拒答）
    """
    if enabled is None:
        from app.core.config import settings

        enabled = settings.agent_l3_evidence_state_enabled
    if not enabled:
        return decision

    if state.evidence.sufficient:
        return AgentDecision(
            action=AgentActionKind.finish,
            reason_code="evidence_sufficient",
        )

    if decision.action != AgentActionKind.finish:
        return decision

    if state.steps_used < state.max_steps:
        query = (
            (state.active_query or state.original_query).strip()
            or state.original_query
        )
        return AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": query},
            reason_code="evidence_insufficient_retrieve",
        )
    return AgentDecision(
        action=AgentActionKind.refuse,
        reason_code="evidence_insufficient_budget",
    )

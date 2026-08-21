"""Gate A · L4 P0 fact-evidence closed loop (W1～W5 · measure only · no Stop→runtime).

验收映射（master@4013da6）：
1. missing required → 不得 premature finish（prefer fill-gap）
2. conflicted → 显式 conflict（refuse / sufficient=False；hints 注入后不得 finish）
3. all required covered → 可 finish
4. budget exhausted + incomplete → partial / refuse
5. flags 全关 → 与 L3 baseline 一致（Stop/Matcher/hints disabled；无 conflicted 注入）

StopPolicy **未**写入 runtime.py；本文件测 evaluate_stop + Matcher + hints→decide_next。
不做 W6。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import settings
from app.services.agent.fact_contracts import (
    fact_coverage_ratio,
    facts_ready_for_stop,
    sync_evidence_fact_views,
)
from app.services.agent.matcher import (
    EvidenceMatcher,
    apply_and_score,
    match_from_fixture,
)
from app.services.agent.planner_fact_hints import apply_observation_fact_hints
from app.services.agent.planners import LLMPlannerFactory, NextActionPlanner
from app.services.agent.state import init_agent_state
from app.services.agent.stop_policy import StopKind, StopPolicy, evaluate_stop
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
    ObservationSummary,
)
from tests.agent_trajectory.helpers import mock_parse


def test_gate_a_defaults_remain_false() -> None:
    """A8 companion: no L3/L4/critic defaults raised on this branch."""
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False


def _goals(*statuses: FactStatus) -> tuple[FactGoal, ...]:
    texts = ("找到 2025 住宿标准", "找到 2026 住宿标准", "确认适用规则")
    return tuple(
        FactGoal(
            id=f"F{i + 1}",
            text=texts[i],
            kind=FactKind.compare if i < 2 else FactKind.condition,
            status=statuses[i],
        )
        for i in range(len(statuses))
    )


def _status_map(evidence: EvidenceState) -> dict[str, FactStatus]:
    return {g.id: g.status for g in evidence.facts}


# ── A1: missing → must not finish; prefer fill-gap ─────────────────────


def test_a1_missing_fact_stop_not_finish_prefer_fill_gap() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.missing, FactStatus.partial)
        )
    )
    signal = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert signal.kind == StopKind.partial
    assert signal.kind != StopKind.finish
    assert signal.ready is False
    assert set(signal.missing_ids) == {"F2", "F3"}

    # Planner path (flag on for measurement only): missing → retrieve / fill-gap
    summary = apply_observation_fact_hints(
        ObservationSummary(original_query="差旅住宿变化？"),
        evidence,
        enabled=True,
    )
    assert summary.missing_facts
    assert "找到 2026 住宿标准" in summary.missing_facts
    # Soft contract from prompt: missing ⇒ 不得 finish；优先补缺 = tool retrieve
    fill_gap = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": summary.missing_facts[0]},
        reason_code="fill_gap_missing_fact",
    )
    assert fill_gap.action != AgentActionKind.finish
    assert fill_gap.tool_name == "semantic_search"


# ── A3: conflict → sufficient=false ────────────────────────────────────


def test_a3_conflict_forces_sufficient_false() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.covered, FactStatus.covered)
        )
    )
    assert facts_ready_for_stop(evidence) is True
    # Force sufficient True before conflict (matcher path would leave it untouched)
    evidence = replace(evidence, sufficient=True)
    assert evidence.sufficient is True

    evidence, _ = apply_and_score(
        evidence,
        match_from_fixture(
            evidence.facts,
            {"E2": {"contradicts": ["F3"], "text": "适用规则矛盾"}},
        ),
    )
    assert _status_map(evidence)["F3"] == FactStatus.conflicted
    assert evidence.sufficient is False
    signal = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert signal.kind == StopKind.refuse
    assert signal.reason_code == "facts_conflicted"


# ── A5: complete → allow finish ────────────────────────────────────────


def test_a5_complete_allows_finish() -> None:
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.covered, FactStatus.covered)
        )
    )
    assert facts_ready_for_stop(evidence) is True
    signal = evaluate_stop(evidence, steps_used=2, max_steps=5)
    assert signal.kind == StopKind.finish
    assert signal.reason_code == "facts_covered"
    assert signal.coverage_ratio == 1.0


# ── A6: budget exhausted → partial/refuse; no fake completeness ────────


def test_a6_budget_exhausted_partial_or_refuse_no_fake_complete() -> None:
    partial_ev = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.missing, FactStatus.missing)
        )
    )
    partial_sig = evaluate_stop(partial_ev, steps_used=5, max_steps=5)
    assert partial_sig.budget_exhausted is True
    assert partial_sig.kind == StopKind.partial
    assert partial_sig.kind != StopKind.finish
    assert partial_sig.coverage_ratio == pytest.approx(1 / 3)
    assert facts_ready_for_stop(partial_ev) is False

    zero_ev = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.missing, FactStatus.missing))
    )
    refuse_sig = evaluate_stop(zero_ev, steps_used=4, max_steps=4)
    assert refuse_sig.kind == StopKind.refuse
    assert refuse_sig.reason_code == "facts_missing_budget"
    assert refuse_sig.kind != StopKind.finish


# ── A8: all L4 flags false → stable / disabled behavior ────────────────


def test_a8_all_l4_flags_false_stable_disabled() -> None:
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False

    evidence = sync_evidence_fact_views(
        EvidenceState(facts=_goals(FactStatus.conflicted, FactStatus.missing))
    )
    matcher = EvidenceMatcher().match(
        evidence.facts,
        fixture={"E1": {"supports": ["F1"]}},
    )
    assert matcher.ok is False
    assert matcher.source == "disabled"

    stop = StopPolicy().evaluate(evidence, steps_used=1, max_steps=3)
    assert stop.ok is False
    assert stop.source == "disabled"
    assert stop.kind is None

    base = ObservationSummary(
        original_query="q",
        missing_facts=("legacy",),
        conflicted_facts=(),
    )
    hinted = apply_observation_fact_hints(base, evidence)
    assert hinted is base
    assert hinted.conflicted_facts == ()
    assert hinted.missing_facts == ("legacy",)


# ── Real runtime trajectory: partial → next action changes on missing ──


class _MissingAwareMockPlanner(NextActionPlanner):
    """Inspect ObservationSummary (post L4 hints) to choose fill-gap vs finish."""

    def __init__(self, query: str) -> None:
        from app.services.agent.planners import SafetyFrame

        safety = SafetyFrame(query)
        super().__init__(
            query, safety_frame=safety, tool_specs=safety.all_tool_specs()
        )
        self.summaries_seen: list[ObservationSummary] = []
        self.decisions_seen: list[AgentDecision] = []

    async def _call_llm(self, summary, tool_specs):  # noqa: ANN001
        del tool_specs
        self.summaries_seen.append(summary)
        if summary.conflicted_facts:
            return mock_parse(
                AgentDecision(
                    action=AgentActionKind.refuse,
                    reason_code="facts_conflicted",
                )
            )
        if summary.missing_facts:
            return mock_parse(
                AgentDecision(
                    action=AgentActionKind.tool,
                    tool_name="semantic_search",
                    args={"query": summary.missing_facts[0]},
                    reason_code="fill_gap_missing_fact",
                )
            )
        return mock_parse(
            AgentDecision(action=AgentActionKind.finish, reason_code="facts_covered")
        )

    async def decide_next(self, state):  # noqa: ANN001
        decision = await super().decide_next(state)
        self.decisions_seen.append(decision)
        return decision


@pytest.mark.asyncio
async def test_gate_a_runtime_trajectory_partial_then_fill_gap_then_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed loop (no Stop wired into runtime.py): Matcher → hints → decide_next.

    Step1 partial coverage → missing injected → next action = semantic_search.
    Step2 all covered → next action = finish. evaluate_stop agrees.
    """
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)

    # Non-simple query so LLMPlannerFactory → NextActionPlanner when L3 on
    query = "对比 2025 与 2026 住宿标准分别是多少？适用规则有何不同？"
    goals = _goals(FactStatus.missing, FactStatus.missing, FactStatus.missing)
    state = init_agent_state(original_query=query, max_steps=5, fact_goals=goals)

    # Step 1: only F1 covered → partial
    evidence, scored = apply_and_score(
        state.evidence,
        match_from_fixture(
            state.evidence.facts,
            {
                "E1": {
                    "supports": ["F1"],
                    "text": "2025 年住宿标准为 500 元",
                }
            },
        ),
    )
    assert scored.coverage_ratio == fact_coverage_ratio(evidence) == pytest.approx(1 / 3)
    assert facts_ready_for_stop(evidence) is False
    stop1 = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert stop1.kind == StopKind.partial
    assert stop1.kind != StopKind.finish

    state = replace(state, evidence=evidence, steps_used=1)
    planner = _MissingAwareMockPlanner(query)

    assert isinstance(LLMPlannerFactory.create(query), NextActionPlanner)
    d1 = await planner.decide_next(state)

    assert d1.action == AgentActionKind.tool
    assert d1.tool_name == "semantic_search"
    assert d1.reason_code == "fill_gap_missing_fact"
    assert planner.summaries_seen[0].missing_facts
    assert "找到 2026 住宿标准" in planner.summaries_seen[0].missing_facts

    # Step 2: cover remaining → finish allowed
    evidence2, scored2 = apply_and_score(
        evidence,
        match_from_fixture(
            evidence.facts,
            {
                "E2": {
                    "supports": ["F2", "F3"],
                    "text": "2026 住宿标准与适用规则",
                }
            },
        ),
    )
    assert scored2.coverage_ratio == 1.0
    assert facts_ready_for_stop(evidence2) is True
    stop2 = evaluate_stop(evidence2, steps_used=2, max_steps=5)
    assert stop2.kind == StopKind.finish

    state2 = replace(state, evidence=evidence2, steps_used=2)
    d2 = await planner.decide_next(state2)
    assert d2.action == AgentActionKind.finish
    assert d2.reason_code == "facts_covered"
    assert not planner.summaries_seen[1].missing_facts

    # Restore defaults (A8 invariant)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l3_next_action_enabled is False


@pytest.mark.asyncio
async def test_gate_a_runtime_trajectory_conflicted_explicit_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验收②：conflicted → hints 注入 → decide_next 显式 refuse（不得 finish）。"""
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)

    query = "对比 2025 与 2026 住宿标准分别是多少？适用规则有何不同？"
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.covered, FactStatus.covered, FactStatus.conflicted)
        )
    )
    stop = evaluate_stop(evidence, steps_used=1, max_steps=5)
    assert stop.kind == StopKind.refuse
    assert stop.reason_code == "facts_conflicted"

    state = replace(
        init_agent_state(original_query=query, max_steps=5, fact_goals=evidence.facts),
        evidence=evidence,
        steps_used=1,
    )
    planner = _MissingAwareMockPlanner(query)
    decision = await planner.decide_next(state)
    assert planner.summaries_seen[0].conflicted_facts
    assert "确认适用规则" in planner.summaries_seen[0].conflicted_facts
    assert decision.action == AgentActionKind.refuse
    assert decision.reason_code == "facts_conflicted"
    assert decision.action != AgentActionKind.finish

    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)


@pytest.mark.asyncio
async def test_gate_a_trajectory_flags_off_conflicted_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验收⑤：L4 stop flag 关 → conflicted_facts 不注入（L3 baseline 稳定）。

    Scheme-A missing_facts 仍可能经 EvidenceState 视图出现；那是 pre-W5 行为，
    不由 agent_l4_stop_policy_enabled 门控。
    """
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    assert settings.agent_l4_stop_policy_enabled is False

    query = "对比 A 与 B 分别是多少？"
    evidence = sync_evidence_fact_views(
        EvidenceState(
            facts=_goals(FactStatus.conflicted, FactStatus.missing, FactStatus.covered)
        )
    )
    # Pretend sufficient was somehow True — sync must keep False under conflict
    evidence = sync_evidence_fact_views(replace(evidence, sufficient=True))
    assert evidence.sufficient is False

    state = replace(
        init_agent_state(original_query=query, max_steps=3),
        evidence=evidence,
        steps_used=1,
    )
    planner = _MissingAwareMockPlanner(query)
    decision = await planner.decide_next(state)
    summary = planner.summaries_seen[0]
    assert summary.conflicted_facts == ()
    # Without L4 conflicted injection, mock does not refuse-for-conflict
    assert decision.reason_code != "facts_conflicted"

    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)

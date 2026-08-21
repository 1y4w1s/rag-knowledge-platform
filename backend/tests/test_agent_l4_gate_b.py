"""Gate B · L4 P0 Product Closure E2E（真实 run_react_loop · 默认关）。

证明 Decomposer → Matcher → StopPolicy 三件套联合闭环。
禁止手工 match(...)/改 FactStatus 冒充轨迹；允许 scripted planner 与 tool mock。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentState,
    FactStatus,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.test_agent_l3_runtime import ScriptedNextActionPlanner

_COMPARE_QUERY = "根据 2025 与 2026 差旅制度，住宿标准发生了什么变化？"
_CONFLICT_QUERY = "确认台湾办公室员工的适用规则？"


class _GateBRecordingPlanner(ScriptedNextActionPlanner):
    """记录每次 decide_next 所见的 FactStatus（证明 Planner 消费 Matcher 后 state）。"""

    def __init__(self, script: list[AgentDecision], *, query: str) -> None:
        super().__init__(script, query=query)
        self.seen_fact_status: list[dict[str, FactStatus]] = []
        self.seen_sufficient: list[bool] = []

    async def decide_next(self, state: AgentState) -> AgentDecision:
        self.seen_fact_status.append(
            {g.id: g.status for g in state.evidence.facts}
        )
        self.seen_sufficient.append(state.evidence.sufficient)
        return await super().decide_next(state)


def _personal_workspace(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def _create_personal_thread(user_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


def _hit(*, excerpt: str, doc_name: str = "差旅.md") -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name=doc_name,
        page=1,
        section_title="住宿",
        excerpt=excerpt,
        score=0.91,
    )


def _search_ok(*, excerpt: str) -> SemanticSearchToolResult:
    return SemanticSearchToolResult(
        ok=True,
        summary="命中 1",
        data=SemanticSearchOutput(hits=(_hit(excerpt=excerpt),), retrieval_ms=12),
    )


def _search_fail_with_covering_payload() -> SemanticSearchToolResult:
    """失败 step 仍带可覆盖正文：Matcher 不得因 data 误标 covered。"""
    return SemanticSearchToolResult(
        ok=False,
        summary="检索失败",
        data=SemanticSearchOutput(
            hits=(
                _hit(
                    excerpt=(
                        "根据制度，2025 住宿标准为每人每晚 500 元；"
                        "2026 住宿标准为每人每晚 600 元。"
                    )
                ),
            ),
            retrieval_ms=12,
        ),
    )


def _dual_year_cover_excerpt() -> str:
    return (
        "根据制度，2025 住宿标准为每人每晚 500 元；"
        "2026 住宿标准为每人每晚 600 元。"
    )


def _conflict_excerpt() -> str:
    return "台湾办公室员工不适用境内差旅档位适用规则。"


def _restore_l4_flags() -> None:
    settings.agent_l4_fact_decomposition_enabled = False
    settings.agent_l4_evidence_matcher_enabled = False
    settings.agent_l4_stop_policy_enabled = False
    settings.agent_l4_contradiction_enabled = False
    settings.agent_l4_reflection_recovery_enabled = False


def test_gate_b_defaults_remain_false() -> None:
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.rag_critic_enabled is False


@pytest.mark.asyncio
async def test_gate_b_d_second_planner_sees_matcher_state(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D：Matcher 更新后的 state 被第二轮 Planner 实际消费。"""
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)

    _, user = await register_and_login(prefix="l4gateb-d")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = _GateBRecordingPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "住宿标准"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=_COMPARE_QUERY,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok(excerpt=_dual_year_cover_excerpt())),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_COMPARE_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 2
    assert len(planner.seen_fact_status) == 2
    first, second = planner.seen_fact_status
    assert first, "Decomposer must seed FactGoals before first decide"
    assert all(s == FactStatus.missing for s in first.values())
    assert second.get("F1") == FactStatus.covered
    assert second.get("F2") == FactStatus.covered
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    _restore_l4_flags()


@pytest.mark.asyncio
async def test_gate_b_e_matcher_then_stop_allows_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E：missing → Stop 拦 finish → tool → Matcher covered → Stop 允许 finish。"""
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)

    _, user = await register_and_login(prefix="l4gateb-e")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = _GateBRecordingPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=_COMPARE_QUERY,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok(excerpt=_dual_year_cover_excerpt())),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_COMPARE_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 2
    assert all(
        s == FactStatus.missing for s in planner.seen_fact_status[0].values()
    )
    assert planner.seen_fact_status[1].get("F1") == FactStatus.covered
    assert planner.seen_fact_status[1].get("F2") == FactStatus.covered
    assert len(outcome.steps) == 1
    assert outcome.steps[0].tool_name == "semantic_search"
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    # Stop 在 signal.finish 时保留 planner reason（或补 facts_covered）——关键是允许 finish、未再拦截
    assert outcome.terminal_decision.reason_code in (
        "facts_covered",
        "evidence_sufficient",
    )
    assert outcome.terminal_decision.reason_code not in (
        "facts_incomplete_retrieve",
        "facts_conflicted",
        "facts_missing_budget",
        "facts_partial_budget",
    )
    _restore_l4_flags()


@pytest.mark.asyncio
async def test_gate_b_f_matcher_conflict_blocks_facts_covered_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F：Observation → Matcher conflicted → Stop 禁止 facts_covered finish。"""
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    # resolution 仍 out of scope：不抬 contradiction
    assert settings.agent_l4_contradiction_enabled is False

    _, user = await register_and_login(prefix="l4gateb-f")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = _GateBRecordingPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "适用规则"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=_CONFLICT_QUERY,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok(excerpt=_conflict_excerpt())),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_CONFLICT_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 2
    assert planner.seen_fact_status[0]
    assert all(s == FactStatus.missing for s in planner.seen_fact_status[0].values())
    assert any(
        s == FactStatus.conflicted for s in planner.seen_fact_status[1].values()
    )
    # conflicted required → contracts 强制 sufficient=False（resolution 仍 OOS）
    assert planner.seen_sufficient[1] is False
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.refuse
    assert "conflict" in (outcome.terminal_decision.reason_code or "")
    assert outcome.terminal_decision.reason_code != "facts_covered"
    _restore_l4_flags()


@pytest.mark.asyncio
async def test_gate_b_g_tool_failure_does_not_cover(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G：tool failure → Matcher 不污染 fact coverage。"""
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_evidence_matcher_enabled", True)
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)

    _, user = await register_and_login(prefix="l4gateb-g")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = _GateBRecordingPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "住宿标准"},
                reason_code="initial_retrieval",
            ),
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=_COMPARE_QUERY,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_fail_with_covering_payload()),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_COMPARE_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 2
    assert len(outcome.steps) == 1
    assert outcome.steps[0].ok is False
    assert planner.seen_fact_status[0]
    assert all(s == FactStatus.missing for s in planner.seen_fact_status[0].values())
    assert all(s == FactStatus.missing for s in planner.seen_fact_status[1].values())
    assert not any(
        s == FactStatus.covered for s in planner.seen_fact_status[1].values()
    )
    _restore_l4_flags()


@pytest.mark.asyncio
async def test_gate_b_h_all_flags_off_l3_baseline(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H：全相关 flags OFF → L3 baseline 非回归（过早 finish 仍放行）。"""
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False

    _, user = await register_and_login(prefix="l4gateb-h")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = _GateBRecordingPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query=_COMPARE_QUERY,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_COMPARE_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert planner.decide_calls == 1
    assert planner.seen_fact_status == [{}]  # 空 ledger
    assert outcome.steps == ()
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    assert outcome.terminal_decision.reason_code == "evidence_sufficient"

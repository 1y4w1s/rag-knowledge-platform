"""L4-W5.5a：StopPolicy → L3 runtime 薄接线（默认关）。

从真实 ``run_react_loop`` / ``_run_l3_next_action_loop`` 入口验收；
不测手工 apply_and_score→evaluate_stop 拼装路径（见 Gate A）。
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.agent.fact_contracts import sync_evidence_fact_views
from app.services.agent.runtime import run_react_loop
from app.services.agent.state import init_agent_state
from app.services.agent.stop_policy import (
    StopKind,
    StopPolicy,
    apply_stop_policy_decision,
    evaluate_stop,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    FactGoal,
    FactKind,
    FactStatus,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.test_agent_l3_runtime import ScriptedNextActionPlanner


def test_l4_stop_and_l3_flags_default_false() -> None:
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.rag_critic_enabled is False


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


def _search_ok(query: str = "q") -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="手册.md",
        page=1,
        section_title="住宿",
        excerpt="2025 住宿标准 500 元",
        score=0.91,
    )
    return SemanticSearchToolResult(
        ok=True,
        summary=f"命中 1 · {query[:40]}",
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=12),
    )


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


def _patch_init_with_goals(monkeypatch: pytest.MonkeyPatch, goals: tuple[FactGoal, ...]):
    real_init = init_agent_state

    def _init(**kwargs):
        # runtime 现始终传 fact_goals=（Decomposer 薄接线）；测试强制覆盖种子
        kwargs["fact_goals"] = goals
        return real_init(**kwargs)

    monkeypatch.setattr("app.services.agent.runtime.init_agent_state", _init)


def test_apply_stop_disabled_passthrough() -> None:
    assert settings.agent_l4_stop_policy_enabled is False
    state = init_agent_state(
        original_query="q",
        max_steps=3,
        fact_goals=_goals(FactStatus.missing),
    )
    finish = AgentDecision(action=AgentActionKind.finish, reason_code="llm_early")
    assert apply_stop_policy_decision(state, finish) is finish


def test_apply_stop_empty_ledger_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """无 required FactGoal：即使 flag 开也不改写（runtime 边界，非 evaluate_stop 改写）。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    state = init_agent_state(original_query="q", max_steps=3)
    finish = AgentDecision(action=AgentActionKind.finish, reason_code="ok")
    assert apply_stop_policy_decision(state, finish) is finish
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_a_premature_finish_blocked(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case A：missing required → planner finish 被 Stop 拦截 → 不得 evidence-complete finish。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    goals = _goals(FactStatus.covered, FactStatus.missing, FactStatus.partial)
    _patch_init_with_goals(monkeypatch, goals)

    evaluate_calls: list[tuple[int, int]] = []
    real_evaluate = StopPolicy.evaluate

    def _spy(self, evidence, *, steps_used=0, max_steps=0):  # noqa: ANN001
        evaluate_calls.append((steps_used, max_steps))
        return real_evaluate(
            self, evidence, steps_used=steps_used, max_steps=max_steps
        )

    monkeypatch.setattr(StopPolicy, "evaluate", _spy)

    _, user = await register_and_login(prefix="l4w55a-a")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
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
        query="对比 2025 与 2026 住宿标准？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("住宿")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert evaluate_calls, "StopPolicy.evaluate must be called"
    assert len(outcome.steps) >= 1
    assert outcome.steps[0].tool_name == "semantic_search"
    assert outcome.terminal_decision is not None
    # 不得伪装成 evidence-complete 正常完成
    if outcome.terminal_decision.action == AgentActionKind.finish:
        assert outcome.terminal_decision.reason_code != "evidence_sufficient"
        assert outcome.terminal_decision.reason_code != "facts_covered"
    stop_probe = evaluate_stop(
        sync_evidence_fact_views(
            init_agent_state(
                original_query="x", max_steps=5, fact_goals=goals
            ).evidence
        ),
        steps_used=1,
        max_steps=5,
    )
    assert stop_probe.kind != StopKind.finish
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_b_complete_allows_finish(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case B：all covered → PASS → 正常 finish；无无意义 tool。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    covered = tuple(
        replace(g, status=FactStatus.covered)
        for g in _goals(FactStatus.missing, FactStatus.missing, FactStatus.missing)
    )
    _patch_init_with_goals(monkeypatch, covered)

    _, user = await register_and_login(prefix="l4w55a-b")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    # Planner 先给 tool：Stop 应强制 finish，避免无意义调用
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.tool,
                tool_name="semantic_search",
                args={"query": "多余检索"},
                reason_code="redundant",
            ),
        ],
        query="对比 2025 与 2026 住宿标准？",
    )
    search_mock = AsyncMock(return_value=_search_ok())
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        search_mock,
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps == ()
    assert search_mock.await_count == 0
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    assert outcome.terminal_decision.reason_code == "facts_covered"
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_c_conflict_refuses_no_fake_complete(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case C：conflicted → refuse；sufficient 不得 true；不得伪装 complete finish。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    goals = _goals(FactStatus.covered, FactStatus.covered, FactStatus.conflicted)
    _patch_init_with_goals(monkeypatch, goals)

    _, user = await register_and_login(prefix="l4w55a-c")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比 2025 与 2026 住宿标准？",
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps == ()
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.refuse
    assert "conflict" in outcome.terminal_decision.reason_code
    # seed 后 sufficient 被 sync 强制 False
    seeded = init_agent_state(
        original_query="x", max_steps=5, fact_goals=goals
    )
    assert seeded.evidence.sufficient is False
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_d_budget_exhausted_partial_or_refuse(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case D：budget 尽 + incomplete → partial/refuse，不伪装完整答案。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    # 零覆盖 → facts_missing_budget → refuse
    goals = _goals(FactStatus.missing, FactStatus.missing)
    _patch_init_with_goals(monkeypatch, goals)

    _, user = await register_and_login(prefix="l4w55a-d")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比住宿标准？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("住宿")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=1,
        )
        await db.commit()

    assert len(outcome.steps) == 1  # premature finish → retrieve once
    assert outcome.capped is True
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.refuse
    assert outcome.terminal_decision.reason_code == "facts_missing_budget"
    assert outcome.terminal_decision.reason_code != "evidence_sufficient"
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_d_budget_partial_coverage_finishes_partial(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case D′：部分覆盖 + 预算尽 → finish + facts_partial_budget（非完整）。"""
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", True)
    goals = _goals(FactStatus.covered, FactStatus.missing, FactStatus.partial)
    _patch_init_with_goals(monkeypatch, goals)

    _, user = await register_and_login(prefix="l4w55a-dp")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比住宿标准？",
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_search_ok("住宿")),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=1,
        )
        await db.commit()

    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    assert outcome.terminal_decision.reason_code == "facts_partial_budget"
    monkeypatch.setattr(settings, "agent_l4_stop_policy_enabled", False)


@pytest.mark.asyncio
async def test_case_e_flag_off_regression(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case E：flag off → Stop 不改 runtime；L3 premature finish 仍放行。"""
    assert settings.agent_l4_stop_policy_enabled is False
    goals = _goals(FactStatus.missing, FactStatus.missing, FactStatus.missing)
    _patch_init_with_goals(monkeypatch, goals)

    evaluate_calls = 0
    real_evaluate = StopPolicy.evaluate

    def _spy(self, evidence, *, steps_used=0, max_steps=0):  # noqa: ANN001
        nonlocal evaluate_calls
        evaluate_calls += 1
        return real_evaluate(
            self, evidence, steps_used=steps_used, max_steps=max_steps
        )

    monkeypatch.setattr(StopPolicy, "evaluate", _spy)

    _, user = await register_and_login(prefix="l4w55a-e")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = ScriptedNextActionPlanner(
        [
            AgentDecision(
                action=AgentActionKind.finish,
                reason_code="evidence_sufficient",
            ),
        ],
        query="对比住宿标准？",
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=planner._query,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps == ()
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action == AgentActionKind.finish
    assert outcome.terminal_decision.reason_code == "evidence_sufficient"
    # evaluate 被调用但返回 disabled，不改写
    assert evaluate_calls >= 1
    disabled = StopPolicy().evaluate(
        init_agent_state(original_query="x", max_steps=5, fact_goals=goals).evidence,
        steps_used=0,
        max_steps=5,
    )
    assert disabled.ok is False
    assert disabled.source == "disabled"

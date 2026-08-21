"""M1-W2 候选① 漂移守卫单测（guard_sub_query_drift）。

覆盖 §6.3 测试策略四层：
  1. 子查询无命中 → 整题直检回退（S2）
  2. 漂移子查询连续漂移 → 改写上限 1 次（S1 不无限循环）
  3. 预算守卫：steps_used + 1 >= max_steps → 跳过 S2
  4. 配置默认关（agent_decompose_drift_recovery=False）→ 零激活回归

守卫只影响 agent 分解-检索链路；默认关时行为与 phase2_m1_agent_base 快照逐字一致
（本组用例「零激活」断言 _run_recovery_search / rewrite_query 均不被触碰）。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.runtime import guard_sub_query_drift
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentStepRecord, StepExecution
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

ORIGINAL = "如果 API 返回 429 错误码，可能是什么原因？怎么解决？"
SUB_QUERY = "API 错误码 原因 解决方案"


def _hit(score: float, excerpt: str = "API 错误码 排查 解决方案") -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="acme_FAQ合集.md",
        page=1,
        section_title="六、集成与API类（10题）",
        excerpt=excerpt,
        score=score,
    )


def _output(*hits: SemanticSearchHit) -> SemanticSearchOutput:
    return SemanticSearchOutput(hits=hits, retrieval_ms=1)


def _execution(output: SemanticSearchOutput) -> StepExecution:
    return StepExecution(
        ok=True,
        summary=f"命中 {len(output.hits)} 条",
        latency_ms=1,
        data=output,
    )


class _RecoveryRecorder:
    """记录 _run_recovery_search 调用（query / step_index），按需返回受控执行结果。"""

    def __init__(self, *executions: StepExecution) -> None:
        self.calls: list[tuple[str, int]] = []
        self.executions: list[StepExecution] = list(executions)
        self.i = 0

    async def __call__(self, db, *, query: str, step_index: int, **kwargs) -> tuple:
        del db, kwargs
        execution = self.executions[min(self.i, len(self.executions) - 1)]
        self.i += 1
        self.calls.append((query, step_index))
        record = AgentStepRecord(
            step_index=step_index,
            tool_name="semantic_search",
            args={"query": query},
            ok=execution.ok,
            summary=execution.summary,
            latency_ms=1,
            data=execution.data,
        )
        return execution, record


def _context(db=None):
    """守卫调用所需的上下文参数（恢复搜索路径被 mock，作用域对象仅透传）。"""
    return dict(
        db=db or _StubDb(),
        workspace=WorkspaceScope(kind=WorkspaceKind.personal, user_id=uuid.uuid4(), org_id=None),
        tool_scope=object(),
        org_scope=None,
        current_user=None,
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )


class _StubDb:
    """守卫单测用最小 db 桩：审计写入只需 add / await flush。"""

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, entry: object) -> None:
        self.added.append(entry)

    async def flush(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _drift_config_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例显式设置漂移配置（默认关；用例内再按需开启），避免串扰。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", False)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 1)


def test_config_readonly_relevance_ceiling() -> None:
    """兼容性断言：0.5 只读配置未被候选① 改动（漂移判定只读该值，不改变其语义）。"""
    assert settings.relevance_low_sim_ceiling == 0.5


@pytest.mark.asyncio
async def test_no_hit_triggers_s2_whole_query_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子查询 0 命中（T1）→ 整题直检回退：S2 用原 query 执行恢复搜索并 +1 步。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)  # 直走 S2

    recovered = _execution(_output(_hit(0.62, excerpt="429 状态码限制 重试时间")))
    recorder = _RecoveryRecorder(recovered)
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )

    drifted = _execution(_output())  # T1：无命中
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=2,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert recs[0].tool_name == "semantic_search"
    assert steps_used == 3  # S2 消耗 1 步
    assert recorder.calls == [(ORIGINAL, 3)]  # 恢复搜索用原 query，新步号 3


@pytest.mark.asyncio
async def test_rewrite_budget_capped_at_one_no_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """漂移子查询连续两次漂移：S1 改写恰 1 次（max_rewrites=1）后丢弃，不无限循环。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 1)

    # S1 改写重检仍漂移（top1 sim 仍 < 0.5）→ 改写结果丢弃，转入 S2
    still_drifted = _execution(_output(_hit(0.3)))
    recorder = _RecoveryRecorder(still_drifted)
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )

    rewrite_mock = AsyncMock(return_value="API 429 错误原因 故障排查")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    drifted = _execution(_output(_hit(0.3)))  # T2：top1 sim < 0.5
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert rewrite_mock.await_count == 1  # 改写上限 1 次，不循环
    # S1 改写结果仍漂移 → 不并入（丢弃）；S2 整题直检回退接管
    assert len(recs) == 1
    assert recorder.calls[0][0] != ORIGINAL  # 首条 = S1 改写重检
    assert recorder.calls[-1][0] == ORIGINAL  # 末条 = S2 整题直检
    assert steps_used == 2 + len(recs)  # S1 + S2 各消耗 1 步


@pytest.mark.asyncio
async def test_budget_guard_skips_s2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预算守卫：steps_used + 1 >= max_steps → 跳过 S2（回到 S3 终点判据）。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)

    recorder = _RecoveryRecorder(_execution(_output(_hit(0.62))))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    drifted = _execution(_output())  # T1：无命中
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=3,
        max_steps=3,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 3
    assert rewrite_mock.await_count == 0  # S1 也被预算挡下
    assert recorder.calls == []  # 无任何恢复搜索执行


@pytest.mark.asyncio
async def test_a0_4_s2_reachable_at_steps_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史边界：A0=4 下漂移链 steps=2、无 S1（rewrite=0）→ S2 可达。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recovered = _execution(_output(_hit(0.62, excerpt="429 状态码限制 重试时间")))
    recorder = _RecoveryRecorder(recovered)
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )

    drifted = _execution(_output())  # T1：无命中
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=2,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 3
    assert recorder.calls == [(ORIGINAL, 3)]


@pytest.mark.asyncio
async def test_a0_4_s2_unreachable_after_s1_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史边界：S1 已占步后 steps=3、A0=4 → S2 仍跳过。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recorder = _RecoveryRecorder(_execution(_output(_hit(0.62))))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )

    drifted = _execution(_output())  # T1
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=3,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 3
    assert recorder.calls == []


@pytest.mark.asyncio
async def test_a0_5_s1_to_s2_reachable_at_steps_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2-W1b：A0=5 下 steps=2 时 S1 改写仍漂移 → S2 可入（满阶梯）。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 1)

    still_drifted = _execution(_output(_hit(0.3)))
    recovered = _execution(_output(_hit(0.62, excerpt="429 状态码限制 重试时间")))
    recorder = _RecoveryRecorder(still_drifted, recovered)
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="API 429 错误原因 故障排查")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    drifted = _execution(_output(_hit(0.3)))  # T2
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert rewrite_mock.await_count == 1
    assert recorder.calls[0][0] != ORIGINAL
    assert recorder.calls[-1][0] == ORIGINAL
    assert steps_used == 3


@pytest.mark.asyncio
async def test_a0_5_s2_reachable_after_s1_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2-W1b：S1 已占步后 steps=3、A0=5 → S2 可达（3+1 < 5）。"""
    monkeypatch.setattr(settings, "agent_decompose_drift_recovery", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recovered = _execution(_output(_hit(0.62, excerpt="429 状态码限制 重试时间")))
    recorder = _RecoveryRecorder(recovered)
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )

    drifted = _execution(_output())  # T1
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=3,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 4
    assert recorder.calls == [(ORIGINAL, 4)]


@pytest.mark.asyncio
async def test_default_off_zero_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置默认关（False）→ 零激活：漂移输入也不触发恢复搜索 / 改写。"""
    # 不开启 agent_decompose_drift_recovery（fixture 已置 False）

    recorder = _RecoveryRecorder(_execution(_output(_hit(0.62))))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    drifted = _execution(_output())  # T1：若开启本应触发
    ctx = _context()
    recs, steps_used = await guard_sub_query_drift(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=drifted,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 2  # 不推进预算
    assert recorder.calls == []  # 零恢复搜索
    assert rewrite_mock.await_count == 0  # 零改写

"""M2 W2 · 证据不足自适应重检策略单测（guard_evidence_insufficiency）。

覆盖：
  1. 配置默认关（agent_evidence_strategy_enabled=False）→ 零激活回归
  2. 证据充分 → 不触发重检（零恢复搜索 / 零改写 / 零 evidence_recovery 审计）
  3. 证据不足（命中数 2 < 3 且 sim 达标）→ S1 收敛改写重检成功 → 恢复记录 +1 步 + 审计
  4. S1 改写后证据仍不足 → 丢弃改写、转入 S2 整题直检（+2 步 + 审计）
  5. 预算守卫：steps_used + 1 >= max_steps → 跳过 S1/S2（回到 S3 终点判据）
  6. 每分解链 S2 至多 1 次（chain_state.evidence_s2_used 去重）

策略只补「有命中但数量/多样性不足」空档，复用 M1 drift guard 的 _run_recovery_search /
rewrite_query 恢复执行器；evidence.py 四维度判定逻辑零改动（兼容性断言见 test_config_readonly）。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.runtime import guard_evidence_insufficiency
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentStepRecord, StepExecution
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

ORIGINAL = "如果 API 返回 429 错误码，可能是什么原因？怎么解决？"
SUB_QUERY = "API 错误码 原因 解决方案"


def _hit(
    score: float,
    chunk_id: uuid.UUID | None = None,
    doc_name: str = "acme_FAQ合集.md",
) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=chunk_id or uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name=doc_name,
        page=1,
        section_title="六、集成与API类（10题）",
        excerpt="API 错误码 排查 解决方案",
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


def _sufficient_output() -> SemanticSearchOutput:
    """证据充分：3 条不同 chunk，sim >= 0.5。"""
    return _output(_hit(0.6), _hit(0.7), _hit(0.65))


def _insufficient_hit_count_output() -> SemanticSearchOutput:
    """证据不足（命中数 2 < 3）：sim 达标，数量不足。"""
    return _output(_hit(0.6), _hit(0.62))


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
def _strategy_config_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例显式设置策略配置（默认关），避免串扰。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", False)
    monkeypatch.setattr(settings, "agent_evidence_sufficiency_obs", False)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 1)


def _evidence_recovery_events(db: _StubDb) -> list:
    """提取审计事件中 signal == 'evidence_recovery' 的条目。"""
    return [
        e for e in db.added
        if getattr(e, "action", None) == "agent.reflection"
        and (getattr(e, "details", None) or {}).get("signal") == "evidence_recovery"
    ]


def test_config_readonly() -> None:
    """兼容性断言：0.5 只读配置未被 M2 改动（evidence 判定用函数默认阈值，不读该配置）。"""
    assert settings.relevance_low_sim_ceiling == 0.5


@pytest.mark.asyncio
async def test_default_off_zero_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置默认关（False）→ 零激活：证据不足输入也不触发恢复搜索 / 改写 / 审计。"""
    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 2  # 不推进预算
    assert recorder.calls == []  # 零恢复搜索
    assert rewrite_mock.await_count == 0  # 零改写
    assert _evidence_recovery_events(ctx["db"]) == []  # 零策略审计


@pytest.mark.asyncio
async def test_sufficient_evidence_no_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证据充分 → 不触发重检（零恢复 / 零改写 / 零策略审计）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    sufficient_exec = _execution(_sufficient_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=sufficient_exec,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 2
    assert recorder.calls == []
    assert rewrite_mock.await_count == 0
    assert _evidence_recovery_events(ctx["db"]) == []


@pytest.mark.asyncio
async def test_insufficient_triggers_s1_rewrite_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证据不足（命中数 2 < 3）→ S1 收敛改写重检成功：恢复记录 +1 步 + 审计。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    # S1 改写后重检返回充分证据 → 以改写恢复记录作为合并贡献
    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="API 429 错误码 重试 具体原因")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert recs[0].tool_name == "semantic_search"
    assert steps_used == 3  # S1 重检消耗 1 步
    assert rewrite_mock.await_count == 1
    assert recorder.calls == [("API 429 错误码 重试 具体原因", 3)]  # 改写重检
    events = _evidence_recovery_events(ctx["db"])
    assert len(events) == 2  # 触发事件 + 改写成功事件
    assert any("triggered=True" in e.details["new_query"] for e in events)
    assert any(
        "sufficient=True" in e.details["new_query"] for e in events
    )


@pytest.mark.asyncio
async def test_rewrite_still_insufficient_falls_to_s2_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1 改写后证据仍不足 → 丢弃改写，转入 S2 整题直检（+2 步 + 审计）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    # 第一次调用（S1 重检）返回仍不足的证据；第二次调用（S2 直检）返回充分证据
    recorder = _RecoveryRecorder(
        _execution(_output(_hit(0.6))),  # S1 重检：1 条，命中数仍不足
        _execution(_sufficient_output()),  # S2 直检：充分
    )
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="API 429 错误码 重试 具体原因")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1  # S2 直检恢复记录接管（改写记录已丢弃）
    assert steps_used == 3  # 仅 S2 计入返回步；被丢弃的 S1 不推进预算（与 drift guard 一致）
    assert rewrite_mock.await_count == 1
    assert recorder.calls[0][0] != ORIGINAL  # 首条 = S1 改写重检
    assert recorder.calls[-1][0] == ORIGINAL  # 末条 = S2 整题直检
    events = _evidence_recovery_events(ctx["db"])
    assert any("triggered=True" in e.details["new_query"] for e in events)
    assert any(f"direct={ORIGINAL}" in e.details["new_query"] for e in events)


@pytest.mark.asyncio
async def test_budget_guard_skips_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预算守卫（耗尽态）：steps_used == max_steps → 跳过 S1/S2（回到 S3 终点判据）。

    W4 方案 C：S1 已放宽为 steps_used < max_steps —— 本用例取步骤触顶（steps_used =
    max_steps）的最紧边界，S1/S2 均仍跳过，保证恢复步不使总步数越界。
    """
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=3,
        max_steps=3,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 3
    assert rewrite_mock.await_count == 0  # S1 也被预算挡下
    assert recorder.calls == []  # 无任何恢复搜索执行
    # 触发审计已写（记录「证据不足但预算挡下」），但无恢复执行审计
    events = _evidence_recovery_events(ctx["db"])
    assert len(events) == 1
    assert events[0].details["new_query"].endswith("triggered=True")


@pytest.mark.asyncio
async def test_s1_executable_at_max_steps_minus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W4 方案 C：steps_used = max_steps - 1 时 S1 单步可达（恢复步计入总步，不越界）。

    W3 预算饿死（S1 守卫 steps_used + 1 < max_steps 在触发点恒阻断）→ W4 放宽为
    steps_used < max_steps。本用例模拟 ENT-026 型触发点（A0=3，steps_used=2）：
    改写重检充分 → S1 恢复记录接管（替换原始不足记录），steps_used 推进到 max_steps
    （capped 由调用方循环统一结算，守卫自身步数不越界）。
    """
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="付款账期 违约金 具体条款")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=3,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1  # 边界下 S1 改写重检可达（W3 此处回到空恢复）
    assert recs[0].tool_name == "semantic_search"
    assert steps_used == 3  # 恢复步计入总步（= max_steps，未越界）
    assert rewrite_mock.await_count == 1
    assert recorder.calls == [("付款账期 违约金 具体条款", 3)]  # 恢复搜索落在最后一步
    events = _evidence_recovery_events(ctx["db"])
    assert len(events) == 2  # 触发 + 改写成功
    assert any("triggered=True" in e.details["new_query"] for e in events)
    assert any("sufficient=True" in e.details["new_query"] for e in events)


@pytest.mark.asyncio
async def test_s2_dedup_per_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """每分解链 S2 至多 1 次：chain_state.evidence_s2_used 已置位 → S2 直接跳过。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)  # 直走 S2

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    chain_state: dict = {"evidence_s2_used": True}  # 前一个子查询已用过 S2
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=5,
        chain_state=chain_state,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    # 触发审计已写（策略确实触发），但 S2 已用 → 不再执行恢复，返回空
    assert recs == []
    assert steps_used == 2
    assert rewrite_mock.await_count == 0  # S1 被预算为 0 跳过，无 S1 改写
    assert recorder.calls == []  # 无恢复搜索执行
    assert len(_evidence_recovery_events(ctx["db"])) == 1  # 仅触发审计
    assert _evidence_recovery_events(ctx["db"])[0].details["new_query"].endswith(
        "triggered=True"
    )


def test_g2_w1b_default_max_steps_and_retrieval_switches() -> None:
    """G2-W1b：A0=5；生产其它检索/加深开关默认不变。"""
    from app.services.agent.runs import DEFAULT_MAX_STEPS

    assert DEFAULT_MAX_STEPS == 5
    assert settings.agent_evidence_strategy_enabled is False
    assert settings.agent_decompose_drift_recovery is False
    assert settings.hyde_enabled is False
    assert settings.rerank_policy == "off"
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False


@pytest.mark.asyncio
async def test_a0_4_s1_reachable_at_steps_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史边界：A0=4 下分解链触发点 steps_used=2 时 S1 可达（方案 C 守卫）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="付款账期 违约金 具体条款")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 3
    assert rewrite_mock.await_count == 1
    assert recorder.calls == [("付款账期 违约金 具体条款", 3)]


@pytest.mark.asyncio
async def test_a0_4_s2_reachable_at_steps_2_without_s1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史边界：A0=4 下 steps=2 时无先 S1（rewrite=0）→ S2 可达（2+1 < 4）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 3
    assert rewrite_mock.await_count == 0
    assert recorder.calls == [(ORIGINAL, 3)]
    events = _evidence_recovery_events(ctx["db"])
    assert any(f"direct={ORIGINAL}" in e.details["new_query"] for e in events)


@pytest.mark.asyncio
async def test_a0_4_s1_to_s2_still_unreachable_after_s1_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史边界：S1 已占步后 steps=3、A0=4 → S2 仍不可达（3+1 < 4 假）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=3,
        max_steps=4,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert recs == []
    assert steps_used == 3
    assert rewrite_mock.await_count == 0
    assert recorder.calls == []
    events = _evidence_recovery_events(ctx["db"])
    assert len(events) == 1  # 仅触发审计，无 direct=


@pytest.mark.asyncio
async def test_a0_5_s1_to_s2_reachable_at_steps_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2-W1b：A0=5 下 steps=2 时 S1 改写仍不足 → S2 可入（满阶梯）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)

    recorder = _RecoveryRecorder(
        _execution(_output(_hit(0.6))),  # S1 重检：仍不足
        _execution(_sufficient_output()),  # S2 直检：充分
    )
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="API 429 错误码 重试 具体原因")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=2,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 3
    assert rewrite_mock.await_count == 1
    assert recorder.calls[0][0] != ORIGINAL
    assert recorder.calls[-1][0] == ORIGINAL
    events = _evidence_recovery_events(ctx["db"])
    assert any(f"direct={ORIGINAL}" in e.details["new_query"] for e in events)


@pytest.mark.asyncio
async def test_a0_5_s2_reachable_after_s1_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2-W1b：S1 已占步后 steps=3、A0=5 → S2 可达（3+1 < 5）。"""
    monkeypatch.setattr(settings, "agent_evidence_strategy_enabled", True)
    monkeypatch.setattr(settings, "agent_decompose_drift_max_rewrites", 0)

    recorder = _RecoveryRecorder(_execution(_sufficient_output()))
    monkeypatch.setattr(
        "app.services.agent.runtime._run_recovery_search", recorder
    )
    rewrite_mock = AsyncMock(return_value="rewritten-query")
    monkeypatch.setattr("app.services.rag.generation.rewrite_query", rewrite_mock)

    insuff = _execution(_insufficient_hit_count_output())
    ctx = _context()
    recs, steps_used = await guard_evidence_insufficiency(
        sub_query=SUB_QUERY,
        original_query=ORIGINAL,
        sub_args={"query": SUB_QUERY},
        sub_execution=insuff,
        steps_used=3,
        max_steps=5,
        **{k: v for k, v in ctx.items() if k != "db"},
        db=ctx["db"],
    )

    assert len(recs) == 1
    assert steps_used == 4
    assert rewrite_mock.await_count == 0
    assert recorder.calls == [(ORIGINAL, 4)]
    events = _evidence_recovery_events(ctx["db"])
    assert any(f"direct={ORIGINAL}" in e.details["new_query"] for e in events)

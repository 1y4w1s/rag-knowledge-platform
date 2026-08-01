"""E2 迭代反思循环专项测试。

覆盖范围（§7 测试策略 · 11 个用例）：
- 正常路径（#1-3）
- 边界条件（#4-6）
- 安全 + 降级（#7-9）
- 退役验证（#10-11）
"""

from __future__ import annotations

import uuid

import pytest

from app.services.agent.runtime import _detect_low_confidence, _detect_reflection_signal
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.agent.tools.semantic_search import SemanticSearchHit, SemanticSearchOutput
from app.services.rag.confidence_reply import LOW_CONFIDENCE_SIM_CEILING


# ── helpers ──────────────────────────────────────────────────────────────────


def _hit(*, score: float) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="test_kb",
        doc_name="doc.md",
        page=1,
        section_title="Section",
        excerpt="test excerpt",
        score=score,
    )


def _semantic_step(
    *,
    scores: tuple[float, ...] = (),
    ok: bool = True,
    step_index: int = 1,
) -> AgentStepRecord:
    hits = tuple(_hit(score=s) for s in scores)
    data = SemanticSearchOutput(hits=hits, retrieval_ms=10) if ok else None
    return AgentStepRecord(
        step_index=step_index,
        tool_name="semantic_search",
        args={"query": "test query"},
        ok=ok,
        summary=f"检索到 {len(hits)} 条" if hits else "无命中",
        latency_ms=10,
        data=data,
    )


# ═══════════════════════════════════════════════════════════════════════════
# §7.2 正常路径
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalDetectionNormal:
    """#1-3：信号检测正常路径。"""

    def test_signal_a_low_recall_empty_hits(self) -> None:
        """#1：semantic_search 返回空 hits → low_recall 信号。"""
        step = _semantic_step(scores=())
        signal = _detect_reflection_signal(step, "test query", 0)
        assert signal == "low_recall"

    def test_signal_a_low_recall_all_below_threshold(self) -> None:
        """#1b：所有 hit score 低于阈值 → low_recall 信号。"""
        step = _semantic_step(scores=(0.3, 0.4))
        signal = _detect_reflection_signal(step, "test query", 0)
        assert signal == "low_recall"

    def test_signal_c_complex_query_first_round(self) -> None:
        """#2：首轮 complex_query 检测。"""
        # complex_query 需要 query_depth 返回 complex，但 _detect_reflection_signal
        # 在首轮 (reflection_count==0) 时会调用 query_depth。
        # query_depth 基于关键词判断，如含"对比""比较""分析""总结"等触发 complex
        step = _semantic_step(scores=(0.6, 0.7))
        signal = _detect_reflection_signal(step, "对比年假和病假政策", 0)
        # A 信号优先，只要 hits >= threshold 就不触发 A
        # C 信号在 reflection_count==0 时触发
        # 这里 hits 都 >= 0.5，所以不走 A；走 C
        # "对比" 触发 query_depth → complex
        assert signal == "complex_query"

    def test_no_signal_normal_retrieval(self) -> None:
        """#3：检索正常，不触发任何信号。"""
        step = _semantic_step(scores=(LOW_CONFIDENCE_SIM_CEILING + 0.1, 0.8))
        signal = _detect_reflection_signal(step, "年假政策", 0)
        assert signal is None

    def test_no_signal_second_round(self) -> None:
        """#3b：第二轮 (reflection_count>0) 即使 query complex 也不触发 C。"""
        step = _semantic_step(scores=(0.6, 0.7))
        signal = _detect_reflection_signal(step, "对比年假和病假政策", 1)
        assert signal is None

    def test_no_signal_non_search_tool(self) -> None:
        """#3c：非检索工具步骤不触发信号。"""
        step = AgentStepRecord(
            step_index=1,
            tool_name="get_chunk_excerpt",
            args={},
            ok=True,
            summary="ok",
            latency_ms=5,
            data=None,
        )
        signal = _detect_reflection_signal(step, "年假政策", 0)
        assert signal is None


# ═══════════════════════════════════════════════════════════════════════════
# §7.3 边界条件
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalBoundaries:
    """#4-6：边界条件。"""

    def test_low_recall_not_applicable_when_step_failed(self) -> None:
        """#4 相关：检索步骤 failed (ok=False) 时 _detect_reflection_signal 仍能正常判断。
        实际 E2 循环体中有 `if signal == "low_recall" and ok:` 额外守卫。
        """
        step = _semantic_step(scores=(), ok=False)
        signal = _detect_reflection_signal(step, "test query", 0)
        # 虽然 ok=False，但检测函数只看 tool_name 和 data，所以仍返回 low_recall
        # 循环中的 `and ok` 守卫会阻止执行改写
        assert signal == "low_recall"

    def test_signal_b_low_confidence_all_below_threshold(self) -> None:
        """#6：所有检索 hits 低于阈值 → low_confidence 标记。"""
        records = [
            _semantic_step(scores=(0.1, 0.2)),
            _semantic_step(scores=(0.3,), step_index=2),
        ]
        assert _detect_low_confidence(records) is True

    def test_signal_b_low_confidence_above_threshold(self) -> None:
        """#6b：有任意 hit 高于阈值 → 不标记 low_confidence。"""
        records = [
            _semantic_step(scores=(0.1, 0.6)),
            _semantic_step(scores=(0.3,), step_index=2),
        ]
        assert _detect_low_confidence(records) is False

    def test_signal_b_low_confidence_empty_hits(self) -> None:
        """#6c：空 hits → 不标记 low_confidence（没有 hits 不触发）。"""
        records = [
            _semantic_step(scores=()),
            _semantic_step(scores=(), step_index=2),
        ]
        assert _detect_low_confidence(records) is False

    def test_signal_b_low_confidence_mixed_tools(self) -> None:
        """#6d：非检索工具不参与 score 汇总。"""
        grep_step = AgentStepRecord(
            step_index=2,
            tool_name="grep_in_document",
            args={},
            ok=True,
            summary="ok",
            latency_ms=5,
            data=None,
        )
        records = [_semantic_step(scores=(0.2,)), grep_step]
        assert _detect_low_confidence(records) is True


# ═══════════════════════════════════════════════════════════════════════════
# §7.4 安全 + 降级
# ═══════════════════════════════════════════════════════════════════════════


class TestSafetyDegradation:
    """#7-9：安全 + 降级。"""

    def test_reflection_count_exceeds_max(self) -> None:
        """#7：reflection_count >= agent_max_reflections 时 _detect_reflection_signal
        在 runtime 中不被调用（循环体中的 reflection_count < settings.agent_max_reflections 守卫）。
        这里验证即使调用，第二轮的 complex_query 也会因 reflection_count>0 而返回 None。
        """
        step = _semantic_step(scores=(0.6, 0.7))
        # reflection_count == 1 且 hits 正常 → 无信号（complex_query 只在首轮触发）
        signal = _detect_reflection_signal(step, "对比年假和病假政策", 1)
        assert signal is None

    def test_complex_query_sub_queries_all_fail(self) -> None:
        """#9 相关：complex_query 触发条件不变（与子查询执行结果无关）。
        子查询全部失败由主循环处理，检测信号函数不关心执行结果。
        """
        step = _semantic_step(scores=(0.6, 0.7))
        signal = _detect_reflection_signal(step, "对比年假和病假政策", 0)
        assert signal == "complex_query"


# ═══════════════════════════════════════════════════════════════════════════
# §7.5 退役验证
# ═══════════════════════════════════════════════════════════════════════════


class TestRetireExpandAndRetry:
    """#10-11：退役验证。"""

    def test_expand_and_retry_method_deleted(self) -> None:
        """#10：engine.py 中不再有 _expand_and_retry 方法。"""
        from app.services.rag.engine import ChatEngine

        assert not hasattr(ChatEngine, "_expand_and_retry")

    def test_retrieve_no_longer_calls_expand_and_retry(self) -> None:
        """#11：_retrieve 中不再引用 _expand_and_retry。"""
        import inspect

        from app.services.rag.engine import ChatEngine

        source = inspect.getsource(ChatEngine._retrieve)
        assert "_expand_and_retry" not in source


# ═══════════════════════════════════════════════════════════════════════════
# prepare_agent_generation 签名验证
# ═══════════════════════════════════════════════════════════════════════════


class TestPrepareGenerationSignature:
    """验证 prepare_agent_generation 已接收 outcome 参数。"""

    def test_prepare_agent_generation_accepts_outcome(self) -> None:
        """新增 outcome 参数且默认 None。"""
        import inspect

        from app.services.agent.finalize import prepare_agent_generation

        sig = inspect.signature(prepare_agent_generation)
        assert "outcome" in sig.parameters
        param = sig.parameters["outcome"]
        # 默认值为 None
        assert param.default is None

    async def test_prepare_agent_generation_with_outcome(self) -> None:
        """验证传入 outcome 后不报错（当前仅接收不消费）。"""
        from unittest.mock import AsyncMock

        from app.services.agent.finalize import prepare_agent_generation

        outcome = AgentRunOutcome(
            run_id=uuid.uuid4(),
            steps_used=1,
            max_steps=5,
            capped=False,
            timed_out=False,
            steps=(),
            low_confidence=True,
        )
        db_mock = AsyncMock(spec_set=["get"])

        plan = await prepare_agent_generation(
            db_mock,
            query="test",
            steps=(),
            workspace_mode=False,
            outcome=outcome,
        )
        assert plan.refusal is True
        assert plan.gated_chunks == ()
        assert plan.citations == ()

"""B3 自适应检索策略 —— 单元 + mock 集成测试。

分层：
- 单元测试：验证 select_strategy() 策略选择正确性（纯函数，无依赖）
- mock 集成测试：验证 effective_rerank_for_strategy 和 HyDE 联动
"""

from __future__ import annotations

import pytest

from app.services.rag.planner import (
    RetrievalStrategy,
    _count_named_entities,
    _has_multi_intent,
    effective_rerank_for_strategy,
    select_strategy,
)


# ═══════════════════════════════════════════════════
# 单元测试：select_strategy 策略选择
# ═══════════════════════════════════════════════════

class TestSelectStrategy:
    """B3 自适应检索策略选择正确性验证。

    测试矩阵：
    - simple：超短问（去标点 < 4 字）
    - medium：常规问句（无实体/多意图标记，长度适中）
    - complex：实体数 >= 2、多意图、或长问 > 20 字
    """

    # ── simple ──

    def test_simple_short_keyword(self):
        """超短关键词 → simple（如"年假"）。"""
        assert select_strategy("年假") == RetrievalStrategy.simple

    def test_simple_greeting(self):
        """超短问候 → simple。"""
        assert select_strategy("你好") == RetrievalStrategy.simple

    def test_simple_short_with_punct(self):
        """带标点的超短问，去标点后 < 4 字 → simple。"""
        assert select_strategy("年假？") == RetrievalStrategy.simple

    # ── medium ──

    def test_medium_normal_question(self):
        """常规问句（无实体/多意图）→ medium。"""
        assert select_strategy("年假有多少天") == RetrievalStrategy.medium

    def test_medium_weather(self):
        """常规天气问句 → medium。"""
        assert select_strategy("今天天气怎么样") == RetrievalStrategy.medium

    def test_medium_single_entity_insufficient(self):
        """单一实体（ent=1 < 2）且无多意图 → medium。"""
        assert select_strategy("百度科技有限公司") == RetrievalStrategy.medium

    def test_medium_single_book_ref(self):
        """单一书名号实体 → medium。"""
        assert select_strategy("《劳动法》的内容") == RetrievalStrategy.medium

    # ── complex (by entity count ≥ 2) ──

    def test_complex_two_book_entities(self):
        """两个书名号实体 → complex。"""
        assert select_strategy("《劳动法》和《劳动合同法》有什么区别") == RetrievalStrategy.complex

    def test_complex_two_org_names(self):
        """两个组织名 → complex。"""
        assert select_strategy("阿里巴巴集团和腾讯控股有限公司的主要业务区别") == RetrievalStrategy.complex

    def test_complex_org_and_book(self):
        """组织名 + 书名号实体 → complex。"""
        assert select_strategy("DeepSeek公司关于《劳动法》的规定") == RetrievalStrategy.complex

    def test_complex_bank_comparison(self):
        """银行名 x2 + 对比词 → complex。"""
        assert select_strategy("中国工商银行和招商银行哪个理财收益高") == RetrievalStrategy.complex

    # ── complex (by multi-intent) ──

    def test_complex_comparison_he(self):
        """"和"字多意图 → complex。"""
        assert select_strategy("Python 和 Go 在并发编程方面各自的优缺点") == RetrievalStrategy.complex

    def test_complex_comparison_qubie(self):
        """"区别"字多意图 → complex。"""
        assert select_strategy("这两种方案的主要区别是什么") == RetrievalStrategy.complex

    def test_complex_comparison_duibi(self):
        """"对比"字多意图 → complex。"""
        assert select_strategy("请对比一下两个产品的价格") == RetrievalStrategy.complex

    # ── complex (by length > 20) ──

    def test_complex_long_query(self):
        """长问（> 20 字）无实体标记 → complex。"""
        assert select_strategy("请问公司的年假政策是什么以及如何申请休假的流程") == RetrievalStrategy.complex

    def test_complex_long_without_multi_intent(self):
        """长句（> 20 字）无比较词 → complex。"""
        q = "我想了解一下关于员工福利的完整政策包括年假病假和事假"
        assert len(q) > 20
        assert select_strategy(q) == RetrievalStrategy.complex

    # ── 边界 / 空值 ──

    def test_empty_query(self):
        """空 query → medium（无长度、无实体、无意图）。"""
        assert select_strategy("") == RetrievalStrategy.medium

    def test_single_char(self):
        """单字符 → 如果<4 且非空 → simple。"""
        assert select_strategy("好") == RetrievalStrategy.simple

    def test_four_chars_exact(self):
        """4 字符 = 正好在边界上 → medium（不是 <4）。"""
        assert select_strategy("四个字符") == RetrievalStrategy.medium


# ═══════════════════════════════════════════════════
# 辅助函数单元测试
# ═══════════════════════════════════════════════════

class TestCountNamedEntities:
    """_count_named_entities 正确性验证。"""

    def test_no_entities(self):
        assert _count_named_entities("今天天气怎么样") == 0

    def test_one_book_entity(self):
        assert _count_named_entities("《劳动法》的内容") == 1

    def test_two_book_entities(self):
        assert _count_named_entities("《劳动法》和《劳动合同法》") == 2

    def test_org_name(self):
        assert _count_named_entities("百度科技有限公司") == 1

    def test_two_org_names(self):
        assert _count_named_entities("阿里巴巴集团和腾讯控股有限公司") == 2

    def test_mixed_entity_types(self):
        """书名号 + 组织名混合。"""
        assert _count_named_entities("DeepSeek公司关于《劳动法》") == 2


class TestHasMultiIntent:
    """_has_multi_intent 正确性验证。"""

    def test_no_intent(self):
        assert not _has_multi_intent("今天天气怎么样")

    def test_he_keyword(self):
        assert _has_multi_intent("ABC 和 DEF")

    def test_qubie_keyword(self):
        assert _has_multi_intent("ABC 和 DEF 的区别")

    def test_duibi_keyword(self):
        assert _has_multi_intent("对比一下这两个")

    def test_fenbie_keyword(self):
        assert _has_multi_intent("分别说一下各自的优缺点")

    def test_empty(self):
        assert not _has_multi_intent("")


# ═══════════════════════════════════════════════════
# effective_rerank_for_strategy 测试
# ═══════════════════════════════════════════════════

class TestEffectiveRerankForStrategy:
    """effective_rerank_for_strategy 在不同策略等级下的行为验证。"""

    def test_complex_passes_through_off(self):
        """complex 透传 base_policy=off（实验 N：不再强制 always）。"""
        assert effective_rerank_for_strategy(
            RetrievalStrategy.complex, "off"
        ) == "off"

    def test_complex_passes_through_conditional(self):
        """complex 透传 base_policy=conditional（实验 N：不再强制 always）。"""
        assert effective_rerank_for_strategy(
            RetrievalStrategy.complex, "conditional"
        ) == "conditional"

    def test_complex_passes_through_always(self):
        """complex 透传 base_policy=always（显式开启全局精排时 complex 也生效）。"""
        assert effective_rerank_for_strategy(
            RetrievalStrategy.complex, "always"
        ) == "always"

    def test_medium_passes_through(self):
        """medium 策略不干预基础策略。"""
        assert effective_rerank_for_strategy(
            RetrievalStrategy.medium, "off"
        ) == "off"

    def test_simple_passes_through(self):
        """simple 策略不干预基础策略。"""
        assert effective_rerank_for_strategy(
            RetrievalStrategy.simple, "conditional"
        ) == "conditional"

    def test_none_strategy_fallback(self):
        """strategy=None 时使用基础策略（无错误）。"""
        assert effective_rerank_for_strategy(None, "off") == "off"


# ═══════════════════════════════════════════════════
# mock 集成测试：_apply_rerank_policy strategy 感知
# ═══════════════════════════════════════════════════

class TestApplyRerankPolicyStrategyAware:
    """验证 _apply_rerank_policy 在 complex 策略下透传 base_policy。

    注意：这些是 mock 测试，不调真实 rerank。验证的是策略逻辑而非 rerank 本身。
    实验 N：complex 不再强制 always，尊重 RERANK_POLICY。
    """

    @pytest.fixture
    def mock_candidates(self):
        """构建简单候选列表（len=3）。"""
        from app.services.rag.types import RetrievedChunk
        from uuid import uuid4
        uid = uuid4()
        return [
            RetrievedChunk(
                chunk_id=uid,
                content="chunk a",
                similarity=0.5,
                kb_id=uid,
                document_id=uid,
                doc_name="test.pdf",
                page_number=1,
                section_title="Section",
                heading_path="/Section",
            )
            for _ in range(3)
        ]

    @pytest.mark.asyncio
    async def test_complex_respects_off(self, mock_candidates, monkeypatch):
        """strategy=complex, RERANK_POLICY=off 时不触发 rerank（实验 N 收紧）。"""
        monkeypatch.setattr(
            "app.services.rag.retrieval.effective_rerank_policy",
            lambda: "off",
        )
        from app.services.rag.retrieval import _apply_rerank_policy

        # 用 monkeypatch 拦截 degradation 检查：未退化
        monkeypatch.setattr(
            "app.services.rag.retrieval.assess_degradation",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.services.rag.retrieval.degradation_requires_rerank",
            lambda _: True,  # True = 需要 rerank = 未退化
        )
        # 不让 should_skip_rerank 跳过（若 complex 仍强制，这里会触发）
        monkeypatch.setattr(
            "app.services.rag.retrieval.should_skip_rerank",
            lambda *a, **kw: False,
        )

        # 打桩 rerank_chunks 返回原列表
        async def fake_rerank(*a, **kw):
            return mock_candidates

        monkeypatch.setattr(
            "app.services.rag.retrieval.rerank_chunks",
            fake_rerank,
        )

        result, did = await _apply_rerank_policy(
            "test query",
            mock_candidates,
            top_k=3,
            strategy=RetrievalStrategy.complex,
        )
        assert not did, "complex 策略应尊重 RERANK_POLICY=off（不再强制 always）"

    @pytest.mark.asyncio
    async def test_medium_off_respected(self, mock_candidates, monkeypatch):
        """strategy=medium, RERANK_POLICY=off 时不触发 rerank。"""
        monkeypatch.setattr(
            "app.services.rag.retrieval.effective_rerank_policy",
            lambda: "off",
        )
        from app.services.rag.retrieval import _apply_rerank_policy

        result, did = await _apply_rerank_policy(
            "test query",
            mock_candidates,
            top_k=3,
            strategy=RetrievalStrategy.medium,
        )
        assert not did, "medium 策略下应尊重 RERANK_POLICY=off"

    @pytest.mark.asyncio
    async def test_complex_respects_off_even_when_not_degraded(
        self, mock_candidates, monkeypatch
    ):
        """strategy=complex 且未退化时仍尊重 RERANK_POLICY=off（实验 N 收紧）。"""
        monkeypatch.setattr(
            "app.services.rag.retrieval.effective_rerank_policy",
            lambda: "off",
        )
        monkeypatch.setattr(
            "app.services.rag.retrieval.assess_degradation",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.services.rag.retrieval.degradation_requires_rerank",
            lambda _: True,  # True = 需要 rerank = 未退化（与测试名一致）
        )
        # 但不让 should_skip_rerank 跳过
        monkeypatch.setattr(
            "app.services.rag.retrieval.should_skip_rerank",
            lambda *a, **kw: False,
        )

        async def fake_rerank(*a, **kw):
            return mock_candidates

        monkeypatch.setattr(
            "app.services.rag.retrieval.rerank_chunks",
            fake_rerank,
        )
        from app.services.rag.retrieval import _apply_rerank_policy

        result, did = await _apply_rerank_policy(
            "test query",
            mock_candidates,
            top_k=3,
            strategy=RetrievalStrategy.complex,
        )
        # complex 不再强制 always → 尊重 base_policy=off
        assert not did, "complex 策略应尊重 RERANK_POLICY=off（不再强制 always）"

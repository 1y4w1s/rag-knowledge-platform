"""RAGAS Scorer 集成测试 — 验证 BenchmarkRunner 的 ragas 分支正确工作。

测试策略：
- Mock RagasRetrievalScorer / RagasGenerationScorer 的评分方法，避免真实 LLM API 调用
- 验证 runner.run_retrieval(scorer_type="ragas") 走 ragas 分支、结果含 ragas_* 字段
- 验证 runner.run_generation(scorer_type="ragas") 走 ragas 分支、不调用 judge
- 验证 checkpoint 恢复在 RAGAS 模式下的正确性
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from tests.benchmark.runner import BenchmarkRunner, CHECKPOINT_DIR
from tests.benchmark.schemas import (
    BenchmarkQuery,
    DatasetMeta,
    DatasetReport,
    RetrievalResult,
    GenerationResult,
)


# ── Mock 数据集（短路径，无需真实文件）──

class _MockDataset:
    """模拟 BenchmarkDataset，直接从内存返回 queries。"""

    def __init__(self, queries: list[BenchmarkQuery]):
        self.queries = queries
        self.meta = DatasetMeta(
            name="mock_ragas_test",
            display_name="Mock RAGAS Test",
            description="测试用 mock 数据集",
            homepage="",
            license="",
            total_questions=len(queries),
            supported_modes=("retrieval", "generation"),
        )

    async def load(self) -> list[BenchmarkQuery]:
        return self.queries

    @staticmethod
    def sample(queries: list[BenchmarkQuery], size: int) -> list[BenchmarkQuery]:
        return queries[:size]


# ── Fixtures ──

@pytest.fixture
def kb_id() -> str:
    return str(uuid4())


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


@pytest.fixture
def mock_retrieve_fn():
    """返回一个模拟检索函数：返回固定 chunk 列表。"""
    async def _retrieve(query: str, kb_id: str, top_k: int) -> list:
        return [
            _FakeChunk(chunk_id="chunk_a", content="睿阁是一个企业级知识库平台，支持文档管理和智能问答。", similarity=0.92),
            _FakeChunk(chunk_id="chunk_b", content="知识库支持多格式文档上传、切片、向量化存储。", similarity=0.85),
            _FakeChunk(chunk_id="chunk_c", content="系统内置混合检索（BM25 + 向量 + RRF）和引用溯源对话。", similarity=0.78),
        ][:top_k]
    return _retrieve


@pytest.fixture
def mock_generate_fn():
    """返回一个模拟生成函数：返回固定回答和引用。"""
    async def _generate(query: str, kb_id: str) -> tuple:
        answer = "睿阁是一个企业级知识库平台，支持文档管理和智能问答。"
        citations = [
            {"chunk_id": "chunk_a", "content": "睿阁是一个企业级知识库平台，支持文档管理和智能问答。"},
            {"chunk_id": "chunk_b", "content": "知识库支持多格式文档上传、切片、向量化存储。"},
        ]
        return answer, citations
    return _generate


@pytest.fixture
def simple_queries():
    """2 条简单测试 query。"""
    return [
        BenchmarkQuery(
            case_id="ragas_test_001",
            query="睿阁是什么？",
            answer="企业级知识库平台",
            expects=({"content_contains": "企业级知识库"},),
            domain="general",
            question_type="factoid",
        ),
        BenchmarkQuery(
            case_id="ragas_test_002",
            query="知识库支持什么功能？",
            answer="文档管理和智能问答",
            expects=({"content_contains": "文档管理"},),
            domain="general",
            question_type="factoid",
        ),
    ]


class _FakeChunk:
    """模拟检索返回的 chunk 对象，兼容 RetrievedChunk.from_raw。"""
    def __init__(self, chunk_id: str, content: str, similarity: float = 0.0):
        self.chunk_id = chunk_id
        self.content = content
        self.similarity = similarity
        self.section_title = ""
        self.heading_path = ""
        self.page_number = None


# ═══════════════════════════════════════════════════════════════
# 测试：RAGAS 检索模式
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ragas_retrieval_scorer_invoked(
    kb_id, user_id, mock_retrieve_fn, simple_queries,
):
    """验证 scorer_type="ragas" 时，RagasRetrievalScorer 被调用且结果含 ragas_* 字段。"""
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_retrieve_fn(mock_retrieve_fn)
    dataset = _MockDataset(simple_queries)

    # Mock 在 source 模块（tests.benchmark.scorers）而非 runner，因为后者是延迟导入
    with patch("tests.benchmark.scorers.RagasRetrievalScorer") as MockScorerCls:
        mock_scorer = MockScorerCls.return_value

        from tests.benchmark.scorers.base import RetrievalScore
        fake_score = RetrievalScore(
            hit_at_1=True, hit_at_3=True, hit_at_5=True,
            mrr=1.0, ndcg_at_k=1.0,
            precision_at_k=0.5, recall_at_k=0.5,
            map_contribution=0.5,
            match_details=[
                {"ragas_context_precision": 0.85},
                {"ragas_context_recall": 0.72},
            ],
        )
        mock_scorer.score_retrieval.return_value = fake_score

        report = await runner.run_retrieval(
            dataset, top_k=3,
            scorer_type="ragas",
        )

    # 验证 RagasRetrievalScorer 被创建并调用了 score_retrieval
    MockScorerCls.assert_called_once()
    assert mock_scorer.score_retrieval.call_count == len(simple_queries)

    # 验证结果结构和 RAGAS 字段
    assert isinstance(report, DatasetReport)
    assert report.dataset_name == "mock_ragas_test"
    assert report.total_queries == 2
    assert report.skipped == 0
    assert report.retrieval is not None

    # RAGAS 模式下 runner 将 precision_at_k/recall_at_k 设为 0.0（RAGAS 值存入 ragas_* 字段）
    assert report.retrieval.precision_at_k == 0.0
    assert report.retrieval.recall_at_k == 0.0


@pytest.mark.asyncio
async def test_ragas_retrieval_init_failure_falls_back(
    kb_id, user_id, mock_retrieve_fn, simple_queries, caplog,
):
    """验证 RagasRetrievalScorer 构造函数抛异常时回退到内容匹配。"""
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_retrieve_fn(mock_retrieve_fn)
    dataset = _MockDataset(simple_queries)

    # 当 _RRS() 被调用时抛出 RuntimeError → 被 runner 的 except Exception 捕获
    # 同时 patch _eval_retrieval 避免触发 golden_qa_loader 的 Python 3.10 语法
    from tests.benchmark.runner import RetrievalResult as _RR
    fake_result = _RR(case_id="", query="", top_k=3, latency_ms=0.0)

    with patch("tests.benchmark.scorers.RagasRetrievalScorer") as MockCls:
        MockCls.side_effect = RuntimeError("mock init failure")
        with patch.object(runner, "_eval_retrieval", return_value=fake_result):
            report = await runner.run_retrieval(
                dataset, top_k=3,
                scorer_type="ragas",
            )

    # 验证回退成功（无崩溃）
    assert report.retrieval is not None
    assert report.total_queries == 2


# ═══════════════════════════════════════════════════════════════
# 测试：RAGAS 生成模式
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ragas_generation_scorer_invoked(
    kb_id, user_id, mock_generate_fn, simple_queries,
):
    """验证 scorer_type="ragas" 时，RagasGenerationScorer 被调用且不调用 judge。"""
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_generate_fn(mock_generate_fn)
    dataset = _MockDataset(simple_queries)

    with patch("tests.benchmark.scorers.RagasGenerationScorer") as MockScorerCls:
        mock_scorer = MockScorerCls.return_value

        from tests.benchmark.scorers.base import GenerationScore
        fake_score = GenerationScore(
            faithfulness=0.88,
            correctness=0.75,
            match_details=[
                {"ragas_faithfulness": 0.88},
                {"ragas_answer_relevancy": 0.92},
                {"ragas_answer_correctness": 0.75},
            ],
        )
        mock_scorer.score_generation.return_value = fake_score

        # 同时 patch _get_judge 验证它不被调用
        with patch("tests.benchmark.runner._get_judge", new_callable=AsyncMock) as mock_get_judge:
            report = await runner.run_generation(
                dataset, judge=True, faithfulness=True,
                scorer_type="ragas",
            )

    # 验证 RagasGenerationScorer 被创建
    MockScorerCls.assert_called_once()
    assert mock_scorer.score_generation.call_count == len(simple_queries)

    # 验证 judge 不被调用（RAGAS 模式下 judge_instance = None）
    mock_get_judge.assert_not_called()

    # 验证报告结构
    assert isinstance(report, DatasetReport)
    assert report.generation is not None
    # 生成模式下 correctness 和 faithfulness 来自于 RAGAS
    assert report.generation.correctness > 0
    assert report.generation.faithfulness > 0


@pytest.mark.asyncio
async def test_ragas_generation_init_failure_falls_back(
    kb_id, user_id, mock_generate_fn, simple_queries, caplog,
):
    """验证 RagasGenerationScorer 初始化失败时回退到传统评测。"""
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_generate_fn(mock_generate_fn)
    dataset = _MockDataset(simple_queries)

    with patch("tests.benchmark.scorers.RagasGenerationScorer") as MockCls:
        MockCls.side_effect = RuntimeError("mock init failure")

        report = await runner.run_generation(
            dataset, judge=False, faithfulness=False,
            scorer_type="ragas",
        )

    # 验证回退：生成仍然完成但评分全 0
    assert report.generation is not None
    assert report.generation.correctness == 0.0


# ═══════════════════════════════════════════════════════════════
# 测试：RAGAS + 检查点恢复
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ragas_retrieval_checkpoint_resume(
    kb_id, user_id, mock_retrieve_fn,
):
    """验证 RAGAS 模式下检查点恢复正确：从已完成的条数继续，不重复评分。"""
    # 创建 5 条 query
    queries = [
        BenchmarkQuery(
            case_id=f"cp_test_{i:03d}",
            query=f"测试问题 {i}",
            answer=f"答案 {i}",
            expects=({"content_contains": f"内容 {i}"},),
        )
        for i in range(5)
    ]
    dataset = _MockDataset(queries)
    run_id = "ragas_cp_test_%s" % int(time.time())
    cp_path = CHECKPOINT_DIR / ("mock_ragas_test_retrieval_%s.json" % run_id)

    # 确保检查点目录存在
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 构造一个含 2 条结果的检查点（模拟中断）
        partial_results = [
            RetrievalResult(
                case_id=f"cp_test_{i:03d}", query=f"测试问题 {i}", top_k=3,
                hit_at_3=True, mrr=1.0,
                ragas_context_precision=0.9, ragas_context_recall=0.8,
                latency_ms=100.0,
            )
            for i in range(2)
        ]
        runner1 = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
        runner1._save_checkpoint(cp_path, partial_results, 2, 5)

        # 第二次运行：resume=True，应从第 2 条继续
        runner2 = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
        runner2.set_retrieve_fn(mock_retrieve_fn)

        with patch("tests.benchmark.scorers.RagasRetrievalScorer") as MockScorerCls2:
            mock_scorer2 = MockScorerCls2.return_value
            from tests.benchmark.scorers.base import RetrievalScore as RS2
            mock_scorer2.score_retrieval.return_value = RS2(
                hit_at_3=True, mrr=1.0,
                match_details=[{"ragas_context_precision": 0.85}, {"ragas_context_recall": 0.75}],
            )

            report = await runner2.run_retrieval(
                dataset, top_k=3,
                run_id=run_id, resume=True,
                scorer_type="ragas",
            )

        # 验证：总结果数 = 5（2 已恢复 + 3 新评）
        assert report.total_queries == 5
        assert report.skipped == 0

        # RagasRetrievalScorer.score_retrieval 只被调用了 3 次（新评 3 条），
        # 而不是 5 次（因为前 2 条从检查点恢复）
        assert mock_scorer2.score_retrieval.call_count == 3, (
            "恢复模式下应只调用 scorer 处理未完成的 query，而非重新评估已有的"
        )

    finally:
        if cp_path.exists():
            cp_path.unlink()


@pytest.mark.asyncio
async def test_ragas_generation_checkpoint_resume(
    kb_id, user_id, mock_generate_fn,
):
    """验证 RAGAS 生成模式下检查点恢复正确。"""
    queries = [
        BenchmarkQuery(
            case_id=f"gen_cp_{i:03d}",
            query=f"生成测试 {i}",
            answer=f"答案 {i}",
        )
        for i in range(4)
    ]
    dataset = _MockDataset(queries)
    run_id = "ragas_gen_cp_%s" % int(time.time())
    cp_path = CHECKPOINT_DIR / ("mock_ragas_test_generation_%s.json" % run_id)

    # 确保检查点目录存在
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 构造一个含 1 条结果的检查点
        partial_results = [
            GenerationResult(
                case_id="gen_cp_000", query="生成测试 0",
                answer="答案 0", citations=[],
                correctness_score=0.8, faithfulness_score=0.9,
                ragas_answer_relevancy=0.85,
                latency_ms=200.0,
            )
        ]
        runner0 = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
        runner0._save_checkpoint(cp_path, partial_results, 1, 4)

        runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
        runner.set_generate_fn(mock_generate_fn)

        with patch("tests.benchmark.scorers.RagasGenerationScorer") as MockScorerCls:
            mock_scorer = MockScorerCls.return_value
            from tests.benchmark.scorers.base import GenerationScore
            mock_scorer.score_generation.return_value = GenerationScore(
                faithfulness=0.95, correctness=0.85,
                match_details=[
                    {"ragas_faithfulness": 0.95},
                    {"ragas_answer_relevancy": 0.88},
                ],
            )

            report = await runner.run_generation(
                dataset, judge=False, faithfulness=False,
                run_id=run_id, resume=True,
                scorer_type="ragas",
            )

        # 验证
        assert report.total_queries == 4
        # score_generation 只被调用 3 次（恢复后还有 3 条未完成）
        assert mock_scorer.score_generation.call_count == 3

    finally:
        if cp_path.exists():
            cp_path.unlink()


# ═══════════════════════════════════════════════════════════════
# 测试：RAGAS scorer 初始化错误处理
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ragas_scorer_init_exception_does_not_crash(
    kb_id, user_id, mock_retrieve_fn, simple_queries, caplog,
):
    """验证 RagasRetrievalScorer 抛异常时不阻塞 runner。"""
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_retrieve_fn(mock_retrieve_fn)
    dataset = _MockDataset(simple_queries)

    # patch _eval_retrieval 避免触发 golden_qa_loader 的 Python 3.10 语法
    from tests.benchmark.runner import RetrievalResult as _RR
    fake_result = _RR(case_id="", query="", top_k=3, latency_ms=0.0)

    with patch("tests.benchmark.scorers.RagasRetrievalScorer") as MockCls:
        MockCls.side_effect = RuntimeError("mock init failure")
        with patch.object(runner, "_eval_retrieval", return_value=fake_result):
            report = await runner.run_retrieval(
                dataset, top_k=3,
                scorer_type="ragas",
            )

    # 不应崩溃，应回退到内容匹配模式
    assert report.retrieval is not None
    assert report.total_queries == 2


@pytest.mark.asyncio
async def test_ragas_retrieval_empty_chunks_handled(
    kb_id, user_id, simple_queries,
):
    """验证检索返回空列表时 RAGAS 模式不崩溃。"""
    async def _empty_retrieve(query: str, kb_id: str, top_k: int) -> list:
        return []

    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id)
    runner.set_retrieve_fn(_empty_retrieve)
    dataset = _MockDataset(simple_queries)

    with patch("tests.benchmark.scorers.RagasRetrievalScorer") as MockScorerCls:
        mock_scorer = MockScorerCls.return_value
        from tests.benchmark.scorers.base import RetrievalScore
        mock_scorer.score_retrieval.return_value = RetrievalScore()

        report = await runner.run_retrieval(
            dataset, top_k=3,
            scorer_type="ragas",
        )

    assert report is not None
    # 空 chunks 导致 RetrievalResult 不会追加，但仍然应该完成
    assert report.total_queries == 2

"""G1 评测代码可信化回归测试（N13 四项缺陷 + 环境修复）。

覆盖：
1. ragas_scorer — score_generation 有 ground_truth 时计算 answer_correctness（原恒 0）
2. runner — 拒答题不再跳过，rejection_accuracy 正常计算（原恒 0）
3. scorers/base — recall 分母为期望条件数（原取字符串长度系统性压低）
4. golden_qa loader — 读取 answer / min_match（原丢弃，judge 分支永不执行）
5. ragas_scorer import — 0.2.x 环境不再强制导入 langchain-google-vertexai
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from tests.benchmark.runner import BenchmarkRunner, _judge_rejection
from tests.benchmark.schemas import BenchmarkQuery, DatasetMeta
from tests.benchmark.scorers.base import Expect, RetrievedChunk
from tests.benchmark.scorers.content_match import ContentMatchScorer


# ═══════════════════════════════════════════════════════════════
# 1. ragas_scorer — answer_correctness 不再恒 0
# ═══════════════════════════════════════════════════════════════


class _FakeMetric:
    """代替 ragas metric 对象（仅验证 evaluate 收到哪些 metric）。"""

    def __init__(self, name: str) -> None:
        self.name = name


def _make_scorer():
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer
    return RagasGenerationScorer()


def test_single_evaluate_includes_correctness_with_ground_truth():
    """有 ground_truth 且 faithfulness_only=False 时，evaluate 收到 3 个 metric。"""
    scorer = _make_scorer()
    metrics = (_FakeMetric("faithfulness"), _FakeMetric("relevancy"), _FakeMetric("correctness"))
    captured: dict = {}

    def _fake_from_dict(dd):
        captured.update(dd)
        return object()

    with patch.object(scorer, "_get_metrics", return_value=metrics), \
         patch("ragas.evaluate", create=True) as mock_eval, \
         patch("datasets.Dataset.from_dict", side_effect=_fake_from_dict):
        mock_eval.return_value = {
            "faithfulness": [0.9], "answer_relevancy": [0.8], "answer_correctness": [0.7],
        }
        scores = scorer._single_evaluate(
            "q", "answer", ["ctx"], llm=None,
            ground_truth="gt", faithfulness_only=False,
        )

    assert scores["answer_correctness"] == 0.7
    assert scores["answer_relevancy"] == 0.8
    assert "ground_truth" in captured
    called_metrics = mock_eval.call_args.kwargs["metrics"]
    assert [m.name for m in called_metrics] == ["faithfulness", "relevancy", "correctness"]


def test_score_generation_passes_faithfulness_only_false_with_ground_truth():
    """score_generation 有 ground_truth（content_contains/answer）时传 faithfulness_only=False。"""
    scorer = _make_scorer()
    expect = Expect(content_contains="年假 10 天", answer="")
    chunks = [RetrievedChunk(chunk_id="c1", content="正式员工每年有10天年假。")]

    with patch.object(scorer, "_single_evaluate", return_value={
        "faithfulness": 0.9, "answer_relevancy": 0.8, "answer_correctness": 0.7,
    }) as mock_se, \
         patch("tests.benchmark.scorers.ragas_scorer._get_llm", return_value=None):
        g = scorer.score_generation("年假多少天", "正式员工每年有10天年假。", expect, chunks)

    assert g.correctness == 0.7
    assert mock_se.call_args.kwargs["faithfulness_only"] is False


def test_score_generation_faithfulness_only_without_ground_truth():
    """无 ground_truth 时仍只算 faithfulness（不强制要求 answer_correctness）。"""
    scorer = _make_scorer()
    expect = Expect(content_contains="", answer="")  # 无 ground truth
    chunks = [RetrievedChunk(chunk_id="c1", content="一些内容")]

    with patch.object(scorer, "_single_evaluate", return_value={
        "faithfulness": 0.9,
    }) as mock_se, \
         patch("tests.benchmark.scorers.ragas_scorer._get_llm", return_value=None):
        g = scorer.score_generation("q", "answer text", expect, chunks)

    assert mock_se.call_args.kwargs["faithfulness_only"] is True
    assert g.correctness == 0.0  # 无 ground truth 不硬算 correctness


# ═══════════════════════════════════════════════════════════════
# 2. runner — 拒答题不再跳过
# ═══════════════════════════════════════════════════════════════


class _MockDataset:
    def __init__(self, queries: list[BenchmarkQuery]):
        self.queries = queries
        self.meta = DatasetMeta(
            name="mock_rej_test",
            display_name="Mock Rejection Test",
            description="",
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


def _rejection_queries():
    return [
        BenchmarkQuery(
            case_id="rej_001", query="知识库没有这个内容的问题",
            expect_rejection=True,
        ),
        BenchmarkQuery(
            case_id="rej_002", query="另一个无依据问题",
            expect_rejection=True,
        ),
    ]


@pytest.mark.asyncio
async def test_rejection_queries_not_skipped_and_counted():
    """拒答题也进入评测；正确拒答 → rejection_accuracy=1.0。"""
    runner = BenchmarkRunner(kb_id="kb", user_id="user")

    async def _gen(query: str, kb_id: str) -> tuple:
        # 模拟系统正确拒答：返回固定拒答话术、无引用
        return "知识库中未找到相关内容，无法根据文档回答您的问题。", []

    runner.set_generate_fn(_gen)
    report = await runner.run_generation(_MockDataset(_rejection_queries()), judge=False)

    assert report.generation is not None
    assert report.generation.total == 2  # 拒答题不再被跳过
    assert report.generation.rejection_accuracy == 1.0


@pytest.mark.asyncio
async def test_rejection_wrong_when_fabricating():
    """拒答题编造答案（带引用）→ rejection_accuracy=0.0。"""
    runner = BenchmarkRunner(kb_id="kb", user_id="user")

    async def _gen(query: str, kb_id: str) -> tuple:
        # 模拟错误行为：拒答题却编造答案并给出引用
        return "答案是 10 天。", [{"chunk_id": "c1", "content": "不相关内容"}]

    runner.set_generate_fn(_gen)
    report = await runner.run_generation(_MockDataset(_rejection_queries()), judge=False)

    assert report.generation is not None
    assert report.generation.total == 2
    assert report.generation.rejection_accuracy == 0.0


def test_judge_rejection_helper():
    """_judge_rejection 判据：无引用+拒答话术/空答案=正确；带引用=错误。"""
    assert _judge_rejection("知识库中未找到相关内容，无法根据文档回答您的问题。", [])[0] is True
    assert _judge_rejection("", [])[0] is True
    assert _judge_rejection(
        "No relevant content was found in the knowledge base to answer your question.", []
    )[0] is True
    assert _judge_rejection("", [{"chunk_id": "c1"}])[0] is False  # 有引用 → 未拒答
    assert _judge_rejection("答案是 10 天。", [])[0] is False  # 有内容 → 编造


# ═══════════════════════════════════════════════════════════════
# 3. scorers/base — recall 分母
# ═══════════════════════════════════════════════════════════════


def test_recall_denominator_is_expect_count_not_string_length():
    """content_contains 命中 1 个期望 → recall=1.0（修复前 len("年假 10 天")=5 → 0.2）。"""
    scorer = ContentMatchScorer()
    chunks = [RetrievedChunk(chunk_id="c1", content="正式员工每年可休年假 10 天，需提前两周申请。")]
    expect = Expect(content_contains="年假 10 天")

    score = scorer.score_retrieval("年假多少天", chunks, expect, top_k=3)

    assert score.hit_at_1 is True
    assert score.recall_at_k == 1.0
    assert score.precision_at_k == pytest.approx(1 / 3)


def test_recall_denominator_with_answer():
    """answer 期望场景分母同样为 1（非字符串长度）。"""
    from tests.benchmark.scorers.answer_match import AnswerMatchScorer
    scorer = AnswerMatchScorer()
    chunks = [RetrievedChunk(chunk_id="c1", content="正式员工每年有10天年假，需提前两周申请。")]
    expect = Expect(content_contains="", answer="正式员工每年有10天年假")

    score = scorer.score_retrieval("年假多少天", chunks, expect, top_k=3)

    assert score.recall_at_k == 1.0


# ═══════════════════════════════════════════════════════════════
# 4. golden_qa loader — answer / min_match
# ═══════════════════════════════════════════════════════════════


def test_golden_qa_loader_reads_answer_and_min_match():
    from tests.benchmark.loaders.golden_qa import GoldenQADataset

    q = GoldenQADataset._parse_case({
        "case_id": "GQ-X",
        "query": "年假多少天？",
        "answer": "正式员工每年有10天年假。",
        "min_match": 2,
        "expects": [{"content_contains": "年假"}, {"content_contains": "10天"}],
    })

    assert q.answer == "正式员工每年有10天年假。"
    assert q.metadata["min_match"] == 2
    assert len(q.expects) == 2


def test_golden_qa_loader_defaults():
    """无 answer/min_match 字段时优雅缺省。"""
    from tests.benchmark.loaders.golden_qa import GoldenQADataset

    q = GoldenQADataset._parse_case({"case_id": "GQ-Y", "query": "q"})
    assert q.answer is None
    assert q.metadata["min_match"] == 1


# ═══════════════════════════════════════════════════════════════
# 5. ragas_scorer import — 0.2.x 环境兼容
# ═══════════════════════════════════════════════════════════════


def test_ragas_scorer_imports_without_forcing_google_vertexai():
    """在 langchain-community 0.2.x 环境，ragas_scorer 应优先使用自带 vertexai 模块，
    不强制导入 langchain-google-vertexai（其新版要求 langchain-core>=1.3）。"""
    mod = importlib.import_module("tests.benchmark.scorers.ragas_scorer")
    assert hasattr(mod, "RagasGenerationScorer")
    assert hasattr(mod, "RagasRetrievalScorer")


def test_sys_modules_vertexai_not_overwritten_when_real_exists():
    """真实 langchain_community.chat_models.vertexai 存在时，不应被 stub 覆盖。"""
    import langchain_community.chat_models.vertexai as real_mod
    assert hasattr(real_mod, "ChatVertexAI")

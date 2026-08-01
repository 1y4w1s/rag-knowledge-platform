"""RAGAS 评分器封装。

提供 RetrievalScorer / GenerationScorer 两种实现，遵循 EvalScorer Protocol。
"""
from __future__ import annotations

import logging
import os
import warnings
from typing import Any

os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

# HACK: ragas 0.3.x 从 langchain_community.chat_models.vertexai 导入 ChatVertexAI。
# langchain-community 0.2.x 自带该模块（直接可用）；0.4+ 已移除，
# 需要桥接到 langchain_google_vertexai。优先尝试真实模块，缺失才桥接，
# 避免在 0.2.x 环境强制导入 langchain-google-vertexai（其新版要求 langchain-core>=1.3）。
import sys as _sys
from types import ModuleType as _ModuleType

try:  # noqa: C901
    from langchain_community.chat_models.vertexai import ChatVertexAI  # noqa: F401
except ImportError:
    try:
        from langchain_google_vertexai import ChatVertexAI as _ChatVertexAI
    except ImportError:
        _ChatVertexAI = None  # type: ignore[assignment]
    _vertex_mod = _ModuleType("langchain_community.chat_models.vertexai")
    _vertex_mod.ChatVertexAI = _ChatVertexAI
    _sys.modules["langchain_community.chat_models.vertexai"] = _vertex_mod

from .base import (
    EvalScorer,
    RetrievalScore,
    GenerationScore,
    Expect,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)

# ── 抑制 RAGAS 旧的 import deprecation warnings ──
warnings.filterwarnings("ignore", category=DeprecationWarning, module="ragas")


# ═══════════════════════════════════════════════════════════════
# LLM 工具（延迟初始化）
# ═══════════════════════════════════════════════════════════════

_llm_instance = None


def _get_llm():
    """获取 RAGAS judge LLM（DeepSeek）。

    优先从 os.environ 读取 DEEPSEEK_API_KEY，若不存在则回退到
    pydantic Settings（兼容 .env 仅被 pydantic-settings 加载的场景）。
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        try:
            from app.core.config import settings
            deepseek_key = settings.deepseek_api_key
        except Exception:
            pass

    if not deepseek_key:
        raise RuntimeError(
            "RAGAS scorer 需要 DEEPSEEK_API_KEY 环境变量"
        )

    deepseek_base = os.environ.get(
        "DEEPSEEK_BASE_URL",
        "https://api.deepseek.com",
    )

    from langchain_openai import ChatOpenAI

    _llm_instance = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=deepseek_key,
        openai_api_base=deepseek_base,
        temperature=0.0,
    )
    logger.info("RAGAS LLM 初始化完成 (model=%s)", "deepseek-chat")
    return _llm_instance


# ═══════════════════════════════════════════════════════════════
# RAGAS 评分器
# ═══════════════════════════════════════════════════════════════


class RagasRetrievalScorer:
    """RAGAS 检索评分器：context_precision + context_recall。

    需要 expect.answer（作为 ground truth / reference）。
    """

    _precision = None
    _recall = None

    @classmethod
    def _get_metrics(cls):
        if cls._precision is not None:
            return cls._precision, cls._recall
        from ragas.metrics import context_precision, context_recall
        cls._precision = context_precision
        cls._recall = context_recall
        return cls._precision, cls._recall

    def _single_evaluate(self, query, chunks_text, ground_truth, llm):
        from datasets import Dataset as HFDataset
        from ragas import evaluate as ragas_evaluate
        precision, recall = self._get_metrics()
        data = HFDataset.from_dict({
            "question": [query],
            "contexts": [chunks_text],
            "ground_truth": [ground_truth],
        })
        result = ragas_evaluate(data, metrics=[precision, recall], llm=llm)
        return {
            "context_precision": float(result["context_precision"][0]),
            "context_recall": float(result["context_recall"][0]),
        }

    def score_retrieval(self, query, chunks, expect, top_k=3):
        ground_truth = expect.answer or expect.content_contains
        if not ground_truth:
            logger.warning("RagasRetrievalScorer: 缺少 ground truth，返回默认分")
            return RetrievalScore()
        chunks_text = [c.content for c in chunks[:top_k] if c.content]
        if not chunks_text:
            return RetrievalScore()
        try:
            llm = _get_llm()
            scores = self._single_evaluate(query, chunks_text, ground_truth, llm)
        except Exception as e:
            logger.warning("RAGAS retrieval evaluate 失败: %s", e)
            return RetrievalScore()
        return RetrievalScore(
            precision_at_k=scores.get("context_precision", 0.0),
            recall_at_k=scores.get("context_recall", 0.0),
            match_details=[
                {"ragas_context_precision": scores.get("context_precision", 0.0)},
                {"ragas_context_recall": scores.get("context_recall", 0.0)},
            ],
        )

    def score_generation(self, query, answer, expect, chunks):
        return GenerationScore()


class RagasGenerationScorer:
    """RAGAS 生成评分器：faithfulness + answer_relevancy + answer_correctness。"""

    _faithfulness = None
    _relevancy = None
    _correctness = None

    @classmethod
    def _get_metrics(cls):
        if cls._faithfulness is not None:
            return cls._faithfulness, cls._relevancy, cls._correctness
        from ragas.metrics import faithfulness, answer_relevancy, answer_correctness
        cls._faithfulness = faithfulness
        cls._relevancy = answer_relevancy
        cls._correctness = answer_correctness
        return cls._faithfulness, cls._relevancy, cls._correctness

    def _single_evaluate(self, query, answer, chunks_text, llm, ground_truth=None, faithfulness_only=True):
        from datasets import Dataset as HFDataset
        from ragas import evaluate as ragas_evaluate
        faithfulness, relevancy, correctness = self._get_metrics()
        data_dict = {"question": [query], "answer": [answer], "contexts": [chunks_text]}
        metrics = [faithfulness]
        if not faithfulness_only:
            metrics.append(relevancy)
            if ground_truth:
                data_dict["ground_truth"] = [ground_truth]
                metrics.append(correctness)
        data = HFDataset.from_dict(data_dict)
        result = ragas_evaluate(data, metrics=metrics, llm=llm)
        scores = {"faithfulness": float(result["faithfulness"][0])}
        if not faithfulness_only:
            scores["answer_relevancy"] = float(result["answer_relevancy"][0])
            if ground_truth:
                scores["answer_correctness"] = float(result["answer_correctness"][0])
        return scores

    def score_retrieval(self, query, chunks, expect, top_k=3):
        return RetrievalScore()

    def score_generation(self, query, answer, expect, chunks):
        if not answer.strip():
            return GenerationScore()
        chunks_text = [c.content for c in chunks if c.content]
        if not chunks_text:
            return GenerationScore()
        ground_truth = expect.answer or expect.content_contains or None
        try:
            llm = _get_llm()
            # N13-1 修复：默认 faithfulness_only=True 导致 answer_correctness 恒 0。
            # 有 ground_truth 时计算 relevancy + correctness，无 ground_truth 时只算 faithfulness。
            scores = self._single_evaluate(
                query, answer, chunks_text, llm, ground_truth,
                faithfulness_only=not ground_truth,
            )
        except Exception as e:
            logger.warning("RAGAS generation evaluate 失败: %s", e)
            return GenerationScore(error=str(e))
        return GenerationScore(
            faithfulness=scores.get("faithfulness", 0.0),
            correctness=scores.get("answer_correctness", 0.0),
            match_details=[
                {"ragas_faithfulness": scores.get("faithfulness", 0.0)},
                {"ragas_answer_relevancy": scores.get("answer_relevancy", 0.0)},
                {"ragas_answer_correctness": scores.get("answer_correctness", 0.0)},
            ],
        )

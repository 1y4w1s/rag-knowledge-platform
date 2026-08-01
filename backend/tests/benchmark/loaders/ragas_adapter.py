"""A2 RAGAS 数据集适配器：将自建评测集映射为 RAGAS Dataset 格式。

将 Golden QA / Enterprise QA / Advanced QA 的 JSON fixture 实时转换为
RAGAS 所需的 Dataset 格式（question, answer, contexts, ground_truth），
其中 answer 和 contexts 通过实际检索+生成产生，非静态映射。

用法：
    from tests.benchmark.loaders.ragas_adapter import RagasAdapter

    adapter = RagasAdapter(db, kb_id)
    dataset = await adapter.to_ragas_dataset("golden_qa")
    # → {"question": [...], "answer": [...], "contexts": [[...]], "ground_truth": [...]}

依赖：
    - RetrievalAdapter（run retrieval 获取 contexts）
    - GenerationAdapter（run generation 获取 answer）
    - fixture JSON（tests/fixtures/golden_qa.json 等）

注意：
    - ground_truth 取自 expect.content_contains（弱真值，片段而非完整答案）
    - 支持 mock 模式：skip_llm=True 跳过真实 LLM 调用（CI 离线使用）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from tests.benchmark.adapters.generation import GenerationAdapter
from tests.benchmark.adapters.retrieval import RetrievalAdapter

logger = logging.getLogger(__name__)

# fixture 目录（backend/tests/fixtures/）
FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"

# 注册的数据集：名称 → 文件名
DATASETS: dict[str, str] = {
    "golden_qa": "golden_qa.json",
    "enterprise_qa": "enterprise_qa.json",
    "advanced_qa": "advanced_qa.json",
}

# RAGAS Dataset 类型别名
RagasDataset = dict[str, list]


def _get_ground_truth(case: dict) -> str:
    """从 case 中提取 ground_truth 文本。

    提取优先级：
    1. expect.content_contains（单数 expect，dict）
    2. expects[].content_contains（复数 expects，list of dicts，拼接）
    3. expected_chunk（agent golden 风格兜底）

    Returns:
        真值文本字符串；若均不存在返回空字符串。
    """
    # 优先级 1: 单数 expect（dict）
    expect = case.get("expect")
    if isinstance(expect, dict):
        gt = expect.get("content_contains", "")
        if gt:
            return gt

    # 优先级 2: 复数 expects（list of dicts，拼接所有 content_contains）
    expects = case.get("expects")
    if isinstance(expects, list):
        parts = [
            e.get("content_contains", "")
            for e in expects
            if isinstance(e, dict) and e.get("content_contains")
        ]
        if parts:
            return " | ".join(parts)

    # 优先级 3: expected_chunk（agent golden 风格）
    gt = case.get("expected_chunk", "")
    return gt or ""


class RagasAdapter:
    """将自建评测集映射为 RAGAS Dataset 格式。

    对每道题执行真实检索+生成以获取 contexts 和 answer。
    """

    def __init__(
        self,
        db,
        kb_id: UUID,
        skip_llm: bool = False,
    ) -> None:
        """
        Args:
            db: SQLAlchemy AsyncSession 实例。
            kb_id: 知识库 ID（fixture 文档所在的 KB）。
            skip_llm: 跳过真实 LLM 调用（mock 模式），CI 离线使用。
        """
        self._retrieval = RetrievalAdapter(db)
        self._generation = GenerationAdapter(db, kb_id)
        self._db = db
        self._kb_id = kb_id
        self._skip_llm = skip_llm

    # ── 公开接口 ──

    async def to_ragas_dataset(
        self,
        dataset_name: str,
        top_k: int = 3,
        sample: int | None = None,
    ) -> RagasDataset:
        """加载并转换指定数据集为 RAGAS Dataset 格式。

        Args:
            dataset_name: 数据集名称（"golden_qa" / "enterprise_qa" / "advanced_qa"）。
            top_k: 检索返回的 chunks 数。
            sample: 可选，仅处理前 N 题（用于快速验证）。

        Returns:
            RAGAS Dataset dict：
                question: list[str]        — 查询文本
                answer: list[str]          — 生成回答（skip_llm=True 时为空字符串）
                contexts: list[list[str]]  — 检索到的 chunk 文本列表
                ground_truth: list[str]    — 期望答案（弱真值）
        """
        cases = self._load_fixture(dataset_name)
        if sample and sample > 0:
            cases = cases[:sample]

        logger.info(
            "RagasAdapter: 转换 %s (%d 题, top_k=%d, skip_llm=%s)",
            dataset_name, len(cases), top_k, self._skip_llm,
        )

        questions: list[str] = []
        answers: list[str] = []
        contexts: list[list[str]] = []
        ground_truths: list[str] = []

        for idx, case in enumerate(cases):
            query = self._get_query(case)
            gt = _get_ground_truth(case)

            questions.append(query)
            ground_truths.append(gt)

            if self._skip_llm:
                # mock 模式：不调 LLM，留空
                answers.append("")
                contexts.append([])
            else:
                # 真实模式：检索 + 生成
                try:
                    chunks = await self._retrieval.retrieve(query, self._kb_id, top_k=top_k)
                except Exception as e:
                    logger.warning(
                        "RagasAdapter: 检索失败 idx=%d case=%s: %s", idx, case.get("case_id", "?"), e
                    )
                    chunks = []

                ctx_texts = [c.content for c in chunks if c.content]
                contexts.append(ctx_texts)

                try:
                    answer, _ = await self._generation.generate(query)
                except Exception as e:
                    logger.warning(
                        "RagasAdapter: 生成失败 idx=%d case=%s: %s", idx, case.get("case_id", "?"), e
                    )
                    answer = ""

                answers.append(answer)

            if (idx + 1) % 20 == 0:
                logger.info("RagasAdapter: 已处理 %d/%d 题", idx + 1, len(cases))

        return {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }

    async def to_ragas_retrieval_dataset(
        self,
        dataset_name: str,
        top_k: int = 3,
        sample: int | None = None,
    ) -> RagasDataset:
        """仅检索模式：只产生 contexts + ground_truth，不跑生成。

        适用于纯检索评测（context_precision / context_recall），
        比 to_ragas_dataset() 快一倍（省去生成步骤）。
        """
        cases = self._load_fixture(dataset_name)
        if sample and sample > 0:
            cases = cases[:sample]

        logger.info(
            "RagasAdapter: 检索模式 %s (%d 题, top_k=%d)",
            dataset_name, len(cases), top_k,
        )

        questions: list[str] = []
        contexts: list[list[str]] = []
        ground_truths: list[str] = []

        for idx, case in enumerate(cases):
            query = self._get_query(case)
            gt = _get_ground_truth(case)

            questions.append(query)
            ground_truths.append(gt)

            try:
                chunks = await self._retrieval.retrieve(query, self._kb_id, top_k=top_k)
            except Exception as e:
                logger.warning(
                    "RagasAdapter: 检索失败 idx=%d case=%s: %s", idx, case.get("case_id", "?"), e
                )
                chunks = []

            ctx_texts = [c.content for c in chunks if c.content]
            contexts.append(ctx_texts)

        return {
            "question": questions,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }

    # ── 内部方法 ──

    def _load_fixture(self, dataset_name: str) -> list[dict]:
        """从 fixtures/ 加载 JSON 数据集的 cases 列表。

        Args:
            dataset_name: 数据集名称。

        Returns:
            cases 列表（每个元素是一个题目的 dict）。

        Raises:
            ValueError: 数据集名称未注册或文件不存在。
        """
        filename = DATASETS.get(dataset_name)
        if not filename:
            raise ValueError(
                f"未知数据集 '{dataset_name}'。可用: {list(DATASETS.keys())}"
            )

        fpath = FIXTURE_DIR / filename
        if not fpath.exists():
            raise FileNotFoundError(
                f"fixture 文件不存在: {fpath}"
            )

        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        cases = data.get("cases", [])
        logger.info("RagasAdapter: 加载 %s (%d 题)", dataset_name, len(cases))
        return cases

    @staticmethod
    def _get_query(case: dict) -> str:
        """从 case 中提取查询文本。"""
        return case.get("query", case.get("question", ""))

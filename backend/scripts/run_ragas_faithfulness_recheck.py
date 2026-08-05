"""方案 B M3 决策：RAGAS faithfulness 真向量复测（faithfulness-only wrapper）。

背景：
- ragas 0.3.9 的 answer_relevancy / answer_correctness 依赖 OpenAI embeddings，
  本环境不可用；多指标 evaluate 单题约 169s（embedding 404 重试 + 额外 LLM 调用），
  89 题全量需 4h+，不可行。
- 本决策口径只看 faithfulness（与实验 L 84.11% 基线同 judge：
  deepseek-chat + temperature=0），faithfulness-only 单题约 23s。

本脚本不改动现有文件：monkey-patch `RagasGenerationScorer.score_generation`
强制 faithfulness_only=True（跳过 relevancy/correctness），其余流程、落盘
（_detail.json / baseline-ragas.json）与 `run_ragas_baseline` 完全一致。

用法（cd backend）：
    python scripts/run_ragas_faithfulness_recheck.py --kb-id <uuid>
    python scripts/run_ragas_faithfulness_recheck.py --kb-id <uuid> --sample 5
    # 分批（断点续跑）：--offset 40 --limit 40 表示第 41~80 题
    python scripts/run_ragas_faithfulness_recheck.py --kb-id <uuid> --offset 40 --limit 40
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("run_ragas_faithfulness_recheck")

# 确保能从 backend 根目录导入 app / tests
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _prepare_env() -> None:
    """从 .env 读取 DeepSeek key 并补齐 RAGAS embeddings 初始化所需变量。

    faithfulness 本身不需要 embeddings，但 ragas.evaluate 初始化默认
    embedding_factory 时会检查 OPENAI_API_KEY（缺失则整体抛异常）。这里补上
    key 并指向 DeepSeek，使 embedding 初始化成功但调用快速 404 → 单指标 NaN
    （不会进入此路径，因为只跑 faithfulness，仅为防御性配置）。
    """
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    os.environ.setdefault("OPENAI_API_KEY", deepseek_key)
    os.environ.setdefault("OPENAI_API_BASE", "https://api.deepseek.com")
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com")


def _patch_scorer() -> None:
    """将 RagasGenerationScorer.score_generation 替换为 faithfulness-only 版本。"""
    from tests.benchmark.scorers.base import GenerationScore
    from tests.benchmark.scorers.ragas_scorer import _get_llm, RagasGenerationScorer

    def score_generation_faithfulness_only(
        self,
        query: str,
        answer: str,
        expect,
        chunks,
    ) -> GenerationScore:
        """faithfulness-only：与 RAGAS 基线同 judge 口径，跳过 relevancy/correctness。"""
        if not answer.strip():
            return GenerationScore()
        chunks_text = [c.content for c in chunks if c.content]
        if not chunks_text:
            return GenerationScore()
        try:
            llm = _get_llm()
            scores = self._single_evaluate(
                query, answer, chunks_text, llm,
                ground_truth=None, faithfulness_only=True,
            )
        except Exception as e:  # noqa: BLE001 - 与上游 score_generation 行为一致
            logger.warning("RAGAS generation evaluate 失败: %s", e)
            return GenerationScore(error=str(e))
        return GenerationScore(
            faithfulness=scores.get("faithfulness", 0.0),
            correctness=0.0,
            match_details=[
                {"ragas_faithfulness": scores.get("faithfulness", 0.0)},
            ],
        )

    RagasGenerationScorer.score_generation = score_generation_faithfulness_only
    logger.info("已启用 faithfulness-only 评分（跳过 relevancy/correctness）")


def _patch_loader(offset: int, limit: int) -> None:
    """按 (offset, limit) 切片 Golden QA 题目，供分批跑（断点续跑）。"""
    if offset == 0 and limit is None:
        return
    from tests.benchmark.loaders.golden_qa import GoldenQADataset

    orig_load = GoldenQADataset.load

    async def load_filtered(self):
        queries = await orig_load(self)
        end = None if limit is None else offset + limit
        return queries[offset:end]

    GoldenQADataset.load = load_filtered
    logger.info("题目切片: offset=%s limit=%s", offset, limit)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args, rest = parser.parse_known_args()

    _prepare_env()
    _patch_scorer()
    _patch_loader(args.offset, args.limit)

    # 复用 run_ragas_baseline 的 argparse / 流程 / 落盘
    from tests.benchmark import run_ragas_baseline

    import asyncio

    # 透传剩余参数（--kb-id / --sample / --output / --reuse），剔除已消费的切片参数
    sys.argv = [sys.argv[0], *rest]
    asyncio.run(run_ragas_baseline.main())


if __name__ == "__main__":
    main()

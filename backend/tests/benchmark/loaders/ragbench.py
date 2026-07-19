"""RAGBench 数据集加载器（rungalileo/ragbench）。

数据来源：https://huggingface.co/datasets/rungalileo/ragbench
格式：HuggingFace Datasets，10 万样本 / 5 行业
许可：需确认（HuggingFace 标准）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tests.benchmark.base import BenchmarkDataset
from tests.benchmark.loaders import register
from tests.benchmark.schemas import (
    BenchmarkQuery,
    DatasetMeta,
)

logger = logging.getLogger(__name__)

RAGBENCH_HOMEPAGE = "https://huggingface.co/datasets/rungalileo/ragbench"
RAGBENCH_LICENSE = "HuggingFace Dataset License (待确认)"
RAGBENCH_SUBSETS = [
    "hotpotqa", "msmarco", "hagrid", "expertqa",
    "finance", "legal", "medical",
    "tech", "creative_writing",
]


@register("ragbench")
class RAGBenchDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="ragbench",
            display_name="RAGBench (跨行业评测)",
            description="大规模跨行业 RAG 评测集，10 万样本 / 5 行业",
            homepage=RAGBENCH_HOMEPAGE,
            license=RAGBENCH_LICENSE,
            total_questions=100_000,
            supported_modes=("retrieval", "generation"),
            domains=("hotpotqa", "msmarco", "hagrid", "expertqa",
                     "finance", "legal", "medical"),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "ragbench"
        local_dir.mkdir(parents=True, exist_ok=True)

        # TODO(R8-REQ): 使用 datasets 库自动下载
        # from datasets import load_dataset
        # ds = load_dataset("rungalileo/ragbench", split="train")

        existing = list(local_dir.glob("*.json")) + list(local_dir.glob("*.jsonl"))
        if not existing:
            logger.info(
                "RAGBench 未找到本地缓存。如需使用，请运行: "
                "pip install datasets && "
                "from datasets import load_dataset; "
                "ds = load_dataset('rungalileo/ragbench', split='train'); "
                "ds.to_json('data/benchmark/ragbench/ragbench.jsonl')"
            )
        else:
            logger.info("RAGBench 本地缓存: %d 个文件", len(existing))
        return local_dir

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        local_dir = await self.download_if_needed()
        queries: list[BenchmarkQuery] = []

        for fpath in sorted(local_dir.glob("*.jsonl")):
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    raw = json.loads(line)
                    queries.append(self._parse_row(raw))

        # 也支持 .json 文件
        for fpath in sorted(local_dir.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("data", [])
            for raw in items:
                queries.append(self._parse_row(raw))

        self._queries = queries
        logger.info("RAGBench: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        # RAGBench 字段映射（基于 huggingface 数据集结构）
        return BenchmarkQuery(
            case_id=str(raw.get("id", raw.get("question_id", ""))),
            query=raw.get("question", raw.get("query", "")),
            answer=raw.get("answer", raw.get("ground_truth")),
            domain=raw.get("domain", raw.get("subset", raw.get("dataset"))),
            metadata={
                "context": raw.get("context"),
                "expected_chunks": raw.get("expected_chunks", raw.get("supporting_docs")),
            },
        )

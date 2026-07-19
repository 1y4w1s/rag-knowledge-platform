"""MIRAGE 数据集加载器（NCBI 医疗 RAG 评测）。

数据来源：https://huggingface.co/datasets/ncbi/MIRAGE
格式：HuggingFace Datasets，7,560 条医疗 QA
许可：NIH 许可
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

MIRAGE_HOMEPAGE = "https://huggingface.co/datasets/ncbi/MIRAGE"
MIRAGE_LICENSE = "NIH / Research"
MIRAGE_FILENAME = "mirage.jsonl"


@register("mirage")
class MIRAGEDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="mirage",
            display_name="MIRAGE (医疗 RAG 评测)",
            description="NCBI 医疗领域 RAG 评测集，7,560 条临床 QA",
            homepage=MIRAGE_HOMEPAGE,
            license=MIRAGE_LICENSE,
            total_questions=7560,
            supported_modes=("retrieval", "generation"),
            domains=("medical", "clinical"),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "mirage"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / MIRAGE_FILENAME

        if local_path.exists():
            return local_path

        logger.info(
            "MIRAGE 未找到本地缓存。如需使用，请运行: "
            "from datasets import load_dataset; "
            "ds = load_dataset('ncbi/MIRAGE', split='train'); "
            "ds.to_json('data/benchmark/mirage/mirage.jsonl')"
        )
        return local_dir

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        local_dir = await self.download_if_needed()
        local_path = local_dir / MIRAGE_FILENAME
        queries: list[BenchmarkQuery] = []

        if local_path.exists():
            with open(local_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    raw = json.loads(line)
                    queries.append(self._parse_row(raw))

        self._queries = queries
        logger.info("MIRAGE: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        return BenchmarkQuery(
            case_id=str(raw.get("id", raw.get("question_id", ""))),
            query=raw.get("question", raw.get("query", "")),
            answer=raw.get("answer", raw.get("gold_answer")),
            domain="medical",
            difficulty=raw.get("difficulty"),
            metadata={
                "source": raw.get("source", "PubMed"),
                "clinical_notes": raw.get("clinical_notes"),
                "pmid": raw.get("pmid"),
            },
        )

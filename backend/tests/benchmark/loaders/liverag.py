"""LiveRAG 数据集加载器（SIGIR 2025 挑战赛）。

数据来源：SIGIR 2025 Challenge（官方发布）
格式：JSONL，895 条合成 QA，带 difficulty / discrimination 评分
许可：比赛许可（需确认）

本地缓存：backend/data/benchmark/liverag/
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

LIVERAG_HOMEPAGE = "https://liverag-challenge.github.io/"
LIVERAG_LICENSE = "Research / Challenge License"
LIVERAG_FILENAMES = [
    "train.jsonl",
    "val.jsonl",
    "test.jsonl",
]


@register("liverag")
class LiveRAGDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="liverag",
            display_name="LiveRAG (SIGIR 2025 Challenge)",
            description="SIGIR 2025 Challenge 官方数据集，895 题，带难度/区分度评分",
            homepage=LIVERAG_HOMEPAGE,
            license=LIVERAG_LICENSE,
            total_questions=895,
            supported_modes=("retrieval", "generation"),
            domains=(),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "liverag"
        local_dir.mkdir(parents=True, exist_ok=True)

        # TODO(R8-REQ): 确认 LiveRAG 下载方式后实现自动下载
        # 目前要求用户自行下载至 local_dir
        existing = [p for p in LIVERAG_FILENAMES if (local_dir / p).exists()]
        if existing:
            logger.info("LiveRAG 已有文件: %s", existing)
        else:
            logger.warning(
                "LiveRAG 数据集未找到。请手动下载至 %s，"
                "文件名: %s",
                local_dir, ", ".join(LIVERAG_FILENAMES),
            )
        return local_dir

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        local_dir = await self.download_if_needed()
        queries: list[BenchmarkQuery] = []

        for fname in LIVERAG_FILENAMES:
            fpath = local_dir / fname
            if not fpath.exists():
                continue
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    raw = json.loads(line)
                    queries.append(self._parse_row(raw))

        self._queries = queries
        logger.info("LiveRAG: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        return BenchmarkQuery(
            case_id=str(raw.get("id", raw.get("question_id", ""))),
            query=raw.get("question", raw.get("query", "")),
            answer=raw.get("answer", raw.get("gold_answer")),
            domain=raw.get("domain"),
            difficulty=raw.get("difficulty"),
            metadata={
                "discrimination": raw.get("discrimination"),
                "source_doc": raw.get("source_document"),
                "challenge_year": "2025",
            },
        )

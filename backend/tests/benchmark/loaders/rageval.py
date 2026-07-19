"""RAGEval 数据集加载器（评测框架）。

RAGEval 不是单一数据集，而是一个评测框架。
本加载器实现其「自动生成评测集」的适配能力。

参考：https://github.com/neulab/rageval（Neulab 版）
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

RAGEVAL_HOMEPAGE = "https://github.com/neulab/rageval"
RAGEVAL_LICENSE = "Apache 2.0"


@register("rageval")
class RAGEvalDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="rageval",
            display_name="RAGEval (自动化评测框架)",
            description="自动化 RAG 评测框架，可生成定制评测集；本加载器适配其输出格式",
            homepage=RAGEVAL_HOMEPAGE,
            license=RAGEVAL_LICENSE,
            total_questions=0,  # 框架无固定数量
            supported_modes=("retrieval", "generation"),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "rageval"
        local_dir.mkdir(parents=True, exist_ok=True)
        return local_dir

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        local_dir = await self.download_if_needed()
        queries: list[BenchmarkQuery] = []

        # 加载所有 JSON 文件作为 RAGEval 格式的评测集
        for json_path in sorted(local_dir.glob("*.json")):
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            cases = data if isinstance(data, list) else data.get("cases", [])
            for raw in cases:
                queries.append(self._parse_row(raw))

        self._queries = queries
        logger.info("RAGEval: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        return BenchmarkQuery(
            case_id=str(raw.get("case_id", raw.get("id", ""))),
            query=raw.get("question", raw.get("query", "")),
            answer=raw.get("answer", raw.get("gold_answer")),
            source=raw.get("source", "txt"),
            domain=raw.get("domain"),
            difficulty=raw.get("difficulty"),
            question_type=raw.get("question_type"),
            expect_rejection=bool(raw.get("expect_rejection", False)),
            expects=tuple(raw.get("expects", [])),
            metadata=raw.get("metadata", {}),
        )

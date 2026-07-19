"""CRAG 数据集加载器（facebookresearch/CRAG）。

数据来源：https://github.com/facebookresearch/CRAG
许可：CC BY-NC 4.0
格式：JSONL.bz2，4,409 条，含 query/answer/domain/popularity/search_results

本地缓存：backend/data/benchmark/crag/
  crag_task_1_and_2_dev_v4.jsonl.bz2
"""

from __future__ import annotations

import bz2
import json
import logging
from pathlib import Path

from tests.benchmark.base import BenchmarkDataset
from tests.benchmark.loaders import register
from tests.benchmark.schemas import (
    BenchmarkQuery,
    DatasetMeta,
    SourceKind,
)

logger = logging.getLogger(__name__)

CRAG_HOMEPAGE = "https://github.com/facebookresearch/CRAG"
CRAG_LICENSE = "CC BY-NC 4.0"
CRAG_FILENAME = "crag_task_1_and_2_dev_v4.jsonl.bz2"
CRAG_URL = (
    "https://github.com/facebookresearch/CRAG/raw/refs/heads/main/data/"
    f"{CRAG_FILENAME}?download="
)
# 下载后解压大小约 200MB+（含完整 HTML）
# 评测仅用 query/answer（检索阶段不需要 HTML）


@register("crag")
class CRAGDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="crag",
            display_name="CRAG (Comprehensive RAG Benchmark)",
            description="全面 RAG 基准，5 领域 8 类别 4,409 题，web + KG 检索",
            homepage=CRAG_HOMEPAGE,
            license=CRAG_LICENSE,
            total_questions=4409,
            supported_modes=("retrieval", "generation"),
            domains=("finance", "music", "movie", "sports", "open"),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "crag"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / CRAG_FILENAME

        if local_path.exists():
            logger.info("CRAG 数据集已存在: %s", local_path)
            return local_path

        logger.info("正在下载 CRAG 数据集 (4409 条)...")
        import httpx

        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            resp = await client.get(CRAG_URL)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
        logger.info("CRAG 下载完成: %s", local_path)
        return local_path

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        local_path = await self.download_if_needed()
        queries: list[BenchmarkQuery] = []

        with bz2.open(str(local_path), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                query = self._parse_row(raw)
                queries.append(query)

        self._queries = queries
        logger.info("CRAG: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        """将 CRAG JSON 行转为统一 BenchmarkQuery。"""
        answers = [raw["answer"]]
        if raw.get("alt_ans"):
            answers.extend(raw["alt_ans"])

        # 从 search_results 提取第一个 snippet 作为源（仅参考）
        source: SourceKind = "txt"
        search_results = raw.get("search_results") or []
        if search_results:
            first = search_results[0]
            page_result = first.get("page_result", "")
            if "<html" in page_result[:500].lower():
                source = "html"

        return BenchmarkQuery(
            case_id=raw["interaction_id"],
            query=raw["query"],
            answer=raw["answer"],
            alt_answers=tuple(answers[1:]),
            source=source,
            domain=raw.get("domain"),
            question_type=raw.get("question_type"),
            difficulty=raw.get("difficulty"),
            metadata={
                "query_time": raw.get("query_time", ""),
                "popularity": raw.get("popularity", ""),
                "static_or_dynamic": raw.get("static_or_dynamic", ""),
                "split": raw.get("split", 0),
                "search_results_count": len(search_results),
            },
        )

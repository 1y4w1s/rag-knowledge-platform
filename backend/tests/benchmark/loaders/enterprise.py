"""EnterpriseRAG-Bench 数据集加载器（模拟企业环境）。

数据来源：研究论文（非公开单一仓库），模拟 Slack/邮件/维基/代码等 9 种数据源
格式：JSON，500 题 / 50 万文档
许可：需确认（学术研究许可）
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

ENTERPRISE_HOMEPAGE = "https://arxiv.org/abs/xxxx.xxxxx"  # TODO: 找到论文链接
ENTERPRISE_LICENSE = "Research License (待确认)"


@register("enterprise")
class EnterpriseRAGBenchDataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="enterprise",
            display_name="EnterpriseRAG-Bench (企业模拟)",
            description="企业级 RAG 评测，9 种数据源（Slack/邮件/维基/代码等），500 题",
            homepage=ENTERPRISE_HOMEPAGE,
            license=ENTERPRISE_LICENSE,
            total_questions=500,
            supported_modes=("retrieval", "generation"),
            domains=("enterprise", "slack", "email", "wiki", "code", "meeting",
                     "doc", "support", "hr"),
        )

    async def download_if_needed(self) -> Path:
        local_dir = self.DATA_DIR / "enterprise"
        local_dir.mkdir(parents=True, exist_ok=True)

        existing = list(local_dir.glob("*.json")) + list(local_dir.glob("*.jsonl"))
        if not existing:
            logger.info(
                "EnterpriseRAG-Bench 未找到本地缓存。"
                "参考 Arxiv 论文获取数据（TODO: 补充论文链接）"
            )
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

        for fpath in sorted(local_dir.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("questions", data.get("data", []))
            for raw in items:
                queries.append(self._parse_row(raw))

        self._queries = queries
        logger.info("EnterpriseRAG-Bench: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_row(raw: dict) -> BenchmarkQuery:
        return BenchmarkQuery(
            case_id=str(raw.get("id", raw.get("question_id", raw.get("qid", "")))),
            query=raw.get("question", raw.get("query", "")),
            answer=raw.get("answer", raw.get("gold_answer")),
            domain=raw.get("domain", raw.get("source_type", "enterprise")),
            difficulty=raw.get("difficulty"),
            metadata={
                "source_type": raw.get("source_type", raw.get("data_source")),
                "source_doc": raw.get("source_document"),
                "department": raw.get("department"),
                "requires_cross_source": raw.get("requires_cross_source", False),
            },
        )

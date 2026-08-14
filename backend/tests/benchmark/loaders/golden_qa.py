"""Golden QA 数据集加载器（索隐自建评测集）。

加载 tests/fixtures/golden_qa.json 并解析为统一的 BenchmarkQuery 格式。
109 题，覆盖考勤、薪酬、合同、IT 等多个企业域。

本地缓存：无需下载，直接引用 fixtures/ 目录。
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
    SourceKind,
)

logger = logging.getLogger(__name__)

# Fixture 路径（backend/tests/fixtures/golden_qa.json）
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURE_FILE = FIXTURE_DIR / "golden_qa.json"

# 标签 → 域/类型映射
DOMAIN_MAP: dict[str, str] = {
    "attendance": "attendance",
    "salary": "salary",
    "contract": "contract",
    "it": "it",
    "hr": "hr",
    "leave": "leave",
    "expense": "expense",
    "training": "training",
    "insurance": "insurance",
    "other": "other",
}


@register("golden_qa")
class GoldenQADataset(BenchmarkDataset):
    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name="golden_qa",
            display_name="Golden QA（索隐自建）",
            description="索隐自建 Golden QA 评测集，109 题，覆盖 10+ 企业域",
            homepage="",
            license="Proprietary",
            total_questions=109,
            supported_modes=("retrieval", "generation"),
            domains=tuple(sorted(DOMAIN_MAP.values())),
        )

    async def load(self) -> list[BenchmarkQuery]:
        if self._queries is not None:
            return self._queries

        if not FIXTURE_FILE.exists():
            raise FileNotFoundError(f"Golden QA fixture 不存在: {FIXTURE_FILE}")

        with open(FIXTURE_FILE, encoding="utf-8") as f:
            data = json.load(f)

        cases = data.get("cases", [])
        queries: list[BenchmarkQuery] = []

        for case in cases:
            query = self._parse_case(case)
            queries.append(query)

        self._queries = queries
        logger.info("Golden QA: 加载 %d 条查询", len(queries))
        return queries

    @staticmethod
    def _parse_case(case: dict) -> BenchmarkQuery:
        """将 golden_qa.json 中的一条 case 解析为 BenchmarkQuery。"""
        case_id = case.get("case_id", "")
        query_text = case.get("query", case.get("question", ""))
        domain = case.get("domain", "")
        difficulty = case.get("difficulty")
        qtype = case.get("question_type", "")
        tags = case.get("tags", [])
        source_kind: SourceKind = case.get("source", "txt")  # type: ignore[assignment]
        expect_rejection = case.get("expect_rejection", False)
        # N13-4 修复：读 answer（judge 分支 runner.run_generation 依赖 q.answer，
        # 缺失时 correctness 恒 0）与 min_match（多相关文档最少命中数）。
        answer = case.get("answer") or None
        min_match = int(case.get("min_match", 1))

        # 处理 expects（支持单数 expect 和复数 expects）
        expects_raw = case.get("expects") or case.get("expect")
        expects: tuple[dict, ...] = ()
        if isinstance(expects_raw, dict):
            expects = (expects_raw,)
        elif isinstance(expects_raw, list):
            expects = tuple(expects_raw)

        return BenchmarkQuery(
            case_id=case_id,
            query=query_text,
            answer=answer,
            domain=DOMAIN_MAP.get(domain, domain),
            difficulty=difficulty,
            question_type=qtype,
            source=source_kind,
            expect_rejection=expect_rejection,
            expects=expects,
            metadata={
                "tags": tags,
                "source": source_kind,
                "min_match": min_match,
            },
        )

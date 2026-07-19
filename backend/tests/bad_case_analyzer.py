"""Bad Case 分析器（企业评测体系 Phase 4-2）。
对比两次评测运行，找出新增/消失的失败 case 并归类。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BadCase:
    """一条 Bad Case 的完整信息。"""
    case_id: str
    query: str
    domain: str
    question_type: str
    difficulty: float
    failed_metric: str  # retrieval | generation | rejection
    expected: str       # 期望结果
    actual: str         # 实际结果
    suggested_reason: str = ""


@dataclass
class BadCaseReport:
    """Bad Case 分析报告。"""
    timestamp: str
    baseline_label: str
    current_label: str
    new_failures: list[BadCase] = field(default_factory=list)
    fixed_cases: list[BadCase] = field(default_factory=list)
    persistent_failures: list[BadCase] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.new_failures) > 0

    def print_summary(self) -> None:
        print()
        print("=" * 60)
        print("  Bad Case 分析报告")
        print("=" * 60)
        print("  基线: %s" % self.baseline_label)
        print("  当前: %s" % self.current_label)
        print("  ---")
        if self.new_failures:
            print("  [新增失败] %d 条" % len(self.new_failures))
            for b in self.new_failures[:10]:
                print("    %s [%s/%s] %s" % (b.case_id, b.domain, b.question_type, b.query[:40]))
            if len(self.new_failures) > 10:
                print("    ... 还有 %d 条" % (len(self.new_failures) - 10))
        if self.fixed_cases:
            print("  [已修复] %d 条" % len(self.fixed_cases))
        if self.persistent_failures:
            print("  [持续失败] %d 条" % len(self.persistent_failures))
        print("=" * 60)


class BadCaseAnalyzer:
    """Bad Case 分析器。"""

    @staticmethod
    def analyze(
        baseline_details: list[dict[str, Any]],
        current_details: list[dict[str, Any]],
        golden_meta: dict[str, dict[str, Any]] | None = None,
        baseline_label: str = "baseline",
        current_label: str = "current",
    ) -> BadCaseReport:
        """对比两次评测的明细结果，找出 bad case。

        Args:
            baseline_details: 基线检索结果列表（含 case_id, hit, rank 等）
            current_details: 当前检索结果列表
            golden_meta: case_id -> {domain, question_type, difficulty, query} 的映射
        """
        # 建立索引
        base_map = {r["case_id"]: r for r in baseline_details}
        curr_map = {r["case_id"]: r for r in current_details}

        new_failures: list[BadCase] = []
        fixed_cases: list[BadCase] = []
        persistent_failures: list[BadCase] = []
        meta = golden_meta or {}

        all_ids = set(base_map.keys()) | set(curr_map.keys())

        for cid in all_ids:
            base = base_map.get(cid)
            curr = curr_map.get(cid)
            m = meta.get(cid, {})

            base_hit = base.get("hit", False) if base else None
            curr_hit = curr.get("hit", False) if curr else None
            query = m.get("query", cid) if m else cid

            # 新增失败
            if base_hit is True and curr_hit is False:
                new_failures.append(BadCase(
                    case_id=cid, query=query,
                    domain=m.get("domain", "?"),
                    question_type=m.get("question_type", "?"),
                    difficulty=m.get("difficulty", 0.5),
                    failed_metric="retrieval",
                    expected="hit", actual="miss",
                ))
            # 已修复
            elif base_hit is False and curr_hit is True:
                fixed_cases.append(BadCase(
                    case_id=cid, query=query,
                    domain=m.get("domain", "?"),
                    question_type=m.get("question_type", "?"),
                    difficulty=m.get("difficulty", 0.5),
                    failed_metric="retrieval",
                    expected="hit", actual="hit",
                ))
            # 持续失败
            elif base_hit is False and curr_hit is False:
                persistent_failures.append(BadCase(
                    case_id=cid, query=query,
                    domain=m.get("domain", "?"),
                    question_type=m.get("question_type", "?"),
                    difficulty=m.get("difficulty", 0.5),
                    failed_metric="retrieval",
                    expected="hit", actual="miss",
                ))

        report = BadCaseReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            baseline_label=baseline_label,
            current_label=current_label,
            new_failures=new_failures,
            fixed_cases=fixed_cases,
            persistent_failures=persistent_failures,
        )
        return report

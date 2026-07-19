"""回归检测告警模块（企业评测体系 Phase 3）。
对比两次评测结果，检测显著偏差。

用法:
    from tests.regression_alert import RegressionChecker
    alerts = RegressionChecker.check(baseline, current, thresholds)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认阈值
DEFAULT_THRESHOLDS = {
    "hit_at_k": -0.02,       # Hit@3 下降超过 2%
    "mrr": -0.03,            # MRR 下降超过 0.03
    "precision_at_k": -0.03, # Precision@K 下降超过 3%
    "recall_at_k": -0.03,    # Recall@K 下降超过 3%
    "rejection_accuracy": -0.05,  # 拒答准确率下降超过 5%
    "p95_latency_ms": 0.20,  # P95 延迟上升超过 20%
}


@dataclass
class RegressionAlert:
    """一条回归告警。"""
    metric: str
    baseline_value: float
    current_value: float
    change: float  # 绝对变化或百分比变化
    severity: str  # "warning" | "critical"
    message: str


@dataclass
class RegressionReport:
    """回归检测报告。"""
    timestamp: str
    baseline_label: str
    current_label: str
    alerts: list[RegressionAlert] = field(default_factory=list)
    passed: int = 0

    @property
    def has_regression(self) -> bool:
        return len(self.alerts) > 0

    def print_summary(self) -> None:
        print()
        print("=" * 60)
        print("  回归检测报告")
        print("=" * 60)
        print("  基线: %s" % self.baseline_label)
        print("  当前: %s" % self.current_label)
        print("  ---")
        if self.alerts:
            print("  告警: %d 条" % len(self.alerts))
            for a in self.alerts:
                tag = "CRIT" if a.severity == "critical" else "WARN"
                print("    [%s] %s" % (tag, a.message))
        else:
            print("  [PASS] 无回归")
        print("  通过: %d 项" % self.passed)
        print("=" * 60)


class RegressionChecker:
    """回归检测器。对比两次 RetrievalMetrics。"""

    @staticmethod
    def check(
        baseline: dict[str, Any],
        current: dict[str, Any],
        thresholds: dict[str, float] | None = None,
        baseline_label: str = "baseline",
        current_label: str = "current",
    ) -> RegressionReport:
        """对比 baseline 和 current 的指标。

        Args:
            baseline: 基线指标 dict（如 RetrievalMetrics 的 asdict）
            current: 当前指标 dict
            thresholds: 自定义阈值，key=指标名，value=允许最大负向变化（负值表示下降）
        """
        thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        alerts: list[RegressionAlert] = []
        passed = 0

        # 标量指标对比
        scalar_metrics = [
            ("hit_at_3", "Hit@3"),
            ("hit_at_1", "Hit@1"),
            ("mean_reciprocal_rank", "MRR"),
            ("precision_at_k", "Precision@K"),
            ("recall_at_k", "Recall@K"),
            ("correct_rejection_rate", "拒答准确率"),
        ]

        for key, display_name in scalar_metrics:
            bv = baseline.get(key, 0.0) or 0.0
            cv = current.get(key, 0.0) or 0.0
            diff = cv - bv
            threshold = thr.get(key, -0.02)

            if diff < threshold:
                severity = "critical" if diff < threshold * 1.5 else "warning"
                alerts.append(RegressionAlert(
                    metric=key, baseline_value=bv, current_value=cv,
                    change=diff, severity=severity,
                    message="%s: %.1f%% → %.1f%% (%.1f%%)" % (
                        display_name, bv * 100, cv * 100, diff * 100),
                ))
            else:
                passed += 1

        # 延迟对比（百分比）
        latency_metrics = [
            ("p50_latency_ms", "P50 延迟"),
            ("p95_latency_ms", "P95 延迟"),
        ]

        for key, display_name in latency_metrics:
            bv = baseline.get(key, 0.0) or 0.0
            cv = current.get(key, 0.0) or 0.0
            if bv > 0:
                change_pct = (cv - bv) / bv
                threshold_pct = thr.get(key, 0.20)
                if change_pct > threshold_pct:
                    severity = "critical" if change_pct > threshold_pct * 1.5 else "warning"
                    alerts.append(RegressionAlert(
                        metric=key, baseline_value=bv, current_value=cv,
                        change=change_pct, severity=severity,
                        message="%s: %.0fms → %.0fms (+%.0f%%)" % (
                            display_name, bv, cv, change_pct * 100),
                    ))
                else:
                    passed += 1

        report = RegressionReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            baseline_label=baseline_label,
            current_label=current_label,
            alerts=alerts,
            passed=passed,
        )
        return report

    @staticmethod
    def check_from_files(
        baseline_path: str | Path,
        current_path: str | Path,
        thresholds: dict[str, float] | None = None,
    ) -> RegressionReport | None:
        """从 JSON 文件加载指标并对比。"""
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                baseline = json.load(f)
            with open(current_path, "r", encoding="utf-8") as f:
                current = json.load(f)

            # 提取 retrieval metrics
            b_ret = baseline.get("retrieval", baseline)
            c_ret = current.get("retrieval", current)

            return RegressionChecker.check(
                b_ret, c_ret, thresholds=thresholds,
                baseline_label=str(baseline_path),
                current_label=str(current_path),
            )
        except Exception as e:
            logger.error("回归检测失败: %s", e)
            return None

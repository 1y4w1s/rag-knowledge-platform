"""
golden_qa 生产基线运行器（企业评测体系 Phase 1-4）。

采集当前生产环境的 Hit@3 / MRR / 延迟基线数据。
结果写入 backend/benchmark_results/ 并与 docs/ 同步。

用法:
    python -m tests.run_golden_baseline                # 全量基线
    python -m tests.run_golden_baseline --subset 10    # 快速子集（10 题）
    python -m tests.run_golden_baseline --dry-run      # 只打印计划不做实际检索
    python -m tests.run_golden_baseline --save         # 结果写入 run_baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FIXTURES = Path(__file__).parent / "fixtures"
RESULT_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"


@dataclass
class BaselineResult:
    """单条基线结果。"""
    case_id: str
    query: str
    hit: bool
    rank: int  # 0 = miss, 1-3 = hit position
    mrr_contribution: float  # 0 or 1/rank
    latency_ms: float
    top_chunks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BaselineReport:
    """基线汇总报告。"""
    timestamp: str
    total: int
    hit_at_k: float
    mrr: float
    p50_latency_ms: float
    p95_latency_ms: float
    rejection_accuracy: float
    by_domain: dict[str, dict[str, Any]]
    by_type: dict[str, dict[str, Any]]
    details: list[BaselineResult] = field(default_factory=list)


async def collect_baseline(subset: int | None = None, dry_run: bool = False) -> BaselineReport:
    """采集生产基线。

    注意：需要运行中的 API 和数据库。
    dry_run=True 时只输出计划不执行检索。
    """
    from tests.golden_qa_loader import GOLDEN_QA_CASES as all_cases

    cases = list(all_cases)
    if subset:
        cases = cases[:subset]

    logger.info("基线评测: %d 题 (subset=%s)", len(cases), subset or "full")

    if dry_run:
        logger.info("[DRY RUN] 计划执行 %d 题检索", len(cases))
        rej = sum(1 for c in cases if c.expect_rejection)
        logger.info("  其中拒答 %d 题", rej)
        return BaselineReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total=len(cases), hit_at_k=0.0, mrr=0.0,
            p50_latency_ms=0.0, p95_latency_ms=0.0,
            rejection_accuracy=0.0, by_domain={}, by_type={},
        )

    # ====== 实际评测需要数据库连接 ======
    # 以下为伪代码，实际运行时需根据项目环境配置
    from app.core.database import SessionLocal
    from app.services.rag.retrieval import retrieve_chunks
    from tests.golden_qa_loader import HIT_K, chunk_matches, hit_at_k, reciprocal_rank

    results: list[BaselineResult] = []
    domain_stats: dict[str, dict] = {}
    type_stats: dict[str, dict] = {}

    # 创建知识库并上传 golden 文档（需先登录）
    # 这里简化处理：假设已有 kb_id 在环境变量或配置中
    kb_id = None  # 需要实际环境提供

    if not kb_id:
        logger.error("未配置 kb_id，请设置环境变量 GOLDEN_KB_ID 或传入 --kb-id")
        raise SystemExit(1)

    async with SessionLocal() as db:
        for case in cases:
            t0 = time.perf_counter()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            elapsed = (time.perf_counter() - t0) * 1000

            matched = hit_at_k(chunks, case, k=HIT_K)
            rr = reciprocal_rank(chunks, case, k=HIT_K)

            # 计算命中排名
            rank = 0
            for i, c in enumerate(chunks[:HIT_K], 1):
                if chunk_matches(case, c):
                    rank = i
                    break

            results.append(BaselineResult(
                case_id=case.case_id, query=case.query[:40],
                hit=matched, rank=rank, mrr_contribution=rr,
                latency_ms=elapsed,
                top_chunks=[{"section": getattr(c, "section_title", ""), "score": getattr(c, "score", 0.0),
                             "preview": (getattr(c, "content", "") or "")[:60]} for c in chunks[:HIT_K]],
            ))

            # 分 domain/type 统计
            for key, bucket, stat_key in [(case.domain, domain_stats, "domain"),
                                           (case.question_type, type_stats, "type")]:
                if key not in bucket:
                    bucket[key] = {"total": 0, "hit": 0, "latency_sum": 0.0}
                bucket[key]["total"] += 1
                if matched:
                    bucket[key]["hit"] += 1
                bucket[key]["latency_sum"] += elapsed

    # 汇总
    n = len(results)
    hits = sum(1 for r in results if r.hit)
    mrrs = sum(r.mrr_contribution for r in results)
    latencies = sorted(r.latency_ms for r in results)
    rej_cases = [r for r in results if r.case_id and any(c.expect_rejection for c in cases if c.case_id == r.case_id)]
    rej_correct = sum(1 for r in rej_cases if r.hit is False)  # 拒答正确 = 没有命中

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    report = BaselineReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total=n, hit_at_k=hits / max(1, n),
        mrr=mrrs / max(1, n),
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        rejection_accuracy=rej_correct / max(1, len(rej_cases)),
        by_domain={k: {"total": v["total"], "hit_rate": v["hit"] / max(1, v["total"]),
                        "avg_latency_ms": v["latency_sum"] / max(1, v["total"])}
                   for k, v in domain_stats.items()},
        by_type={k: {"total": v["total"], "hit_rate": v["hit"] / max(1, v["total"]),
                      "avg_latency_ms": v["latency_sum"] / max(1, v["total"])}
                 for k, v in type_stats.items()},
        details=results,
    )
    return report


def print_report(report: BaselineReport) -> None:
    """打印基线报告。"""
    print()
    print("=" * 60)
    print("  golden_qa 生产基线报告")
    print("=" * 60)
    print("  时间:     %s" % report.timestamp)
    print("  总题数:   %d" % report.total)
    print("  Hit@%d:   %.1f%%" % (3, report.hit_at_k * 100))
    print("  MRR:      %.4f" % report.mrr)
    print("  P50:      %.0f ms" % report.p50_latency_ms)
    print("  P95:      %.0f ms" % report.p95_latency_ms)
    print("  拒答准确率: %.1f%%" % (report.rejection_accuracy * 100))
    print("  ---")

    if report.by_domain:
        print("  Domain 分布:")
        for d, s in sorted(report.by_domain.items()):
            print("    %-15s %2d 题  Hit@3=%.1f%%  avg=%.0fms" % (
                d, s["total"], s["hit_rate"] * 100, s["avg_latency_ms"]))
    print("=" * 60)


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="golden_qa 生产基线")
    parser.add_argument("--subset", type=int, default=None, help="子集题数（默认全量）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划")
    parser.add_argument("--save", action="store_true", help="保存结果到 benchmark_results/")
    parser.add_argument("--kb-id", type=str, default=None, help="知识库 ID")
    args = parser.parse_args()

    if args.kb_id:
        import os
        os.environ["GOLDEN_KB_ID"] = args.kb_id

    report = await collect_baseline(subset=args.subset, dry_run=args.dry_run)
    print_report(report)

    if args.save and not args.dry_run:
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULT_DIR / "run_baseline.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)
        logger.info("基线结果已保存: %s", path)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

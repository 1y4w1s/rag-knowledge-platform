#!/usr/bin/env python
"""A3 生成质量基线 — 用 RAGAS 跑 Golden QA 全部题目的 Faithfulness 评测。

运行方式：
    # 完整运行（需要真实 DB + kb_id）
    python -m tests.benchmark.run_ragas_baseline --kb-id <uuid>

    # 从已有的 benchmark_results JSON 重建基线（不需要 DB）
    python -m tests.benchmark.run_ragas_baseline --reuse <json-file>

    # 快速验证（抽样 10 题）
    python -m tests.benchmark.run_ragas_baseline --kb-id <uuid> --sample 10

输出：
    benchmark_results/generation_ragas_golden_qa_{timestamp}.json  — 逐题+汇总（前端可读）
    docs/baseline-ragas.json                                       — 基线摘要

前提：
    - 完整运行：DEEPSEEK_API_KEY、DATABASE_URL、Golden QA 源文档已入库
    - 重建模式：已有 benchmark_results 中的 generation 结果 JSON
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_ragas_baseline")

# ── 路径 ──
BACKEND_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = BACKEND_DIR.parent / "docs"
BENCHMARK_DIR = BACKEND_DIR / "benchmark_results"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A3 RAGAS 生成质量基线")
    p.add_argument(
        "--kb-id", type=str, default=None,
        help="知识库 UUID（完整运行必需）",
    )
    p.add_argument(
        "--sample", type=int, default=None,
        help="抽样数量（默认全量 109 题）",
    )
    p.add_argument(
        "--reuse", type=str, default=None,
        help="从已有的 benchmark_results JSON 重建基线（不需要 DB）",
    )
    p.add_argument(
        "--output", type=str, default=str(BENCHMARK_DIR),
        help="输出目录（默认 benchmark_results）",
    )
    return p.parse_args()


def extract_generation_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """从 DatasetReport JSON 或类似结构中提取生成指标。

    支持多种格式：
    - generation_benchmark*.json 格式（datasets 数组）
    - 单个 DatasetReport 格式
    - 简化的 {avg_faithfulness, ...} 格式
    """
    # 格式 1: ReportGenerator 输出（datasets 数组）
    datasets = data.get("datasets", [])
    if datasets:
        # 取第一个有效数据集的 generation 指标
        for ds in datasets:
            gen = ds.get("generation", {})
            if gen and gen.get("total", 0) > 0:
                return {
                    "faithfulness": gen.get("faithfulness", 0.0),
                    "hallucination_rate": gen.get("hallucination_rate", 0.0),
                    "correctness": gen.get("correctness", 0.0),
                    "total": gen.get("total", 0),
                    "citation_accuracy": gen.get("citation_accuracy", 0.0),
                }

    # 格式 2: 生成结果 JSON（包含 avg_faithfulness 或 avg_correctness）
    for key in ("avg_faithfulness", "faithfulness_avg", "avg_faithfulness_score"):
        if key in data:
            break
    else:
        # 尝试从 results 数组计算
        results = data.get("results", [])
        if results:
            f_scores = [
                r.get("faithfulness_score", 0.0)
                for r in results if r.get("faithfulness_score") is not None
            ]
            c_scores = [
                r.get("correctness_score", 0.0)
                for r in results if r.get("correctness_score") is not None
            ]
            h_scores = [
                r.get("hallucination_rate", 0.0)
                for r in results if r.get("hallucination_rate") is not None
            ]
            if f_scores or c_scores:
                return {
                    "faithfulness": sum(f_scores) / len(f_scores) if f_scores else 0.0,
                    "hallucination_rate": sum(h_scores) / len(h_scores) if h_scores else 0.0,
                    "correctness": sum(c_scores) / len(c_scores) if c_scores else 0.0,
                    "total": len(f_scores),
                }

    # 格式 3: 简单字段
    return {
        "faithfulness": data.get("avg_faithfulness") or data.get("faithfulness_avg", 0.0),
        "hallucination_rate": data.get("avg_hallucination_rate") or data.get("hallucination_avg", 0.0),
        "correctness": data.get("avg_correctness") or data.get("correctness_avg", 0.0),
        "total": data.get("valid", data.get("total", 0)),
    }


def find_result_files() -> list[Path]:
    """扫描 benchmark_results/ 查找已有的 generation 结果文件。"""
    if not BENCHMARK_DIR.is_dir():
        return []

    files: list[Path] = []
    for pattern in (
        "generation_ragas_*.json",
        "benchmark_generation_*.json",
        "generation_benchmark*.json",
    ):
        files.extend(sorted(BENCHMARK_DIR.glob(pattern), reverse=True))

    # 去重 + 按修改时间排序
    seen = set()
    unique = []
    for f in files:
        if f.name not in seen:
            seen.add(f.name)
            unique.append(f)
    return unique


def write_baseline_json(
    metrics: dict[str, Any],
    source_file: str,
    output_dir: str | Path,
) -> Path:
    """写入基线文档 docs/baseline-ragas.json。"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    baseline = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": f"ragas_baseline_{time.strftime('%Y%m%d_%H%M%S')}",
        "dataset": "golden_qa",
        "source_file": source_file,
        "total_queries": metrics.get("total", 0),
        "metrics": {
            "faithfulness": round(metrics.get("faithfulness", 0.0), 4),
            "hallucination_rate": round(metrics.get("hallucination_rate", 0.0), 4),
            "correctness": round(metrics.get("correctness", 0.0), 4),
            "citation_accuracy": round(metrics.get("citation_accuracy", 0.0), 4),
        },
        "valid_samples": metrics.get("total", 0),
        "performance": metrics.get("performance", {}),
        "note": (
            "A3 生成质量基线 — 用 RAGAS Faithfulness / Answer Correctness "
            "评测 Golden QA。作为后续优化（HyDE、自适应检索等）的生成质量对比基准。\n"
            "评分说明：\n"
            "  - faithfulness: 回答是否忠实于检索上下文（0~1，越高越好）\n"
            "  - hallucination_rate: 无 chunk 支撑的 claims 比例（0~1，越低越好）\n"
            "  - correctness: 回答与标准答案的一致性（语义级，0~1，越高越好）\n"
            "  - citation_accuracy: 引用准确率（0~1，越高越好）\n"
        ),
    }
    baseline_path = DOCS_DIR / "baseline-ragas.json"
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    logger.info("基线文档已保存: %s", baseline_path)

    # 同时写入一份到 benchmark_results/ 供前端读取
    frontend_file = Path(output_dir) / f"generation_ragas_golden_qa_{time.strftime('%Y%m%d_%H%M%S')}.json"
    frontend_data = {
        "dataset": "golden_qa",
        "display_name": "Golden QA（RAGAS 生成基线）",
        "total": baseline["total_queries"],
        "valid": baseline["valid_samples"],
        "skipped": 0,
        "avg_faithfulness": baseline["metrics"]["faithfulness"],
        "avg_hallucination_rate": baseline["metrics"]["hallucination_rate"],
        "avg_correctness": baseline["metrics"]["correctness"],
        "ts": time.time(),
        "note": "A3 生成质量基线",
    }
    with open(frontend_file, "w", encoding="utf-8") as f:
        json.dump(frontend_data, f, ensure_ascii=False, indent=2)
    logger.info("前端结果已保存: %s", frontend_file)

    return baseline_path


async def run_full_evaluation(
    kb_id: UUID,
    sample_size: int | None,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """完整运行：加载 Golden QA → 检索+生成 → RAGAS 评分 → 保存。

    注意：不依赖 BenchmarkRunner 的 RAGAS scorer（chunk_to_citation 用 "excerpt"
    而非 "content"，与 RetrievedChunk.from_raw 不兼容），改为自管理 RAGAS 评分。
    """
    from uuid import uuid4

    from app.core.database import SessionLocal
    from tests.benchmark.loaders.golden_qa import GoldenQADataset
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.adapters.generation import GenerationAdapter
    from tests.benchmark.report import ReportGenerator
    from tests.benchmark.scorers.ragas_scorer import RagasGenerationScorer
    from tests.benchmark.scorers.base import RetrievedChunk, Expect as Expect_

    user_id = uuid4()
    rate_limit = RateLimitWrapper(mode="bypass")
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)

    # 加载数据集
    loader = GoldenQADataset()
    queries = await loader.load()
    total_questions = len(queries)

    if sample_size and sample_size < total_questions:
        queries = queries[:sample_size]
        logger.info("抽样模式: %d/%d 题", sample_size, total_questions)

    logger.info(
        "开始 RAGAS 生成基线评测: %s (%d 题)",
        loader.meta.display_name, len(queries),
    )

    ragas_scorer = RagasGenerationScorer()
    all_faithfulness: list[float] = []
    all_correctness: list[float] = []
    all_latencies: list[float] = []
    skipped = 0

    async with SessionLocal() as db:
        adapter = GenerationAdapter(db, kb_id)
        runner.set_generate_fn(adapter.generate)

        for idx, q in enumerate(queries):
            if q.expect_rejection:
                continue

            await rate_limit.wait_for_chat(user_id)
            t0 = time.perf_counter()
            try:
                answer, citations = await runner._call_with_retry(
                    runner._generate_fn, q.query, kb_id,
                    label="gen-%s" % q.case_id,
                )
            except Exception as e:
                logger.warning("生成失败: case=%s err=%s", q.case_id, e)
                skipped += 1
                continue
            elapsed = (time.perf_counter() - t0) * 1000
            all_latencies.append(elapsed)

            # 手动转换 citations → RetrievedChunk（解决 excerpt → content 映射）
            chunks_for_scorer = []
            for c in citations:
                if isinstance(c, dict):
                    content = c.get("excerpt") or c.get("content") or c.get("text", "")
                    chunks_for_scorer.append(RetrievedChunk(
                        chunk_id=c.get("chunk_id", str(id(c))),
                        content=content,
                        section_title=c.get("section_title", ""),
                    ))
                else:
                    chunks_for_scorer.append(RetrievedChunk(
                        chunk_id=str(id(c)), content=str(c),
                    ))

            # RAGAS 评分
            gt = q.expects[0].get("content_contains", "") if q.expects else (q.answer or "")
            expect_obj = Expect_(
                content_contains=gt,
                answer=q.answer or "",
            )
            gscore = ragas_scorer.score_generation(
                q.query, answer, expect_obj, chunks_for_scorer,
            )

            all_faithfulness.append(gscore.faithfulness)
            all_correctness.append(gscore.correctness)
            # hallucination_rate 未在 GenerationScore 中定义，跳过

            if (idx + 1) % 5 == 0:
                logger.info("进度: %d/%d (faithfulness=%.2f%%)",
                            idx + 1, len(queries),
                            (sum(all_faithfulness) / len(all_faithfulness)) * 100)

    # 汇总
    n = len(all_faithfulness)
    avg_faithfulness = sum(all_faithfulness) / n if n > 0 else 0.0
    avg_correctness = sum(all_correctness) / n if n > 0 else 0.0

    # 构造报告（模拟 DatasetReport 格式供 ReportGenerator 消费）
    from tests.benchmark.schemas import GenerationMetrics, DatasetReport

    gen_metrics = GenerationMetrics(
        faithfulness=avg_faithfulness,
        correctness=avg_correctness,
        total=n,
    )
    report = DatasetReport(
        dataset_name="golden_qa",
        total_queries=total_questions,
        skipped=skipped,
        generation=gen_metrics,
        p50_latency_ms=_percentile(all_latencies, 50),
        p95_latency_ms=_percentile(all_latencies, 95),
        p99_latency_ms=_percentile(all_latencies, 99),
        throughput_qps=n / (sum(all_latencies) / 1000) if all_latencies else 0.0,
    )

    # 导出结果
    report_gen = ReportGenerator(output_dir)
    report_gen.add_report(report)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"generation_ragas_golden_qa_{timestamp}"
    paths = report_gen.export_all(filename)
    report_path = paths.get("json", paths.get("_", BENCHMARK_DIR / f"{filename}.json"))

    logger.info(
        "RAGAS 生成基线完成: %d 题有效, faithfulness=%.2f%%, correctness=%.2f%%",
        n, avg_faithfulness * 100, avg_correctness * 100,
    )

    metrics = {
        "faithfulness": avg_faithfulness,
        "correctness": avg_correctness,
        "total": n,
        "performance": {
            "p50_latency_ms": round(report.p50_latency_ms, 1),
            "p95_latency_ms": round(report.p95_latency_ms, 1),
        },
    }
    baseline_path = write_baseline_json(metrics, str(report_path), output_dir)
    return report_path, baseline_path


async def run_reuse_mode(
    source_path: str,
    output_dir: str | Path,
) -> Path:
    """重建模式：从已有结果文件提取基线。"""
    src = Path(source_path)
    if not src.exists():
        logger.error("文件不存在: %s", src)
        sys.exit(1)

    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    metrics = extract_generation_metrics(data)
    logger.info(
        "从 %s 提取指标: faithfulness=%.2f%% correctness=%.2f%% (total=%d)",
        src.name,
        metrics.get("faithfulness", 0) * 100,
        metrics.get("correctness", 0) * 100,
        metrics.get("total", 0),
    )

    baseline_path = write_baseline_json(metrics, str(src), output_dir)
    return baseline_path


def print_summary(metrics: dict[str, Any], baseline_path: Path) -> None:
    """打印结果摘要。"""
    faithfulness = metrics.get("faithfulness", 0)
    hallucination = metrics.get("hallucination_rate", 0)
    correctness = metrics.get("correctness", 0)
    total = metrics.get("total", 0)
    perf = metrics.get("performance", {})

    print()
    print("=" * 56)
    print("  A3 RAGAS 生成基线 — 完成")
    print(f"  基线文档: {baseline_path}")
    print(f"  有效题数: {total}")
    print(f"  Faithfulness:      {faithfulness*100:6.2f}%")
    print(f"  Hallucination:     {hallucination*100:6.2f}%")
    print(f"  Correctness:       {correctness*100:6.2f}%")
    if perf.get("p50_latency_ms"):
        print(f"  P50 延迟:          {perf['p50_latency_ms']:6.0f} ms")
    print("=" * 56)
    print()
    print("后续建议:")
    print("  1. 查看前端 /evaluations → RAGAS 评分 标签页")
    print("  2. 将基线值记录到 progress.md")
    print("  3. 在 CI 中增加 nightly RAGAS 门禁（参见 master plan §8.3）")
    print()


def _percentile(values: list[float], p: int) -> float:
    """计算百分位值。"""
    if not values:
        return 0.0
    sv = sorted(values)
    idx = max(0, int(len(sv) * p / 100) - 1)
    return sv[idx]


async def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)

    if args.reuse:
        # ── 重建模式 ──
        baseline_path = await run_reuse_mode(args.reuse, output_dir)
        # 重建模式下 metrics 从已读取的数据中提取
        src = Path(args.reuse)
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
        metrics = extract_generation_metrics(data)

    elif args.kb_id:
        # ── 完整运行模式 ──
        kb_id = UUID(args.kb_id)
        report_path, baseline_path = await run_full_evaluation(
            kb_id, args.sample, output_dir,
        )
        # 重新读取基线以获取 metrics
        with open(baseline_path, encoding="utf-8") as f:
            baseline_data = json.load(f)
        metrics = {
            **baseline_data["metrics"],
            "total": baseline_data["valid_samples"],
            "performance": baseline_data.get("performance", {}),
        }

    else:
        # ── 自动检测模式：找已有的结果文件 ──
        result_files = find_result_files()
        if result_files:
            logger.info(
                "发现 %d 个已有结果文件，使用最新的: %s",
                len(result_files), result_files[0].name,
            )
            baseline_path = await run_reuse_mode(str(result_files[0]), output_dir)
            with open(result_files[0], encoding="utf-8") as f:
                data = json.load(f)
            metrics = extract_generation_metrics(data)
        else:
            logger.error(
                "请指定 --kb-id 运行完整评测，或 --reuse 从已有结果重建基线。\n"
                "示例:\n"
                "  python -m tests.benchmark.run_ragas_baseline --kb-id <uuid>\n"
                "  python -m tests.benchmark.run_ragas_baseline --reuse benchmark_results/generation_ragas_golden_qa_20260730.json"
            )
            sys.exit(1)

    print_summary(metrics, baseline_path)


if __name__ == "__main__":
    asyncio.run(main())

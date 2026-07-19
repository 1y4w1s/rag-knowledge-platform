#!/usr/bin/env python
"""睿阁 RAG 生成质量评测入口。

运行方式：
    # 单一数据集
    python -m tests.benchmark.run_generation --datasets crag --sample 50
    
    # 全部数据集（抽样）
    python -m tests.benchmark.run_generation --all --sample 100 --output ./benchmark_results
    
注意：生成评测需要 DeepSeek API key，受 chat 限流（bypass 模式下 10000次/小时）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_generation")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="睿阁 RAG 生成质量评测")
    p.add_argument(
        "--datasets",
        type=str,
        default="crag",
        help="数据集名称，逗号分隔",
    )
    p.add_argument("--all", action="store_true", help="运行所有已注册数据集")
    p.add_argument(
        "--mode",
        choices=["bypass", "enforce"],
        default="bypass",
        help="限流模式 (默认 bypass)",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=100,
        help="每个数据集抽样数量（默认 100，生成评测较慢）",
    )
    p.add_argument(
        "--output",
        type=str,
        default="benchmark_results",
        help="输出目录",
    )
    p.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="跳过检索阶段（仅评估已缓存的生成结果）",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # 设置限流模式
    os.environ["RAG_RATE_LIMIT_MODE"] = args.mode
    # 生成评测必须用真实嵌入 + 真实 LLM
    os.environ["RAG_REAL_EMBEDDING"] = "1"

    from app.core.database import SessionLocal
    from tests.benchmark.loaders import list_datasets, get_loader
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.report import ReportGenerator

    # 确定数据集
    if args.all:
        dataset_names = list_datasets()
    else:
        dataset_names = [n.strip() for n in args.datasets.split(",")]

    logger.info("生成评测数据集: %s", dataset_names)
    logger.info("限流模式: %s", args.mode)
    logger.info("抽样数量: %d/数据集", args.sample)

    kb_id = uuid4()
    user_id = uuid4()
    rate_limit = RateLimitWrapper(mode=args.mode)
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)

    if not args.skip_retrieval:
        from tests.benchmark.adapters.generation import GenerationAdapter

        async with SessionLocal() as db:
            adapter = GenerationAdapter(db, kb_id)
            runner.set_generate_fn(adapter.generate)

    report_gen = ReportGenerator(args.output)

    for name in dataset_names:
        try:
            loader = get_loader(name)
        except KeyError as e:
            logger.error(e)
            continue

        # 检查数据集是否有源文档可上传
        # 注意：生成评测需要知识库中有对应文档。
        # 当前 Golden QA 已含 handbook 等源文档。
        # CRAG 等数据集需要额外准备源文档（Phase 3 后续迭代）。
        if not loader.meta.domains:
            logger.warning(
                "%s 无领域信息，可能需要手动准备源文档", name
            )

        logger.info("开始生成评测: %s (抽样 %d)", name, args.sample)
        report = await runner.run_generation(
            loader,
            sample_size=args.sample,
        )
        report_gen.add_report(report)

        gen = report.generation
        logger.info(
            "%s 完成: 正确性=%.1f%% 引用准确率=%.1f%% (延迟 P50=%.0fms)",
            name,
            (gen.correctness * 100) if gen else 0,
            (gen.citation_accuracy * 100) if gen else 0,
            report.p50_latency_ms,
        )

    # 导出报告
    paths = report_gen.export_all("generation_benchmark")
    for fmt, p in paths.items():
        logger.info("报告已保存: %s (%s)", p, fmt)

    total_wait = rate_limit.total_waited
    if total_wait > 0:
        logger.info("限流累计等待: %.1f 秒", total_wait)


if __name__ == "__main__":
    asyncio.run(main())

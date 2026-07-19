#!/usr/bin/env python
"""睿阁 RAG 检索质量评测入口。

运行方式：
    # 快速模式（mock 嵌入，不依赖 API）
    python -m tests.benchmark.run_retrieval --datasets crag --mode bypass --mock
    
    # 真实嵌入模式（下载数据集 + 真实检索）
    python -m tests.benchmark.run_retrieval --datasets crag,liverag --mode bypass
    
    # 全部数据集（限流模式）
    python -m tests.benchmark.run_retrieval --all --mode enforce --output ./benchmark_results
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from uuid import uuid4

# 确保后端模块可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_retrieval")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="睿阁 RAG 检索质量评测")
    p.add_argument(
        "--datasets",
        type=str,
        default="crag",
        help="数据集名称，逗号分隔 (crag, liverag, rageval, ragbench, mirage, enterprise)",
    )
    p.add_argument("--all", action="store_true", help="运行所有已注册数据集")
    p.add_argument(
        "--mode",
        choices=["bypass", "enforce"],
        default="bypass",
        help="限流模式 (默认 bypass 提额)",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="使用 mock 嵌入（快速验证，不调用通义 API）",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="检索 Top-K (默认 3)",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="每个数据集抽样数量（大规模数据集使用）",
    )
    p.add_argument(
        "--output",
        type=str,
        default="benchmark_results",
        help="输出目录 (默认 benchmark_results)",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # 设置限流模式
    os.environ["RAG_RATE_LIMIT_MODE"] = args.mode

    # 设置 mock 嵌入
    if args.mock:
        os.environ["RAG_REAL_EMBEDDING"] = "0"
        from app.core.config import settings
        settings.embedding_provider = "mock"
        logger.info("使用 MOCK 嵌入模式")
    else:
        os.environ["RAG_REAL_EMBEDDING"] = "1"
        logger.info("使用真实嵌入模式（需通义 API Key）")

    # 导入后端模块（需在设置环境之后）
    from app.core.database import SessionLocal
    from app.services.ingestion.embedder import _mock_vector
    from tests.benchmark.loaders import list_datasets, get_loader
    from tests.benchmark.rate_limit import RateLimitWrapper
    from tests.benchmark.runner import BenchmarkRunner
    from tests.benchmark.report import ReportGenerator

    # 确定数据集列表
    if args.all:
        dataset_names = list_datasets()
    else:
        dataset_names = [n.strip() for n in args.datasets.split(",")]

    logger.info("评测数据集: %s", dataset_names)
    logger.info("限流模式: %s", args.mode)
    logger.info("Top-K: %d", args.top_k)

    # 创建测试用户和 KB
    kb_id = uuid4()
    user_id = uuid4()

    # 限流器 + 执行引擎
    rate_limit = RateLimitWrapper(mode=args.mode)
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)

    # 注入检索适配器
    async with SessionLocal() as db:
        from tests.benchmark.adapters.retrieval import RetrievalAdapter
        adapter = RetrievalAdapter(db)
        runner.set_retrieve_fn(adapter.retrieve)

        # 报告收集器
        report_gen = ReportGenerator(args.output)

        for name in dataset_names:
            try:
                loader = get_loader(name)
            except KeyError as e:
                logger.error(e)
                continue

            logger.info("开始评测: %s (%s)", name, loader.meta.display_name)
            report = await runner.run_retrieval(
                loader,
                top_k=args.top_k,
                sample_size=args.sample,
            )
            report_gen.add_report(report)

            ret = report.retrieval
            logger.info(
                "%s 完成: Hit@3=%.1f%% MRR=%.4f (延迟 P50=%.0fms)",
                name,
                (ret.hit_at_3 * 100) if ret else 0,
                ret.mean_reciprocal_rank if ret else 0,
                report.p50_latency_ms,
            )

        # 导出报告
        paths = report_gen.export_all("retrieval_benchmark")
        for fmt, p in paths.items():
            logger.info("报告已保存: %s (%s)", p, fmt)

    # 打印限流等待统计
    total_wait = rate_limit.total_waited
    if total_wait > 0:
        logger.info("限流累计等待: %.1f 秒", total_wait)


if __name__ == "__main__":
    asyncio.run(main())

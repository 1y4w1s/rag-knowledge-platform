#!/usr/bin/env python
"""睿阁 Benchmark 统一评测入口（v1.0：支持 retrieval + generation + RAGAS scorer）。

运行方式：
    # 检索评测（默认）
    python -m tests.benchmark.run_benchmark --datasets crag --rate-limit bypass --top-k 3

    # 生成评测
    python -m tests.benchmark.run_benchmark --mode generation --datasets crag --sample 50

    # 使用 RAGAS scorer（需 DEEPSEEK_API_KEY）
    python -m tests.benchmark.run_benchmark --datasets crag --scorer ragas

    # 全部数据集 + RAGAS + 恢复模式
    python -m tests.benchmark.run_benchmark --all --scorer ragas --resume --sample 50

    # 仅查看帮助
    python -m tests.benchmark.run_benchmark --help
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass
class _BeirChunk:
    """BEIR BM25 检索结果的轻量 chunk 包装，兼容 BenchmarkRunner。"""
    chunk_id: str
    content: str
    similarity: float = 0.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_benchmark")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="睿阁 RAG Benchmark 统一评测入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode", dest="bench_mode",
        choices=["retrieval", "generation"],
        default="retrieval",
        help="评测模式：retrieval（检索）或 generation（生成，默认 retrieval）",
    )
    p.add_argument(
        "--datasets", type=str, default="crag",
        help="数据集名称，逗号分隔 (crag, liverag, rageval, ragbench, mirage, enterprise, ...)",
    )
    p.add_argument("--all", action="store_true", help="运行所有已注册数据集")
    p.add_argument(
        "--scorer", choices=["default", "ragas"],
        default="default",
        help="评分器类型：default（内容匹配/LLM-judge）或 ragas（RAGAS 标准 metric）",
    )
    p.add_argument(
        "--rate-limit", choices=["bypass", "enforce"],
        default="bypass", dest="rate_limit_mode",
        help="限流模式 (默认 bypass 提额)",
    )
    p.add_argument("--mock", action="store_true", help="使用 mock 嵌入（快速验证）")
    p.add_argument("--top-k", type=int, default=3, help="检索 Top-K")
    p.add_argument("--sample", type=int, default=None, help="每个数据集抽样数量")
    p.add_argument("--resume", action="store_true", help="从上次检查点恢复")
    p.add_argument(
        "--run-id", type=str, default=None,
        help="运行 ID（用于检查点恢复，默认自动生成）",
    )
    p.add_argument(
        "--output", type=str, default="benchmark_results",
        help="输出目录（默认 benchmark_results）",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    # 设置环境
    os.environ["RAG_RATE_LIMIT_MODE"] = args.rate_limit_mode

    if args.mock:
        os.environ["RAG_REAL_EMBEDDING"] = "0"
        from app.core.config import settings
        settings.embedding_provider = "mock"
        logger.info("使用 MOCK 嵌入模式")
    else:
        os.environ["RAG_REAL_EMBEDDING"] = "1"
        logger.info("使用真实嵌入模式")

    # 导入后端模块
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

    logger.info("评测模式: %s", args.bench_mode)
    logger.info("评分器: %s", args.scorer)
    logger.info("数据集: %s", dataset_names)
    logger.info("限流: %s", args.rate_limit_mode)

    if args.scorer == "ragas":
        logger.info("RAGAS scorer 模式 — 需要 DEEPSEEK_API_KEY 环境变量")

    # 检查是否有 BEIR 数据集
    has_beir = any(n.startswith("beir/") for n in dataset_names)
    has_system = any(not n.startswith("beir/") for n in dataset_names)
    beir_datasets = [n for n in dataset_names if n.startswith("beir/")]
    system_datasets = [n for n in dataset_names if not n.startswith("beir/")]

    if has_beir:
        logger.info("BEIR 数据集: %s", beir_datasets)
    if has_system:
        logger.info("系统数据集: %s", system_datasets)

    kb_id = uuid4()
    user_id = uuid4()
    rate_limit = RateLimitWrapper(mode=args.rate_limit_mode)
    runner = BenchmarkRunner(kb_id=kb_id, user_id=user_id, rate_limit=rate_limit)

    async with SessionLocal() as db:
        if args.bench_mode == "retrieval" and has_system:
            from tests.benchmark.adapters.retrieval import RetrievalAdapter
            adapter = RetrievalAdapter(db)
            runner.set_retrieve_fn(adapter.retrieve)
        elif args.bench_mode == "generation":
            from tests.benchmark.adapters.generation import GenerationAdapter
            adapter = GenerationAdapter(db, kb_id)
            runner.set_generate_fn(adapter.generate)
        else:
            from tests.benchmark.adapters.generation import GenerationAdapter
            adapter = GenerationAdapter(db, kb_id)
            runner.set_generate_fn(adapter.generate)

        report_gen = ReportGenerator(args.output)

        for name in dataset_names:
            try:
                loader = get_loader(name)
            except KeyError as e:
                logger.error(e)
                continue

            is_beir = name.startswith("beir/")

            # BEIR 数据集仅支持 retrieval 模式
            if is_beir and args.bench_mode != "retrieval":
                logger.warning("BEIR 数据集 '%s' 不支持 %s 模式，跳过", name, args.bench_mode)
                continue

            logger.info("开始 %s: %s (%s)", args.bench_mode, name, loader.meta.display_name)

            # BEIR 数据集：使用 BM25 检索而非系统适配器
            if is_beir and args.bench_mode == "retrieval":
                beir_runner = BenchmarkRunner(kb_id=uuid4(), user_id=user_id, rate_limit=rate_limit)
                # 创建 BM25 检索函数
                async def _make_beir_retrieve_fn(loader):
                    # 确保语料库下载并构建索引
                    await loader.download_if_needed()
                    # 返回闭包
                    def _beir_retrieve(query: str, _kb_id=None, top_k: int = 3) -> list:
                        results = loader.search(query, top_k=top_k)
                        chunks = []
                        for r in results:
                            chunks.append(
                                _BeirChunk(
                                    chunk_id=r["doc_id"],
                                    content=r["content"],
                                    similarity=r["score"],
                                )
                            )
                        return chunks
                    return _beir_retrieve

                beir_retrieve_fn = await _make_beir_retrieve_fn(loader)
                beir_runner.set_retrieve_fn(beir_retrieve_fn)
                used_runner = beir_runner
            else:
                used_runner = runner

            if args.bench_mode == "retrieval":
                report = await used_runner.run_retrieval(
                    loader,
                    top_k=args.top_k,
                    sample_size=args.sample,
                    run_id=args.run_id,
                    resume=args.resume,
                    scorer_type=args.scorer if args.scorer == "ragas" else None,
                )

                ret = report.retrieval
                if ret:
                    logger.info(
                        "%s 完成: Hit@3=%.1f%% MRR=%.4f (P50=%.0fms)",
                        name, ret.hit_at_3 * 100, ret.mean_reciprocal_rank,
                        report.p50_latency_ms,
                    )
                    if args.scorer == "ragas":
                        logger.info(
                            "  RAGAS: ContextPrecision=%.3f ContextRecall=%.3f",
                            getattr(ret, "context_precision_avg", 0),
                            getattr(ret, "context_recall_avg", 0),
                        )
            else:
                report = await runner.run_generation(
                    loader,
                    sample_size=args.sample,
                    judge=(args.scorer != "ragas"),
                    faithfulness=(args.scorer != "ragas"),
                    run_id=args.run_id,
                    resume=args.resume,
                    scorer_type=args.scorer if args.scorer == "ragas" else None,
                )

                gen = report.generation
                if gen:
                    logger.info(
                        "%s 完成: 正确性=%.1f%% (P50=%.0fms)",
                        name, gen.correctness * 100, report.p50_latency_ms,
                    )

            report_gen.add_report(report)

        # 导出报告
        suffix = "%s_%s" % (args.bench_mode, args.scorer)
        paths = report_gen.export_all("benchmark_%s" % suffix)
        for fmt, p in paths.items():
            logger.info("报告已保存: %s (%s)", p, fmt)

    # 打印限流统计
    total_wait = rate_limit.total_waited
    if total_wait > 0:
        logger.info("限流累计等待: %.1f 秒", total_wait)


if __name__ == "__main__":
    asyncio.run(main())

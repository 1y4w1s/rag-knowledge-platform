"""检索缓存预热脚本。

用法：
    python scripts/prewarm_cache.py --kb-id <UUID> --queries-file queries.txt

queries.txt 每行一个 query，空行和 # 注释会被跳过。

该脚本只预热检索 chunk 缓存（不调 LLM），适用于批量预加载常见查询。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from uuid import UUID

from app.core.database import SessionLocal
from app.core.latency import get_tracker
from app.services.rag.retrieval import retrieve_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _prewarm(kb_id: UUID, queries: list[str], top_k: int) -> None:
    total = len(queries)
    ok = 0
    fail = 0
    t0 = time.perf_counter()

    for idx, query in enumerate(queries, start=1):
        try:
            async with SessionLocal() as db:
                result = await retrieve_chunks(
                    db,
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    visible_kb_ids=None,
                    hide_admin_only=False,
                )
            ok += 1
            n_chunks = len(result) if result else 0
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                "[%d/%d] ok  chunks=%d  query=%.60s  elapsed=%.0fms",
                idx, total, n_chunks, query, elapsed,
            )
        except Exception as e:
            fail += 1
            logger.error("[%d/%d] FAIL  query=%.60s  reason=%s", idx, total, query, e)

    total_elapsed = (time.perf_counter() - t0)
    logger.info(
        "预热完成: %d/%d ok, %d fail, %.1fs 总计",
        ok, total, fail, total_elapsed,
    )


def _load_queries(path: str) -> list[str]:
    queries: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            queries.append(line)
    return queries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="预热检索 chunk 缓存（不调 LLM）",
    )
    parser.add_argument(
        "--kb-id",
        required=True,
        type=UUID,
        help="知识库 UUID",
    )
    parser.add_argument(
        "--queries-file",
        required=True,
        type=str,
        help="查询文件路径（每行一个 query）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="检索 Top-K（默认 8，与 llm_top_k 一致）",
    )
    args = parser.parse_args()

    queries = _load_queries(args.queries_file)
    if not queries:
        logger.error("查询文件为空或格式错误: %s", args.queries_file)
        sys.exit(1)
    logger.info("加载 %d 条查询，kb_id=%s", len(queries), args.kb_id)

    asyncio.run(_prewarm(args.kb_id, queries, args.top_k))


if __name__ == "__main__":
    main()

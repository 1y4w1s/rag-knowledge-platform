"""pgvector 索引重建（季度维护）。

IVFFlat 索引在频繁 INSERT/UPDATE 后碎片化，检索延迟会逐渐升高。
季度重建索引可恢复检索性能。

用法：:
    python scripts/reindex_pgvector.py              # 干跑，仅报告索引大小
    python scripts/reindex_pgvector.py --apply      # 重建（CONCURRENTLY，不锁表）
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INDEXES = [
    "ix_document_chunks_embedding",
]


async def main(apply: bool = False) -> None:
    from app.core.database import SessionLocal
    from sqlalchemy import text

    async with SessionLocal() as db:
        for idx in INDEXES:
            # 报告索引大小
            r = await db.execute(text("""
                SELECT pg_size_pretty(pg_relation_size(:idx)) as size,
                       pg_relation_size(:idx) as bytes
            """), {"idx": idx})
            row = r.first()
            logger.info("索引 %s: 大小=%s", idx, row[0] if row else "N/A")

            if apply:
                logger.info("重建索引 %s (CONCURRENTLY)...", idx)
                await db.execute(text(f"REINDEX INDEX CONCURRENTLY {idx}"))
                logger.info("索引 %s 重建完成", idx)

    if apply:
        from app.services.ops.maintenance_tracker import record_maintenance
        record_maintenance("reindex_pgvector")
        logger.info("pgvector 索引重建完成")
    else:
        logger.info("干跑模式：未实际重建。加 --apply 执行")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="pgvector 索引重建")
    parser.add_argument("--apply", action="store_true", help="执行重建（CONCURRENTLY）")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))

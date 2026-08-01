"""文档去重脚本（并发上传竞态第二层回退）。

扫描同库同名同指纹文档，保留最早那条，软删其余的。
在维护日历中月跑。

用法：:
    python scripts/dedup_documents.py --apply   # 真删
    python scripts/dedup_documents.py           # 干跑，只看不删
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(dry_run: bool = True) -> None:
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.services.ops.maintenance_tracker import record_maintenance
    from sqlalchemy import select, text

    async with SessionLocal() as db:
        # 查找重复文档
        rows = await db.execute(text("""
            SELECT kb_id, filename, content_sha256, MIN(created_at) as min_created, COUNT(*) as cnt
            FROM documents
            WHERE deleted_at IS NULL AND content_sha256 IS NOT NULL
            GROUP BY kb_id, filename, content_sha256
            HAVING COUNT(*) > 1
        """))
        dupes = rows.all()
        if not dupes:
            logger.info("无重复文档")
            return

        total_deleted = 0
        for d in dupes:
            kb_id, filename, sha256, min_created, cnt = d
            logger.info("重复: kb=%s file=%s cnt=%d", kb_id, filename, cnt)
            # 找出重复中不是最早的那些
            to_delete = await db.execute(text("""
                SELECT id FROM documents
                WHERE kb_id = :kb AND filename = :fn AND content_sha256 = :sha
                  AND deleted_at IS NULL AND created_at > :min_created
            """), {"kb": kb_id, "fn": filename, "sha": sha256, "min_created": min_created})
            ids = [row[0] for row in to_delete]
            if ids and not dry_run:
                await db.execute(text("""
                    UPDATE documents SET deleted_at = :now, status = 'failed',
                        error_message = '去重：同名同内容文档保留最早一条'
                    WHERE id = ANY(:ids)
                """), {"now": datetime.now(timezone.utc), "ids": ids})
                total_deleted += len(ids)
                logger.info("  软删 %d 条重复", len(ids))

        await db.commit()

    if dry_run:
        logger.info("干跑模式：未实际删除。加 --apply 执行")
    else:
        record_maintenance("dedup_documents")
        logger.info("已清理 %d 条重复文档", total_deleted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="文档去重")
    parser.add_argument("--apply", action="store_true", help="执行删除（默认干跑）")
    args = parser.parse_args()
    asyncio.run(main(dry_run=not args.apply))

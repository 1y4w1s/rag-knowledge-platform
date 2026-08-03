"""D1 GraphRAG — 实体 fuzzy 合并（pg_trgm）。

对同 kb_id 内的 entities 表做相似度扫描，
找到近似重复后合并 entity_mentions / relations 引用，再删除冗余实体行。
"""

import logging
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity

logger = logging.getLogger(__name__)

# 实体名相似度阈值（pg_trgm SIMILARITY，0~1）
_SIMILARITY_THRESHOLD = 0.7


async def merge_fuzzy_entities(
    db: AsyncSession,
    kb_id: UUID,
    *,
    threshold: float = _SIMILARITY_THRESHOLD,
    dry_run: bool = True,
) -> dict:
    """扫描单个 kb 内近似重复实体，合并后删除冗余。

    返回合并统计（合并对数、删除行数）。
    默认 dry_run=True，不执行实际写库。
    """
    # 1. 用 pg_trgm 找候选对
    sql = text("""
        SELECT a.id AS keep_id, a.name AS keep_name,
               b.id AS remove_id, b.name AS remove_name,
               similarity(a.name, b.name) AS sim
        FROM entities a
        JOIN entities b ON a.kb_id = b.kb_id
            AND a.type = b.type
            AND a.id < b.id
            AND similarity(a.name, b.name) >= :threshold
        WHERE a.kb_id = :kb_id
        ORDER BY sim DESC
    """)
    try:
        rows = await db.execute(sql, {"kb_id": kb_id, "threshold": threshold})
    except ProgrammingError:
        logger.exception("pg_trgm 扩展未启用，无法执行 fuzzy 合并")
        return {"error": "pg_trgm 扩展未启用", "candidates": 0, "merged": 0}

    candidates = rows.all()

    if not candidates:
        return {"candidates": 0, "merged": 0, "dry_run": dry_run}

    # 2. 逐对合并（保守策略：保留 id 较小的实体，删除 id 较大的）
    merged_pairs = []
    keep_ids: set[UUID] = set()
    remove_ids: set[UUID] = set()

    for row in candidates:
        remove_id = row.remove_id
        if remove_id in remove_ids or remove_id in keep_ids:
            continue  # 已被其他合并处理
        keep_id = row.keep_id
        if keep_id in remove_ids:
            continue  # keep 方已被删，跳过

        merged_pairs.append((keep_id, remove_id))
        keep_ids.add(keep_id)
        remove_ids.add(remove_id)

    if dry_run:
        return {
            "candidates": len(candidates),
            "merged": len(merged_pairs),
            "dry_run": True,
            "pairs": [
                {"keep": str(k), "remove": str(r)}
                for k, r in merged_pairs
            ],
        }

    # 3. 执行合并（同一事务内）
    for keep_id, remove_id in merged_pairs:
        # 3a. entity_mentions：将 remove 的提及指向 keep
        await db.execute(
            text("""
                UPDATE entity_mentions
                SET entity_id = :keep_id
                WHERE entity_id = :remove_id
                AND NOT EXISTS (
                    SELECT 1 FROM entity_mentions existing
                    WHERE existing.chunk_id = entity_mentions.chunk_id
                    AND existing.entity_id = :keep_id2
                )
            """),
            {"keep_id": keep_id, "remove_id": remove_id, "keep_id2": keep_id},
        )

        # 3b. relations：将 remove 的 source/target 改为 keep
        for col, other_col in (("source_id", "target_id"), ("target_id", "source_id")):
            await db.execute(
                text(f"""
                    UPDATE relations
                    SET {col} = :keep_id
                    WHERE {col} = :remove_id
                    AND NOT EXISTS (
                        SELECT 1 FROM relations existing
                        WHERE existing.{col} = :keep_id
                        AND existing.{other_col} = relations.{other_col}
                        AND existing.relation_type = relations.relation_type
                        AND existing.id != relations.id
                    )
                """),
                {"keep_id": keep_id, "remove_id": remove_id},
            )

        # 3c. 删除冗余实体
        await db.execute(
            delete(Entity).where(Entity.id == remove_id)
        )

    await db.flush()

    # 4. 审计事件（仅非 dry_run 且有合并时）
    if merged_pairs:
        from app.services.audit.log import write_audit_log
        await write_audit_log(
            db,
            action="entity_merge_fuzzy",
            resource_type="entity",
            kb_id=kb_id,
            metadata={
                "merged": len(merged_pairs),
                "removed_entities": len(remove_ids),
                "threshold": threshold,
            },
        )

    return {
        "candidates": len(candidates),
        "merged": len(merged_pairs),
        "dry_run": False,
        "removed_entities": len(remove_ids),
    }

"""D1 GraphRAG — 存量文档实体抽取 backfill + 实体 fuzzy 合并。"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.audit.log import write_audit_log
from app.services.rag.entity_extractor import extract_entities_for_document
from app.services.rag.entity_merge import merge_fuzzy_entities

router = APIRouter(prefix="/internal/backfill", tags=["internal"])


@router.post("/entities")
async def post_backfill_entities(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_id: Annotated[str | None, Query(description="限定到单个知识库 UUID")] = None,
    batch_size: Annotated[int, Query(ge=1, le=50, description="单批处理文档数")] = 10,
    dry_run: Annotated[bool, Query(description="仅预览，不执行抽取")] = False,
) -> dict:
    """对存量文档逐条触发实体抽取。

    仅处理 status=completed 且 entity_extracted_at IS NULL 的文档。
    dry_run=True（默认）仅返回待处理文档列表，不执行抽取。
    """
    # 1. 查出待处理文档
    stmt = select(Document).where(
        Document.status == DocumentStatus.completed,
        Document.entity_extracted_at.is_(None),
    )
    if kb_id:
        stmt = stmt.where(Document.kb_id == UUID(kb_id))
    stmt = stmt.limit(batch_size)

    result = await db.execute(stmt)
    docs = result.scalars().all()

    if dry_run:
        return {
            "status": "dry_run",
            "pending": len(docs),
            "kb_id": kb_id,
            "documents": [
                {"id": str(d.id), "filename": d.filename, "kb_id": str(d.kb_id)}
                for d in docs
            ],
        }

    # 2. 逐条抽取（整批 commit）
    succeeded = 0
    failed = 0
    for doc in docs:
        try:
            await extract_entities_for_document(db, doc)
            doc.entity_extracted_at = datetime.now(timezone.utc)
            succeeded += 1
        except Exception:
            failed += 1

    # 审计事件（在 commit 之前，与文档更新同事务）
    await write_audit_log(
        db,
        action="backfill_entities",
        actor_user_id=current_user.id,
        resource_type="system",
        metadata={
            "kb_id": kb_id,
            "succeeded": succeeded,
            "failed": failed,
            "batch_size": batch_size,
        },
    )

    await db.commit()

    return {
        "status": "completed",
        "succeeded": succeeded,
        "failed": failed,
        "kb_id": kb_id,
    }


@router.post("/merge-entities")
async def post_merge_entities(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kb_id: Annotated[str, Query(description="知识库 UUID")],
    threshold: Annotated[float, Query(ge=0.3, le=1.0, description="pg_trgm 相似度阈值")] = 0.7,
    dry_run: Annotated[bool, Query(description="仅预览")] = True,
) -> dict:
    """对单个知识库内的实体做 fuzzy 合并（pg_trgm）。"""
    result = await merge_fuzzy_entities(
        db, UUID(kb_id), threshold=threshold, dry_run=dry_run,
    )

    if not dry_run:
        await db.commit()

    return result

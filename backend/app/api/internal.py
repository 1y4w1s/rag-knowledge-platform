"""运维内部路由：全库重嵌（R2-4）+ orphan 扫描（H2）。

F2（authz-security-survey R1）：JWT 鉴权 + 静态令牌双因子；orphan-scan 真删需 confirm=true。
"""

import hmac
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.services.audit.log import write_audit_log
from app.services.ingestion.embedder import current_bge_en_model
from app.services.ingestion.re_embed import (
    count_en_gap_chunks,
    count_embedding_en_coverage,
    count_stale_chunks,
    re_embed_all_chunks,
    re_embed_en_gap_chunks,
)
from app.services.storage.orphan_scan import (
    apply_orphans,
    load_owner_index,
    report_to_dict,
    scan_orphans,
)

router = APIRouter(prefix="/internal", tags=["internal"])


class ReEmbedRequest(BaseModel):
    """POST /re-embed 可选范围：缺省为全库 stale 重嵌；en_gap 按 kb 补嵌偏英缺口。"""

    kb_id: UUID | None = None
    mode: Literal["stale", "en_gap"] = "stale"


def _check_static_token(provided: str | None, expected: str | None, label: str) -> None:
    """校验静态运维令牌；明文配置为空视为未启用，比较用常量时间避免时序侧信道。"""
    if not expected:
        raise NotFoundError(detail="未启用")
    if not provided or not hmac.compare_digest(provided, expected):
        raise ForbiddenError(detail=f"{label}无效")


async def require_re_embed_operator(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    x_re_embed_token: Annotated[str | None, Header(alias="X-Re-Embed-Token")] = None,
) -> CurrentUser:
    _check_static_token(x_re_embed_token, settings.re_embed_token, "re-embed 令牌")
    return current_user


async def require_orphan_scan_operator(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    x_orphan_scan_token: Annotated[str | None, Header(alias="X-Orphan-Scan-Token")] = None,
) -> CurrentUser:
    _check_static_token(x_orphan_scan_token, settings.orphan_scan_token, "orphan-scan 令牌")
    return current_user


@router.post("/re-embed")
async def post_re_embed(
    background_tasks: BackgroundTasks,
    operator: Annotated[CurrentUser, Depends(require_re_embed_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ReEmbedRequest | None = None,
) -> dict[str, object]:
    """触发后台重嵌；en_gap 按 kb 补嵌偏英缺口（须 JWT + RE_EMBED_TOKEN）。"""
    kb_id = body.kb_id if body is not None else None
    mode = body.mode if body is not None else "stale"
    if mode == "en_gap":
        if kb_id is None:
            raise ValidationError(detail="en_gap 模式必须指定 kb_id")
        en_model = current_bge_en_model()
        en_gap = await count_en_gap_chunks(kb_id=kb_id)
        background_tasks.add_task(re_embed_en_gap_chunks, kb_id=kb_id)
        await write_audit_log(
            db,
            action="re_embed_trigger",
            actor_user_id=operator.id,
            resource_type="system",
            kb_id=kb_id,
            metadata={
                "mode": "en_gap",
                "en_gap_chunks": en_gap,
                "en_model": en_model,
                "kb_id": str(kb_id),
            },
        )
        await db.commit()
        return {
            "status": "started",
            "en_gap_chunks": en_gap,
            "en_model": en_model,
            "operator": str(operator.id),
            "kb_id": str(kb_id),
        }
    stale = await count_stale_chunks(kb_id=kb_id)
    background_tasks.add_task(re_embed_all_chunks, kb_id=kb_id)
    await write_audit_log(
        db,
        action="re_embed_trigger",
        actor_user_id=operator.id,
        resource_type="system",
        kb_id=kb_id,
        metadata={
            "stale_chunks": stale,
            "embedding_model": settings.embedding_model,
            "kb_id": str(kb_id) if kb_id else None,
        },
    )
    await db.commit()
    return {
        "status": "started",
        "stale_chunks": stale,
        "embedding_model": settings.embedding_model,
        "operator": str(operator.id),
        "kb_id": str(kb_id) if kb_id else None,
    }


@router.get("/re-embed/status")
async def get_re_embed_status(
    operator: Annotated[CurrentUser, Depends(require_re_embed_operator)],
    kb_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, object]:
    """查询重嵌进度与 EN 列覆盖度，可按 kb_id 限定（不启动任务）。"""
    stale = await count_stale_chunks(kb_id=kb_id)
    en_coverage = await count_embedding_en_coverage(kb_id=kb_id)
    body: dict[str, object] = {
        "stale_chunks": stale,
        **en_coverage,
        "embedding_model": settings.embedding_model,
        "provider": settings.embedding_provider,
        "operator": str(operator.id),
        "kb_id": str(kb_id) if kb_id else None,
    }
    if kb_id is not None:
        body["en_gap_chunks"] = await count_en_gap_chunks(kb_id=kb_id)
    return body


@router.post("/orphan-scan")
async def post_orphan_scan(
    operator: Annotated[CurrentUser, Depends(require_orphan_scan_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    dry_run: Annotated[bool, Query()] = True,
    confirm: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    """扫描 upload_dir 无主文件；默认干跑，真删需 confirm=true（JWT + ORPHAN_SCAN_TOKEN）。"""
    if not dry_run and not confirm:
        raise BadRequestError(detail="执行删除需显式 confirm=true")

    async with SessionLocal() as scan_db:
        owners = await load_owner_index(scan_db)
        report = scan_orphans(
            owners=owners,
            grace_hours=settings.orphan_grace_hours,
        )
        result = await apply_orphans(
            scan_db,
            report,
            dry_run=dry_run,
            max_delete=settings.orphan_max_delete,
        )
    if not dry_run:
        client_ip = request.client.host if request.client else None
        await write_audit_log(
            db,
            action="orphan_scan_delete",
            actor_user_id=operator.id,
            resource_type="storage",
            metadata={
                "deleted": result.deleted,
                "skipped": result.skipped,
                "errors": result.errors,
                "ip": client_ip,
            },
        )

    return {
        **report_to_dict(report),
        "dry_run": dry_run,
        "deleted": result.deleted,
        "apply_skipped": result.skipped,
        "apply_errors": result.errors,
        "operator": str(operator.id),
    }

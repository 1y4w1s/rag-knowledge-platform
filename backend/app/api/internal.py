"""运维内部路由：全库重嵌（R2-4）+ orphan 扫描（H2）。

F2（authz-security-survey R1）：纳入 JWT 鉴权 + 静态令牌双因子。
- 全局中间件默认拒绝 → /api/v1/internal/* 不再匿名可达，须持合法 JWT（操作可归因）。
- 路由级保留静态令牌（X-Re-Embed-Token / X-Orphan-Scan-Token）作授权第二因子。
- orphan-scan 真删需 confirm=true 二次确认（R1 防误删他租户活动文件护栏），并写审计。
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.audit.log import write_audit_log
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks
from app.services.storage.orphan_scan import (
    apply_orphans,
    load_owner_index,
    report_to_dict,
    scan_orphans,
)

router = APIRouter(prefix="/internal", tags=["internal"])


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
) -> dict[str, object]:
    """触发后台全库重嵌（须 JWT + RE_EMBED_TOKEN）。"""
    stale = await count_stale_chunks()
    background_tasks.add_task(re_embed_all_chunks)
    await write_audit_log(
        db,
        action="re_embed_trigger",
        actor_user_id=operator.id,
        resource_type="system",
        metadata={"stale_chunks": stale, "embedding_model": settings.embedding_model},
    )
    return {
        "status": "started",
        "stale_chunks": stale,
        "embedding_model": settings.embedding_model,
        "operator": str(operator.id),
    }


@router.get("/re-embed/status")
async def get_re_embed_status(
    operator: Annotated[CurrentUser, Depends(require_re_embed_operator)],
) -> dict[str, object]:
    """查询待重嵌 chunk 数量（不启动任务）。"""
    stale = await count_stale_chunks()
    return {
        "stale_chunks": stale,
        "embedding_model": settings.embedding_model,
        "provider": settings.embedding_provider,
        "operator": str(operator.id),
    }


@router.post("/orphan-scan")
async def post_orphan_scan(
    operator: Annotated[CurrentUser, Depends(require_orphan_scan_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    dry_run: Annotated[bool, Query()] = True,
    confirm: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    """扫描 upload_dir 无主文件；默认干跑。须 JWT + ORPHAN_SCAN_TOKEN。

    dry_run=False 执行物理删除时，必须 confirm=true 作为二次确认（R1 防误删护栏）。
    """
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

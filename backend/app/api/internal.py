"""运维内部路由（Plan-RAG R2-4）：全库重嵌入，不对普通用户暴露。"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_re_embed_token(x_re_embed_token: str) -> None:
    if not settings.re_embed_token:
        raise NotFoundError(detail="未启用")
    if x_re_embed_token != settings.re_embed_token:
        raise ForbiddenError(detail="密钥无效")


@router.post("/re-embed")
async def post_re_embed(
    background_tasks: BackgroundTasks,
    x_re_embed_token: Annotated[str, Header(alias="X-Re-Embed-Token")],
) -> dict[str, object]:
    """触发后台全库重嵌（须配置 RE_EMBED_TOKEN）。"""
    _require_re_embed_token(x_re_embed_token)
    stale = await count_stale_chunks()
    background_tasks.add_task(re_embed_all_chunks)
    return {"status": "started", "stale_chunks": stale, "embedding_model": settings.embedding_model}


@router.get("/re-embed/status")
async def get_re_embed_status(
    x_re_embed_token: Annotated[str, Header(alias="X-Re-Embed-Token")],
) -> dict[str, object]:
    """查询待重嵌 chunk 数量（不启动任务）。"""
    _require_re_embed_token(x_re_embed_token)
    stale = await count_stale_chunks()
    return {
        "stale_chunks": stale,
        "embedding_model": settings.embedding_model,
        "provider": settings.embedding_provider,
    }

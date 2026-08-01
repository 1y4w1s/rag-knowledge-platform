"""健康检查（TECH-6：部署假成功时用 /health 探 DB）。
v0.6 新增：降级信息 + 熔断器状态。
"""

import json
import logging

from fastapi import APIRouter

from app.core.database import check_database
from app.core.degradation import (
    DegradationLevel,
    assess_degradation,
    degradation_label,
    get_degradation_events,
)
from app.core.redis import get_redis
from app.core.retry import get_breaker
from app.services.ingestion.embed_health import probe_embed_readiness

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)

BREAKER_NAMES = (
    "deepseek_llm",
    "tongyi_llm",
    "bge_rerank",
    "tongyi_rerank",
    "bge_embed",
    "tongyi_embed",
)


async def _check_redis() -> bool:
    """Redis 连接检查（非关键依赖——失败不影响整体状态）。"""
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False


@router.get("/health")
async def health() -> dict:
    db_ok = await check_database()
    redis_ok = await _check_redis()
    deg_level = assess_degradation()
    events = get_degradation_events(limit=10)

    breakers: dict[str, dict] = {}
    for name in BREAKER_NAMES:
        try:
            cb = get_breaker(name)
            breakers[name] = cb.status()
        except Exception:
            breakers[name] = {"state": "unknown", "failures": -1}

    payload: dict = {
        "status": "ok" if db_ok and redis_ok and deg_level == DegradationLevel.NORMAL else "degraded",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "degradation": {
            "level": int(deg_level),
            "label": degradation_label(deg_level),
            "breakers": breakers,
            "recent_events": events,
        },
    }

    if deg_level >= DegradationLevel.LLM_DOWN:
        logger.warning("健康检查降级: %s", json.dumps(payload, ensure_ascii=False))

    return payload


@router.get("/health/live")
async def health_live() -> dict:
    """Liveness 探针：进程是否存活（Docker healthcheck 用）。"""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> dict:
    """Readiness 探针：数据库 + API Key 是否就绪。"""
    db_ok = await check_database()
    from app.core.config import settings
    keys_ok = bool(settings.deepseek_api_key) and bool(settings.tongyi_api_key)
    ready = db_ok and keys_ok
    return {
        "status": "ok" if ready else "degraded",
        "database": "ok" if db_ok else "error",
        "api_keys_ok": keys_ok,
    }


@router.get("/health/detailed")
async def health_detailed() -> dict:
    """详细健康检查：数据库 + API Key 状态 + 磁盘使用。"""
    db_ok = await check_database()

    # API Key 状态（检查是否已配置，不实际调用 API）
    from app.core.config import settings
    provider = settings.rerank_provider.lower()
    if provider == "bge":
        rerank_ready = settings.rerank_enabled
    elif provider == "tongyi":
        rerank_ready = bool(settings.tongyi_api_key) and settings.rerank_enabled
    else:
        rerank_ready = settings.rerank_enabled
    embed_provider = settings.embedding_provider.lower()
    embed_ready = embed_provider in ("bge", "bge_en", "mock") or bool(
        settings.tongyi_api_key
    )
    api_keys = {
        "deepseek": bool(settings.deepseek_api_key),
        "tongyi": bool(settings.tongyi_api_key),
        "rerank": rerank_ready,
        "embedding": embed_ready,
    }

    # 检索延迟追踪（P50/P95/P99）
    from app.core.latency import all_tracker_stats
    latency = all_tracker_stats(min_count=5)

    # 磁盘使用
    import shutil
    upload_path = settings.upload_dir
    disk = {}
    try:
        usage = shutil.disk_usage(upload_path)
        disk = {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "usage_pct": round(usage.used / usage.total * 100, 1),
        }
    except Exception:
        disk = {"error": "无法获取磁盘信息"}

    # status 仅看 DB + api_keys；ocr / embed / chat 块自报，不参与公式（NW-8 / B3 / NW-9）
    from app.services.rag.chat_llm import resolve_chat_provider

    from app.services.ops.maintenance_tracker import get_maintenance_status

    return {
        "status": "ok" if db_ok and all(api_keys.values()) else "degraded",
        "database": "ok" if db_ok else "error",
        "api_keys": api_keys,
        "latency": latency,
        "disk": disk,
        "ocr": _ocr_health_block(),
        "embed": await probe_embed_readiness(),
        "chat": {"provider": resolve_chat_provider()},
        "maintenance": get_maintenance_status(),
    }


def _ocr_health_block() -> dict:
    """OCR 可选依赖就绪态；不参与整体 status（未装 ≠ degraded）。"""
    from app.services.ingestion.ocr import (
        has_ocr_python_deps,
        is_ocr_enabled,
        is_poppler_on_path,
    )

    return {
        "enabled": is_ocr_enabled(),
        "python_deps": has_ocr_python_deps(),
        "poppler": is_poppler_on_path(),
    }

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
from app.core.retry import get_breaker

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)

BREAKER_NAMES = ("deepseek_llm", "tongyi_rerank", "tongyi_embed")


@router.get("/health")
async def health() -> dict:
    db_ok = await check_database()
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
        "status": "ok" if db_ok and deg_level == DegradationLevel.NORMAL else "degraded",
        "database": "ok" if db_ok else "error",
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

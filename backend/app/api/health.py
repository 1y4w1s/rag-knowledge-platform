"""健康检查（TECH-6：部署假成功时用 /health 探 DB）。"""

from fastapi import APIRouter

from app.core.database import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    db_ok = await check_database()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
    }

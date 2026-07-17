"""数据库连接（Wave 0.2：health 探活；支持本机 Docker 或 Supabase 托管）。"""

from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _connect_args(database_url: str) -> dict:
    """Supabase 等云 Postgres 需要 SSL；本机 Docker 默认不需要。"""
    host = urlparse(database_url.replace("+asyncpg", "")).hostname or ""
    if "supabase.co" in host:
        return {"ssl": "require"}
    return {}


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖占位，Wave 1+ 路由使用。"""
    async with SessionLocal() as session:
        yield session

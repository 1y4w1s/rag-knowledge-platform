"""E4 只读 SQL 查询工具 — sql_query。

安全约束：
1. 独立只读连接（AGENT_DB_URL 优先，READONLY_DATABASE_URL 回退）
2. 仅允许 SELECT / EXPLAIN
3. 禁止多条语句（分号后接非空字符）
4. 敏感表黑名单 users/api_keys/agent_memories/audit_logs
5. 自动追加 LIMIT 100
6. 禁止危险函数 pg_read_file / dblink / COPY
"""

from __future__ import annotations

import logging
import os
import re as _re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

AGENT_DB_URL_ENV = "AGENT_DB_URL"
READONLY_DB_URL_ENV = "READONLY_DATABASE_URL"
FORBIDDEN_TABLES = {"users", "api_keys", "agent_memories", "audit_logs"}
QUERY_MAX_ROWS = 100

_DANGEROUS_FUNC_PATTERNS = [
    r"\bpg_read_file\b",
    r"\bpg_read_binary_file\b",
    r"\bpg_ls_dir\b",
    r"\bpg_stat_file\b",
    r"\blo_export\b",
    r"\blo_import\b",
    r"\bdblink\b",
    r"\bdblink_connect\b",
    r"\bCOPY\b",
]


def _reject_dangerous_functions(sql: str) -> str | None:
    """检查 SQL 中是否包含危险函数，有则返回错误信息，否则返回 None。"""
    for pat in _DANGEROUS_FUNC_PATTERNS:
        if _re.search(pat, sql, _re.IGNORECASE):
            # 去掉首尾的 \b 边界标记，获得可读的函数名
            name = pat
            if name.startswith(r"\b") and name.endswith(r"\b"):
                name = name[2:-2]
            return f"禁止危险函数: {name}"
    return None


def _resolve_db_url() -> str | None:
    """解析数据库连接 URL：AGENT_DB_URL 优先，READONLY_DATABASE_URL 回退。"""
    url = os.environ.get(AGENT_DB_URL_ENV)
    if url:
        return url
    url = os.environ.get(READONLY_DB_URL_ENV)
    if url:
        logger.warning("请迁移到 %s 环境变量（%s 已弃用）", AGENT_DB_URL_ENV, READONLY_DB_URL_ENV)
        return url
    return None


@dataclass
class QueryResult:
    ok: bool
    data: list[dict] = field(default_factory=list)
    summary: str = ""


async def sql_query(sql: str) -> QueryResult:
    """执行只读 SQL 查询。

    Args:
        sql: SELECT / EXPLAIN 语句。

    Returns:
        QueryResult(ok, data, summary)
    """
    from sqlalchemy import text

    sql_stripped = sql.strip()
    if not sql_stripped:
        return QueryResult(ok=False, summary="SQL 为空")

    # 禁止多条语句
    if ";" in sql_stripped.rstrip(";"):
        return QueryResult(ok=False, summary="不允许多条语句")

    # 仅允许 SELECT / EXPLAIN
    if not _re.match(r"^\s*(SELECT|EXPLAIN)\s", sql_stripped, _re.IGNORECASE):
        return QueryResult(ok=False, summary="仅支持 SELECT / EXPLAIN")

    # 敏感表黑名单（含 schema. 前缀）
    lowered = sql_stripped.lower()
    for t in FORBIDDEN_TABLES:
        if _re.search(rf"\b(\w+\.)?{_re.escape(t)}\b", lowered):
            return QueryResult(ok=False, summary=f"禁止访问敏感表: {t}")

    # 危险函数拦截
    danger = _reject_dangerous_functions(sql_stripped)
    if danger is not None:
        return QueryResult(ok=False, summary=danger)

    # 行上限
    if not _re.search(r"\bLIMIT\s+\d+\b", sql_stripped, _re.IGNORECASE):
        sql_stripped += f" LIMIT {QUERY_MAX_ROWS}"

    db_url = _resolve_db_url()
    if not db_url:
        return QueryResult(ok=False, summary=f"sql_query 需要 {AGENT_DB_URL_ENV} 环境变量")

    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            result = await conn.execute(text(sql_stripped))
            rows = [dict(row._mapping) for row in result]
        await engine.dispose()
        logger.info("sql_query: rows=%d sql=%.60s", len(rows), sql)
        return QueryResult(ok=True, data=rows, summary=f"返回 {len(rows)} 行")
    except Exception as e:
        logger.warning("sql_query 失败: %s", e)
        return QueryResult(ok=False, summary=f"sql_query 失败: {e}")

"""sql_query 工具已下线（H2 权限收口 · P0-02/03 闭环）。

背景：raw SQL 工具在多租户下无法可靠施加 visible_kb_ids 行级过滤（无 SQL parser、
禁止新增依赖），且独立连接可直读全库（T4-C2）、EXPLAIN ANALYZE 可绕过只读校验
（T4-C3/T5-14）。经三案对比（移除 / 白名单 / 过滤，见
docs/tasks/audit-h2-sql-query-permission.md §2），结论为 fail-closed 下线：

- 任何调用一律返回「无权限」拒绝（ToolDenial 语义，summary = FORBIDDEN_KB_SUMMARY）；
- runtime 对 summary == "无权限" 自动写 agent.tool_denied 审计（403 语义 + 可审计）；
- 注册表保留 sql_query 名称（LLM 被诱导调用时仍走显式拒绝而非 unknown）；
- LLM planner 不再暴露该工具（planners.py 已移除 schema/描述/独立工具名单）。

后续若确需结构化统计能力，应另立「受控聚合查询」工具（显式 kb_id + service 层
SQLAlchemy 过滤），属新功能立项。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY


@dataclass
class QueryResult:
    ok: bool
    data: list[dict] = field(default_factory=list)
    summary: str = ""


async def sql_query(sql: str, *, tool_scope=None) -> QueryResult:
    """sql_query 已下线：任何输入一律拒绝（fail-closed）。

    Args:
        sql: 原始 SQL（已不执行，仅保留签名兼容调用方）。
        tool_scope: 预留 AgentToolScope；下线后不再使用。

    Returns:
        QueryResult(ok=False, summary="无权限")。
    """
    del sql, tool_scope  # 下线语义：忽略一切输入，拒绝执行
    return QueryResult(ok=False, summary=FORBIDDEN_KB_SUMMARY)

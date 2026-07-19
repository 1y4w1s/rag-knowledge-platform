"""跨模块公共 scope 工具函数（Phase 1 从 search/documents.py 迁移）。

消除 rag/ → search/ 的跨包交叉依赖。
"""

from sqlalchemy import ColumnElement

from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceScope


def kb_scope_clause(
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
) -> ColumnElement[bool]:
    """构造 KB 可见性约束子句。"""
    clause = scope.kb_owner_clause()
    if org_scope is not None:
        clause = clause & org_scope.kb_visibility_clause()
    return clause

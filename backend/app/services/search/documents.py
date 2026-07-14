"""跨库文件名搜索（EW-E1 / Plan-RAG R1-1）。

团队空间叠加 OrgScope（ORG-1.5），与 GET /knowledge-bases 同源可见集。
"""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.enums import DocumentVisibility
from app.models.knowledge_base import KnowledgeBase
from app.schemas.search import SearchDocumentItem, SearchDocumentsResponse
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceScope

MAX_QUERY_LEN = 200
DEFAULT_LIMIT = 50
MAX_LIMIT = 50


def _escape_ilike(value: str) -> str:
    """转义 ILIKE 通配符，避免 % / _ 扩大匹配范围。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def validate_search_query(raw: str) -> str:
    """校验并规范化搜索关键词。"""
    query = raw.strip()
    if not query:
        raise ValueError("搜索关键词不能为空")
    if len(query) > MAX_QUERY_LEN:
        raise ValueError("搜索关键词过长")
    return query


def normalize_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    return min(max(raw, 1), MAX_LIMIT)


def kb_scope_clause(
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
) -> ColumnElement[bool]:
    clause = scope.kb_owner_clause()
    if org_scope is not None:
        clause = clause & org_scope.kb_visibility_clause()
    return clause


async def search_documents_by_filename(
    db: AsyncSession,
    scope: WorkspaceScope,
    query: str,
    limit: int,
    *,
    org_scope: OrgScope | None = None,
    hide_admin_only: bool = False,
) -> SearchDocumentsResponse:
    """在当前 workspace 内按文件名子串搜索文档。"""
    scope_clause = kb_scope_clause(scope, org_scope)
    pattern = f"%{_escape_ilike(query)}%"

    base = (
        select(
            Document.id,
            Document.filename,
            Document.file_type,
            Document.status,
            Document.kb_id,
            KnowledgeBase.name.label("kb_name"),
            Document.created_at,
        )
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(scope_clause)
        .where(Document.filename.ilike(pattern, escape="\\"))
    )
    if hide_admin_only:
        base = base.where(Document.visibility != DocumentVisibility.admin_only)
    base = base.where(Document.deleted_at.is_(None))

    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    )
    total_count = int(total or 0)

    rows = await db.execute(
        base.order_by(Document.created_at.desc()).limit(limit)
    )

    items = [
        SearchDocumentItem(
            doc_id=row.id,
            filename=row.filename,
            file_type=row.file_type,
            status=row.status,
            kb_id=row.kb_id,
            kb_name=row.kb_name,
            created_at=row.created_at,
        )
        for row in rows.all()
    ]

    return SearchDocumentsResponse(
        items=items,
        query=query,
        total=total_count,
        mode="filename",
    )

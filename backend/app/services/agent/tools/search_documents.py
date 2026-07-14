"""G3-1.4 · search_documents 只读 tool（包装 search 服务 · §2.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.org.scope import OrgScope
from app.services.search.content import search_documents_by_content
from app.services.search.documents import (
    normalize_limit,
    search_documents_by_filename,
    validate_search_query,
)
from app.services.workspace.scope import WorkspaceScope

SearchMode = Literal["filename", "content"]
DEFAULT_MODE: SearchMode = "filename"


def normalize_mode(raw: str | None) -> SearchMode:
    """Agent tool 默认 filename · 非法值回退 filename。"""
    if raw == "content":
        return "content"
    return DEFAULT_MODE


def build_result_summary(total: int, mode: SearchMode) -> str:
    if total == 0:
        return "无命中"
    label = "文件名" if mode == "filename" else "正文"
    return f"{label}匹配 {total} 篇"


@dataclass(frozen=True, slots=True)
class SearchDocumentsItem:
    document_id: UUID
    kb_id: UUID
    kb_name: str
    filename: str
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class SearchDocumentsOutput:
    items: tuple[SearchDocumentsItem, ...]
    total: int


@dataclass(frozen=True, slots=True)
class SearchDocumentsToolResult:
    ok: bool
    data: SearchDocumentsOutput | None
    summary: str


def _map_items(
    response_items: list,
) -> tuple[SearchDocumentsItem, ...]:
    return tuple(
        SearchDocumentsItem(
            document_id=item.doc_id,
            kb_id=item.kb_id,
            kb_name=item.kb_name,
            filename=item.filename,
            snippet=item.snippet,
        )
        for item in response_items
    )


async def run_search_documents(
    db: AsyncSession,
    workspace: WorkspaceScope,
    *,
    query: str,
    org_scope: OrgScope | None = None,
    mode: str | None = None,
    limit: int | None = None,
) -> SearchDocumentsToolResult:
    """跨库文档搜索 · scope 由请求上下文注入（G3-1.4 · EW-E1）。"""
    try:
        validated_query = validate_search_query(query)
    except ValueError as exc:
        return SearchDocumentsToolResult(
            ok=False,
            data=None,
            summary=str(exc),
        )

    effective_mode = normalize_mode(mode)
    effective_limit = normalize_limit(limit)

    if effective_mode == "content":
        response = await search_documents_by_content(
            db,
            workspace,
            validated_query,
            effective_limit,
            org_scope=org_scope,
        )
    else:
        response = await search_documents_by_filename(
            db,
            workspace,
            validated_query,
            effective_limit,
            org_scope=org_scope,
        )

    items = _map_items(response.items)
    output = SearchDocumentsOutput(items=items, total=response.total)
    return SearchDocumentsToolResult(
        ok=True,
        data=output,
        summary=build_result_summary(response.total, effective_mode),
    )

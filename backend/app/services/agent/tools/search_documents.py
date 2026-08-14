"""G3-1.4 · search_documents 只读 tool（包装 search 服务 · §2.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.search import SearchDocumentsResponse
from app.services.org.scope import OrgScope
from app.services.search.content import search_documents_by_content
from app.services.search.documents import (
    normalize_limit,
    search_documents_by_filename,
    validate_search_query,
)
from app.services.agent.tools.scope import AgentToolScope, ToolDenial
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


async def _search_documents_once(
    db: AsyncSession,
    workspace: WorkspaceScope,
    query: str,
    limit: int,
    *,
    org_scope: OrgScope | None,
    hide_admin_only: bool,
    mode: SearchMode,
    kb_id: UUID | None,
) -> SearchDocumentsResponse:
    """单次调用 search 服务；kb_id 非 None 时收窄到该库（P2-A2）。"""
    if mode == "content":
        return await search_documents_by_content(
            db,
            workspace,
            query,
            limit,
            org_scope=org_scope,
            hide_admin_only=hide_admin_only,
            kb_id=kb_id,
        )
    return await search_documents_by_filename(
        db,
        workspace,
        query,
        limit,
        org_scope=org_scope,
        hide_admin_only=hide_admin_only,
        kb_id=kb_id,
    )


async def _search_documents_multi_kb(
    db: AsyncSession,
    workspace: WorkspaceScope,
    query: str,
    limit: int,
    *,
    kb_ids: list[UUID],
    org_scope: OrgScope | None,
    hide_admin_only: bool,
    mode: SearchMode,
) -> SearchDocumentsOutput:
    """多库指定 kb_ids：逐库搜索后按创建时间合并，与单库排序口径一致。"""
    keyed: list[tuple[datetime, UUID, SearchDocumentsItem]] = []
    total = 0
    for kb_id in kb_ids:
        response = await _search_documents_once(
            db,
            workspace,
            query,
            limit,
            org_scope=org_scope,
            hide_admin_only=hide_admin_only,
            mode=mode,
            kb_id=kb_id,
        )
        total += response.total
        for raw, mapped in zip(response.items, _map_items(response.items)):
            keyed.append((raw.created_at, raw.doc_id, mapped))
    keyed.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return SearchDocumentsOutput(
        items=tuple(row[2] for row in keyed[:limit]),
        total=total,
    )


async def run_search_documents(
    db: AsyncSession,
    workspace: WorkspaceScope,
    *,
    query: str,
    org_scope: OrgScope | None = None,
    tool_scope: AgentToolScope | None = None,
    mode: str | None = None,
    limit: int | None = None,
    kb_ids: list[UUID] | None = None,
) -> SearchDocumentsToolResult:
    """跨库文档搜索 · kb_ids 与 visible 求交（G3-1.4 · EW-E1 · M6 · P2-A2）。"""
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
    effective_tool_scope = tool_scope or AgentToolScope()

    scope_result = effective_tool_scope.resolve_kb_ids(kb_ids)
    if isinstance(scope_result, ToolDenial):
        return SearchDocumentsToolResult(
            ok=False,
            data=None,
            summary=scope_result.summary,
        )
    if scope_result.kb_ids is not None and not scope_result.kb_ids:
        return SearchDocumentsToolResult(
            ok=True,
            data=SearchDocumentsOutput(items=(), total=0),
            summary=build_result_summary(0, effective_mode),
        )

    if scope_result.kb_ids is not None and len(scope_result.kb_ids) > 1:
        output = await _search_documents_multi_kb(
            db,
            workspace,
            validated_query,
            effective_limit,
            kb_ids=sorted(scope_result.kb_ids),
            org_scope=org_scope,
            hide_admin_only=effective_tool_scope.hide_admin_only,
            mode=effective_mode,
        )
    else:
        kb_id = (
            next(iter(scope_result.kb_ids))
            if scope_result.kb_ids is not None
            else None
        )
        response = await _search_documents_once(
            db,
            workspace,
            validated_query,
            effective_limit,
            org_scope=org_scope,
            hide_admin_only=effective_tool_scope.hide_admin_only,
            mode=effective_mode,
            kb_id=kb_id,
        )
        output = SearchDocumentsOutput(
            items=_map_items(response.items),
            total=response.total,
        )

    return SearchDocumentsToolResult(
        ok=True,
        data=output,
        summary=build_result_summary(output.total, effective_mode),
    )

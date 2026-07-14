"""G3-1.2 · list_knowledge_bases 只读 tool（包装 listing 服务 · §2.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge_base.listing import (
    DEFAULT_LIMIT,
    list_knowledge_bases as fetch_knowledge_bases,
)
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

AGENT_MAX_LIMIT = 24


def normalize_agent_limit(raw: int | None) -> int:
    """Agent tool 默认 24 · 上限 24（G3-1.2 验收）。"""
    if raw is None:
        return DEFAULT_LIMIT
    return min(max(raw, 1), AGENT_MAX_LIMIT)


def build_scope_label(
    workspace: WorkspaceScope,
    org_scope: OrgScope | None,
) -> str:
    """tool_result 摘要字段 · 对齐预览「可见库 N 个 · OrgScope」。"""
    if workspace.kind == WorkspaceKind.personal:
        return "personal"
    if org_scope is not None:
        return "OrgScope"
    return "organization"


def build_result_summary(total: int, scope_label: str) -> str:
    return f"可见库 {total} 个 · {scope_label}"


@dataclass(frozen=True, slots=True)
class ListKnowledgeBasesItem:
    kb_id: UUID
    name: str
    document_count: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ListKnowledgeBasesOutput:
    items: tuple[ListKnowledgeBasesItem, ...]
    total: int
    scope_label: str


@dataclass(frozen=True, slots=True)
class ListKnowledgeBasesToolResult:
    ok: bool
    data: ListKnowledgeBasesOutput
    summary: str


async def run_list_knowledge_bases(
    db: AsyncSession,
    workspace: WorkspaceScope,
    *,
    org_scope: OrgScope | None = None,
    q: str | None = None,
    limit: int | None = None,
) -> ListKnowledgeBasesToolResult:
    """列可见资料库 · scope 由请求上下文注入，不信模型传的 workspace/department。"""
    capped_limit = normalize_agent_limit(limit)
    scope_label = build_scope_label(workspace, org_scope)

    listing = await fetch_knowledge_bases(
        db,
        workspace,
        org_scope=org_scope,
        limit=capped_limit,
        offset=0,
        q=q,
    )

    items = tuple(
        ListKnowledgeBasesItem(
            kb_id=item.id,
            name=item.name,
            document_count=item.document_count,
            updated_at=item.updated_at,
        )
        for item in listing.items
    )
    output = ListKnowledgeBasesOutput(
        items=items,
        total=listing.total,
        scope_label=scope_label,
    )
    return ListKnowledgeBasesToolResult(
        ok=True,
        data=output,
        summary=build_result_summary(listing.total, scope_label),
    )

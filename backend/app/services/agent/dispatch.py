"""G3-2.4 · Agent mode dispatch 辅助（tool_scope / planner / workspace）。

Planner 实现见 `planners.py`（thorough 多步 · edit FAQ）；本模块保留
scope 构建与向后兼容导出。
"""

from __future__ import annotations

from uuid import UUID

from app.models.knowledge_base import KnowledgeBase
from app.services.agent.planners import (
    DocumentWritePlanner,
    EditFaqDraftPlanner,
    LLMPlanner,
    LLMPlannerFactory,
    QueryDepth,
    SafetyFrame,
    SemanticSearchPlanner,
    ThoroughReadPlanner,
    ToolSpec,
    create_document_write_planner,
    create_edit_tool_planner,
    create_tool_planner,
    detect_write_intent,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

__all__ = [
    "EditFaqDraftPlanner",
    "LLMPlanner",
    "LLMPlannerFactory",
    "QueryDepth",
    "SafetyFrame",
    "SemanticSearchPlanner",
    "ThoroughReadPlanner",
    "ToolSpec",
    "build_kb_tool_scope",
    "build_workspace_tool_scope",
    "create_document_write_planner",
    "create_edit_tool_planner",
    "create_tool_planner",
    "detect_write_intent",
    "workspace_scope_for_kb",
]


def build_workspace_tool_scope(org_scope: OrgScope | None) -> AgentToolScope:
    if org_scope is not None:
        return AgentToolScope(visible_kb_ids=org_scope.visible_kb_ids)
    return AgentToolScope(visible_kb_ids=None)


def build_kb_tool_scope(
    kb_id: UUID,
    visible_kb_ids: frozenset[UUID] | None,
) -> AgentToolScope:
    visible = visible_kb_ids if visible_kb_ids is not None else frozenset({kb_id})
    return AgentToolScope(visible_kb_ids=visible, default_kb_id=kb_id)


def workspace_scope_for_kb(kb: KnowledgeBase, *, user_id: UUID) -> WorkspaceScope:
    if kb.owner_user_id is not None:
        return WorkspaceScope(
            kind=WorkspaceKind.personal,
            user_id=user_id,
            org_id=None,
        )
    return WorkspaceScope(
        kind=WorkspaceKind.organization,
        user_id=user_id,
        org_id=kb.owner_org_id,
    )

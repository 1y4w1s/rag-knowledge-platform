"""G3-2.4 · Agent mode dispatch 辅助（tool_scope / planner / workspace）。

G4-2.1：新增编辑模式 Planner（EditFaqDraftPlanner）——只读步 + 末步
generate_faq_draft，绝不把 adopt_draft_to_kb 暴露给模型。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from app.models.knowledge_base import KnowledgeBase
from app.services.agent.runtime import ToolPlanner
from app.services.agent.tools.registry import AgentToolName, ReadOnlyToolName
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentStepRecord, ToolCallPlan
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


class SemanticSearchPlanner:
    """首版精准模式 planner：一步 semantic_search 后结束（与 G3-2.3 测试同构）。"""

    def __init__(self, query: str) -> None:
        self._query = query.strip()
        self._done = False

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index, steps_used, max_steps, prior_steps
        if self._done or not self._query:
            return None
        self._done = True
        return ToolCallPlan(tool_name="semantic_search", args={"query": self._query})


def create_tool_planner(message: str) -> ToolPlanner:
    return SemanticSearchPlanner(message)


# --- G4-2.1 · 编辑模式 Planner -------------------------------------------------

_EDIT_FAQ_DRAFT_NAME_BASE_MAX = 40
_EDIT_FAQ_DRAFT_TITLE_MAX = 40


def _slugify(text: str, max_len: int) -> str:
    """query → 安全文件名 base（保留 CJK/字母/数字/_ · 其余变 _ · 截断）。"""
    kept = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text.strip(), flags=re.UNICODE)
    kept = re.sub(r"_+", "_", kept).strip("_")
    return (kept or "FAQ")[:max_len]


def _collect_search_hits(
    prior_steps: tuple[AgentStepRecord, ...],
) -> list[SemanticSearchHit]:
    """汇总 prior 中 semantic_search 命中的片段（用于推导草稿依据）。"""
    hits: list[SemanticSearchHit] = []
    for rec in prior_steps:
        if (
            rec.tool_name == ReadOnlyToolName.semantic_search.value
            and rec.ok
            and isinstance(rec.data, SemanticSearchOutput)
        ):
            hits.extend(rec.data.hits)
    return hits


def _best_hit(hits: list[SemanticSearchHit]) -> SemanticSearchHit | None:
    if not hits:
        return None
    return max(hits, key=lambda h: h.score)


def _build_draft_args(
    query: str,
    default_kb_id: UUID | None,
    prior_steps: tuple[AgentStepRecord, ...],
) -> dict[str, Any]:
    """末步 generate_faq_draft 入参：由搜索命中推导依据 / 目标库 / 文件名。"""
    hits = _collect_search_hits(prior_steps)
    source_chunk_ids = [str(h.chunk_id) for h in hits]
    if default_kb_id is not None:
        kb_id = default_kb_id  # 库内 edit：强制截断到路径 kb（G4-E19）
    elif hits:
        kb_id = hits[0].kb_id  # /ask：首个命中库（搜索已 enforce visible）
    else:
        kb_id = None  # 无命中 → tool 走 no_source / kb 解析 deny，runtime 拒答（G4-E11）
    base = _slugify(query, _EDIT_FAQ_DRAFT_NAME_BASE_MAX)
    return {
        "kb_id": str(kb_id) if kb_id is not None else None,
        "filename": f"{base}.md",
        "source_chunk_ids": source_chunk_ids,
        "title": (query.strip() or "FAQ")[:_EDIT_FAQ_DRAFT_TITLE_MAX],
    }


class EditFaqDraftPlanner:
    """G4-2.1 · 编辑模式 Planner：只读步 + 末步 generate_faq_draft（≤3 步）。

    确定性步骤规划（非模型驱动 ReAct）：
    - 第 1 步：semantic_search（库内 edit 带 kb_ids=[default_kb_id]；/ask 跨库不带）。
    - 条件第 2 步：若搜索命中且预算允许，get_chunk_excerpt 取最相关片段（只读校验）。
    - 末步：generate_faq_draft，args 由 prior 搜索命中推导。

    绝不输出 adopt_draft_to_kb（服务端写 · 非模型调用 · G4-2.1 红线）。
    """

    def __init__(self, query: str, *, default_kb_id: UUID | None = None) -> None:
        self._query = query.strip()
        self._default_kb_id = default_kb_id
        self._search_done = False
        self._excerpt_done = False
        self._draft_done = False

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index
        # 1) 只读 gather：semantic_search
        if not self._search_done:
            self._search_done = True
            args: dict[str, Any] = {"query": self._query}
            if self._default_kb_id is not None:
                args["kb_ids"] = [str(self._default_kb_id)]
            return ToolCallPlan(
                tool_name=ReadOnlyToolName.semantic_search.value, args=args
            )
        # 2) 可选只读 enrichment：get_chunk_excerpt（保留末步 draft 的预算）
        if not self._excerpt_done:
            best = _best_hit(_collect_search_hits(prior_steps))
            if best is not None and (steps_used + 1) < max_steps:
                self._excerpt_done = True
                return ToolCallPlan(
                    tool_name=ReadOnlyToolName.get_chunk_excerpt.value,
                    args={"chunk_id": str(best.chunk_id)},
                )
        # 3) 末步：generate_faq_draft
        if not self._draft_done:
            self._draft_done = True
            return ToolCallPlan(
                tool_name=AgentToolName.generate_faq_draft.value,
                args=_build_draft_args(
                    self._query, self._default_kb_id, prior_steps
                ),
            )
        return None


def create_edit_tool_planner(
    query: str, *, default_kb_id: UUID | None = None
) -> EditFaqDraftPlanner:
    """工厂：构造编辑模式 planner（G4-2.3 dispatch 调用点将用此）。"""
    return EditFaqDraftPlanner(query, default_kb_id=default_kb_id)


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

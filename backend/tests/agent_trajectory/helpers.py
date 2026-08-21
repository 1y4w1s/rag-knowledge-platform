"""Trajectory 测共用：mock 命中 / mock-LLM planner / 线程夹具。"""

from __future__ import annotations

import json
import uuid

from app.core.database import SessionLocal
from app.services.agent.planners import NextActionPlanner, SafetyFrame
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import AgentDecision, DecisionParseResult
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


def hits_sufficient() -> tuple[SemanticSearchHit, ...]:
    return tuple(
        SemanticSearchHit(
            chunk_id=uuid.uuid4(),
            kb_id=uuid.uuid4(),
            kb_name="kb",
            doc_name=f"doc{i}.md",
            page=i,
            section_title="s",
            excerpt=f"excerpt {i}",
            score=0.9 - i * 0.01,
        )
        for i in range(3)
    )


def hits_weak_one() -> tuple[SemanticSearchHit, ...]:
    return (
        SemanticSearchHit(
            chunk_id=uuid.uuid4(),
            kb_id=uuid.uuid4(),
            kb_name="kb",
            doc_name="only.md",
            page=1,
            section_title="s",
            excerpt="half",
            score=0.91,
        ),
    )


def search_ok(
    query: str = "q",
    hits: tuple[SemanticSearchHit, ...] | None = None,
) -> SemanticSearchToolResult:
    resolved = hits if hits is not None else hits_sufficient()
    return SemanticSearchToolResult(
        ok=True,
        summary=f"命中 {len(resolved)} · {query[:40]}",
        data=SemanticSearchOutput(hits=resolved, retrieval_ms=12),
    )


def mock_parse(decision: AgentDecision) -> DecisionParseResult:
    payload: dict = {
        "action": decision.action.value,
        "reason_code": decision.reason_code,
    }
    if decision.tool_name:
        payload["tool_name"] = decision.tool_name
        payload["args"] = decision.args
    if decision.user_message:
        payload["user_message"] = decision.user_message
    return DecisionParseResult(
        ok=True,
        decision=decision,
        llm_raw=json.dumps(payload, ensure_ascii=False),
    )


def personal_workspace(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def create_personal_thread(user_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


class QueueMockLLMPlanner(NextActionPlanner):
    """mock-LLM：按队列返回 DecisionParseResult，走真实 decide_next/gate。"""

    def __init__(self, query: str, queue: list[AgentDecision]) -> None:
        safety = SafetyFrame(query)
        super().__init__(
            query, safety_frame=safety, tool_specs=safety.all_tool_specs()
        )
        self._queue = list(queue)
        self.decisions_seen: list[AgentDecision] = []

    async def _call_llm(self, summary, tool_specs):  # type: ignore[no-untyped-def]
        del summary, tool_specs
        if not self._queue:
            return DecisionParseResult(ok=False, error="script_exhausted")
        return mock_parse(self._queue.pop(0))

    async def decide_next(self, state):  # type: ignore[no-untyped-def]
        decision = await super().decide_next(state)
        self.decisions_seen.append(decision)
        return decision

"""G1 W2 · runtime 工具失败替换 / 熔断早停 / 重规划计数接线测试。

覆盖实施文档 §9.2 六条用例：等价替换、熔断早停、denied 不替换、
SSE 顺序、替换深度 1、agent.tool_replanned 审计 metadata。
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.retry import get_breaker, reset_all_breakers
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import AgentRunStatus, DocumentStatus
from app.schemas.auth import UserPublic
from app.services.agent.runs import get_agent_run_for_user
from app.services.agent.runtime import run_react_loop
from app.services.agent.stream import stream_agent_workspace_events
from app.services.agent.tools.guard import (
    ensure_agent_tool_breakers,
    tool_breaker_name,
)
from app.services.agent.tools.grep_in_document import (
    GrepInDocumentOutput,
    GrepInDocumentToolResult,
    GrepMatch,
)
from app.services.agent.tools.scope import (
    FORBIDDEN_KB_SUMMARY,
    AgentToolScope,
)
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
    SearchDocumentsToolResult,
)
from app.services.agent.tools.semantic_search import SemanticSearchToolResult
from app.services.agent.types import (
    AgentBudgetEvent,
    AgentStepRecord,
    ToolCallPlan,
    ToolResultEvent,
    ToolStartEvent,
)
from app.services.audit.agent import audit_agent_tool_replanned
from app.services.rag.thread_persistence import (
    create_workspace_thread,
)
from app.services.workspace.scope import (
    WorkspaceKind,
    WorkspaceScope,
    resolve_workspace,
)
from tests.conftest import create_test_kb


@pytest.fixture(autouse=True)
def _disable_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """单测 infra：关闭指数退避，避免每个失败用例等待约 1s。"""
    monkeypatch.setattr(settings, "retry_max_attempts", 0)


@pytest.fixture(autouse=True)
def _reset_breakers() -> None:
    ensure_agent_tool_breakers()
    reset_all_breakers()
    yield
    reset_all_breakers()


def _personal_workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def _create_personal_thread(user_id: UUID) -> UUID:
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


@dataclass
class SequencePlanner:
    plans: list[ToolCallPlan | None]
    calls: int = 0

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
        if self.calls >= len(self.plans):
            return None
        plan = self.plans[self.calls]
        self.calls += 1
        return plan


@dataclass
class RecordingHooks:
    starts: list[ToolStartEvent] = field(default_factory=list)
    results: list[ToolResultEvent] = field(default_factory=list)
    budgets: list[AgentBudgetEvent] = field(default_factory=list)

    async def on_tool_start(self, event: ToolStartEvent) -> None:
        self.starts.append(event)

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        self.results.append(event)

    async def on_agent_budget(self, event: AgentBudgetEvent) -> None:
        self.budgets.append(event)


def _search_documents_result(
    *,
    document_id: UUID,
    kb_id: UUID,
) -> SearchDocumentsToolResult:
    return SearchDocumentsToolResult(
        ok=True,
        data=SearchDocumentsOutput(
            items=(
                SearchDocumentsItem(
                    document_id=document_id,
                    kb_id=kb_id,
                    kb_name="制度库",
                    filename="年假手册.md",
                ),
            ),
            total=1,
        ),
        summary="正文匹配 1 篇",
    )


def _grep_result(chunk_id: UUID) -> GrepInDocumentToolResult:
    return GrepInDocumentToolResult(
        ok=True,
        data=GrepInDocumentOutput(
            matches=(
                GrepMatch(
                    chunk_id=chunk_id,
                    doc_name="年假手册.md",
                    content="员工年假 10 天，需提前申请",
                    page_number=1,
                    section_title="年假",
                ),
            ),
        ),
        summary="found 1 matches in 年假手册.md",
    )


async def _raise_infra(*args, **kwargs) -> None:
    del args, kwargs
    raise RuntimeError("embedding provider down")


@pytest.mark.asyncio
async def test_runtime_substitutes_on_infra_failure(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """planner 出 semantic_search，dispatch 抛 RuntimeError → 替换两步并成功收口。"""
    _, user = await register_and_login(prefix="g1-runtime-sub")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="semantic_search", args={"query": "年假制度"}), None]
    )

    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", _raise_infra
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents",
        AsyncMock(
            return_value=_search_documents_result(
                document_id=doc_id, kb_id=kb_id
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_grep_in_document",
        AsyncMock(return_value=_grep_result(chunk_id)),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假制度",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == [
        "semantic_search",
        "search_documents",
        "grep_in_document",
    ]
    assert outcome.steps[0].ok is False
    assert outcome.steps[1].ok is True
    assert outcome.steps[2].ok is True
    assert outcome.steps_used == 3
    assert outcome.capped is False
    assert outcome.tool_fallback_count == 2
    assert outcome.tool_replanned == 0


@pytest.mark.asyncio
async def test_runtime_breaker_open_freezes_only_that_tool(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """web_search breaker open → 只冻结 web_search，其余工具照常执行。"""
    _, user = await register_and_login(prefix="g1-runtime-breaker")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="semantic_search", args={"query": "最近行业动态"}),
            ToolCallPlan(tool_name="web_search", args={"query": "最近行业动态"}),
            None,
        ]
    )

    breaker = get_breaker(tool_breaker_name("web_search"))
    breaker.record_failure()
    breaker.record_failure()
    monkeypatch.setattr(
        "app.services.agent.runtime.find_equivalent_tool",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(
            return_value=SemanticSearchToolResult(
                ok=True,
                data=None,
                summary="ok",
            )
        ),
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假制度",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == [
        "web_search",
        "semantic_search",
    ]
    assert outcome.steps[0].ok is False
    assert outcome.steps[1].ok is True
    assert outcome.steps_used == 2
    assert outcome.tool_fallback_count == 0
    assert outcome.tool_replanned == 0

    async with SessionLocal() as db:
        run = await get_agent_run_for_user(
            db, run_id=outcome.run_id, user_id=user_id
        )
    assert run is not None
    assert run.status == AgentRunStatus.completed


@pytest.mark.asyncio
async def test_runtime_no_substitution_for_denied(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FORBIDDEN_KB_SUMMARY → 不替换、不重规划，agent.tool_denied 审计保留。"""
    _, user = await register_and_login(prefix="g1-runtime-denied")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="semantic_search", args={"query": "年假制度"}), None]
    )

    async def _denied(*args, **kwargs) -> SemanticSearchToolResult:
        del args, kwargs
        return SemanticSearchToolResult(
            ok=False,
            data=None,
            summary=FORBIDDEN_KB_SUMMARY,
        )

    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", _denied
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假制度",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 1
    assert len(outcome.steps) == 1
    assert outcome.steps[0].ok is False
    assert outcome.tool_fallback_count == 0
    assert outcome.tool_replanned == 0

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "agent.tool_denied",
                    AuditLog.resource_id == outcome.run_id,
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].details["tool"] == "semantic_search"
    assert rows[0].details["reason"] == "forbidden_kb"


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in re.split(r"\n\n+", raw.strip()):
        if not block.strip():
            continue
        event_name = "message"
        data_str = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data_str = line.removeprefix("data: ").strip()
        if data_str:
            events.append((event_name, json.loads(data_str)))
    return events


async def _collect_stream_frames(gen) -> tuple[str, list[tuple[str, dict]]]:
    raw = ""
    async for frame in gen:
        raw += frame
    return raw, _parse_sse_events(raw)


@pytest.mark.asyncio
async def test_runtime_sse_order_with_fallback(
    client,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSE：tool_start/tool_result 全部在首条 citation 前，token 在其后，done 最后。"""
    headers, user = await register_and_login(prefix="g1-runtime-sse")
    user_id = UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="替换 SSE 库")
    kb_id = UUID(kb["id"])
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="年假手册.md",
                file_type="md",
                file_size=10,
                storage_path=f"/tmp/g1/{doc_id}.md",
                status=DocumentStatus.queued,
                uploaded_by=user_id,
            )
        )
        db.add(
            DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                kb_id=kb_id,
                chunk_index=0,
                section_title="年假",
                content="员工年假 10 天，需提前申请",
            )
        )
        await db.commit()

    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", _raise_infra
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents",
        AsyncMock(
            return_value=_search_documents_result(
                document_id=doc_id, kb_id=kb_id
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_grep_in_document",
        AsyncMock(return_value=_grep_result(chunk_id)),
    )

    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        thread_id = thread.id

        current_user = UserPublic.model_validate(user)
        scope = await resolve_workspace(db, current_user, "personal")
        planner = SequencePlanner(
            [
                ToolCallPlan(
                    tool_name="semantic_search",
                    args={"query": "员工年假有几天？"},
                ),
                None,
            ]
        )
        raw, events = await _collect_stream_frames(
            stream_agent_workspace_events(
                db,
                scope=scope,
                org_scope=None,
                user_id=user_id,
                message="员工年假有几天？",
                department_id=None,
                thread_id=thread_id,
                tool_scope=AgentToolScope(visible_kb_ids=None),
                planner=planner,
            )
        )
        await db.commit()

    assert raw
    tool_names = [data["tool"] for name, data in events if name == "tool_start"]
    assert tool_names == ["semantic_search", "search_documents", "grep_in_document"]

    first_citation = next(
        (i for i, (name, _) in enumerate(events) if name == "citation"), None
    )
    assert first_citation is not None, "替换后的 grep 证据应生成 citation"
    last_tool_idx = max(
        i
        for i, (name, _) in enumerate(events)
        if name in {"tool_start", "tool_result", "agent_budget"}
    )
    assert last_tool_idx < first_citation
    first_token = next(i for i, (name, _) in enumerate(events) if name == "token")
    assert first_citation < first_token
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_runtime_substitution_depth_one(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """等价替换步骤自身失败 → 不再递归替换，交回 planner 正常收口。"""
    _, user = await register_and_login(prefix="g1-runtime-depth")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="semantic_search", args={"query": "年假制度"}), None]
    )

    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", _raise_infra
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents",
        AsyncMock(
            return_value=_search_documents_result(
                document_id=doc_id, kb_id=kb_id
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_grep_in_document", _raise_infra
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假制度",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == [
        "semantic_search",
        "search_documents",
        "grep_in_document",
    ]
    assert outcome.steps[0].ok is False
    assert outcome.steps[1].ok is True
    assert outcome.steps[2].ok is False
    assert outcome.steps_used == 3
    assert outcome.tool_fallback_count == 2
    assert outcome.tool_replanned == 0


@pytest.mark.asyncio
async def test_audit_tool_replanned_metadata(register_and_login) -> None:
    """agent.tool_replanned metadata 仅含 run_id/step/tool/kind/fallback_tool/replan_count。"""
    _, user = await register_and_login(prefix="g1-audit-replan")
    user_id = UUID(user["id"])
    run_id = uuid.uuid4()

    async with SessionLocal() as db:
        await audit_agent_tool_replanned(
            db,
            actor_user_id=user_id,
            run_id=run_id,
            step=2,
            tool="semantic_search",
            kind="infra",
            fallback_tool="get_chunk_excerpt",
            replan_count=1,
        )
        await db.commit()

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "agent.tool_replanned",
                    AuditLog.resource_id == run_id,
                )
            )
        ).scalars().all()
    assert rows
    row = rows[0]
    assert row.resource_id == run_id
    assert row.details == {
        "run_id": str(run_id),
        "step": 2,
        "tool": "semantic_search",
        "kind": "infra",
        "fallback_tool": "get_chunk_excerpt",
        "replan_count": 1,
    }
    assert "query" not in row.details
    assert "用户问题" not in json.dumps(row.details, ensure_ascii=False)

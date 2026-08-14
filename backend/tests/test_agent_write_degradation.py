"""G4/G5 写类链路降级 W1：LLM_DOWN 下 G4 编辑模式确定性基线。

契约：docs/tasks/audit-g4g5-write-degradation-plan.md §5 W1。
- LLM_DOWN 下 edit 流仍确定性生成 FAQ 草稿（_compose_faq_draft）；
- stream_deepseek_tokens 零调用；SSE 事件序 tool* → citation → token →
  approval_required/refusal → done 不变；落库 completed；G4-E11 no_source 先拒答。
不预埋未消费开关/守卫/指标；未来润色接入须同窗消费 degradation_requires_llm()。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel, degradation_message
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    AgentRunStatus,
    ApprovalStatus,
    DocumentStatus,
    DocumentVisibility,
    MessageRole,
    MessageStatus,
)
from app.services.agent.dispatch import create_edit_tool_planner
from app.services.agent.stream import stream_agent_kb_edit_events
from app.services.agent.tools.get_chunk_excerpt import (
    GetChunkExcerptOutput,
    GetChunkExcerptToolResult,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.rag.thread_persistence import create_kb_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import create_test_kb


QUERY = "年假制度 FAQ"
SECTION_TITLE = "1.2 年假"
CONTENT = "员工年假规定为 10 天，需提前申请。"
DOC_NAME = "员工手册.md"


def _degradation_text() -> str:
    return degradation_message(DegradationLevel.LLM_DOWN)


def _parse_frame(frame: str) -> tuple[str, dict]:
    assert frame.startswith("event: "), frame
    rest = frame[len("event: "):]
    ev, _sep, data_str = rest.partition("\ndata: ")
    return ev, json.loads(data_str.strip())


def _first(events: list[tuple[str, dict]], name: str) -> dict:
    for ev, data in events:
        if ev == name:
            return data
    raise AssertionError(f"event not found: {name}")


def _names(events: list[tuple[str, dict]]) -> list[str]:
    return [ev for ev, _ in events]


def _patch_llm_down(
    monkeypatch: pytest.MonkeyPatch,
    *,
    level: DegradationLevel = DegradationLevel.LLM_DOWN,
    no_key: bool = False,
) -> dict[str, int]:
    """权威判定钉在指定等级；双无 key 时清空 chat key。两条生成入口换成计数桩。"""
    calls = {"stream": 0, "engine": 0}

    if no_key:
        monkeypatch.setattr(settings, "chat_provider", "deepseek")
        monkeypatch.setattr(settings, "deepseek_api_key", "")
        monkeypatch.setattr(settings, "tongyi_api_key", "")

    async def _never_stream(_messages: list) -> None:
        calls["stream"] += 1
        yield "不应到达"

    async def _never_engine(_messages: list) -> None:
        calls["engine"] += 1
        yield "不应到达"

    for target in (
        "app.core.degradation.assess_degradation",
        "app.services.agent.stream.assess_degradation",
        "app.services.rag.engine.assess_degradation",
    ):
        monkeypatch.setattr(target, lambda: level)
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _never_stream
    )
    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens", _never_engine
    )
    return calls


async def _create_kb_doc_chunk(
    client,
    headers: dict[str, str],
    user: dict,
    tmp_path: Path,
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """个人库 + 库内 thread + 一篇文档一个片段（不触发入库 / 嵌入）。"""
    kb = await create_test_kb(client, headers, user, name="W1 降级库")
    kb_id = UUID(kb["id"])
    user_id = UUID(user["id"])
    doc_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    async with SessionLocal() as db:
        thread = await create_kb_thread(db, kb_id=kb_id, user_id=user_id)
        db.add(Document(
            id=doc_id, kb_id=kb_id, filename=DOC_NAME, file_type="md",
            file_size=len(CONTENT.encode("utf-8")),
            storage_path=str(tmp_path / "w1-handbook.md"),
            status=DocumentStatus.completed,
            visibility=DocumentVisibility.everyone,
        ))
        await db.flush()
        db.add(DocumentChunk(
            id=chunk_id, document_id=doc_id, kb_id=kb_id, chunk_index=0,
            page_number=1, section_title=SECTION_TITLE,
            heading_path=SECTION_TITLE, content=CONTENT,
        ))
        await db.commit()
        thread_id = thread.id
    return user_id, kb_id, thread_id, doc_id, chunk_id


def _semantic_tool_result(kb_id: UUID, chunk_id: UUID) -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=chunk_id, kb_id=kb_id, kb_name="W1 降级库", doc_name=DOC_NAME,
        page=1, section_title=SECTION_TITLE, excerpt=CONTENT, score=0.95,
    )
    return SemanticSearchToolResult(
        ok=True,
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
        summary="命中 1 条",
    )


def _excerpt_tool_result(
    kb_id: UUID,
    chunk_id: UUID,
    doc_id: UUID,
) -> GetChunkExcerptToolResult:
    return GetChunkExcerptToolResult(
        ok=True,
        data=GetChunkExcerptOutput(
            chunk_id=chunk_id, document_id=doc_id, doc_name=DOC_NAME, page=1,
            section_title=SECTION_TITLE, excerpt=CONTENT, kb_id=kb_id,
            kb_name="W1 降级库",
        ),
        summary="员工手册.md p.1 摘录",
    )


async def _run_kb_edit(
    monkeypatch: pytest.MonkeyPatch,
    *,
    user_id: UUID,
    kb_id: UUID,
    thread_id: UUID,
    doc_id: UUID,
    chunk_id: UUID,
    with_hits: bool = True,
    dual_no_key: bool = False,
) -> tuple[list[tuple[str, dict]], dict[str, int]]:
    """驱动真实库内 edit SSE（默认 LLM_DOWN 注入），返回事件列表与 LLM 计数。"""
    calls = _patch_llm_down(
        monkeypatch,
        level=(
            DegradationLevel.NORMAL if dual_no_key else DegradationLevel.LLM_DOWN
        ),
        no_key=dual_no_key,
    )
    if with_hits:
        monkeypatch.setattr(
            "app.services.agent.runtime.run_semantic_search",
            AsyncMock(return_value=_semantic_tool_result(kb_id, chunk_id)),
        )
        monkeypatch.setattr(
            "app.services.agent.runtime.run_get_chunk_excerpt",
            AsyncMock(return_value=_excerpt_tool_result(kb_id, chunk_id, doc_id)),
        )
    else:
        no_hits = SemanticSearchToolResult(
            ok=True,
            data=SemanticSearchOutput(hits=(), retrieval_ms=0),
            summary="无命中",
        )
        monkeypatch.setattr(
            "app.services.agent.runtime.run_semantic_search",
            AsyncMock(return_value=no_hits),
        )

    planner = create_edit_tool_planner(QUERY, default_kb_id=kb_id)
    frames: list[str] = []
    async with SessionLocal() as db:
        stream = stream_agent_kb_edit_events(
            db,
            kb_id=kb_id,
            user_id=user_id,
            message=QUERY,
            thread_id=thread_id,
            workspace=WorkspaceScope(
                kind=WorkspaceKind.personal, user_id=user_id, org_id=None
            ),
            tool_scope=AgentToolScope(
                visible_kb_ids=frozenset({kb_id}), default_kb_id=kb_id
            ),
            planner=planner,
            can_adopt=True,
        )
        async for frame in stream:
            frames.append(frame)
    return [_parse_frame(f) for f in frames], calls


async def _assert_persisted(
    *,
    run_id: UUID,
    thread_id: UUID,
    expect_approval: bool,
    expect_contain: str | None = None,
) -> None:
    async with SessionLocal() as db:
        approval = await db.scalar(
            select(AgentApproval).where(AgentApproval.run_id == run_id)
        )
        if expect_approval:
            assert approval is not None
            assert approval.status == ApprovalStatus.pending
        else:
            assert approval is None
        run = await db.get(AgentRun, run_id)
        assert run is not None
        assert run.status == AgentRunStatus.completed
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.created_at)
            )
        ).scalars().all()
        assistant = next(r for r in rows if r.role == MessageRole.assistant)
        assert assistant.status == MessageStatus.completed
        if expect_contain is not None:
            assert expect_contain in assistant.content
@pytest.mark.asyncio
async def test_edit_zero_llm_calls_on_llm_down(
    client,
    register_and_login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM_DOWN 下 edit 流零 LLM 调用、事件序不变、落库 completed / pending。"""
    headers, user = await register_and_login(prefix="g4-w1-degrade")
    user_id, kb_id, thread_id, doc_id, chunk_id = await _create_kb_doc_chunk(
        client, headers, user, tmp_path
    )

    events, calls = await _run_kb_edit(
        monkeypatch,
        user_id=user_id,
        kb_id=kb_id,
        thread_id=thread_id,
        doc_id=doc_id,
        chunk_id=chunk_id,
        with_hits=True,
    )

    names = _names(events)
    assert names == [
        "tool_start",
        "tool_result",
        "agent_budget",
        "tool_start",
        "tool_result",
        "agent_budget",
        "tool_start",
        "tool_result",
        "agent_budget",
        "citation",
        "token",
        "approval_required",
        "done",
    ], names
    assert calls == {"stream": 0, "engine": 0}

    approval_event = _first(events, "approval_required")
    done_event = _first(events, "done")
    assert approval_event["approval_id"] == done_event["approval_id"]
    await _assert_persisted(
        run_id=UUID(done_event["agent_run_id"]),
        thread_id=thread_id,
        expect_approval=True,
        expect_contain="FAQ 草稿",
    )


@pytest.mark.asyncio
async def test_edit_deterministic_draft_on_llm_down(
    client,
    register_and_login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM_DOWN 下草稿由确定性组装产出，不含对话降级文案。"""
    headers, user = await register_and_login(prefix="g4-w1-draft")
    user_id, kb_id, thread_id, doc_id, chunk_id = await _create_kb_doc_chunk(
        client, headers, user, tmp_path
    )

    events, calls = await _run_kb_edit(
        monkeypatch,
        user_id=user_id,
        kb_id=kb_id,
        thread_id=thread_id,
        doc_id=doc_id,
        chunk_id=chunk_id,
        with_hits=True,
    )

    assert calls == {"stream": 0, "engine": 0}
    run_id = UUID(_first(events, "done")["agent_run_id"])
    async with SessionLocal() as db:
        approval = await db.scalar(
            select(AgentApproval).where(AgentApproval.run_id == run_id)
        )
        assert approval is not None
        markdown = approval.payload_json["markdown"]

    # _compose_faq_draft 确定性结构：标题 / 检索章节 / 片段正文
    assert markdown.startswith(f"# FAQ：{QUERY}")
    assert f"## 问：关于「{SECTION_TITLE}」" in markdown
    assert f"答：{CONTENT}" in markdown
    assert _degradation_text() not in markdown

    token_text = "".join(
        data.get("text", "") for ev, data in events if ev == "token"
    )
    assert "FAQ 草稿" in token_text
    assert _degradation_text() not in token_text


@pytest.mark.asyncio
async def test_edit_dual_no_key_draft_no_placeholder_or_degradation(
    client,
    register_and_login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双无 key（判定 NORMAL）：edit 流仍确定性生成 FAQ 草稿，零 LLM。"""
    headers, user = await register_and_login(prefix="g4-dual-nokey")
    user_id, kb_id, thread_id, doc_id, chunk_id = await _create_kb_doc_chunk(
        client, headers, user, tmp_path
    )

    events, calls = await _run_kb_edit(
        monkeypatch,
        user_id=user_id,
        kb_id=kb_id,
        thread_id=thread_id,
        doc_id=doc_id,
        chunk_id=chunk_id,
        with_hits=True,
        dual_no_key=True,
    )

    assert calls == {"stream": 0, "engine": 0}
    run_id = UUID(_first(events, "done")["agent_run_id"])
    async with SessionLocal() as db:
        approval = await db.scalar(
            select(AgentApproval).where(AgentApproval.run_id == run_id)
        )
        assert approval is not None
        markdown = approval.payload_json["markdown"]

    assert markdown.startswith(f"# FAQ：{QUERY}")
    assert f"答：{CONTENT}" in markdown
    assert "根据知识库内容回答" not in markdown
    assert _degradation_text() not in markdown

    token_text = "".join(
        data.get("text", "") for ev, data in events if ev == "token"
    )
    assert "FAQ 草稿" in token_text
    assert "根据知识库内容回答" not in token_text
    assert _degradation_text() not in token_text


@pytest.mark.asyncio
async def test_edit_no_source_gate_wins_on_llm_down(
    client,
    register_and_login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G4-E11 无依据 gate 先于降级：LLM_DOWN 下仍拒答，不发 approval。"""
    headers, user = await register_and_login(prefix="g4-w1-nosrc")
    user_id, kb_id, thread_id, doc_id, chunk_id = await _create_kb_doc_chunk(
        client, headers, user, tmp_path
    )

    events, calls = await _run_kb_edit(
        monkeypatch,
        user_id=user_id,
        kb_id=kb_id,
        thread_id=thread_id,
        doc_id=doc_id,
        chunk_id=chunk_id,
        with_hits=False,
    )

    names = _names(events)
    assert "approval_required" not in names
    assert "refusal" in names
    assert names[-1] == "done"
    refusal = _first(events, "refusal")
    assert refusal["reason"] == "no_source"
    assert "未检索到" in refusal["message"]
    done_event = _first(events, "done")
    assert done_event["approval_id"] is None
    assert done_event["approval_status"] is None
    assert calls == {"stream": 0, "engine": 0}

    await _assert_persisted(
        run_id=UUID(done_event["agent_run_id"]),
        thread_id=thread_id,
        expect_approval=False,
        expect_contain="未检索到",
    )

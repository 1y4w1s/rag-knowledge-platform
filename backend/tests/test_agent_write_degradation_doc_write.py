"""G4/G5 写类链路降级 W2 · G5 文档操作降级边界固化（A/B 提案 SSE + clarify）。

契约：docs/tasks/audit-g4g5-write-degradation-plan.md §5 W2。LLM_DOWN 下
delete / restore A 路径 SSE 仍产出确定性提案（proposal_preview），事件序
tool* → token → proposal_preview → done 不变，落库 completed 不建 pending；
B 路径 detect_write_intent 仍确定性路由且 double_confirm=True 提案正常；
Owner clarify → 结构化提案（dry），零 LLM 依赖；不预埋未消费开关 / 守卫 /
指标；未来写类链路接入 LLM 须同窗消费 degradation_requires_llm()。
submit / resolve adopt / Member 权限另见 test_agent_write_degradation_doc_submit.py。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

import app.services.rag.chat_llm as chat_llm_mod
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel, degradation_message
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.enums import (
    AgentRunStatus,
    DocumentStatus,
    MessageRole,
    MessageStatus,
)
from app.services.agent.planners import (
    create_document_write_planner,
    detect_write_intent,
)
from app.services.agent.stream import (
    _DOC_WRITE_SUCCESS_DEBRIEF,
    stream_agent_document_write_events,
)
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
    SearchDocumentsToolResult,
)
from app.services.rag.thread_persistence import create_kb_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

CLARIFY_URL = "/api/v1/agent/document-write/clarify"

DELETE_MSG = "删除 员工手册 v3.pdf"
RESTORE_MSG = "恢复 员工手册 v2.pdf"
B_PATH_MSG = "帮我把员工手册删掉"
DOC_NAME = "员工手册 v3.pdf"


def _degradation_text() -> str:
    return degradation_message(DegradationLevel.LLM_DOWN)


def _parse_frame(frame: str) -> tuple[str, dict]:
    assert frame.startswith("event: "), frame
    rest = frame[len("event: "):]
    ev, _sep, data_str = rest.partition("\ndata: ")
    return ev, json.loads(data_str.strip())


def _names(events: list[tuple[str, dict]]) -> list[str]:
    return [ev for ev, _ in events]


def _first(events: list[tuple[str, dict]], name: str) -> dict:
    for ev, data in events:
        if ev == name:
            return data
    raise AssertionError(f"event not found: {name}")


def _patch_llm_down(
    monkeypatch: pytest.MonkeyPatch,
    *,
    level: DegradationLevel = DegradationLevel.LLM_DOWN,
    no_key: bool = False,
) -> dict[str, int]:
    """权威判定钉在指定等级；双无 key 时清空 chat key。三条 LLM 入口换成计数桩。"""
    calls = {"stream": 0, "engine": 0, "chat_llm": 0}

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

    async def _never_chat_llm(_messages: list) -> tuple[str, None]:
        calls["chat_llm"] += 1
        return "", None

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
    monkeypatch.setattr(
        chat_llm_mod, "complete_chat_with_usage", _never_chat_llm
    )
    return calls


async def _login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "Test123!@"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_doc(kb_id: UUID, user_id: UUID, *, deleted: bool = False) -> UUID:
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=DOC_NAME,
                file_type="pdf",
                file_size=10,
                storage_path=f"/tmp/{doc_id}.pdf",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )
        await db.commit()
    return doc_id


async def _insert_kb_thread(kb_id: UUID, user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        thread = await create_kb_thread(db, kb_id=kb_id, user_id=user_id)
        await db.commit()
        return thread.id


def _search_result(kb_id: UUID, doc_id: UUID) -> SearchDocumentsToolResult:
    item = SearchDocumentsItem(
        document_id=doc_id,
        kb_id=kb_id,
        kb_name="公司公共库",
        filename=DOC_NAME,
    )
    return SearchDocumentsToolResult(
        ok=True,
        data=SearchDocumentsOutput(items=(item,), total=1),
        summary="文件名匹配 1 篇",
    )


async def _run_doc_write_sse(
    monkeypatch: pytest.MonkeyPatch,
    *,
    org_id: UUID,
    kb_id: UUID,
    current_user,
    thread_id: UUID,
    message: str,
    doc_id: UUID,
    double_confirm: bool = False,
    dual_no_key: bool = False,
) -> tuple[list[tuple[str, dict]], dict[str, int]]:
    """驱动真实库内 document_write SSE（默认 LLM_DOWN；search 步打桩、写 tool 真实执行）。"""
    calls = _patch_llm_down(
        monkeypatch,
        level=(
            DegradationLevel.NORMAL if dual_no_key else DegradationLevel.LLM_DOWN
        ),
        no_key=dual_no_key,
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents",
        AsyncMock(return_value=_search_result(kb_id, doc_id)),
    )

    planner = create_document_write_planner(message, default_kb_id=kb_id)
    frames: list[str] = []
    async with SessionLocal() as db:
        stream = stream_agent_document_write_events(
            db,
            kb_id=kb_id,
            user_id=current_user.id,
            message=message,
            thread_id=thread_id,
            workspace=WorkspaceScope(
                kind=WorkspaceKind.organization,
                user_id=current_user.id,
                org_id=org_id,
            ),
            tool_scope=AgentToolScope(
                visible_kb_ids=frozenset({kb_id}),
                default_kb_id=kb_id,
            ),
            planner=planner,
            current_user=current_user,
            can_adopt=True,
            save_turn=None,
            save_kwargs={"kb_id": kb_id, "thread_id": thread_id},
            double_confirm=double_confirm,
        )
        async for frame in stream:
            frames.append(frame)
    return [_parse_frame(f) for f in frames], calls


async def _assert_proposal_persisted(
    *,
    run_id: UUID,
    thread_id: UUID,
) -> None:
    async with SessionLocal() as db:
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
        assert assistant.content == _DOC_WRITE_SUCCESS_DEBRIEF
        approval = await db.scalar(
            select(AgentApproval).where(AgentApproval.run_id == run_id)
        )
        assert approval is None


async def _approval_count_for_doc(doc_id: UUID) -> int:
    async with SessionLocal() as db:
        return int(
            await db.scalar(
                text(
                    "SELECT count(*) FROM agent_approvals "
                    "WHERE document_id = :did"
                ),
                {"did": doc_id},
            )
            or 0
        )


# --------------------------------------------------------------------------- #
# A 路径 · delete / restore 提案 SSE
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_doc_write_delete_proposal_zero_llm_on_llm_down(
    monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """LLM_DOWN 下 delete A 路径：确定性提案、事件序不变、零 LLM、不建 pending。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id = await _insert_kb_thread(kb_id, org_iso.owner.id)

    events, calls = await _run_doc_write_sse(
        monkeypatch,
        org_id=org_iso.org_id,
        kb_id=kb_id,
        current_user=org_iso.owner,
        thread_id=thread_id,
        message=DELETE_MSG,
        doc_id=doc_id,
    )

    names = _names(events)
    assert names == [
        "tool_start",
        "tool_result",
        "agent_budget",
        "tool_start",
        "tool_result",
        "agent_budget",
        "token",
        "proposal_preview",
        "done",
    ], names
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}

    preview = _first(events, "proposal_preview")
    done = _first(events, "done")
    assert preview["operation"] == "delete"
    assert preview["document_id"] == str(doc_id)
    assert preview["kb_id"] == str(kb_id)
    assert preview["filename"] == DOC_NAME
    assert preview["impact"]
    assert preview["conflict"] is None
    assert preview["can_adopt"] is True
    assert preview["double_confirm"] is False
    assert preview["run_id"] == done["agent_run_id"]

    run_id = UUID(done["agent_run_id"])
    await _assert_proposal_persisted(run_id=run_id, thread_id=thread_id)


@pytest.mark.asyncio
async def test_doc_write_dual_no_key_proposal_no_placeholder_or_degradation(
    monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """双无 key（判定 NORMAL）：delete 提案确定性产出，不含占位文案与降级说明。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id = await _insert_kb_thread(kb_id, org_iso.owner.id)

    events, calls = await _run_doc_write_sse(
        monkeypatch,
        org_id=org_iso.org_id,
        kb_id=kb_id,
        current_user=org_iso.owner,
        thread_id=thread_id,
        message=DELETE_MSG,
        doc_id=doc_id,
        dual_no_key=True,
    )

    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}
    preview = _first(events, "proposal_preview")
    assert preview["operation"] == "delete"
    assert preview["filename"] == DOC_NAME
    assert _names(events)[-1] == "done"

    token_text = "".join(
        data.get("text", "") for ev, data in events if ev == "token"
    )
    assert "根据知识库内容回答" not in token_text
    assert _degradation_text() not in token_text

    preview_text = json.dumps(preview, ensure_ascii=False)
    assert "根据知识库内容回答" not in preview_text
    assert _degradation_text() not in preview_text
    assert "根据知识库内容回答" not in _DOC_WRITE_SUCCESS_DEBRIEF
    assert _degradation_text() not in _DOC_WRITE_SUCCESS_DEBRIEF


@pytest.mark.asyncio
async def test_doc_write_restore_proposal_zero_llm_on_llm_down(
    monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """LLM_DOWN 下 restore A 路径：回收站文档 → 确定性恢复提案，零 LLM。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id, deleted=True)
    thread_id = await _insert_kb_thread(kb_id, org_iso.owner.id)

    events, calls = await _run_doc_write_sse(
        monkeypatch,
        org_id=org_iso.org_id,
        kb_id=kb_id,
        current_user=org_iso.owner,
        thread_id=thread_id,
        message=RESTORE_MSG,
        doc_id=doc_id,
    )

    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}
    preview = _first(events, "proposal_preview")
    assert preview["operation"] == "restore"
    assert preview["document_id"] == str(doc_id)
    assert preview["double_confirm"] is False
    run_id = UUID(_first(events, "done")["agent_run_id"])
    await _assert_proposal_persisted(run_id=run_id, thread_id=thread_id)


@pytest.mark.asyncio
async def test_doc_write_b_path_intent_and_double_confirm_zero_llm_on_llm_down(
    monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """LLM_DOWN 下 B 路径意图识别仍命中，double_confirm=True 提案正常。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id = await _insert_kb_thread(kb_id, org_iso.owner.id)

    events, calls = await _run_doc_write_sse(
        monkeypatch,
        org_id=org_iso.org_id,
        kb_id=kb_id,
        current_user=org_iso.owner,
        thread_id=thread_id,
        message=B_PATH_MSG,
        doc_id=doc_id,
        double_confirm=True,
    )

    intent = detect_write_intent(B_PATH_MSG)
    assert intent is not None
    assert intent.operation == "delete"
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}

    preview = _first(events, "proposal_preview")
    assert preview["operation"] == "delete"
    assert preview["double_confirm"] is True
    assert preview["can_adopt"] is True


@pytest.mark.asyncio
async def test_doc_write_clarify_proposal_no_llm_on_llm_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, org_iso
) -> None:
    """Owner clarify → 结构化提案（double_confirm=True），dry 不建 pending，零 LLM。"""
    kb_id = org_iso.public_kb_id
    doc_id = await _insert_doc(kb_id, org_iso.owner.id)
    thread_id = await _insert_kb_thread(kb_id, org_iso.owner.id)
    headers = await _login(client, org_iso.owner)
    calls = _patch_llm_down(monkeypatch)

    resp = await client.post(
        CLARIFY_URL,
        headers=headers,
        json={
            "thread_id": str(thread_id),
            "document_id": str(doc_id),
            "operation": "delete",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["operation"] == "delete"
    assert data["document_id"] == str(doc_id)
    assert data["kb_id"] == str(kb_id)
    assert data["double_confirm"] is True
    assert data["can_adopt"] is True
    assert "run_id" in data
    assert calls == {"stream": 0, "engine": 0, "chat_llm": 0}
    assert await _approval_count_for_doc(doc_id) == 0

"""Plan-RAG R4-4：SSE 流式 UX 回归（引用与正文时序 · 落库一致 · 历史可读）。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus, MessageRole
from app.schemas.auth import UserPublic
from app.services.agent.stream import stream_agent_kb_events, stream_agent_workspace_events
from app.services.agent.types import AgentStepRecord, ToolCallPlan
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.persistence import get_message_by_id
from app.services.rag.thread_persistence import create_kb_thread, create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, resolve_workspace
from tests.conftest import create_test_kb as _create_kb, unique_email, unique_username

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD = FIXTURES / "golden_handbook.md"


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    blocks = re.split(r"\n\n+", raw.strip())
    for block in blocks:
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


def _assert_sse_frames_well_formed(raw: str) -> None:
    """每帧须含 event: 与 data: 行，data 为合法 JSON。"""
    blocks = [b for b in re.split(r"\n\n+", raw.strip()) if b.strip()]
    assert blocks, "SSE 响应不应为空"
    for block in blocks:
        assert "event: " in block
        assert "data: " in block
        data_line = next(l for l in block.splitlines() if l.startswith("data: "))
        json.loads(data_line.removeprefix("data: ").strip())


async def _ingest_fixture(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    source: Path,
    file_type: str,
    upload_dir: Path,
) -> Document:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=source.name,
            file_type=file_type,
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed
        return row


async def _chat(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    message: str,
) -> tuple[int, str, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": message},
    ) as resp:
        body = await resp.aread()
        raw = body.decode("utf-8")
        events = _parse_sse_events(raw)
        return resp.status_code, raw, events


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_r4_4_sse_frames_well_formed(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：SSE 帧格式合法（event + JSON data）。"""
    headers, user = await register_and_login(prefix="r4-4-sse-fmt")
    kb = await _create_kb(client, headers, user, name="流式格式库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, raw, events = await _chat(
        client, headers, str(kb_id), "员工年假有几天？"
    )
    assert status == 200
    _assert_sse_frames_well_formed(raw)
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_r4_4_citations_strictly_before_tokens(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：所有 citation 须在首个 token 之前，引用与正文不同步时序。"""
    headers, user = await register_and_login(prefix="r4-4-order")
    kb = await _create_kb(client, headers, user, name="时序库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    first_token_idx = next(
        (i for i, (name, _) in enumerate(events) if name == "token"),
        len(events),
    )
    for i, (name, _) in enumerate(events):
        if name == "citation":
            assert i < first_token_idx, "citation 不得出现在 token 之后"
        if name == "token" and i > 0:
            assert events[i - 1][0] in {"citation", "token"}


@pytest.mark.asyncio
async def test_r4_4_only_expected_event_types(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：流中仅 citation / token / done 三类事件。"""
    headers, user = await register_and_login(prefix="r4-4-types")
    kb = await _create_kb(client, headers, user, name="事件类型库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200
    assert {name for name, _ in events} <= {"citation", "token", "done"}
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_r4_4_token_aggregate_matches_persisted_content(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：token 拼接结果与落库 assistant 正文一致。"""
    headers, user = await register_and_login(prefix="r4-4-persist-txt")
    kb = await _create_kb(client, headers, user, name="落库正文库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    streamed = "".join(data["text"] for name, data in events if name == "token")
    assert streamed

    done = next(data for name, data in events if name == "done")
    message_id = uuid.UUID(done["message_id"])

    async with SessionLocal() as db:
        row = await get_message_by_id(db, message_id)
        assert row is not None
        assert row.role == MessageRole.assistant
        assert row.content == streamed


@pytest.mark.asyncio
async def test_r4_4_done_citations_match_streamed_citations(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：done.citations 与流式 citation 事件列表完全一致（前端 onDone 同步依据）。"""
    headers, user = await register_and_login(prefix="r4-4-done-sync")
    kb = await _create_kb(client, headers, user, name="done 同步库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    streamed_citations = [data for name, data in events if name == "citation"]
    assert streamed_citations

    done = next(data for name, data in events if name == "done")
    assert done["citations"] == streamed_citations


@pytest.mark.asyncio
async def test_r4_4_refusal_streams_tokens_only(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：无依据拒答路径无 citation，仅 token 流 + done 空 citations。"""
    headers, user = await register_and_login(prefix="r4-4-refusal")
    kb = await _create_kb(client, headers, user, name="拒答流式库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(
        client,
        headers,
        str(kb_id),
        "公司火星殖民计划的政策是什么？",
    )
    assert status == 200

    assert not any(name == "citation" for name, _ in events)
    token_events = [data for name, data in events if name == "token"]
    assert len(token_events) >= 2, "拒答应逐字/逐段流式 token"

    done = next(data for name, data in events if name == "done")
    assert done["citations"] == []


@pytest.mark.asyncio
async def test_r4_4_get_messages_reflects_stream(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-4：流式结束后 GET messages 与 SSE 聚合结果一致（刷新/重进页可读）。"""
    headers, user = await register_and_login(prefix="r4-4-history")
    kb = await _create_kb(client, headers, user, name="历史同步库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, _, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    streamed = "".join(data["text"] for name, data in events if name == "token")
    streamed_citations = [data for name, data in events if name == "citation"]
    done = next(data for name, data in events if name == "done")

    hist = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/messages",
        headers=headers,
    )
    assert hist.status_code == 200
    messages = hist.json()["messages"]
    assistant_rows = [m for m in messages if m["role"] == "assistant"]
    assert assistant_rows

    latest = assistant_rows[-1]
    assert latest["id"] == done["message_id"]
    assert latest["content"] == streamed
    assert latest["citations"] == streamed_citations


@dataclass
class _SingleSemanticPlanner:
    """精准模式测试用：一步 semantic_search 后结束。"""

    query: str
    _done: bool = False

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
        if self._done:
            return None
        self._done = True
        return ToolCallPlan(tool_name="semantic_search", args={"query": self.query})


async def _collect_stream_frames(gen) -> tuple[str, list[tuple[str, dict]]]:
    raw = ""
    async for frame in gen:
        raw += frame
    return raw, _parse_sse_events(raw)


def _assert_agent_tool_phase_before_citations(events: list[tuple[str, dict]]) -> None:
    """G3-2.3：每步 tool_start → tool_result → agent_budget · 全部在首条 citation 前。"""
    first_citation_idx = next(
        (i for i, (name, _) in enumerate(events) if name == "citation"),
        len(events),
    )
    tool_events = [
        (name, data)
        for name, data in events[:first_citation_idx]
        if name in {"tool_start", "tool_result", "agent_budget"}
    ]
    assert tool_events, "精准模式应至少有一步 tool 事件"

    step = 0
    for name, data in tool_events:
        if name == "tool_start":
            step += 1
            assert data["step"] == step
        elif name == "tool_result":
            assert data["step"] == step
        elif name == "agent_budget":
            assert data["steps_used"] == step
            assert data["max_steps"] == 5

    assert events[-1][0] == "done"


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.mark.asyncio
async def test_r4_4_agent_kb_thorough_event_order(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """G3-2.3 / G3-E9：库内精准 tool_* → agent_budget → citation → token → done。"""
    from app.services.agent.tools.scope import AgentToolScope

    headers, user = await register_and_login(prefix="r4-4-agent-kb")
    kb = await _create_kb(client, headers, user, name="精准库内库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        thread = await create_kb_thread(
            db,
            kb_id=kb_id,
            user_id=user_id,
            title="精准会话",
        )
        await db.commit()
        thread_id = thread.id

        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        tool_scope = AgentToolScope(
            visible_kb_ids=frozenset({kb_id}),
            default_kb_id=kb_id,
        )
        planner = _SingleSemanticPlanner("员工年假有几天？")
        raw, events = await _collect_stream_frames(
            stream_agent_kb_events(
                db,
                kb_id=kb_id,
                user_id=user_id,
                message="员工年假有几天？",
                thread_id=thread_id,
                workspace=workspace,
                tool_scope=tool_scope,
                planner=planner,
            )
        )
        await db.commit()

    _assert_sse_frames_well_formed(raw)
    _assert_agent_tool_phase_before_citations(events)

    first_token_idx = next(i for i, (name, _) in enumerate(events) if name == "token")
    for i, (name, _) in enumerate(events):
        if name == "citation":
            assert i < first_token_idx

    done = next(data for name, data in events if name == "done")
    assert done.get("agent_run_id")
    assert done["citations"] == [data for name, data in events if name == "citation"]


@pytest.mark.asyncio
async def test_r4_4_agent_workspace_thorough_event_order(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
) -> None:
    """G3-2.3：工作区精准 SSE 序 · citation 仍先于 token（R4-4 继承）。"""
    from app.services.agent.tools.scope import AgentToolScope

    headers, user = await register_and_login(prefix="r4-4-agent-ws")
    kb = await _create_kb(client, headers, user, name="工作区精准库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
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
        tool_scope = AgentToolScope(visible_kb_ids=None)
        planner = _SingleSemanticPlanner("员工年假有几天？")
        raw, events = await _collect_stream_frames(
            stream_agent_workspace_events(
                db,
                scope=scope,
                org_scope=None,
                user_id=user_id,
                message="员工年假有几天？",
                department_id=None,
                thread_id=thread_id,
                tool_scope=tool_scope,
                planner=planner,
            )
        )
        await db.commit()

    _assert_sse_frames_well_formed(raw)
    _assert_agent_tool_phase_before_citations(events)
    assert any(name == "citation" for name, _ in events)
    done = next(data for name, data in events if name == "done")
    assert done.get("agent_run_id")

    streamed = "".join(data["text"] for name, data in events if name == "token")
    message_id = uuid.UUID(done["message_id"])
    async with SessionLocal() as db:
        row = await get_message_by_id(db, message_id)
    assert row is not None
    assert row.role == MessageRole.assistant
    assert row.content == streamed

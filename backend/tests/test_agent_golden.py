"""G3-4.2 · golden_agent_qa.json 15 题 runner（multi_step / refusal / forbidden_kb）。"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.schemas.auth import UserPublic
from app.services.agent.dispatch import build_workspace_tool_scope
from app.services.agent.stream import stream_agent_kb_events, stream_agent_workspace_events
from app.services.agent.tools.scope import AgentToolScope, FORBIDDEN_KB_SUMMARY
from app.services.agent.types import ToolCallPlan
from app.services.ingestion import embedder
from app.services.ingestion.embedder import EMBEDDING_DIM
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.rag.thread_persistence import create_kb_thread, create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, resolve_workspace
from tests.conftest import create_test_kb
from tests.golden_agent_qa_loader import (
    GOLDEN_AGENT_CASES,
    AgentGoldenCase,
    EXPECTED_CASE_COUNT,
    REQUIRED_CATEGORIES,
)
from tests.golden_qa_loader import GOLDEN_MD
from tests.test_agent_runtime import SequencePlanner
from tests.test_chat import _ingest_fixture, _parse_sse_events

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-z0-9]+")


def _lexical_mock_vector(text: str) -> list[float]:
    tokens: set[str] = set(_CJK.findall(text))
    tokens.update(_LATIN.findall(text.lower()))
    vec = [0.0] * EMBEDDING_DIM
    for token in tokens:
        seed = sum(ord(ch) for ch in token)
        for j in range(8):
            idx = (seed * (j + 1) * 17 + j * 31) % EMBEDDING_DIM
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def lexical_mock_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedder, "_mock_vector", _lexical_mock_vector)


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@dataclass
class _CaseRuntimeContext:
    forbidden_kb_id: UUID
    forbidden_chunk_id: UUID
    visible_chunk_id: UUID | None


def _assert_no_context_refusal(tokens: str) -> None:
    assert "未找到" in tokens or "No relevant content" in tokens


async def _first_chunk_id(kb_id: UUID, *, section_contains: str | None = None) -> UUID:
    async with SessionLocal() as db:
        stmt = select(DocumentChunk.id).where(DocumentChunk.kb_id == kb_id)
        if section_contains:
            stmt = stmt.where(DocumentChunk.section_title.contains(section_contains))
        stmt = stmt.order_by(DocumentChunk.chunk_index).limit(1)
        row = (await db.execute(stmt)).scalar_one_or_none()
    assert row is not None, "seeded kb 应有 chunk"
    return row


def _case_needs_forbidden_assets(case: AgentGoldenCase) -> bool:
    if case.category == "forbidden_kb":
        return True
    blob = str(case.planner_steps)
    return "$forbidden_kb_id" in blob or "$forbidden_chunk_id" in blob


async def _seed_foreign_chunk(client: AsyncClient) -> tuple[UUID, UUID]:
    """另一用户的 kb + chunk（当前用户不可见）。"""
    from tests.conftest import unique_email, unique_username

    email = unique_email("foreign")
    username = unique_username("foreign")
    password = "Test123!@"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201
    foreign_user = reg.json()["user"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    foreign_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    foreign_kb = await create_test_kb(
        client, foreign_headers, foreign_user, name="Foreign KB"
    )
    foreign_kb_id = UUID(foreign_kb["id"])
    foreign_user_id = UUID(foreign_user["id"])
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    content = "FOREIGN_CHUNK 员工年假规定为 10 天"

    async with SessionLocal() as db:
        from app.models.document import Document

        db.add(
            Document(
                id=doc_id,
                kb_id=foreign_kb_id,
                filename="foreign.txt",
                file_type="txt",
                file_size=len(content),
                storage_path=f"/tmp/{foreign_kb_id}/{doc_id}.txt",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=foreign_user_id,
            )
        )
        db.add(
            DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                kb_id=foreign_kb_id,
                chunk_index=0,
                page_number=1,
                section_title="1.1 年假",
                content=content,
                embedding=None,
            )
        )
        await db.flush()
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
                "WHERE id = :chunk_id"
            ),
            {"src": content, "chunk_id": chunk_id},
        )
        await db.commit()

    return foreign_kb_id, chunk_id


def _resolve_planner_value(value: Any, ctx: _CaseRuntimeContext) -> Any:
    if isinstance(value, str):
        if value == "$forbidden_kb_id":
            return str(ctx.forbidden_kb_id)
        if value == "$forbidden_chunk_id":
            return str(ctx.forbidden_chunk_id)
        if value == "$visible_chunk_id":
            assert ctx.visible_chunk_id is not None
            return str(ctx.visible_chunk_id)
        return value
    if isinstance(value, list):
        return [_resolve_planner_value(item, ctx) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_planner_value(item, ctx) for key, item in value.items()}
    return value


def _build_planner(
    case: AgentGoldenCase,
    ctx: _CaseRuntimeContext,
) -> SequencePlanner:
    plans: list[ToolCallPlan | None] = []
    for step in case.planner_steps:
        tool = str(step["tool"])
        raw_args = step.get("args") or {}
        args = _resolve_planner_value(raw_args, ctx)
        plans.append(ToolCallPlan(tool_name=tool, args=args))
    return SequencePlanner(plans)


async def _collect_stream_frames(gen) -> list[tuple[str, dict]]:
    raw = ""
    async for frame in gen:
        raw += frame
    return _parse_sse_events(raw)


async def _run_agent_case(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    upload_dir: Path,
    case: AgentGoldenCase,
) -> list[tuple[str, dict]]:
    kb = await create_test_kb(
        client, headers, user, name=f"Agent Golden {case.case_id}"
    )
    kb_id = UUID(kb["id"])
    user_id = UUID(user["id"])

    if case.fixture == "md":
        await _ingest_fixture(
            kb_id=kb_id,
            user_id=user_id,
            source=GOLDEN_MD,
            file_type="md",
            upload_dir=upload_dir,
        )

    if _case_needs_forbidden_assets(case):
        forbidden_kb_id, forbidden_chunk_id = await _seed_foreign_chunk(client)
    else:
        forbidden_kb_id = uuid.uuid4()
        forbidden_chunk_id = uuid.uuid4()

    visible_chunk_id = None
    if case.fixture == "md" and any(
        step.get("args", {}).get("chunk_id") == "$visible_chunk_id"
        for step in case.planner_steps
    ):
        visible_chunk_id = await _first_chunk_id(kb_id, section_contains="2.2")

    ctx = _CaseRuntimeContext(
        forbidden_kb_id=forbidden_kb_id,
        forbidden_chunk_id=forbidden_chunk_id,
        visible_chunk_id=visible_chunk_id,
    )
    planner = _build_planner(case, ctx)

    async with SessionLocal() as db:
        if case.scope == "kb":
            thread = await create_kb_thread(
                db,
                kb_id=kb_id,
                user_id=user_id,
                title=f"GAQ {case.case_id}",
            )
            await db.commit()
            current_user = UserPublic.model_validate(user)
            workspace = await resolve_workspace(db, current_user, "personal")
            tool_scope = AgentToolScope(
                visible_kb_ids=frozenset({kb_id}),
                default_kb_id=kb_id,
            )
            events = await _collect_stream_frames(
                stream_agent_kb_events(
                    db,
                    kb_id=kb_id,
                    user_id=user_id,
                    message=case.query,
                    thread_id=thread.id,
                    workspace=workspace,
                    tool_scope=tool_scope,
                    planner=planner,
                )
            )
        else:
            thread = await create_workspace_thread(
                db,
                user_id=user_id,
                workspace_kind=WorkspaceKind.personal,
                workspace_org_id=None,
                department_id=None,
            )
            await db.commit()
            current_user = UserPublic.model_validate(user)
            scope = await resolve_workspace(db, current_user, "personal")
            org_scope = await resolve_org_scope_for_workspace(db, current_user, scope)
            if case.category == "forbidden_kb":
                tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}))
            else:
                tool_scope = build_workspace_tool_scope(org_scope)
            events = await _collect_stream_frames(
                stream_agent_workspace_events(
                    db,
                    scope=scope,
                    org_scope=org_scope,
                    user_id=user_id,
                    message=case.query,
                    department_id=None,
                    thread_id=thread.id,
                    tool_scope=tool_scope,
                    planner=planner,
                )
            )
        await db.commit()

    return events


def _assert_case_expectations(
    case: AgentGoldenCase,
    events: list[tuple[str, dict]],
) -> None:
    expect = case.expect
    tool_results = [data for name, data in events if name == "tool_result"]
    citations = [data for name, data in events if name == "citation"]
    tokens = "".join(data["text"] for name, data in events if name == "token")

    assert len(tool_results) >= expect.min_steps, (
        f"{case.case_id} 步数不足：{len(tool_results)} < {expect.min_steps}"
    )

    if expect.tools_used:
        actual_tools = [data["tool"] for data in tool_results[: len(expect.tools_used)]]
        assert actual_tools == list(expect.tools_used), (
            f"{case.case_id} tool 序不符：{actual_tools} != {list(expect.tools_used)}"
        )

    if expect.tool_denied:
        denied = [r for r in tool_results if not r.get("ok")]
        assert denied, f"{case.case_id} 应有 tool_denied"
        assert any(r.get("summary") == FORBIDDEN_KB_SUMMARY for r in denied)

    if expect.has_citations:
        assert citations, f"{case.case_id} 应有 citation"
        if expect.citation_section_contains:
            joined = " ".join(
                str(c.get("section_title") or "") for c in citations
            )
            assert expect.citation_section_contains in joined, (
                f"{case.case_id} citation 未含 {expect.citation_section_contains!r}"
            )
    else:
        assert not citations, f"{case.case_id} 不应有 citation"

    if expect.refusal:
        _assert_no_context_refusal(tokens)
    elif citations:
        assert tokens, f"{case.case_id} 有 citation 时应有 token"

    assert events[-1][0] == "done"
    done = events[-1][1]
    assert done.get("agent_run_id")


def test_golden_agent_qa_manifest() -> None:
    """SSOT：15 题 · 三类齐全。"""
    assert len(GOLDEN_AGENT_CASES) == EXPECTED_CASE_COUNT
    categories = {case.category for case in GOLDEN_AGENT_CASES}
    assert categories == REQUIRED_CATEGORIES


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    GOLDEN_AGENT_CASES,
    ids=[c.case_id for c in GOLDEN_AGENT_CASES],
)
async def test_golden_agent_qa_case(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    rerank_mock: None,
    case: AgentGoldenCase,
) -> None:
    """golden_agent_qa.json 各题：精准 Agent 路径 outcome 符合 expect。"""
    headers, user = await register_and_login(prefix=f"gaq-{case.case_id.lower()}")
    events = await _run_agent_case(client, headers, user, upload_dir, case)
    _assert_case_expectations(case, events)

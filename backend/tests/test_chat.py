"""Wave 3.1～3.3 RAG 对话 SSE、落库与无依据拒绝测试。"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, MessageRole, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.persistence import get_message_by_id
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


def _assert_no_context_refusal(tokens: str) -> None:
    """R4-2：中/英固定拒答话术任一即可。"""
    assert "未找到" in tokens or "No relevant content" in tokens


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
) -> tuple[int, list[tuple[str, dict]]]:
    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": message},
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    email = unique_email("chat-member")
    username = unique_username("chatmem")
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(org_id),
                user_id=user.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return headers, data["user"]


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_chat_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{uuid.uuid4()}/chat",
        json={"message": "年假几天"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_forbidden_for_other_users_kb(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, user_a = await register_and_login(prefix="chat-owner")
    kb = await _create_kb(client, headers_a, user_a, name="A 的库")
    kb_id = kb["id"]

    headers_b, _ = await register_and_login(prefix="chat-intruder")
    status, _ = await _chat(client, headers_b, kb_id, "年假几天")
    assert status == 403


@pytest.mark.asyncio
async def test_org_member_can_chat_team_kb(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R2：企业 Member 对团队库只读但可对话（read 权限 · WS-2-6）。"""
    admin_headers, admin_user = await register_and_login(
        prefix="chat-team-admin",
        account_type="enterprise",
        org_name="成员可对话公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user, name="团队对话库")
    kb_id = uuid.UUID(kb["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=uuid.UUID(admin_user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    status, events = await _chat(
        client,
        member_headers,
        str(kb_id),
        "员工年假有几天？",
    )
    assert status == 200
    event_types = [name for name, _ in events]
    assert "done" in event_types


@pytest.mark.asyncio
async def test_chat_sse_streams_tokens_and_citations(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="chat-sse")
    kb = await _create_kb(client, headers, user, name="对话测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    event_types = [name for name, _ in events]
    assert "citation" in event_types
    assert "token" in event_types
    assert "done" in event_types

    citations = [data for name, data in events if name == "citation"]
    assert citations
    assert any("年假" in c.get("excerpt", "") or "10" in c.get("excerpt", "") for c in citations)
    assert all(c.get("doc_name") == GOLDEN_MD.name for c in citations)

    tokens = "".join(data["text"] for name, data in events if name == "token")
    assert tokens

    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")
    assert isinstance(done.get("citations"), list)
    assert len(done["citations"]) >= 1


CITATION_FIELD_KEYS = frozenset(
    {
        "chunk_id",
        "document_id",
        "doc_name",
        "page",
        "section_title",
        "excerpt",
    }
)


@pytest.mark.asyncio
async def test_r4_3_citation_block_contract(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """R4-3：引用块六字段 · citation 先于 token · done 与 SSE 一致。"""
    headers, user = await register_and_login(prefix="r4-3-cite")
    kb = await _create_kb(client, headers, user, name="引用块测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    first_citation_idx = next(
        i for i, (name, _) in enumerate(events) if name == "citation"
    )
    first_token_idx = next(i for i, (name, _) in enumerate(events) if name == "token")
    assert first_citation_idx < first_token_idx

    citations = [data for name, data in events if name == "citation"]
    assert citations
    for cite in citations:
        assert set(cite.keys()) == CITATION_FIELD_KEYS
        assert cite["doc_name"] == GOLDEN_MD.name
        assert cite["chunk_id"]
        assert cite["document_id"]
        assert cite["section_title"]
        assert cite["excerpt"].strip()
        assert len(cite["excerpt"]) <= 200

    done = next(data for name, data in events if name == "done")
    assert done["citations"] == citations


@pytest.mark.asyncio
async def test_chat_kb_id_isolation_in_retrieval(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
) -> None:
    headers, user = await register_and_login(prefix="chat-iso")
    user_id = uuid.UUID(user["id"])

    kb_a = await _create_kb(client, headers, user, name="库 A")
    kb_b = await _create_kb(client, headers, user, name="库 B")
    kb_a_id = uuid.UUID(kb_a["id"])
    kb_b_id = uuid.UUID(kb_b["id"])

    await _ingest_fixture(
        kb_id=kb_a_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET_ALPHA_BRAVO 唯一标识符", encoding="utf-8")
    await _ingest_fixture(
        kb_id=kb_b_id,
        user_id=user_id,
        source=secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    status, events = await _chat(
        client,
        headers,
        str(kb_a_id),
        "SECRET_ALPHA_BRAVO 在哪里",
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations == []

    tokens = "".join(data["text"] for name, data in events if name == "token")
    _assert_no_context_refusal(tokens)


@pytest.mark.asyncio
async def test_chat_empty_kb_returns_no_context_reply(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="chat-empty")
    kb = await _create_kb(client, headers, user, name="空库")
    kb_id = kb["id"]

    status, events = await _chat(client, headers, kb_id, "随便问点什么")
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations == []

    tokens = "".join(data["text"] for name, data in events if name == "token")
    _assert_no_context_refusal(tokens)


@pytest.mark.asyncio
async def test_chat_persists_citations_to_db(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="chat-persist")
    kb = await _create_kb(client, headers, user, name="落库测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(client, headers, str(kb_id), "员工年假有几天？")
    assert status == 200

    done = next(data for name, data in events if name == "done")
    message_id = uuid.UUID(done["message_id"])

    async with SessionLocal() as db:
        row = await get_message_by_id(db, message_id)
        assert row is not None
        assert row.role == MessageRole.assistant
        assert row.kb_id == kb_id
        assert row.user_id == user_id
        assert row.content
        assert row.citations is not None
        assert len(row.citations) >= 1
        assert all(c.get("doc_name") == GOLDEN_MD.name for c in row.citations)
        assert all(c.get("chunk_id") for c in row.citations)
        assert all(c.get("section_title") for c in row.citations)
        assert any(
            "年假" in c.get("excerpt", "") or "10" in c.get("excerpt", "")
            for c in row.citations
        )
        assert row.retrieval_duration_ms is not None
        assert row.retrieval_duration_ms >= 0


@pytest.mark.asyncio
async def test_chat_empty_kb_persists_no_citations(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="chat-persist-empty")
    kb = await _create_kb(client, headers, user, name="空库落库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    status, events = await _chat(client, headers, str(kb_id), "随便问点什么")
    assert status == 200

    done = next(data for name, data in events if name == "done")
    message_id = uuid.UUID(done["message_id"])

    async with SessionLocal() as db:
        row = await get_message_by_id(db, message_id)
        assert row is not None
        assert row.role == MessageRole.assistant
        assert row.kb_id == kb_id
        assert row.user_id == user_id
        assert row.citations == []


@pytest.mark.asyncio
async def test_chat_irrelevant_question_returns_no_context_reply(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """AC-4：库里有文档，但问题与内容无关 → 声明未找到，不吐 citation。"""
    headers, user = await register_and_login(prefix="chat-ac4")
    kb = await _create_kb(client, headers, user, name="AC4 测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(
        client,
        headers,
        str(kb_id),
        "公司火星殖民计划的政策是什么？",
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations == []

    tokens = "".join(data["text"] for name, data in events if name == "token")
    _assert_no_context_refusal(tokens)
    assert "殖民" not in tokens

    done = next(data for name, data in events if name == "done")
    assert done["citations"] == []


@pytest.mark.asyncio
async def test_chat_ipo_question_returns_no_context_reply(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """答辩脚本步骤 11 / AC-4：「公司上市计划是什么？」→ 无 citation + 未找到。"""
    headers, user = await register_and_login(prefix="chat-ipo")
    kb = await _create_kb(client, headers, user, name="IPO AC4 测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(
        client,
        headers,
        str(kb_id),
        "公司上市计划是什么？",
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations == []

    tokens = "".join(data["text"] for name, data in events if name == "token")
    _assert_no_context_refusal(tokens)

    done = next(data for name, data in events if name == "done")
    assert done["citations"] == []

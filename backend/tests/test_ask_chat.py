"""G-1 Wave 2：工作区 /ask API · T-ask-1～7。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus, GrantPermission, GranteeType
from app.models.kb_unit_grant import KbUnitGrant
from app.models.user import User
from app.services.rag.persistence import save_workspace_chat_turn
from app.services.workspace.scope import WorkspaceKind
from tests.conftest import create_test_kb as _create_kb
from tests.test_chat import (
    CITATION_FIELD_KEYS,
    GOLDEN_MD,
    _chat,
    _ingest_fixture,
    _parse_sse_events,
)
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user
from tests.test_retrieval_workspace import _seed_chunk

FIXTURES = Path(__file__).parent / "fixtures"


async def _ask(
    client: AsyncClient,
    headers: dict[str, str],
    message: str,
    *,
    workspace: str,
    department_id: str | None = None,
) -> tuple[int, list[tuple[str, dict]]]:
    params: dict[str, str] = {"workspace": workspace}
    if department_id is not None:
        params["department_id"] = department_id
    async with client.stream(
        "POST",
        "/api/v1/ask/chat",
        headers=headers,
        json={"message": message},
        params=params,
    ) as resp:
        body = await resp.aread()
        events = _parse_sse_events(body.decode("utf-8"))
        return resp.status_code, events


async def _get_ask_messages(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    workspace: str,
    department_id: str | None = None,
) -> tuple[int, dict]:
    params: dict[str, str] = {"workspace": workspace}
    if department_id is not None:
        params["department_id"] = department_id
    resp = await client.get(
        "/api/v1/ask/messages",
        headers=headers,
        params=params,
    )
    return resp.status_code, resp.json()


def _assert_no_context_refusal(tokens: str) -> None:
    assert "未找到" in tokens or "No relevant content" in tokens


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.mark.asyncio
async def test_t_ask_1_personal_two_kbs_citation_from_target_kb(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
    rerank_mock: None,
) -> None:
    """T-ask-1：个人 2 库 · 问 A 专属 → citation 来自 A 且带 A 库名。"""
    headers, user = await register_and_login(prefix="ask-t1")
    user_id = uuid.UUID(user["id"])

    kb_a = await _create_kb(client, headers, user, name="Ask 库 A", workspace_kind="personal")
    kb_b = await _create_kb(client, headers, user, name="Ask 库 B", workspace_kind="personal")
    kb_a_id = uuid.UUID(kb_a["id"])

    await _ingest_fixture(
        kb_id=kb_a_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    secret = tmp_path / "b-only.txt"
    secret.write_text("ASK_B_ONLY_MARKER 仅 B 库", encoding="utf-8")
    await _ingest_fixture(
        kb_id=uuid.UUID(kb_b["id"]),
        user_id=user_id,
        source=secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    status, events = await _ask(
        client,
        headers,
        "员工年假有多少天",
        workspace="personal",
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations
    assert all(c.get("kb_name") == "Ask 库 A" for c in citations)
    assert all(c.get("kb_id") == str(kb_a_id) for c in citations)
    assert all("ASK_B_ONLY_MARKER" not in c.get("excerpt", "") for c in citations)

    done = next(data for name, data in events if name == "done")
    assert done.get("message_id")


@pytest.mark.asyncio
async def test_t_ask_2_org_member_handbook_no_ungranted_salary_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
    rerank_mock: None,
) -> None:
    """T-ask-2：研发 member 问手册 → 有引用 · 无未 grant 薪酬库 chunk。"""
    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=org_iso.rd_kb_id,
            uploaded_by=org_iso.rd_member.id,
            filename="rd-handbook.txt",
            content="研发员工手册 年假 10 天 规定",
        )
        await _seed_chunk(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="salary-secret.txt",
            content="薪酬库机密 年终奖 专属关键词 salary_alpha",
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

    status, events = await _ask(
        client,
        headers,
        "研发员工手册 年假",
        workspace=str(org_iso.org_id),
        department_id=str(org_iso.rd_id),
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations
    assert all(c.get("kb_id") != str(org_iso.mkt_kb_id) for c in citations)
    assert all("salary_alpha" not in c.get("excerpt", "") for c in citations)
    assert any(c.get("kb_name") for c in citations)

    msg_status, body = await _get_ask_messages(
        client,
        headers,
        workspace=str(org_iso.org_id),
        department_id=str(org_iso.rd_id),
    )
    assert msg_status == 200
    assert len(body["messages"]) >= 2


@pytest.mark.asyncio
async def test_t_ask_3_org_member_sibling_department_secret_refusal(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
    rerank_mock: None,
) -> None:
    """T-ask-3：研发 member 问兄弟部门机密 → 拒答（AC-4）。"""
    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="mkt-only.txt",
            content="市场部专属机密 alpha_bravo 不得外泄",
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

    status, events = await _ask(
        client,
        headers,
        "市场部专属机密 alpha_bravo",
        workspace=str(org_iso.org_id),
        department_id=str(org_iso.rd_id),
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations == []
    tokens = "".join(data["text"] for name, data in events if name == "token")
    _assert_no_context_refusal(tokens)


@pytest.mark.asyncio
async def test_t_ask_4_unassigned_member_ask_forbidden(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """T-ask-4：未分配 member · /ask → 403。"""
    async with SessionLocal() as db:
        user = await db.get(User, org_iso.unassigned_member.id)
        assert user is not None
        headers, _ = await _login_user(client, user.email, "password123")

    status, _ = await _ask(
        client,
        headers,
        "任意问题",
        workspace=str(org_iso.org_id),
    )
    assert status == 403

    msg_status, _ = await _get_ask_messages(
        client,
        headers,
        workspace=str(org_iso.org_id),
    )
    assert msg_status == 403


@pytest.mark.asyncio
async def test_t_ask_5_missing_workspace_returns_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T-ask-5：缺 workspace → 403。"""
    headers, _ = await register_and_login(prefix="ask-t5")

    async with client.stream(
        "POST",
        "/api/v1/ask/chat",
        headers=headers,
        json={"message": "测试问题"},
    ) as resp:
        body = await resp.aread()
        assert resp.status_code == 403
        assert body


@pytest.mark.asyncio
async def test_t_ask_6_multi_kb_diverse_kb_names_in_citations(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
    rerank_mock: None,
) -> None:
    """T-ask-6：多库同主题 → ≤5 chip · kb_name 可不同。"""
    async with SessionLocal() as db:
        for i in range(4):
            await _seed_chunk(
                db,
                kb_id=org_iso.rd_kb_id,
                uploaded_by=org_iso.rd_member.id,
                filename=f"rd-leave-{i}.txt",
                content=f"年假统一主题 研发库 片段{i} 10天",
            )
        await _seed_chunk(
            db,
            kb_id=org_iso.public_kb_id,
            uploaded_by=org_iso.owner.id,
            filename="public-leave.txt",
            content="年假统一主题 公共库 片段 10天",
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

    status, events = await _ask(
        client,
        headers,
        "年假统一主题 10天",
        workspace=str(org_iso.org_id),
        department_id=str(org_iso.rd_id),
    )
    assert status == 200

    citations = [data for name, data in events if name == "citation"]
    assert citations
    assert len(citations) <= 5
    kb_names = {c.get("kb_name") for c in citations if c.get("kb_name")}
    assert len(kb_names) >= 2


@pytest.mark.asyncio
async def test_t_ask_7_kb_chat_citations_without_kb_name(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """T-ask-7：库内 chat 回归 · chip 仍无 kb_name。"""
    headers, user = await register_and_login(prefix="ask-t7")
    kb = await _create_kb(client, headers, user, name="库内回归库")
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

    citations = [data for name, data in events if name == "citation"]
    assert citations
    for cite in citations:
        assert set(cite.keys()) == CITATION_FIELD_KEYS
        assert "kb_id" not in cite
        assert "kb_name" not in cite


@pytest.mark.asyncio
async def test_e14_workspace_messages_marks_revoked_grant_inaccessible(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E14 / ORG-1.7：撤 grant 后工作区历史 citation 灰态。"""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.org_unit,
                grantee_id=org_iso.rd_id,
                permission=GrantPermission.read,
            )
        )
        db.add(
            Document(
                id=doc_id,
                kb_id=org_iso.mkt_kb_id,
                filename="ws-grant.txt",
                file_type="txt",
                file_size=20,
                storage_path=f"/tmp/{org_iso.mkt_kb_id}/{doc_id}.txt",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=org_iso.mkt_member.id,
            )
        )
        db.add(
            DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                kb_id=org_iso.mkt_kb_id,
                chunk_index=0,
                content="工作区 grant 引用内容",
                embedding=None,
            )
        )
        await save_workspace_chat_turn(
            db,
            user_id=org_iso.rd_member.id,
            workspace_kind=WorkspaceKind.organization,
            workspace_org_id=org_iso.org_id,
            department_id=str(org_iso.rd_id),
            user_content="grant 可见时的问题",
            assistant_content="引用市场部文档",
            citations=[
                {
                    "chunk_id": str(chunk_id),
                    "document_id": str(doc_id),
                    "doc_name": "ws-grant.txt",
                    "page": None,
                    "section_title": None,
                    "excerpt": "工作区 grant 引用内容",
                    "kb_id": str(org_iso.mkt_kb_id),
                    "kb_name": "市场机密库",
                }
            ],
        )
        await db.commit()

        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "password123")

        await db.execute(delete(KbUnitGrant).where(KbUnitGrant.kb_id == org_iso.mkt_kb_id))
        await db.commit()

    msg_status, body = await _get_ask_messages(
        client,
        headers,
        workspace=str(org_iso.org_id),
        department_id=str(org_iso.rd_id),
    )
    assert msg_status == 200
    assistant = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant["citations"]
    assert assistant["citations"][0]["source_status"] == "source_inaccessible"

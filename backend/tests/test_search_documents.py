"""EW-E1 跨库文件名搜索测试（S1～S8）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization
from tests.conftest import create_test_kb, workspace_query


async def _seed_document(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    status: DocumentStatus = DocumentStatus.completed,
) -> Document:
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="pdf",
            file_size=1024,
            storage_path=f"/tmp/{doc_id}.pdf",
            status=status,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
        return doc


async def _search(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    q: str,
    workspace: str,
    limit: int | None = None,
    mode: str | None = None,
):
    params: dict[str, str | int] = {"q": q, "workspace": workspace}
    if limit is not None:
        params["limit"] = limit
    if mode is not None:
        params["mode"] = mode
    return await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params=params,
    )


@pytest.mark.asyncio
async def test_s1_personal_workspace_matches_single_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S1: personal workspace，两库各 1 文档，q 命中库 A 文件名。"""
    headers, user = await register_and_login(prefix="search-s1")
    user_id = uuid.UUID(user["id"])

    kb_a = await create_test_kb(
        client, headers, user, name="S1 库 A", workspace_kind="personal"
    )
    kb_b = await create_test_kb(
        client, headers, user, name="S1 库 B", workspace_kind="personal"
    )
    await _seed_document(
        kb_id=uuid.UUID(kb_a["id"]),
        user_id=user_id,
        filename="采购合同.pdf",
    )
    await _seed_document(
        kb_id=uuid.UUID(kb_b["id"]),
        user_id=user_id,
        filename="员工手册.pdf",
    )

    resp = await _search(
        client,
        headers,
        q="合同",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["filename"] == "采购合同.pdf"
    assert body["items"][0]["kb_name"] == "S1 库 A"
    assert body["items"][0]["kb_id"] == kb_a["id"]


@pytest.mark.asyncio
async def test_s2_query_matches_multiple_kbs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S2: q 命中两库。"""
    headers, user = await register_and_login(prefix="search-s2")
    user_id = uuid.UUID(user["id"])

    kb_a = await create_test_kb(
        client, headers, user, name="S2 库 A", workspace_kind="personal"
    )
    kb_b = await create_test_kb(
        client, headers, user, name="S2 库 B", workspace_kind="personal"
    )
    await _seed_document(
        kb_id=uuid.UUID(kb_a["id"]),
        user_id=user_id,
        filename="2024年度报告.pdf",
    )
    await _seed_document(
        kb_id=uuid.UUID(kb_b["id"]),
        user_id=user_id,
        filename="2025年度报告.docx",
    )

    resp = await _search(
        client,
        headers,
        q="年度报告",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
    kb_ids = {item["kb_id"] for item in body["items"]}
    assert kb_a["id"] in kb_ids
    assert kb_b["id"] in kb_ids
    assert len(kb_ids) >= 2


@pytest.mark.asyncio
async def test_s3_no_match_returns_empty(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S3: q 无匹配。"""
    headers, user = await register_and_login(prefix="search-s3")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(
        client, headers, user, name="S3 库", workspace_kind="personal"
    )
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="唯一文件.pdf",
    )

    resp = await _search(
        client,
        headers,
        q="不存在的关键词",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_s4_missing_workspace_returns_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S4: 缺 workspace。"""
    headers, _user = await register_and_login(prefix="search-s4")
    resp = await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params={"q": "test"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "缺少工作区参数"


@pytest.mark.asyncio
async def test_s5_forged_org_workspace_returns_403(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S5: 伪造 org workspace。"""
    headers, _user = await register_and_login(prefix="search-s5")
    async with SessionLocal() as db:
        other_org = Organization(id=uuid.uuid4(), name="他人组织")
        db.add(other_org)
        await db.commit()
        forged_org_id = str(other_org.id)

    resp = await _search(
        client,
        headers,
        q="test",
        workspace=forged_org_id,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该工作区"


@pytest.mark.asyncio
async def test_s6_empty_query_returns_400(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S6: q 空字符串。"""
    headers, _user = await register_and_login(prefix="search-s6")
    resp = await _search(
        client,
        headers,
        q="   ",
        workspace="personal",
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "搜索关键词不能为空"


@pytest.mark.asyncio
async def test_s7_personal_workspace_excludes_team_docs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S7: personal workspace 搜不到 team 库文档。"""
    headers, user = await register_and_login(
        prefix="search-s7",
        account_type="enterprise",
        org_name="S7 公司",
    )
    user_id = uuid.UUID(user["id"])
    org_id = user["org_id"]

    team_kb = await create_test_kb(
        client, headers, user, name="S7 团队库", workspace_kind="organization"
    )
    await _seed_document(
        kb_id=uuid.UUID(team_kb["id"]),
        user_id=user_id,
        filename="团队机密合同.pdf",
    )

    async with SessionLocal() as db:
        personal_kb = KnowledgeBase(
            id=uuid.uuid4(),
            name="S7 个人库",
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.add(personal_kb)
        await db.commit()
        personal_kb_id = personal_kb.id

    await _seed_document(
        kb_id=personal_kb_id,
        user_id=user_id,
        filename="个人笔记.pdf",
    )

    resp = await _search(
        client,
        headers,
        q="合同",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    filenames = [item["filename"] for item in body["items"]]
    assert "团队机密合同.pdf" not in filenames
    assert all(item["kb_id"] != team_kb["id"] for item in body["items"])


@pytest.mark.asyncio
async def test_s8_team_workspace_excludes_personal_docs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S8: team workspace 搜不到 personal 库文档。"""
    headers, user = await register_and_login(
        prefix="search-s8",
        account_type="enterprise",
        org_name="S8 公司",
    )
    user_id = uuid.UUID(user["id"])
    org_id = user["org_id"]

    team_kb = await create_test_kb(
        client, headers, user, name="S8 团队库", workspace_kind="organization"
    )
    await _seed_document(
        kb_id=uuid.UUID(team_kb["id"]),
        user_id=user_id,
        filename="团队共享手册.pdf",
    )

    async with SessionLocal() as db:
        personal_kb = KnowledgeBase(
            id=uuid.uuid4(),
            name="S8 个人库",
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.add(personal_kb)
        await db.commit()
        personal_kb_id = personal_kb.id

    await _seed_document(
        kb_id=personal_kb_id,
        user_id=user_id,
        filename="个人日记.pdf",
    )

    resp = await _search(
        client,
        headers,
        q="手册",
        workspace=org_id,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) >= 1
    assert body["items"][0]["filename"] == "团队共享手册.pdf"
    assert all(item["kb_id"] != str(personal_kb_id) for item in body["items"])


@pytest.mark.asyncio
async def test_query_over_200_chars_returns_400(
    client: AsyncClient,
    register_and_login,
) -> None:
    """H2-A: 超长 q → 400。"""
    headers, user = await register_and_login(prefix="search-h2")
    resp = await _search(
        client,
        headers,
        q="a" * 201,
        workspace=workspace_query(user, kind="personal")["workspace"],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "搜索关键词过长"

"""Plan-RAG R1-2 跨库正文搜索测试（C1～C5）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from tests.conftest import create_test_kb
from tests.test_search_documents import _search, _seed_document


async def _seed_chunk(
    *,
    doc,
    content: str,
    page_number: int | None = None,
) -> DocumentChunk:
    chunk_id = uuid.uuid4()
    async with SessionLocal() as db:
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
            chunk_index=0,
            page_number=page_number,
            section_title=None,
            heading_path=None,
            content=content,
            embedding=None,
        )
        db.add(chunk)
        await db.flush()
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
                "WHERE id = :chunk_id"
            ),
            {"src": content, "chunk_id": chunk_id},
        )
        await db.commit()
        return chunk


async def _search_content(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    q: str,
    workspace: str,
):
    return await _search(
        client,
        headers,
        q=q,
        workspace=workspace,
        mode="content",
    )


@pytest.mark.asyncio
async def test_c1_content_matches_pdf_body(
    client: AsyncClient,
    register_and_login,
) -> None:
    """C1: 正文模式命中 PDF 内文字（文件名不含关键词）。"""
    headers, user = await register_and_login(prefix="search-c1")
    user_id = uuid.UUID(user["id"])

    kb = await create_test_kb(
        client, headers, user, name="C1 库", workspace_kind="personal"
    )
    doc = await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="人事制度汇编.pdf",
    )
    await _seed_chunk(
        doc=doc,
        content="员工年满一年后可享受年假10天，须提前两周申请。",
        page_number=3,
    )

    resp = await _search_content(
        client,
        headers,
        q="年假10天",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "content"
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["filename"] == "人事制度汇编.pdf"
    assert item["kb_name"] == "C1 库"
    assert item["snippet"]
    assert "年假" in item["snippet"] or "10天" in item["snippet"]
    assert item["page_number"] == 3


@pytest.mark.asyncio
async def test_c2_content_no_match_returns_empty(
    client: AsyncClient,
    register_and_login,
) -> None:
    """C2: 正文无匹配返回空列表。"""
    headers, user = await register_and_login(prefix="search-c2")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(
        client, headers, user, name="C2 库", workspace_kind="personal"
    )
    doc = await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="空白文档.pdf",
    )
    await _seed_chunk(doc=doc, content="本段不含特殊关键词。")

    resp = await _search_content(
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
async def test_c3_content_workspace_isolation(
    client: AsyncClient,
    register_and_login,
) -> None:
    """C3: personal 正文搜不到 team 库 chunk。"""
    headers, user = await register_and_login(
        prefix="search-c3",
        account_type="enterprise",
        org_name="C3 公司",
    )
    user_id = uuid.UUID(user["id"])

    team_kb = await create_test_kb(
        client, headers, user, name="C3 团队库", workspace_kind="organization"
    )
    team_doc = await _seed_document(
        kb_id=uuid.UUID(team_kb["id"]),
        user_id=user_id,
        filename="团队保密.pdf",
    )
    await _seed_chunk(doc=team_doc, content="团队专属条款 ALPHA_SECRET 内容。")

    async with SessionLocal() as db:
        personal_kb = KnowledgeBase(
            id=uuid.uuid4(),
            name="C3 个人库",
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.add(personal_kb)
        await db.commit()
        personal_kb_id = personal_kb.id

    personal_doc = await _seed_document(
        kb_id=personal_kb_id,
        user_id=user_id,
        filename="个人笔记.pdf",
    )
    await _seed_chunk(doc=personal_doc, content="个人学习笔记。")

    resp = await _search_content(
        client,
        headers,
        q="ALPHA_SECRET",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_c4_filename_mode_default_unchanged(
    client: AsyncClient,
    register_and_login,
) -> None:
    """C4: 默认 filename 模式行为与 R1-1 一致（不因正文有词而命中）。"""
    headers, user = await register_and_login(prefix="search-c4")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(
        client, headers, user, name="C4 库", workspace_kind="personal"
    )
    doc = await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="无关名称.pdf",
    )
    await _seed_chunk(doc=doc, content="唯一正文关键词 BETA_UNIQUE 在此。")

    resp = await _search(
        client,
        headers,
        q="BETA_UNIQUE",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("mode", "filename") == "filename"
    assert body["items"] == []


@pytest.mark.asyncio
async def test_c5_content_aggregates_one_row_per_document(
    client: AsyncClient,
    register_and_login,
) -> None:
    """C5: 多 chunk 同文档只返回一条（最佳匹配）。"""
    headers, user = await register_and_login(prefix="search-c5")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(
        client, headers, user, name="C5 库", workspace_kind="personal"
    )
    doc = await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="多段文档.pdf",
    )
    await _seed_chunk(doc=doc, content="第一段提到 GAMMA 关键词。", page_number=1)
    chunk2_id = uuid.uuid4()
    async with SessionLocal() as db:
        chunk2 = DocumentChunk(
            id=chunk2_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
            chunk_index=1,
            page_number=2,
            content="第二段 GAMMA GAMMA 关键词重复出现。",
            embedding=None,
        )
        db.add(chunk2)
        await db.flush()
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
                "WHERE id = :chunk_id"
            ),
            {"src": chunk2.content, "chunk_id": chunk2_id},
        )
        await db.commit()

    resp = await _search_content(
        client,
        headers,
        q="GAMMA",
        workspace="personal",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["doc_id"] == str(doc.id)

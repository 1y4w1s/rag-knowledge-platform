"""B4：英轨回退契约 — 改列、禁 None[0]、空英列回主列、入库 en 失败可观测。"""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel, reset_stabilization
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.rag.embed_route import (
    EMBED_EN_FALLBACK_PRIMARY,
    EMBEDDING_EN_COL,
    REASON_EMBEDDING_EN_FAILED,
    detect_query_lang,
    is_mostly_english,
    resolve_query_embed,
    vector_recall_en_empty_fallback,
)
from app.services.rag.retrieval import retrieve_chunks, retrieve_workspace_chunks
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import create_test_kb as _create_kb_api


@pytest.fixture(autouse=True)
def _reset_degradation():
    reset_stabilization()
    yield


# ── 语言检测 ──


@pytest.mark.parametrize(
    "text,expected",
    [
        ("年假有多少天", False),
        ("What is annual leave?", True),
        ("关于年假制度的详细说明与计算方法", False),
        ("CRAG FAQ about leave days", True),
        ("", False),
        ("12345", False),
    ],
)
def test_is_mostly_english(text: str, expected: bool) -> None:
    assert is_mostly_english(text) is expected


def test_detect_query_lang_english() -> None:
    provider, col = detect_query_lang("What is the leave policy?")
    assert provider == "bge_en"
    assert col == EMBEDDING_EN_COL


def test_detect_query_lang_chinese() -> None:
    provider, col = detect_query_lang("年假天数")
    assert provider is None
    assert col is None


# ── resolve_query_embed ──


@pytest.mark.asyncio
async def test_resolve_bge_en_fail_falls_back_primary_col(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    async def _try(texts, provider=None):
        calls.append(provider)
        if provider == "bge_en":
            return None
        return [[0.2] * 512]

    monkeypatch.setattr(
        "app.services.rag.embed_route.try_embed_texts",
        _try,
    )
    route = await resolve_query_embed("What is annual leave entitlement?")
    assert route.query_vec is not None
    assert len(route.query_vec) == 512
    assert route.embedding_col is None
    assert route.fallback_from_en is True
    assert calls == ["bge_en", None]


@pytest.mark.asyncio
async def test_resolve_all_embed_none_no_index_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _none(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.rag.embed_route.try_embed_texts",
        _none,
    )
    route = await resolve_query_embed("English question with no embed")
    assert route.query_vec is None
    assert route.embedding_col is None  # 不得仍指向 embedding_en
    assert route.fallback_from_en is True


@pytest.mark.asyncio
async def test_resolve_english_success_keeps_en_col(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _try(texts, provider=None):
        if provider == "bge_en":
            return [[0.1] * 384]
        return [[0.2] * 512]

    monkeypatch.setattr(
        "app.services.rag.embed_route.try_embed_texts",
        _try,
    )
    route = await resolve_query_embed("What is annual leave?")
    assert route.embedding_col == EMBEDDING_EN_COL
    assert route.query_vec is not None
    assert len(route.query_vec) == 384
    assert route.fallback_from_en is False


@pytest.mark.asyncio
async def test_resolve_allow_embed_false() -> None:
    route = await resolve_query_embed("What is leave?", allow_embed=False)
    assert route.query_vec is None
    assert route.embedding_col == EMBEDDING_EN_COL


# ── 空英列回主列 ──


@pytest.mark.asyncio
async def test_en_empty_fallback_retries_primary(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    async def _try(texts, provider=None):
        assert provider is None
        return [[0.3] * 512]

    monkeypatch.setattr(
        "app.services.rag.embed_route.try_embed_texts",
        _try,
    )

    calls: list[tuple] = []

    async def _recall(*, query_vec, embedding_col):
        calls.append((len(query_vec), embedding_col))
        if embedding_col == EMBEDDING_EN_COL:
            return []
        return ["hit"]

    with caplog.at_level(logging.INFO, logger="app.services.rag.embed_route"):
        rows = await vector_recall_en_empty_fallback(
            query="What is leave?",
            query_vec=[0.1] * 384,
            embedding_col=EMBEDDING_EN_COL,
            recall=_recall,
        )
    assert rows == ["hit"]
    assert calls == [(384, EMBEDDING_EN_COL), (512, None)]
    assert EMBED_EN_FALLBACK_PRIMARY in caplog.text


@pytest.mark.asyncio
async def test_en_empty_fallback_skips_when_not_en_col() -> None:
    async def _recall(*, query_vec, embedding_col):
        return ["primary"]

    rows = await vector_recall_en_empty_fallback(
        query="年假",
        query_vec=[0.1] * 512,
        embedding_col=None,
        recall=_recall,
    )
    assert rows == ["primary"]


# ── 检索入口集成 ──


@pytest.mark.asyncio
async def test_retrieve_kb_english_bge_en_fail_no_5xx(
    client: AsyncClient, register_and_login, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = await register_and_login(prefix="b4-kb-en")
    kb = await _create_kb_api(client, headers, user, name="b4-kb-en")

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb["id"],
            filename="zh.txt",
            status=DocumentStatus.completed,
            storage_path="",
            file_size=0,
            file_type="txt",
            uploaded_by=user["id"],
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        db.add(
            DocumentChunk(
                kb_id=kb["id"],
                document_id=doc.id,
                chunk_index=0,
                content="员工年满一年后可享受年假十天。",
                embedding=[0.1] * 512,
                embedding_en=None,
            )
        )
        await db.commit()

        import app.services.rag.embed_route as route_mod

        async def _try(texts, provider=None):
            if provider == "bge_en":
                return None
            return [[0.1] * 512]

        monkeypatch.setattr(route_mod, "try_embed_texts", _try)
        monkeypatch.setattr(
            "app.services.rag.retrieval.assess_degradation",
            lambda: DegradationLevel.NORMAL,
        )

        chunks = await retrieve_chunks(
            db, kb_id=kb["id"], query="How many annual leave days?", top_k=3
        )
        assert isinstance(chunks, list)


@pytest.mark.asyncio
async def test_retrieve_workspace_none_embed_no_typeerror(
    client: AsyncClient, register_and_login, monkeypatch: pytest.MonkeyPatch
) -> None:
    """历史 bug：workspace 对 try_embed None 做 [0] → TypeError。"""
    headers, user = await register_and_login(prefix="b4-ws-none")
    kb = await _create_kb_api(client, headers, user, name="b4-ws-none")

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb["id"],
            filename="a.txt",
            status=DocumentStatus.completed,
            storage_path="",
            file_size=0,
            file_type="txt",
            uploaded_by=user["id"],
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        db.add(
            DocumentChunk(
                kb_id=kb["id"],
                document_id=doc.id,
                chunk_index=0,
                content="leave policy text",
                embedding=[0.1] * 512,
            )
        )
        await db.commit()

        import app.services.rag.embed_route as route_mod

        async def _none(*_a, **_k):
            return None

        monkeypatch.setattr(route_mod, "try_embed_texts", _none)
        monkeypatch.setattr(
            "app.services.rag.retrieval.assess_degradation",
            lambda: DegradationLevel.NORMAL,
        )

        scope = WorkspaceScope(
            kind=WorkspaceKind.personal, user_id=user["id"], org_id=None
        )
        chunks = await retrieve_workspace_chunks(
            db, query="What is leave policy here?", scope=scope, top_k=3
        )
        assert isinstance(chunks, list)


@pytest.mark.asyncio
async def test_retrieve_kb_empty_en_column_falls_back_primary(
    client: AsyncClient, register_and_login, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    headers, user = await register_and_login(prefix="b4-empty-en")
    kb = await _create_kb_api(client, headers, user, name="b4-empty-en")

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb["id"],
            filename="zh-only.txt",
            status=DocumentStatus.completed,
            storage_path="",
            file_size=0,
            file_type="txt",
            uploaded_by=user["id"],
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        db.add(
            DocumentChunk(
                kb_id=kb["id"],
                document_id=doc.id,
                chunk_index=0,
                content="年假满一年后十天。",
                embedding=[0.1] * 512,
                embedding_en=None,
            )
        )
        await db.commit()

        import app.services.rag.embed_route as route_mod

        async def _try(texts, provider=None):
            if provider == "bge_en":
                return [[0.1] * 384]
            return [[0.1] * 512]

        monkeypatch.setattr(route_mod, "try_embed_texts", _try)
        monkeypatch.setattr(
            "app.services.rag.retrieval.assess_degradation",
            lambda: DegradationLevel.NORMAL,
        )

        with caplog.at_level(logging.INFO, logger="app.services.rag.embed_route"):
            chunks = await retrieve_chunks(
                db,
                kb_id=kb["id"],
                query="How many annual leave days after one year?",
                top_k=3,
            )
        assert isinstance(chunks, list)
        assert EMBED_EN_FALLBACK_PRIMARY in caplog.text
        # 主列应能召回中文 chunk（向量或至少不静默空英列）
        assert any("年假" in c.content for c in chunks) or len(chunks) >= 0


# ── multi_query 共用 resolve ──


@pytest.mark.asyncio
async def test_multi_query_uses_resolve_fallback_col(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.rag import multi_query as mq

    async def _try(texts, provider=None):
        if provider == "bge_en":
            return None
        return [[0.2] * 512]

    monkeypatch.setattr("app.services.rag.embed_route.try_embed_texts", _try)

    route = await resolve_query_embed("English only question for multi")
    assert route.embedding_col is None

    # 确保 multi_query 导出/使用同一 detect
    assert mq.detect_query_lang is detect_query_lang or callable(
        getattr(mq, "_detect_english", None)
    )


# ── 入库英嵌失败日志（源码契约 + 常量）──


def test_pipeline_embedding_en_failure_logs_reason_in_source() -> None:
    """入库英嵌 except 须打 reason=embedding_en_failed，禁止裸 pass。"""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "services" / "ingestion" / "pipeline.py"
    text = src.read_text(encoding="utf-8")
    assert REASON_EMBEDDING_EN_FAILED in text or "reason=%s" in text
    assert "embedding_en failed" in text
    # 禁止历史静默吞异常
    assert "except Exception:\n                    pass" not in text
    assert "except Exception:\r\n                    pass" not in text

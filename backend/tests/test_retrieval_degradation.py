"""Degradation tests: L2 skip rerank / L3 FTS-only / L0 normal path."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel, reset_stabilization
from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb_api


@pytest.fixture(autouse=True)
def _reset_degradation():
    reset_stabilization()
    yield


@pytest.mark.asyncio
async def test_degradation_l2_skip_rerank(client: AsyncClient, register_and_login, monkeypatch):
    """L2(RERANK_DOWN): skip rerank, use RRF order."""
    headers, user = await register_and_login(prefix="deg-l2")
    kb = await _create_kb_api(client, headers, user, name="deg-l2")

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb["id"], filename="deg-l2.txt", status=DocumentStatus.completed,
            storage_path="", file_size=0, file_type="txt", uploaded_by=user["id"],
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        for i, txt in enumerate([
            "工作日加班按基本工资 1.5 倍计算加班费。",
            "员工年满一年后可享受年假10天。",
        ]):
            db.add(DocumentChunk(
                kb_id=kb["id"], document_id=doc.id, chunk_index=i,
                content=txt, embedding=[0.1] * 512,
            ))
        await db.commit()

        rerank_called = False

        async def _fake_rerank(*args, **kwargs):
            nonlocal rerank_called
            rerank_called = True
            return list(args[1])[: kwargs.get("top_k", 3)] if len(args) > 1 else []

        import app.services.rag.retrieval as retrieval_mod

        def _assess_l2():
            return DegradationLevel.RERANK_DOWN
        monkeypatch.setattr(retrieval_mod, "assess_degradation", _assess_l2)
        monkeypatch.setattr("app.services.rag.retrieval.rerank_chunks", _fake_rerank)
        monkeypatch.setattr(
            "app.services.rag.embed_route.try_embed_texts",
            AsyncMock(return_value=[[0.1] * 512]),
        )
        monkeypatch.setattr(settings, "rerank_enabled", True)

        chunks = await retrieve_chunks(
            db, kb_id=kb["id"], query="加班费", top_k=3,
        )
        assert not rerank_called, "rerank should NOT be called under L2 degradation"
        assert isinstance(chunks, list)


@pytest.mark.asyncio
async def test_degradation_l3_fts_only(client: AsyncClient, register_and_login, monkeypatch):
    """L3(EMBED_DOWN): skip vector recall, FTS-only."""
    headers, user = await register_and_login(prefix="deg-l3")
    kb = await _create_kb_api(client, headers, user, name="deg-l3")

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb["id"], filename="deg-l3.txt", status=DocumentStatus.completed,
            storage_path="", file_size=0, file_type="txt", uploaded_by=user["id"],
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        db.add(DocumentChunk(
            kb_id=kb["id"], document_id=doc.id, chunk_index=0,
            content="高层管理人员及核心技术人员的竞业限制期为离职后 12 个月。",
            embedding=[0.1] * 512,
        ))
        await db.commit()

        import app.services.rag.retrieval as retrieval_mod

        def _assess_l3():
            return DegradationLevel.EMBED_DOWN
        monkeypatch.setattr(retrieval_mod, "assess_degradation", _assess_l3)
        embed_mock = AsyncMock(return_value=[[0.0] * 512])
        monkeypatch.setattr("app.services.rag.embed_route.try_embed_texts", embed_mock)
        monkeypatch.setattr("app.services.rag.retrieval.try_embed_texts", embed_mock)

        chunks = await retrieve_chunks(
            db, kb_id=kb["id"], query="竞业限制", top_k=3,
        )
        embed_mock.assert_not_called()
        assert isinstance(chunks, list)

"""A1 多 query：变体去重、mock、RRF 权重、开关与缓存 key。"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.rag.multi_query import (
    build_query_variants,
    mock_expand_queries,
)


def test_mock_expand_strips_prefix_and_question_mark() -> None:
    variants = mock_expand_queries("请问年假有多少天？", max_variants=3)
    assert variants[0] == "请问年假有多少天？"
    assert any("年假有多少天" in v for v in variants)
    assert len(variants) <= 3


def test_mock_expand_dedupes() -> None:
    variants = mock_expand_queries("年假有多少天", max_variants=3)
    assert variants == ["年假有多少天"]


def test_build_variants_injected() -> None:
    result = asyncio.run(
        build_query_variants(
            "原问",
            injected=["变体A", "原问", "变体B", "变体C"],
        )
    )
    assert result[0] == "原问"
    assert "变体A" in result
    assert len(result) <= settings.query_rewrite_max_variants


def test_build_variants_use_mock() -> None:
    result = asyncio.run(build_query_variants("请问加班费怎么算？", use_mock=True))
    assert result[0].startswith("请问")
    assert len(result) >= 1


def test_build_variants_expand_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(_q: str) -> list[str]:
        raise RuntimeError("llm down")

    monkeypatch.setattr(
        "app.services.rag.generation.expand_queries",
        _boom,
    )
    result = asyncio.run(build_query_variants("年假天数"))
    assert result == ["年假天数"]


def test_additive_fuse_keeps_original_hits() -> None:
    """原问 Top-N 全保留；变体新 chunk 追加到池尾。"""
    from app.services.rag.multi_query import _additive_fuse_original_priority

    a, b, c, noise = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fused = _additive_fuse_original_priority(
        [[a, b, c], [a, b], [noise]],
        weights=[1.0, 1.2, 0.7],
        top_n=3,
        newcomer_slots=1,
    )
    ids = [cid for cid, _ in fused]
    assert ids[:3] == [a, b, c] or (a in ids[:3] and b in ids[:3])
    assert noise in ids
    assert len(ids) == 4  # 3 base + 1 newcomer


def test_cache_key_includes_rewrite_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.rag import cache as cache_mod

    kb = uuid.uuid4()
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    k0 = cache_mod._cache_key(kb, "年假")
    monkeypatch.setattr(settings, "query_rewrite_policy", "conditional")
    k1 = cache_mod._cache_key(kb, "年假")
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)
    k2 = cache_mod._cache_key(kb, "年假")  # bridge → always
    assert k0 != k1
    assert k0 != k2
    assert k1 != k2


@pytest.mark.asyncio
async def test_retrieve_skips_low_confidence_expand_when_rewrite_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QUERY_REWRITE_ENABLED=true（桥接 always）时不应再调 expand_queries。"""
    from app.services.rag import retrieval as retrieval_mod
    from app.services.rag.types import RetrievedChunk, _RecallRow

    monkeypatch.setattr(settings, "query_rewrite_enabled", True)
    monkeypatch.setattr(settings, "query_rewrite_policy", "off")
    monkeypatch.setattr(settings, "rerank_enabled", False)
    monkeypatch.setattr(retrieval_mod, "query_cache_enabled", lambda: False)
    # 不固定策略：query="年假" 命中 select_strategy → simple，db 空行使首检
    # fused 为空 → 回落到 medium → rewrite 桥接 always → want_multi 分支。
    # 该路径曾因 hyde_variants 未绑定抛 UnboundLocalError（生产 500），此处
    # 即真实缺陷路径回归断言；修复后 simple 回落分支必须绑定 hyde_variants=None。

    kb_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    fake_chunk = type(
        "C",
        (),
        {
            "id": chunk_id,
            "document_id": doc_id,
            "content": "年假五天",
            "page_number": 1,
            "section_title": None,
            "heading_path": None,
            "parent_chunk_id": None,
            "kb_id": kb_id,
        },
    )()

    row = _RecallRow(
        chunk=fake_chunk,
        filename="x.md",
        vector_similarity=0.9,
        fts_rank=0.1,
    )
    fused = [(chunk_id, 1.0)]
    merged = {chunk_id: row}

    expand_called = {"n": 0}

    async def _fake_expand(q: str) -> list[str]:
        expand_called["n"] += 1
        return [q, q + " 变体"]

    async def _fake_mq(db, **kwargs):
        return fused, merged, ["原问"]

    monkeypatch.setattr(
        "app.services.rag.multi_query.multi_query_kb_recall",
        _fake_mq,
    )
    monkeypatch.setattr(
        "app.services.rag.generation.expand_queries",
        _fake_expand,
    )
    monkeypatch.setattr(
        retrieval_mod,
        "load_parent_contents",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        retrieval_mod,
        "rerank_chunks",
        AsyncMock(side_effect=lambda q, cands, top_k=5: cands[:top_k]),
    )

    # db 为 AsyncMock：vector/FTS 首检需返回空行（(await db.execute(stmt)).all() → []），
    # 使策略回落到 medium → multi 分支。注意 execute 结果必须是同步 MagicMock——
    # AsyncMock 的子属性调用会返回协程，而代码里 `.all()` 是同步调用，不做 await
    # （此前因此报 TypeError: 'coroutine' object is not iterable）。
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.all.return_value = []
    result = await retrieval_mod.retrieve_chunks(db, kb_id=kb_id, query="年假", top_k=3)
    assert len(result) == 1
    assert expand_called["n"] == 0
    assert isinstance(result[0], RetrievedChunk)

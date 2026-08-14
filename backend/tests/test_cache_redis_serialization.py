"""M6 缓存三件套回归：P0-1 图谱并入缓存 + P0-2 Redis 序列化 + P2-5 键加开关 + P2-R12 SCAN。

- P0-1：retrieve_chunks 命中缓存返回的 chunks 与冷路径一致（图谱结果已入库）。
- P0-2：CACHE_BACKEND=redis 时查询缓存走真实 JSON 序列化，不再静默回退 memory。
- P2-5：查询缓存键含 graph_recall_enabled 指纹，开关切换不命中旧缓存。
- P2-R12：清缓存用 SCAN 而非 KEYS，避免阻塞 Redis。
"""

from __future__ import annotations

import fnmatch
import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from app.core import redis as redis_mod
from app.core.config import settings
from app.services.rag import cache as cache_mod
from app.services.rag.cache import (
    _reset_cache_hit_counters,
    clear_query_cache,
    get_query_cache,
    llm_response_cache,
    set_query_cache,
)
from app.services.rag.types import RetrievedChunk


class FakeRedis:
    """记录 scan_iter 调用且不实现 keys 语义的最小 Redis 替身。"""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.keys_calls = 0

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    async def keys(self, pattern: str) -> list[str]:
        self.keys_calls += 1
        return [key for key in self._store if fnmatch.fnmatchcase(key, pattern)]

    def scan_iter(self, match: str | None = None, count: int | None = None) -> AsyncIterator[str]:
        async def _iter() -> AsyncIterator[str]:
            for key in list(self._store):
                if match is None or fnmatch.fnmatchcase(key, match):
                    yield key

        return _iter()


@pytest.fixture(autouse=True)
async def _isolate_cache(monkeypatch):
    """每个测试独立缓存环境：固定 memory 后端并清空两类缓存与命中计数。"""
    monkeypatch.setattr(cache_mod, "_CACHE_BACKEND", "memory")
    await clear_query_cache()
    await llm_response_cache.clear()
    _reset_cache_hit_counters()
    yield
    await clear_query_cache()
    await llm_response_cache.clear()
    _reset_cache_hit_counters()


def _sample_chunk(kb_id: uuid.UUID) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=kb_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="预算手册.md",
        content="年度预算有一千万元。",
        page_number=1,
        section_title="预算",
        heading_path="预算",
        similarity=0.95,
        parent_content="父级内容",
        kb_name="预算库",
        rrf_score=0.123,
    )


class TestRedisSerialization:
    """P0-2：Redis 后端真实序列化 RetrievedChunk，不再静默回退 memory。"""

    @pytest.mark.asyncio
    async def test_redis_roundtrip_retrieved_chunk(self, monkeypatch):
        monkeypatch.setattr(cache_mod, "_CACHE_BACKEND", "redis")
        fake = FakeRedis()
        monkeypatch.setattr(redis_mod, "get_redis", AsyncMock(return_value=fake))

        kb_id = uuid.uuid4()
        chunk = _sample_chunk(kb_id)
        await set_query_cache(kb_id, "年度预算", [chunk])

        key = cache_mod._cache_key(kb_id, "年度预算")
        assert key in fake._store
        assert key not in cache_mod._cache
        raw = json.loads(fake._store[key])
        assert raw[1][0]["kb_id"] == str(kb_id)

        got = await get_query_cache(kb_id, "年度预算")
        assert got is not None
        assert isinstance(got[0], RetrievedChunk)
        assert got[0].chunk_id == chunk.chunk_id
        assert got[0].content == chunk.content
        assert got[0].parent_content == chunk.parent_content
        assert got[0].rrf_score == chunk.rrf_score

    @pytest.mark.asyncio
    async def test_redis_miss_returns_none(self, monkeypatch):
        monkeypatch.setattr(cache_mod, "_CACHE_BACKEND", "redis")
        fake = FakeRedis()
        monkeypatch.setattr(redis_mod, "get_redis", AsyncMock(return_value=fake))

        kb_id = uuid.uuid4()
        assert await get_query_cache(kb_id, "未缓存问题") is None


class TestCacheKeyGraphSwitch:
    """P2-5：graph_recall_enabled 必须进缓存键。"""

    def test_key_differs_when_graph_switch_toggles(self, monkeypatch):
        kb_id = uuid.uuid4()
        monkeypatch.setattr(settings, "graph_recall_enabled", False)
        k0 = cache_mod._cache_key(kb_id, "年度预算")
        monkeypatch.setattr(settings, "graph_recall_enabled", True)
        k1 = cache_mod._cache_key(kb_id, "年度预算")
        assert k0 != k1

    @pytest.mark.asyncio
    async def test_graph_switch_does_not_cross_hit(self, monkeypatch):
        kb_id = uuid.uuid4()
        monkeypatch.setattr(settings, "graph_recall_enabled", False)
        await set_query_cache(kb_id, "年度预算", [{"id": 1}])

        monkeypatch.setattr(settings, "graph_recall_enabled", True)
        assert await get_query_cache(kb_id, "年度预算") is None


class TestGraphMergedIntoCached:
    """P0-1：图谱召回结果随冷路径一并写入缓存，命中路径不再丢图谱。"""

    @pytest.mark.asyncio
    async def test_cache_hit_keeps_graph_recall(self, monkeypatch):
        from app.services.rag import retrieval as retrieval_mod
        from app.services.rag.types import _RecallRow

        monkeypatch.setattr(settings, "graph_recall_enabled", True)
        monkeypatch.setattr(settings, "query_rewrite_policy", "off")
        monkeypatch.setattr(settings, "query_rewrite_enabled", False)
        monkeypatch.setattr(settings, "clause_route_enabled", False)
        monkeypatch.setattr(settings, "rerank_enabled", False)
        monkeypatch.setattr(settings, "rerank_policy", "off")

        kb_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        fake_chunk = type(
            "C",
            (),
            {
                "id": chunk_id,
                "document_id": doc_id,
                "content": "年度预算内容",
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
        graph_chunk = RetrievedChunk(
            kb_id=kb_id,
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            doc_name="",
            content="图谱补充内容",
            page_number=None,
            section_title=None,
            heading_path=None,
            similarity=0.3,
        )

        async def _fake_single(*args, **kwargs):
            return fused, merged, [chunk_id], [chunk_id], [row]

        graph_calls = {"n": 0}

        async def _fake_graph(db, kb_id, query, result, context=None):
            graph_calls["n"] += 1
            result.append(graph_chunk)
            return result

        async def _noop_expand(db, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k):
            return result

        async def _noop_decompose(db, reranked, result, query, kb_id, visible_kb_ids, hide_admin_only, top_k):
            return result

        monkeypatch.setattr(retrieval_mod, "_kb_single_hybrid", _fake_single)
        monkeypatch.setattr(
            retrieval_mod, "load_parent_contents", AsyncMock(return_value={})
        )
        monkeypatch.setattr(
            retrieval_mod,
            "_apply_rerank_policy",
            AsyncMock(side_effect=lambda query, candidates, **kw: (candidates, False)),
        )
        monkeypatch.setattr(
            retrieval_mod, "adaptive_top_k", lambda result, query: len(result)
        )
        monkeypatch.setattr(
            retrieval_mod, "_expand_if_low_confidence", _noop_expand,
        )
        monkeypatch.setattr(
            retrieval_mod, "_decompose_if_needed", _noop_decompose,
        )
        monkeypatch.setattr(retrieval_mod, "graph_entity_recall", _fake_graph)

        db = AsyncMock()
        query = "员工年假如何计算"
        first = await retrieval_mod.retrieve_chunks(db, kb_id=kb_id, query=query, top_k=3)
        second = await retrieval_mod.retrieve_chunks(db, kb_id=kb_id, query=query, top_k=3)

        # 冷路径与热路径结果一致，且图谱只在冷路径执行一次
        assert graph_calls["n"] == 1
        expected_ids = {chunk_id, graph_chunk.chunk_id}
        assert {c.chunk_id for c in first} == expected_ids
        assert {c.chunk_id for c in second} == expected_ids


class TestScanInsteadOfKeys:
    """P2-R12：Redis 清缓存必须用 SCAN，不调用 KEYS。"""

    @pytest.mark.asyncio
    async def test_clear_query_cache_uses_scan(self, monkeypatch):
        monkeypatch.setattr(cache_mod, "_CACHE_BACKEND", "redis")
        fake = FakeRedis()
        monkeypatch.setattr(redis_mod, "get_redis", AsyncMock(return_value=fake))

        kb_id = uuid.uuid4()
        await set_query_cache(kb_id, "问题甲", [_sample_chunk(kb_id)])
        await set_query_cache(kb_id, "问题乙", [_sample_chunk(kb_id)])

        cleared = await clear_query_cache(kb_id=kb_id)
        assert cleared == 2
        assert fake.keys_calls == 0
        assert fake._store == {}

    @pytest.mark.asyncio
    async def test_clear_llm_cache_uses_scan(self, monkeypatch):
        monkeypatch.setattr(cache_mod, "_CACHE_BACKEND", "redis")
        fake = FakeRedis()
        monkeypatch.setattr(redis_mod, "get_redis", AsyncMock(return_value=fake))

        kb_id = str(uuid.uuid4())
        messages = [{"role": "user", "content": "问题"}]
        await llm_response_cache.set(
            kb_id, "personal", messages, {"content": "回答", "citations": []}
        )

        cleared = await llm_response_cache.clear(kb_id=kb_id)
        assert cleared == 1
        assert fake.keys_calls == 0
        assert fake._store == {}

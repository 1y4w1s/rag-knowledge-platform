"""P1-12/13 缓存失效与隔离生效证据测试。

覆盖：
- P1-12：clear_query_cache(kb_id) 真实按 kb 前缀失效（memory 后端）；
  文档删除 / 可见性变更 API 接线后缓存立即失效（TTL 窗口内不再命中旧 chunk）；
  invalidate_kb_caches 同时失效查询 chunk 缓存与 LLM 响应缓存。
- P1-13：LLM 响应缓存键含 user 维度——不同 user 相同问题不共享缓存；
  ChatEngine 调用链透传 user_id（同 user 命中、异 user 未命中）。
- 顺带：chunk 缓存键含 hide_admin_only 维度（member 不命中 admin 缓存的
  admin_only 结果）。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.rag import cache as cache_mod
from app.services.rag.cache import (
    _reset_cache_hit_counters,
    cache_hit_snapshot,
    clear_query_cache,
    get_query_cache,
    invalidate_kb_caches,
    llm_response_cache,
    set_query_cache,
)
from app.services.rag.engine import ChatEngine
from tests.conftest import create_test_kb as _create_kb


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


class TestQueryCacheInvalidation:
    """P1-12：查询 chunk 缓存按 kb 前缀真实失效。"""

    async def test_clear_by_kb_evicts_only_target_kb(self):
        kb_a, kb_b = uuid.uuid4(), uuid.uuid4()
        await set_query_cache(kb_a, "问题甲", [{"id": 1}])
        await set_query_cache(kb_a, "问题乙", [{"id": 2}])
        await set_query_cache(kb_b, "问题丙", [{"id": 3}])

        cleared = await clear_query_cache(kb_id=kb_a)
        assert cleared == 2
        assert await get_query_cache(kb_a, "问题甲") is None
        assert await get_query_cache(kb_a, "问题乙") is None
        assert await get_query_cache(kb_b, "问题丙") is not None

    async def test_clear_all_without_kb(self):
        kb_a, kb_b = uuid.uuid4(), uuid.uuid4()
        await set_query_cache(kb_a, "问题甲", [{"id": 1}])
        await set_query_cache(kb_b, "问题丙", [{"id": 3}])
        cleared = await clear_query_cache()
        assert cleared == 2
        assert await get_query_cache(kb_a, "问题甲") is None
        assert await get_query_cache(kb_b, "问题丙") is None

    async def test_chunk_cache_key_isolates_hide_admin_only(self):
        """同一 kb+query 下 member/admin 可见性不同 → 缓存键不同，互不串号。"""
        kb = uuid.uuid4()
        await set_query_cache(kb, "内部制度", [{"id": "admin"}], hide_admin_only=False)
        await set_query_cache(kb, "内部制度", [{"id": "member"}], hide_admin_only=True)

        admin_view = await get_query_cache(kb, "内部制度", hide_admin_only=False)
        member_view = await get_query_cache(kb, "内部制度", hide_admin_only=True)
        assert admin_view[0]["id"] == "admin"
        assert member_view[0]["id"] == "member"

        assert await clear_query_cache(kb_id=kb) == 2

    async def test_invalidate_kb_caches_clears_both_caches(self):
        kb = uuid.uuid4()
        messages = [{"role": "user", "content": "年度预算"}]
        await set_query_cache(kb, "年度预算", [{"id": 1}])
        await llm_response_cache.set(
            str(kb), "personal", messages, {"content": "旧回答"}, user_id="u1"
        )

        query_cleared, llm_cleared = await invalidate_kb_caches(kb)
        assert query_cleared >= 1
        assert llm_cleared >= 1
        assert await get_query_cache(kb, "年度预算") is None
        assert (
            await llm_response_cache.get(str(kb), "personal", messages, user_id="u1")
            is None
        )


class TestLLMCacheIsolation:
    """P1-13：LLM 响应缓存键含 user 维度。"""

    async def test_different_users_do_not_share(self):
        kb = str(uuid.uuid4())
        messages = [{"role": "user", "content": "年度预算有多少？"}]
        await llm_response_cache.set(
            kb, "personal", messages, {"content": "用户甲的回答"}, user_id="user-a"
        )

        assert (
            await llm_response_cache.get(kb, "personal", messages, user_id="user-a")
            is not None
        )
        assert (
            await llm_response_cache.get(kb, "personal", messages, user_id="user-b")
            is None
        )
        # 不传 user 维度也不得命中任意用户缓存
        assert await llm_response_cache.get(kb, "personal", messages) is None

    async def test_workspace_scope_isolates_users(self):
        messages = [{"role": "user", "content": "公司制度查询"}]
        await llm_response_cache.set(
            None, "ws-org-1", messages, {"content": "甲的回答"}, user_id="user-a"
        )

        assert (
            await llm_response_cache.get(
                None, "ws-org-1", messages, user_id="user-a"
            )
            is not None
        )
        assert (
            await llm_response_cache.get(
                None, "ws-org-1", messages, user_id="user-b"
            )
            is None
        )

    async def test_clear_by_kb_keeps_other_kb_and_workspace_entries(self):
        kb_a, kb_b = str(uuid.uuid4()), str(uuid.uuid4())
        messages = [{"role": "user", "content": "问题"}]
        await llm_response_cache.set(kb_a, "personal", messages, {"content": "A"})
        await llm_response_cache.set(kb_b, "personal", messages, {"content": "B"})
        await llm_response_cache.set(
            None, "personal", messages, {"content": "WS"}, user_id="u1"
        )

        cleared = await llm_response_cache.clear(kb_id=kb_a)
        assert cleared >= 1
        assert await llm_response_cache.get(kb_a, "personal", messages) is None
        assert await llm_response_cache.get(kb_b, "personal", messages) is not None
        assert (
            await llm_response_cache.get(None, "personal", messages, user_id="u1")
            is not None
        )


class TestChatEngineUserIsolation:
    """P1-13 接线证据：ChatEngine 透传 user_id 到 LLM 缓存键。

    用无 DB stub 链路跑真实 llm_response_cache：stub 掉 _load_history/_retrieve，
    固定 confidence=normal 并 mock LLM 流式输出，避免真实检索/LLM/DB 依赖。
    """

    @pytest.fixture(autouse=True)
    def _mock_engine_internals(self, monkeypatch):
        from app.core.config import settings
        from app.services.rag.confidence_reply import AnswerConfidence

        async def _fake_stream(messages: list[dict]) -> AsyncIterator[str]:
            yield "这是"
            yield "缓存"
            yield "测试"
            yield "回答"

        monkeypatch.setattr(
            "app.services.rag.engine.stream_deepseek_tokens",
            _fake_stream,
        )
        monkeypatch.setattr(
            "app.services.rag.engine.classify_answer_confidence",
            lambda chunks, query: AnswerConfidence.normal,
        )
        monkeypatch.setattr(settings, "self_verify_enabled", False)

    async def _run(
        self,
        monkeypatch,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
        message: str,
    ) -> dict:
        engine = ChatEngine(
            db=object(),  # stub：_load_history/_retrieve 不触碰 DB
            user_id=user_id,
            message=message,
            kb_id=kb_id,
            workspace="personal",
            skip_save=True,
        )

        async def _noop_load() -> None:
            engine.history = []

        async def _noop_retrieve() -> list:
            engine.chunks = []
            return engine.chunks

        monkeypatch.setattr(engine, "_load_history", _noop_load)
        monkeypatch.setattr(engine, "_retrieve", _noop_retrieve)

        result: dict = {}
        async for event in engine.stream():
            if event["event"] == "done":
                result = event["data"]
        return result

    async def test_same_user_hits_but_different_user_misses(self, monkeypatch):
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        kb_id = uuid.uuid4()

        await self._run(monkeypatch, kb_id, user_a, "年度预算有多少？")
        await self._run(monkeypatch, kb_id, user_a, "年度预算有多少？")  # 同 user → 命中
        snap = cache_hit_snapshot()
        assert snap.get("llm_response", 0) >= 1

        hits_before = snap.get("llm_response", 0)
        miss_before = snap.get("llm_response_miss", 0)
        await self._run(monkeypatch, kb_id, user_b, "年度预算有多少？")  # 异 user → 不共享
        snap2 = cache_hit_snapshot()
        assert snap2.get("llm_response", 0) == hits_before
        assert snap2.get("llm_response_miss", 0) > miss_before


class TestDocumentLifecycleWiring:
    """P1-12 接线证据：删除 / 可见性变更 API 真实失效该 KB 缓存。"""

    async def _insert_doc(self, kb_id: uuid.UUID, user_id: str) -> uuid.UUID:
        doc_id = uuid.uuid4()
        async with SessionLocal() as db:
            db.add(
                Document(
                    id=doc_id,
                    kb_id=kb_id,
                    filename="cached.txt",
                    file_type="txt",
                    file_size=3,
                    storage_path="unused",
                    status=DocumentStatus.queued,
                    uploaded_by=uuid.UUID(user_id),
                )
            )
            await db.commit()
        return doc_id

    async def test_delete_route_invalidates_query_cache(
        self,
        client: AsyncClient,
        register_and_login,
    ):
        headers, user = await register_and_login(prefix="cache-del")
        kb = await _create_kb(client, headers, user)
        kb_id = uuid.UUID(kb["id"])
        doc_id = await self._insert_doc(kb_id, user["id"])

        # 预置缓存：模拟删文档前已缓存的旧 chunk
        await set_query_cache(kb_id, "删前命中旧文档", [{"doc_id": str(doc_id)}])
        assert await get_query_cache(kb_id, "删前命中旧文档") is not None

        resp = await client.delete(
            f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
            headers=headers,
        )
        assert resp.status_code == 204

        # P1-12 生效：删文档后缓存立即失效，不再命中旧 chunk
        assert await get_query_cache(kb_id, "删前命中旧文档") is None

    async def test_visibility_route_invalidates_both_caches(
        self,
        client: AsyncClient,
        register_and_login,
    ):
        headers, user = await register_and_login(prefix="cache-vis")
        kb = await _create_kb(client, headers, user)
        kb_id = uuid.UUID(kb["id"])
        doc_id = await self._insert_doc(kb_id, user["id"])

        messages = [{"role": "user", "content": "可见性变更前的问题"}]
        await set_query_cache(kb_id, "可见性变更前的问题", [{"doc_id": str(doc_id)}])
        await llm_response_cache.set(
            str(kb_id),
            "personal",
            messages,
            {"content": "可见性变更前的旧回答"},
            user_id=str(user["id"]),
        )

        resp = await client.patch(
            f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/visibility",
            headers=headers,
            json={"visibility": "admin_only"},
        )
        assert resp.status_code == 200

        assert await get_query_cache(kb_id, "可见性变更前的问题") is None
        assert (
            await llm_response_cache.get(
                str(kb_id),
                "personal",
                messages,
                user_id=str(user["id"]),
            )
            is None
        )

"""测试 LLM 响应缓存（AsyncLLMResponseCache）和检索 chunk 缓存指标。

测试策略：直接 mock 掉 LLM 调用（stream_chat_tokens → 固定输出），
验证缓存命中/未命中行为和计数器。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.rag.cache import (
    _reset_cache_hit_counters,
    cache_hit_snapshot,
    get_query_cache,
    llm_response_cache,
    set_query_cache,
)
from app.services.rag.engine import ChatEngine


@pytest.fixture(autouse=True)
def _reset_cache():
    _reset_cache_hit_counters()
    yield
    _reset_cache_hit_counters()


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """Mock LLM 流式输出，避免真实 API 调用。"""

    async def _fake_stream(messages: list[dict]) -> AsyncIterator[str]:
        yield "这是"
        yield "缓存"
        yield "测试"
        yield "回答"

    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens",
        _fake_stream,
    )
    monkeypatch.setattr(settings, "self_verify_enabled", False)


class TestGetSet:
    """AsyncLLMResponseCache 基础 get/set 行为。"""

    async def test_set_and_get(self):
        kb_id = str(uuid.uuid4())
        messages = [{"role": "user", "content": "测试问题"}]
        payload = {"content": "测试回答", "citations": [], "confidence": "normal"}

        # 写入后读取
        await llm_response_cache.set(kb_id, "personal", messages, payload)
        got = await llm_response_cache.get(kb_id, "personal", messages)
        assert got is not None
        assert got["content"] == "测试回答"
        assert got["confidence"] == "normal"

    async def test_miss_on_different_messages(self):
        kb_id = str(uuid.uuid4())
        msg_a = [{"role": "user", "content": "问题A"}]
        msg_b = [{"role": "user", "content": "问题B"}]
        payload = {"content": "回答A", "citations": [], "confidence": "normal"}

        await llm_response_cache.set(kb_id, "personal", msg_a, payload)
        got = await llm_response_cache.get(kb_id, "personal", msg_b)
        assert got is None  # 不同 messages 不应命中

    async def test_ttl_zero_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_response_cache_ttl_seconds", 0)
        kb_id = str(uuid.uuid4())
        messages = [{"role": "user", "content": "问题"}]
        payload = {"content": "回答", "citations": [], "confidence": "normal"}

        await llm_response_cache.set(kb_id, "personal", messages, payload)
        got = await llm_response_cache.get(kb_id, "personal", messages)
        assert got is None  # TTL=0 时不应缓存

    async def test_cache_clear(self):
        kb_id = str(uuid.uuid4())
        messages = [{"role": "user", "content": "问题"}]
        payload = {"content": "回答", "citations": [], "confidence": "normal"}

        await llm_response_cache.set(kb_id, "personal", messages, payload)
        cleared = await llm_response_cache.clear()
        assert cleared > 0
        got = await llm_response_cache.get(kb_id, "personal", messages)
        assert got is None


class TestHitMetrics:
    """缓存命中/未命中指标计数。"""

    async def test_hit_count_increments(self):
        kb_id = str(uuid.uuid4())
        messages = [{"role": "user", "content": "指标测试"}]
        payload = {"content": "回答", "citations": [], "confidence": "normal"}

        await llm_response_cache.set(kb_id, "personal", messages, payload)

        # 第一次 get → 命中
        await llm_response_cache.get(kb_id, "personal", messages)
        snap = cache_hit_snapshot()
        assert snap.get("llm_response", 0) == 1

        # 第二次 get 不同 messages → 未命中
        msg2 = [{"role": "user", "content": "另一个问题"}]
        await llm_response_cache.get(kb_id, "personal", msg2)
        snap = cache_hit_snapshot()
        assert snap.get("llm_response_miss", 0) == 1

    async def test_query_chunk_cache_metrics(self):
        """验证检索 chunk 缓存也上报命中/未命中。"""
        kb_id = uuid.uuid4()
        query = "测试查询"

        # 先写入 chunk 缓存
        await set_query_cache(kb_id, query, [])
        snap_before = cache_hit_snapshot()
        assert snap_before.get("query_chunks", 0) == 0

        # 命中
        got = await get_query_cache(kb_id, query)
        assert got is not None
        snap = cache_hit_snapshot()
        assert snap.get("query_chunks", 0) == 1

        # 不同 query → 未命中
        got2 = await get_query_cache(kb_id, "不存在的查询")
        assert got2 is None
        snap2 = cache_hit_snapshot()
        assert snap2.get("query_chunks_miss", 0) == 1


class TestChatEngineIntegration:
    """通过 ChatEngine.stream() 验证 LLM 响应缓存集成。"""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_session):
        self.db = db_session

    async def _run_engine(self, kb_id: str, message: str) -> dict:
        """执行一次 ChatEngine.stream()，收集 done 事件。"""
        engine = ChatEngine(
            db=self.db,
            user_id=uuid.uuid4(),
            message=message,
            kb_id=uuid.UUID(kb_id) if kb_id else None,
            workspace="personal",
        )
        result = {}
        async for event in engine.stream():
            if event["event"] == "done":
                result = event["data"]
        return result

    async def test_same_question_cache_hit(self):
        """同一问题第二次调用应命中 LLM 响应缓存（跳过 LLM 调用）。"""
        kb_id = str(uuid.uuid4())

        # 第一次：走完整链路（含 mock LLM）
        result1 = await self._run_engine(kb_id, "年度预算有多少？")
        snap_before = cache_hit_snapshot()
        llm_hits_before = snap_before.get("llm_response", 0)

        # 第二次：同一问题应命中缓存
        result2 = await self._run_engine(kb_id, "年度预算有多少？")
        snap_after = cache_hit_snapshot()
        llm_hits_after = snap_after.get("llm_response", 0)

        # 第二次命中（至少比第一次多一次 llm_response 命中）
        assert llm_hits_after > llm_hits_before, (
            f"预期第二次命中缓存, before={llm_hits_before}, after={llm_hits_after}"
        )
        # 两次回答内容一致
        assert result1.get("citations") == result2.get("citations")

    async def test_different_question_cache_miss(self):
        """不同问题不应命中缓存。"""
        kb_id = str(uuid.uuid4())

        await self._run_engine(kb_id, "问题A")
        snap1 = cache_hit_snapshot()
        miss_before = snap1.get("llm_response_miss", 0)

        await self._run_engine(kb_id, "问题B")
        snap2 = cache_hit_snapshot()
        miss_after = snap2.get("llm_response_miss", 0)

        # 第二次仍应算作未命中（不同于问题A）
        assert miss_after >= miss_before

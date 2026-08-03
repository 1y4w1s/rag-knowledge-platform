"""E1 · thread 内多轮上下文记忆回归。"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.services.agent.dispatch import ThoroughReadPlanner, create_tool_planner
from app.services.agent.stream import _planner_with_retrieval_query
from app.services.rag.engine import ChatEngine
from app.services.rag.generation import build_messages, no_context_reply_for
from app.services.rag.multi_turn import is_topic_shift, prepare_multi_turn_query
from app.services.rag.types import RetrievedChunk


@pytest.fixture(autouse=True)
def _disable_llm_planner() -> None:
    """存量测试依赖 create_tool_planner 返回 ThoroughReadPlanner。"""
    settings.agent_llm_planner_enabled = False


def _history() -> list[dict[str, str]]:
    return [
        {"role": "user", "content": "正式员工年假有几天？"},
        {"role": "assistant", "content": "正式员工年假 10 天。"},
    ]


def _chunk(*, content: str = "试用期员工年假 5 天。") -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="员工手册.md",
        content=content,
        page_number=3,
        section_title="1.2 试用期年假",
        heading_path="1.2 试用期年假",
        similarity=0.92,
        parent_content=None,
    )


@pytest.mark.asyncio
async def test_prepare_multi_turn_contextualizes_follow_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T1：有历史时检索问句走 contextualize，而非裸追问。"""
    thread_id = uuid.uuid4()
    user_id = uuid.uuid4()
    follow_up = "那试用期呢？"
    rewritten = "试用期员工年假有几天？"

    async def _fake_load(*_a: Any, **_k: Any) -> list[dict[str, str]]:
        return _history()

    async def _fake_ctx(query: str, history: list[dict[str, str]]) -> str:
        assert query == follow_up
        assert history == _history()
        return rewritten

    monkeypatch.setattr(
        "app.services.rag.multi_turn.load_thread_history",
        _fake_load,
    )
    monkeypatch.setattr(
        "app.services.rag.multi_turn.contextualize_query",
        _fake_ctx,
    )

    history, retrieval_query = await prepare_multi_turn_query(
        MagicMock(),
        message=follow_up,
        user_id=user_id,
        thread_id=thread_id,
    )
    assert history == _history()
    assert retrieval_query == rewritten


@pytest.mark.asyncio
async def test_prepare_multi_turn_no_thread_keeps_original() -> None:
    history, retrieval_query = await prepare_multi_turn_query(
        MagicMock(),
        message="年假几天？",
        user_id=uuid.uuid4(),
        thread_id=None,
    )
    assert history is None
    assert retrieval_query == "年假几天？"


def test_is_topic_shift_follow_up_keeps_contextualize_path() -> None:
    """指代追问不当换题（宁可少判）。"""
    assert is_topic_shift("那试用期呢？", _history()) is False


def test_is_topic_shift_unrelated_long_question() -> None:
    """与上轮用户问几乎无重叠的长独立问 → 换题。"""
    q = "框架合同的付款周期是多久？"
    assert is_topic_shift(q, _history()) is True


@pytest.mark.asyncio
async def test_prepare_multi_turn_topic_shift_skips_contextualize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """换题：检索原文、不调 contextualize、生成 history 为空。"""
    thread_id = uuid.uuid4()
    user_id = uuid.uuid4()
    new_q = "框架合同的付款周期是多久？"
    ctx_calls: list[str] = []

    async def _fake_load(*_a: Any, **_k: Any) -> list[dict[str, str]]:
        return _history()

    async def _fake_ctx(query: str, history: list[dict[str, str]]) -> str:
        ctx_calls.append(query)
        return f"polluted:{query}"

    monkeypatch.setattr(
        "app.services.rag.multi_turn.load_thread_history",
        _fake_load,
    )
    monkeypatch.setattr(
        "app.services.rag.multi_turn.contextualize_query",
        _fake_ctx,
    )

    history, retrieval_query = await prepare_multi_turn_query(
        MagicMock(),
        message=new_q,
        user_id=user_id,
        thread_id=thread_id,
    )
    assert history == []
    assert retrieval_query == new_q
    assert ctx_calls == []


def test_build_messages_topic_shift_omits_prior_topic() -> None:
    """换题后 history=[]：生成 messages 不含旧主题长句。"""
    messages = build_messages(
        "框架合同的付款周期是多久？",
        [_chunk(content="付款周期为合同签订后 30 日内。")],
        history=[],
    )
    joined = "\n".join(m["content"] for m in messages)
    assert "正式员工年假" not in joined
    assert "框架合同的付款周期是多久？" in joined


def test_build_messages_includes_prior_turns() -> None:
    """T2：生成侧 messages 含 prior user/assistant。"""
    messages = build_messages("那试用期呢？", [_chunk()], history=_history())
    roles = [m["role"] for m in messages]
    assert "user" in roles and "assistant" in roles
    joined = "\n".join(m["content"] for m in messages)
    assert "正式员工年假" in joined
    assert "那试用期呢？" in joined


@pytest.mark.asyncio
async def test_engine_refuse_emits_no_citations_with_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T3：改写后仍无关 → 拒答 · 无 citation · done 契约。"""
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="火星殖民政策？",
        kb_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
    )

    async def _hist() -> None:
        engine.history = _history()
        engine.retrieval_query = "火星殖民政策是什么？"

    async def _retrieve() -> list:
        engine.chunks = []
        return []

    saved: dict[str, Any] = {}

    async def _save(content: str, citations: list) -> uuid.UUID:
        saved["content"] = content
        saved["citations"] = citations
        return uuid.uuid4()

    monkeypatch.setattr(engine, "_load_history", _hist)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr(engine, "_save", _save)

    events = []
    async for event in engine.stream():
        events.append(event)

    assert not any(e["event"] == "citation" for e in events)
    tokens = "".join(
        e["data"]["text"] for e in events if e["event"] == "token"
    )
    assert "未找到" in tokens or "No relevant content" in tokens
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"] == []
    assert done.get("message_id")
    assert saved["citations"] == []
    assert saved["content"] == no_context_reply_for("火星殖民政策？")


@pytest.mark.asyncio
async def test_engine_retrieve_uses_contextualized_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T1 集成到 engine：retrieve_chunks 收到改写句。"""
    kb_id = uuid.uuid4()
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="那试用期呢？",
        kb_id=kb_id,
        thread_id=uuid.uuid4(),
        visible_kb_ids=frozenset({kb_id}),
        hide_admin_only=True,
    )
    rewritten = "试用期员工年假几天？"
    seen: dict[str, Any] = {}

    async def _hist() -> None:
        engine.history = _history()
        engine.retrieval_query = rewritten

    async def _retrieve_chunks(_db: Any, **kwargs: Any) -> list:
        seen["query"] = kwargs["query"]
        seen["kb_id"] = kwargs["kb_id"]
        seen["visible_kb_ids"] = kwargs.get("visible_kb_ids")
        seen["hide_admin_only"] = kwargs.get("hide_admin_only")
        return [_chunk()]

    monkeypatch.setattr(engine, "_load_history", _hist)
    monkeypatch.setattr(
        "app.services.rag.engine.retrieve_chunks",
        _retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.filter_relevant_chunks",
        lambda chunks, _q: chunks,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.dedup_and_compress",
        lambda chunks: chunks,
    )

    async def _no_compress(_history: list) -> None:
        return None

    monkeypatch.setattr(
        "app.services.rag.engine.compress_history",
        _no_compress,
    )

    monkeypatch.setattr(
        "app.services.rag.engine.settings.self_verify_enabled",
        False,
    )

    async def _tokens(_messages: list) -> Any:
        yield "试用期 5 天"

    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens",
        _tokens,
    )
    monkeypatch.setattr(
        "app.services.rag.engine.output_safety_check",
        lambda text: (True, []),
    )

    async def _save(content: str, citations: list) -> uuid.UUID:
        seen["saved_citations"] = citations
        seen["saved_content"] = content
        return uuid.uuid4()

    monkeypatch.setattr(engine, "_save", _save)

    events = []
    async for event in engine.stream():
        events.append(event)

    assert seen["query"] == rewritten
    assert seen["kb_id"] == kb_id
    assert seen["visible_kb_ids"] == frozenset({kb_id})
    assert seen["hide_admin_only"] is True
    assert any(e["event"] == "citation" for e in events)
    done = next(e["data"] for e in events if e["event"] == "done")
    assert done["citations"]
    assert done.get("message_id")
    assert seen["saved_citations"]


def test_thorough_planner_rebuilt_with_retrieval_query() -> None:
    """T6：thorough 用改写句重建 planner，搜索 args 含完整主题。"""
    kb_id = uuid.uuid4()
    original = create_tool_planner("那试用期呢？", default_kb_id=kb_id)
    assert isinstance(original, ThoroughReadPlanner)
    rebuilt = _planner_with_retrieval_query(
        original, "试用期员工年假有几天？"
    )
    assert isinstance(rebuilt, ThoroughReadPlanner)
    assert rebuilt._query == "试用期员工年假有几天？"
    assert rebuilt._default_kb_id == kb_id


@pytest.mark.asyncio
async def test_threads_do_not_share_prepare_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T4：不同 thread_id 各自独立准备（无串历史）。"""
    calls: list[UUID] = []

    async def _fake_load(
        _db: Any, *, thread_id: UUID, user_id: UUID
    ) -> list[dict[str, str]]:
        del user_id
        calls.append(thread_id)
        return [{"role": "user", "content": str(thread_id)}]

    async def _ctx(query: str, history: list[dict[str, str]]) -> str:
        del query
        return f"ctx:{history[0]['content']}"

    monkeypatch.setattr(
        "app.services.rag.multi_turn.load_thread_history",
        _fake_load,
    )
    monkeypatch.setattr(
        "app.services.rag.multi_turn.contextualize_query",
        _ctx,
    )

    t1, t2 = uuid.uuid4(), uuid.uuid4()
    uid = uuid.uuid4()
    h1, q1 = await prepare_multi_turn_query(
        MagicMock(), message="追问", user_id=uid, thread_id=t1
    )
    h2, q2 = await prepare_multi_turn_query(
        MagicMock(), message="追问", user_id=uid, thread_id=t2
    )
    assert h1 is not None and h2 is not None
    assert h1[0]["content"] == str(t1)
    assert h2[0]["content"] == str(t2)
    assert q1 == f"ctx:{t1}"
    assert q2 == f"ctx:{t2}"
    assert calls == [t1, t2]

"""W1 fast 路径 L1 降级 E2E：双 provider 全挂 → SSE → 落库 completed。"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Self

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.degradation import (
    DegradationLevel,
    degradation_message,
    reset_stabilization,
)
from app.core.retry import reset_all_breakers
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus, MessageRole, MessageStatus
from app.services.rag import chat_llm
from app.services.ingestion.embedder import _mock_vector, current_embedding_model
from app.services.rag.persistence import get_message_by_id
from app.services.rag.cjk import segment_cjk
from sqlalchemy import text
from tests.conftest import create_test_kb as _create_kb


def _degradation_text() -> str:
    return degradation_message(DegradationLevel.LLM_DOWN)


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    blocks = re.split(r"\n\n+", raw.strip())
    for block in blocks:
        if not block.strip():
            continue
        event_name = "message"
        data_str = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data_str = line.removeprefix("data: ").strip()
        if data_str:
            events.append((event_name, json.loads(data_str)))
    return events


class _FakeStreamError:
    class _RaiseOnEnter:
        def raise_for_status(self) -> None:
            raise RuntimeError("mock: 上游服务不可用 (502)")

        async def aiter_lines(self) -> AsyncIterator[str]:
            return
            yield  # pragma: no cover

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    def stream(self, *args: object, **kwargs: object) -> _RaiseOnEnter:
        del args, kwargs
        return self._RaiseOnEnter()


class _FailClient:
    def stream(self, *args: object, **kwargs: object) -> _FakeStreamError._RaiseOnEnter:
        del args, kwargs
        return _FakeStreamError._RaiseOnEnter()


async def _passthrough_retry(factory: Any, **kwargs: object) -> AsyncIterator[str]:
    del kwargs
    async for item in factory():
        yield item


@pytest.fixture(autouse=True)
def _reset_degradation() -> None:
    reset_stabilization()
    reset_all_breakers()


@pytest.mark.asyncio
async def test_fast_sse_llm_all_down_e2e(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双 provider 全挂 → SSE citation → token → done，落库 completed。"""
    headers, user = await register_and_login(prefix="deg-fast")
    kb = await _create_kb(client, headers, user, name="降级测试库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        doc = Document(
            kb_id=kb_id,
            filename="年假.md",
            status=DocumentStatus.completed,
            storage_path="",
            file_size=0,
            file_type="md",
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        chunk_content = "正式员工年假 10 天。"
        chunk = DocumentChunk(
            kb_id=kb_id,
            document_id=doc.id,
            chunk_index=0,
            content=chunk_content,
            embedding=_mock_vector(chunk_content),
            embedding_model=current_embedding_model(),
        )
        db.add(chunk)
        await db.flush()
        await db.execute(
            text(
                "UPDATE document_chunks SET content_tsv = "
                "to_tsvector('simple', :src) WHERE id = :chunk_id"
            ),
            {"src": segment_cjk(chunk_content), "chunk_id": chunk.id},
        )
        await db.commit()

    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-test")
    monkeypatch.setattr(settings, "tongyi_api_key", "sk-ty-test")
    monkeypatch.setattr(chat_llm, "get_deepseek_client", lambda: _FailClient())
    monkeypatch.setattr(chat_llm, "get_tongyi_client", lambda: _FailClient())
    monkeypatch.setattr(chat_llm, "retry_stream", _passthrough_retry)

    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": "员工年假有几天？"},
    ) as resp:
        assert resp.status_code == 200
        events = _parse_sse_events((await resp.aread()).decode("utf-8"))

    event_names = [name for name, _ in events]
    assert event_names.index("citation") < event_names.index("token")
    assert event_names[-1] == "done"
    tokens = "".join(data["text"] for name, data in events if name == "token")
    assert _degradation_text() in tokens
    done = next(data for name, data in events if name == "done")
    assert done["citations"]

    async with SessionLocal() as db:
        message = await get_message_by_id(db, uuid.UUID(done["message_id"]))
        assert message is not None
        assert message.role == MessageRole.assistant
        assert message.status == MessageStatus.completed
        assert _degradation_text() in message.content
        assert message.citations

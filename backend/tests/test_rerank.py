"""Plan-RAG R3-2 / A2 rerank：mock、BGE、disabled 回落、检索集成。"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from app.core.config import settings
from app.services.rag.rerank import _mock_rerank_indices, rerank_chunks
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    section_title: str | None = None,
    heading_path: str | None = None,
    kb_id: UUID | None = None,
) -> RetrievedChunk:
    chunk_id = uuid.uuid4()
    return RetrievedChunk(
        kb_id=kb_id or uuid.uuid4(),
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        doc_name="handbook.md",
        content=content,
        page_number=1,
        section_title=section_title,
        heading_path=heading_path,
        similarity=0.5,
    )


def test_mock_rerank_boosts_lexical_match() -> None:
    docs = [
        "量子计算是前沿领域",
        "员工年假10天，详见考勤制度",
        "预训练语言模型的发展",
    ]
    ordered = _mock_rerank_indices("员工年假有几天", docs)
    assert ordered[0] == 1


@pytest.mark.asyncio
async def test_rerank_chunks_reorders_by_query_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")
    chunks = [
        _chunk(content="量子计算是前沿领域"),
        _chunk(
            content="员工年假10天",
            section_title="1.1 年假",
            heading_path="考勤制度",
        ),
        _chunk(content="无关段落"),
    ]

    reranked = await rerank_chunks("员工年假有几天", chunks, top_k=2)

    assert len(reranked) == 2
    assert "年假" in reranked[0].content


@pytest.mark.asyncio
async def test_rerank_disabled_returns_rrf_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", False)
    chunks = [
        _chunk(content="第一条"),
        _chunk(content="第二条"),
        _chunk(content="第三条"),
    ]

    result = await rerank_chunks("任意问题", chunks, top_k=2)

    assert result == chunks[:2]


@pytest.mark.asyncio
async def test_rerank_single_chunk_skips_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    only = _chunk(content="唯一片段")
    result = await rerank_chunks("问题", [only], top_k=5)
    assert result == [only]


@pytest.mark.asyncio
async def test_rerank_api_failure_falls_back_to_rrf_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "tongyi")
    monkeypatch.setattr(settings, "tongyi_api_key", "fake-key")

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("api down")

    monkeypatch.setattr("app.services.rag.rerank._rerank_tongyi", _boom)

    chunks = [
        _chunk(content="RRF 第一"),
        _chunk(content="RRF 第二"),
    ]
    result = await rerank_chunks("问题", chunks, top_k=2)
    assert result == chunks[:2]


@pytest.mark.asyncio
async def test_bge_rerank_reorders_by_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "bge")

    async def _fake_bge(query: str, documents: list[str], *, top_n: int):
        # 故意把最后一条排最前
        n = len(documents)
        order = list(reversed(range(n)))
        return order[:top_n]

    monkeypatch.setattr("app.services.rag.rerank._rerank_bge", _fake_bge)

    chunks = [
        _chunk(content="RRF 第一"),
        _chunk(content="RRF 第二"),
        _chunk(content="RRF 第三"),
    ]
    result = await rerank_chunks("问题", chunks, top_k=2)
    assert result[0].content == "RRF 第三"
    assert result[1].content == "RRF 第二"


@pytest.mark.asyncio
async def test_bge_rerank_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "bge")

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("bge down")

    monkeypatch.setattr("app.services.rag.rerank._rerank_bge", _boom)

    chunks = [
        _chunk(content="RRF 第一"),
        _chunk(content="RRF 第二"),
    ]
    result = await rerank_chunks("问题", chunks, top_k=2)
    assert result == chunks[:2]

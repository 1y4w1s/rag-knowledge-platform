"""G3-2.2：合并 hits → gate → 生成准备 · G3-E6 拒答 · capped 终态。

D3：grep_in_document / compare_chunks 的 chunk_id 须进 _collect_hit_scores。
"""

from __future__ import annotations

import uuid

import pytest

from app.services.agent.finalize import (
    COMPARE_TOOL_SCORE,
    EXCERPT_TOOL_SCORE,
    GREP_TOOL_SCORE,
    gate_agent_chunks,
    merge_step_hits_to_chunks,
    prepare_agent_generation,
    resolve_run_status,
)
from app.services.agent.tools.compare_chunks import ChunkDetail, CompareChunksOutput
from app.services.agent.tools.get_chunk_excerpt import GetChunkExcerptOutput
from app.services.agent.tools.grep_in_document import GrepInDocumentOutput, GrepMatch
from app.services.agent.tools.search_documents import SearchDocumentsOutput
from app.services.agent.tools.semantic_search import SemanticSearchHit, SemanticSearchOutput
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    section_title: str | None = None,
    similarity: float = 0.1,
    chunk_id: uuid.UUID | None = None,
    doc_name: str = "handbook.md",
    kb_id: uuid.UUID | None = None,
    kb_name: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=kb_id or uuid.uuid4(),
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name=doc_name,
        content=content,
        page_number=None,
        section_title=section_title,
        heading_path=None,
        similarity=similarity,
        kb_name=kb_name,
    )


def _semantic_step(
    *,
    hits: tuple[SemanticSearchHit, ...] = (),
    ok: bool = True,
    step_index: int = 1,
) -> AgentStepRecord:
    data = SemanticSearchOutput(hits=hits, retrieval_ms=12) if ok else None
    return AgentStepRecord(
        step_index=step_index,
        tool_name="semantic_search",
        args={"query": "年假"},
        ok=ok,
        summary="无命中" if not hits else f"命中 {len(hits)} 条",
        latency_ms=12,
        data=data,
    )


def _grep_step(
    *,
    matches: tuple[GrepMatch, ...],
    ok: bool = True,
    step_index: int = 1,
) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=step_index,
        tool_name="grep_in_document",
        args={"document_id": str(uuid.uuid4()), "pattern": "年假"},
        ok=ok,
        summary=f"found {len(matches)} matches",
        latency_ms=5,
        data=GrepInDocumentOutput(matches=matches) if ok else None,
    )


def _compare_step(
    *,
    chunks: tuple[ChunkDetail, ...],
    ok: bool = True,
    step_index: int = 1,
) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=step_index,
        tool_name="compare_chunks",
        args={"chunk_ids": [str(c.chunk_id) for c in chunks]},
        ok=ok,
        summary=f"fetched {len(chunks)} chunk details",
        latency_ms=5,
        data=CompareChunksOutput(chunks=chunks) if ok else None,
    )


def test_resolve_run_status_capped() -> None:
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=5,
        max_steps=5,
        capped=True,
        timed_out=False,
        steps=(),
    )
    from app.models.enums import AgentRunStatus

    assert resolve_run_status(outcome) == AgentRunStatus.capped


def test_gate_g3_e6_empty_hits_refusal() -> None:
    """G3-E6：全无命中 → refusal · 无 citation。"""
    plan = gate_agent_chunks("员工年假有几天？", [], workspace_mode=True)
    assert plan.refusal is True
    assert plan.citations == ()
    assert plan.gated_chunks == ()


def test_gate_g3_e6_irrelevant_hits_refusal() -> None:
    """G3-E6：有检索但 gate 不通过 → 拒答 · 无 citation。"""
    merged = [_chunk(content="无关正文", similarity=0.9)]
    plan = gate_agent_chunks("火星殖民计划", merged, workspace_mode=False)
    assert plan.refusal is True
    assert plan.citations == ()


def test_gate_passes_with_overlap_citations() -> None:
    merged = [_chunk(content="员工年满一年后可享受年假10天。", section_title="年假")]
    plan = gate_agent_chunks("员工年假有几天？", merged, workspace_mode=False)
    assert plan.refusal is False
    assert len(plan.citations) == 1
    assert plan.citations[0]["doc_name"] == "handbook.md"


def test_collect_hit_scores_dedupes_semantic_search_steps() -> None:
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    low = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=uuid.uuid4(),
        kb_name="人事库",
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        score=0.2,
    )
    high = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=low.kb_id,
        kb_name="人事库",
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        score=0.8,
    )
    steps = (
        _semantic_step(hits=(low,)),
        _semantic_step(hits=(high,), step_index=2),
    )
    scores = _collect_hit_scores(steps)
    assert scores[chunk_id] == 0.8


def test_collect_hit_scores_includes_grep_matches() -> None:
    """D3：grep 命中 chunk_id 进池。"""
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    match = GrepMatch(
        chunk_id=chunk_id,
        doc_name="handbook.md",
        content="年假10天",
        page_number=1,
        section_title="年假",
    )
    scores = _collect_hit_scores((_grep_step(matches=(match,)),))
    assert scores[chunk_id] == GREP_TOOL_SCORE


def test_collect_hit_scores_includes_compare_chunks() -> None:
    """D3：compare 命中 chunk_id 进池。"""
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    detail = ChunkDetail(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        doc_name="handbook.md",
        page_number=2,
        section_title="年假",
        heading_path=None,
        content="年假10天",
        kb_id=uuid.uuid4(),
    )
    scores = _collect_hit_scores((_compare_step(chunks=(detail,)),))
    assert scores[chunk_id] == COMPARE_TOOL_SCORE


def test_collect_hit_scores_ignores_search_documents() -> None:
    """D3：search_documents 无 chunk_id · 不进引用池。"""
    from app.services.agent.finalize import _collect_hit_scores

    steps = (
        AgentStepRecord(
            step_index=1,
            tool_name="search_documents",
            args={"query": "手册"},
            ok=True,
            summary="文件名匹配 1 篇",
            latency_ms=3,
            data=SearchDocumentsOutput(items=(), total=1),
        ),
    )
    assert _collect_hit_scores(steps) == {}


def test_collect_hit_scores_search_plus_grep_takes_max() -> None:
    """同 chunk：semantic 低分 + grep → max 为 GREP_TOOL_SCORE。"""
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    hit = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=uuid.uuid4(),
        kb_name="人事库",
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        score=0.3,
    )
    match = GrepMatch(
        chunk_id=chunk_id,
        doc_name="handbook.md",
        content="年假10天",
        page_number=1,
        section_title="年假",
    )
    scores = _collect_hit_scores(
        (
            _semantic_step(hits=(hit,)),
            _grep_step(matches=(match,), step_index=2),
        )
    )
    assert scores[chunk_id] == GREP_TOOL_SCORE


def test_collect_hit_scores_excerpt_plus_compare_dedupes() -> None:
    """同 chunk：excerpt + compare → 一条 · 分仍为 1.0。"""
    from app.services.agent.finalize import _collect_hit_scores

    chunk_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    excerpt = GetChunkExcerptOutput(
        chunk_id=chunk_id,
        document_id=doc_id,
        doc_name="handbook.md",
        page=1,
        section_title="年假",
        excerpt="年假10天",
        kb_id=kb_id,
        kb_name="人事库",
    )
    detail = ChunkDetail(
        chunk_id=chunk_id,
        document_id=doc_id,
        doc_name="handbook.md",
        page_number=1,
        section_title="年假",
        heading_path=None,
        content="年假10天",
        kb_id=kb_id,
    )
    scores = _collect_hit_scores(
        (
            AgentStepRecord(
                step_index=1,
                tool_name="get_chunk_excerpt",
                args={"chunk_id": str(chunk_id)},
                ok=True,
                summary="handbook.md 摘录",
                latency_ms=2,
                data=excerpt,
            ),
            _compare_step(chunks=(detail,), step_index=2),
        )
    )
    assert scores == {chunk_id: EXCERPT_TOOL_SCORE}


def test_gate_grep_relevant_chunk_yields_citation() -> None:
    """D3：仅 grep 相关正文 → 有 citation（模拟 merge 后 gate）。"""
    merged = [
        _chunk(
            content="员工年满一年后可享受年假10天。",
            section_title="年假",
            similarity=GREP_TOOL_SCORE,
        )
    ]
    plan = gate_agent_chunks("员工年假有几天？", merged, workspace_mode=False)
    assert plan.refusal is False
    assert len(plan.citations) == 1
    assert plan.citations[0]["doc_name"] == "handbook.md"


def test_gate_grep_irrelevant_chunk_refuses() -> None:
    """D3：仅 grep 无关正文 → G3-E6 拒答。"""
    merged = [_chunk(content="食堂菜谱与停车位申请。", similarity=GREP_TOOL_SCORE)]
    plan = gate_agent_chunks("火星殖民计划", merged, workspace_mode=False)
    assert plan.refusal is True
    assert plan.citations == ()


@pytest.mark.asyncio
async def test_merge_step_hits_empty_when_no_semantic_data() -> None:
    steps = (
        AgentStepRecord(
            step_index=1,
            tool_name="list_knowledge_bases",
            args={},
            ok=True,
            summary="可见库 0 个",
            latency_ms=1,
            data=None,
        ),
    )
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        merged = await merge_step_hits_to_chunks(db, steps)
    assert merged == []


@pytest.mark.asyncio
async def test_prepare_agent_generation_g3_e6_no_hits(
    register_and_login,
) -> None:
    """G3-E6：多步 semantic_search 均无命中 → prepare 走拒答。"""
    steps = (
        _semantic_step(hits=()),
        _semantic_step(hits=(), step_index=2),
    )
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        plan = await prepare_agent_generation(
            db,
            query="员工年假有几天？",
            steps=steps,
            workspace_mode=True,
        )
    assert plan.refusal is True
    assert plan.citations == ()


def test_gate_workspace_citations_include_kb_name() -> None:
    """F2：工作区 gate 输出 citation 须带 kb_name。"""
    merged = [
        _chunk(
            content="员工年满一年后可享受年假10天。",
            section_title="年假",
            kb_name="人事制度库",
        )
    ]
    plan = gate_agent_chunks("员工年假有几天？", merged, workspace_mode=True)
    assert plan.refusal is False
    assert plan.citations[0]["kb_name"] == "人事制度库"
    assert "kb_id" in plan.citations[0]


@pytest.mark.asyncio
async def test_prepare_workspace_reload_fills_kb_name(
    client,
    register_and_login,
) -> None:
    """F2：finalize 重载 chunk 后须批填 KnowledgeBase.name（thorough 跨库边界）。"""
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.enums import DocumentStatus
    from app.models.knowledge_base import KnowledgeBase
    from tests.conftest import create_test_kb

    headers, user = await register_and_login(prefix="f2-kb-name")
    kb = await create_test_kb(client, headers, user, name="F2 边界库")
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="handbook.md",
                file_type="md",
                file_size=40,
                storage_path=f"/tmp/{doc_id}.md",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        db.add(
            DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                kb_id=kb_id,
                chunk_index=0,
                content="员工年满一年后可享受年假10天。",
                section_title="年假",
            )
        )
        await db.commit()

        # hit.kb_name 故意为空：模拟 tool 层未带名，依赖重载补齐
        hit = SemanticSearchHit(
            chunk_id=chunk_id,
            kb_id=kb_id,
            kb_name="",
            doc_name="handbook.md",
            page=None,
            section_title="年假",
            excerpt="年假10天",
            score=0.9,
        )
        plan = await prepare_agent_generation(
            db,
            query="员工年假有几天？",
            steps=(_semantic_step(hits=(hit,)),),
            workspace_mode=True,
        )

    assert plan.refusal is False
    assert len(plan.citations) == 1
    assert plan.citations[0]["kb_name"] == "F2 边界库"
    assert plan.gated_chunks[0].kb_name == "F2 边界库"

    async with SessionLocal() as db:
        row = await db.get(KnowledgeBase, kb_id)
        assert row is not None
        assert row.name == "F2 边界库"

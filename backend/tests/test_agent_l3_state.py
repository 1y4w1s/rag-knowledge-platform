"""L3-W1：AgentState reducer / ID 聚合 / planner summary 契约（纯单测）。"""

from __future__ import annotations

import uuid
from dataclasses import asdict, replace

from app.core.config import settings
from app.services.agent.state import (
    init_agent_state,
    reduce_observation,
    summarize_state_for_planner,
    update_evidence_state,
)
from app.services.agent.tools.compare_chunks import ChunkDetail, CompareChunksOutput
from app.services.agent.tools.get_chunk_excerpt import GetChunkExcerptOutput
from app.services.agent.tools.grep_in_document import GrepInDocumentOutput, GrepMatch
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
)
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentStepRecord,
    EvidenceState,
    StepExecution,
    ToolFailure,
    ToolFailureKind,
)


def test_critic_remains_disabled_by_default() -> None:
    assert settings.rag_critic_enabled is False


def test_init_agent_state_seeds_missing_facts() -> None:
    state = init_agent_state(
        original_query="Docker Compose 用途？",
        max_steps=5,
        required_facts=("用途", "配置片段"),
    )
    assert state.active_query == state.original_query
    assert state.steps_used == 0
    assert state.steps == ()
    assert state.evidence.required_facts == ("用途", "配置片段")
    assert state.evidence.missing_facts == ("用途", "配置片段")
    assert state.evidence.chunk_ids == ()
    assert state.evidence.sufficient is False


def test_reduce_observation_success_aggregates_ids_deduped() -> None:
    c1 = uuid.uuid4()
    c2 = uuid.uuid4()
    d1 = uuid.uuid4()
    state = init_agent_state(original_query="q", max_steps=3)

    hit = SemanticSearchHit(
        chunk_id=c1,
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="compose.md",
        page=1,
        section_title="用途",
        excerpt="Docker Compose 用于编排多容器。" * 20,
        score=0.91,
    )
    search_record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "q"},
        ok=True,
        summary="命中 1 条",
        latency_ms=10,
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=10),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(ok=True, summary="命中 1 条", latency_ms=10, data=search_record.data),
        search_record,
    )
    assert state.steps_used == 1
    assert state.evidence.chunk_ids == (c1,)

    excerpt_record = AgentStepRecord(
        step_index=2,
        tool_name="get_chunk_excerpt",
        args={"chunk_id": str(c1)},
        ok=True,
        summary="compose.md p.1 摘录",
        latency_ms=5,
        data=GetChunkExcerptOutput(
            chunk_id=c1,
            document_id=d1,
            doc_name="compose.md",
            page=1,
            section_title="用途",
            excerpt="SECRET_FULL_CHUNK_BODY_SHOULD_NOT_LEAK " * 30,
            kb_id=uuid.uuid4(),
            kb_name="kb",
        ),
    )
    # 重复 c1 + 新 document_id
    state = reduce_observation(
        state,
        AgentDecision(
            action=AgentActionKind.tool,
            tool_name="get_chunk_excerpt",
            args={"chunk_id": str(c1)},
        ),
        StepExecution(
            ok=True,
            summary="compose.md p.1 摘录",
            latency_ms=5,
            data=excerpt_record.data,
        ),
        excerpt_record,
    )
    assert state.evidence.chunk_ids == (c1,)  # 去重
    assert state.evidence.document_ids == (d1,)

    # 再搜带 c2
    hit2 = SemanticSearchHit(
        chunk_id=c2,
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="compose.md",
        page=2,
        section_title="配置",
        excerpt="version: '3'",
        score=0.88,
    )
    search2 = AgentStepRecord(
        step_index=3,
        tool_name="semantic_search",
        args={"query": "配置"},
        ok=True,
        summary="命中 2 条",
        latency_ms=8,
        data=SemanticSearchOutput(hits=(hit, hit2), retrieval_ms=8),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(ok=True, summary="命中 2 条", latency_ms=8, data=search2.data),
        search2,
    )
    assert state.evidence.chunk_ids == (c1, c2)


def test_reduce_observation_failure_clears_confidence() -> None:
    state = init_agent_state(original_query="q", max_steps=3)
    state = replace(
        state,
        evidence=EvidenceState(
            chunk_ids=(uuid.uuid4(),),
            sufficient=True,
            confidence=0.9,
        ),
    )
    failure = ToolFailure(
        kind=ToolFailureKind.denied,
        tool_name="semantic_search",
        summary="越权知识库",
    )
    record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={},
        ok=False,
        summary="越权知识库",
        latency_ms=3,
        data=None,
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(
            ok=False,
            summary="越权知识库",
            latency_ms=3,
            data=None,
            failure=failure,
        ),
        record,
    )
    assert state.last_failure == failure
    assert state.evidence.sufficient is False
    assert state.evidence.confidence == 0.0


def test_reduce_low_recall_empty_semantic_search() -> None:
    state = init_agent_state(original_query="冷门问法", max_steps=3)
    record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "冷门问法"},
        ok=True,
        summary="无命中",
        latency_ms=9,
        data=SemanticSearchOutput(hits=(), retrieval_ms=9),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(ok=True, summary="无命中", latency_ms=9, data=record.data),
        record,
    )
    assert state.evidence.sufficient is False
    assert state.evidence.confidence == 0.0
    assert state.evidence.chunk_ids == ()


def test_update_evidence_from_search_documents_and_grep() -> None:
    evidence = EvidenceState()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    search = AgentStepRecord(
        step_index=1,
        tool_name="search_documents",
        args={"query": "手册"},
        ok=True,
        summary="命中 1 篇",
        latency_ms=4,
        data=SearchDocumentsOutput(
            items=(
                SearchDocumentsItem(
                    document_id=doc_id,
                    kb_id=uuid.uuid4(),
                    kb_name="kb",
                    filename="handbook.md",
                    snippet="不应进入 EvidenceState 正文",
                ),
            ),
            total=1,
        ),
    )
    evidence = update_evidence_state(evidence, search)
    assert evidence.document_ids == (doc_id,)
    assert evidence.chunk_ids == ()

    grep = AgentStepRecord(
        step_index=2,
        tool_name="grep_in_document",
        args={"document_id": str(doc_id), "pattern": "年假"},
        ok=True,
        summary="命中 1 处",
        latency_ms=6,
        data=GrepInDocumentOutput(
            matches=(
                GrepMatch(
                    chunk_id=chunk_id,
                    doc_name="handbook.md",
                    content="完整正文年假规定" * 40,
                    page_number=3,
                    section_title="假期",
                ),
            )
        ),
    )
    evidence = update_evidence_state(evidence, grep)
    assert evidence.chunk_ids == (chunk_id,)


def test_update_evidence_compare_chunks_ids() -> None:
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    record = AgentStepRecord(
        step_index=1,
        tool_name="compare_chunks",
        args={"chunk_ids": [str(c1), str(c2)]},
        ok=True,
        summary="对比 2 段",
        latency_ms=7,
        data=CompareChunksOutput(
            chunks=(
                ChunkDetail(
                    chunk_id=c1,
                    document_id=d1,
                    doc_name="a.md",
                    page_number=1,
                    section_title=None,
                    heading_path=None,
                    content="FULL_A",
                    kb_id=uuid.uuid4(),
                ),
                ChunkDetail(
                    chunk_id=c2,
                    document_id=d2,
                    doc_name="b.md",
                    page_number=2,
                    section_title=None,
                    heading_path=None,
                    content="FULL_B",
                    kb_id=uuid.uuid4(),
                ),
            )
        ),
    )
    evidence = update_evidence_state(EvidenceState(), record)
    assert evidence.chunk_ids == (c1, c2)
    assert evidence.document_ids == (d1, d2)


def test_summarize_state_for_planner_no_chunk_body_leak() -> None:
    secret = "LEAK_ME_FULL_CHUNK_BODY_" + ("x" * 200)
    c1 = uuid.uuid4()
    d1 = uuid.uuid4()
    state = init_agent_state(original_query="用途与配置", max_steps=4)
    hit = SemanticSearchHit(
        chunk_id=c1,
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name="compose.md",
        page=1,
        section_title="用途",
        excerpt=secret,
        score=0.93,
    )
    record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "用途"},
        ok=True,
        summary="命中 1 条",
        latency_ms=10,
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=10),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(ok=True, summary="命中 1 条", latency_ms=10, data=record.data),
        record,
    )
    excerpt = AgentStepRecord(
        step_index=2,
        tool_name="get_chunk_excerpt",
        args={"chunk_id": str(c1)},
        ok=True,
        summary="compose.md 摘录",
        latency_ms=4,
        data=GetChunkExcerptOutput(
            chunk_id=c1,
            document_id=d1,
            doc_name="compose.md",
            page=1,
            section_title="用途",
            excerpt=secret,
            kb_id=uuid.uuid4(),
            kb_name="kb",
        ),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="get_chunk_excerpt"),
        StepExecution(ok=True, summary="compose.md 摘录", latency_ms=4, data=excerpt.data),
        excerpt,
    )

    summary = summarize_state_for_planner(state)
    blob = str(asdict(summary))
    assert secret not in blob
    assert "LEAK_ME" not in blob
    assert summary.last_tool == "get_chunk_excerpt"
    assert summary.chunk_ids == (c1,)
    assert summary.document_ids == (d1,)
    assert "compose.md" in summary.doc_names
    assert summary.steps_used == 2
    assert summary.max_steps == 4


def test_summarize_caps_do_not_grow_unbounded() -> None:
    state = init_agent_state(original_query="q", max_steps=50)
    hits = tuple(
        SemanticSearchHit(
            chunk_id=uuid.uuid4(),
            kb_id=uuid.uuid4(),
            kb_name="kb",
            doc_name=f"doc-{i}.md",
            page=i,
            section_title=None,
            excerpt=f"body-{i}",
            score=0.5 + (i % 10) * 0.01,
        )
        for i in range(40)
    )
    record = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={},
        ok=True,
        summary="命中很多",
        latency_ms=1,
        data=SemanticSearchOutput(hits=hits, retrieval_ms=1),
    )
    state = reduce_observation(
        state,
        AgentDecision(action=AgentActionKind.tool, tool_name="semantic_search"),
        StepExecution(ok=True, summary="命中很多", latency_ms=1, data=record.data),
        record,
    )
    summary = summarize_state_for_planner(state)
    assert len(summary.chunk_ids) <= 32
    assert len(summary.doc_names) <= 16
    assert len(summary.top_scores) <= 8

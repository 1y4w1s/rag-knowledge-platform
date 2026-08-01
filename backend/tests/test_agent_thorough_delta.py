"""D1 · thorough 相对 fast（单步 search）可测增量：merge 召回扩面。

口径：同题、同 gate。
- fast 等价：仅 1 次 semantic_search（噪声命中）→ 拒答或无 needle
- thorough：search + excerpt + 二次收窄 search（含 needle）→ gate 通过且 content 含 needle

不改正文 retrieve_*；纯 finalize / gate 路径证明「多步有用」。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.agent.finalize import gate_agent_chunks
from app.services.agent.planners import refine_query
from app.services.agent.tools.semantic_search import SemanticSearchHit
from app.services.rag.types import RetrievedChunk

FIXTURE = Path(__file__).parent / "fixtures" / "thorough_delta.json"


def _load_cases() -> list[dict]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return list(data["cases"])


def _hit(
    *,
    chunk_id: uuid.UUID,
    content_excerpt: str,
    score: float,
    section: str,
) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=uuid.uuid4(),
        kb_name="制度库",
        doc_name="员工手册.md",
        page=1,
        section_title=section,
        excerpt=content_excerpt[:80],
        score=score,
    )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
def test_thorough_delta_vs_fast_one_search(case: dict) -> None:
    query = case["query"]
    needle = case["needle"]
    noise_text = case["noise_content"]
    gold_text = case["gold_content"]
    assert needle in gold_text

    noise_id = uuid.uuid4()
    gold_id = uuid.uuid4()

    noise_hit = _hit(
        chunk_id=noise_id,
        content_excerpt=noise_text,
        score=0.92,
        section=case.get("noise_section", "杂项"),
    )
    gold_hit = _hit(
        chunk_id=gold_id,
        content_excerpt=gold_text,
        score=0.88,
        section=case.get("gold_section", "制度"),
    )

    # --- fast：仅噪声 Top 命中（单步 search）---
    fast_chunks = [
        RetrievedChunk(
            kb_id=noise_hit.kb_id,
            chunk_id=noise_id,
            document_id=uuid.uuid4(),
            doc_name=noise_hit.doc_name,
            content=noise_text,
            page_number=1,
            section_title=noise_hit.section_title,
            heading_path=None,
            similarity=0.95,
        )
    ]
    fast_plan = gate_agent_chunks(query, fast_chunks, workspace_mode=False)
    fast_ok = (not fast_plan.refusal) and any(
        needle in c.content for c in fast_plan.gated_chunks
    )

    # --- thorough：噪声 search + excerpt + 收窄 search 捞到 gold ---
    focus = refine_query(query) or case.get("focus_query") or query
    thorough_hits_ordered = [
        RetrievedChunk(
            kb_id=gold_hit.kb_id,
            chunk_id=gold_id,
            document_id=uuid.uuid4(),
            doc_name=gold_hit.doc_name,
            content=gold_text,
            page_number=1,
            section_title=gold_hit.section_title,
            heading_path=None,
            similarity=1.0,  # excerpt 提升
        ),
        RetrievedChunk(
            kb_id=noise_hit.kb_id,
            chunk_id=noise_id,
            document_id=uuid.uuid4(),
            doc_name=noise_hit.doc_name,
            content=noise_text,
            page_number=1,
            section_title=noise_hit.section_title,
            heading_path=None,
            similarity=0.92,
        ),
    ]
    thorough_plan = gate_agent_chunks(
        query, thorough_hits_ordered, workspace_mode=False
    )
    thorough_ok = (not thorough_plan.refusal) and any(
        needle in c.content for c in thorough_plan.gated_chunks
    )

    assert thorough_ok, f"{case['case_id']}: thorough 应命中 needle={needle!r}"
    assert not fast_ok, (
        f"{case['case_id']}: fast 单步噪声路径不应命中 needle（否则无增量）"
    )
    assert refine_query(query) is not None or case.get("focus_query")
    assert focus


def test_fixture_has_at_least_five_delta_cases() -> None:
    assert len(_load_cases()) >= 5

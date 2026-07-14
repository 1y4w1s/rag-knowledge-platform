"""Plan-RAG R4-3：引用块 payload 契约（chunk_to_citation）。"""

from __future__ import annotations

import uuid

from app.schemas.chat import CitationPayload
from app.services.rag.retrieval import chunk_to_citation
from app.services.rag.types import RetrievedChunk

CITATION_KEYS = frozenset(
    {
        "chunk_id",
        "document_id",
        "doc_name",
        "page",
        "section_title",
        "excerpt",
    }
)


def _chunk(
    *,
    content: str = "员工年满一年后可享受年假10天。",
    page_number: int | None = 3,
    section_title: str | None = "1.1 年假",
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="golden_handbook.md",
        content=content,
        page_number=page_number,
        section_title=section_title,
        heading_path="员工手册>考勤",
        similarity=0.82,
    )


def test_chunk_to_citation_required_fields() -> None:
    chunk = _chunk()
    citation = chunk_to_citation(chunk)

    assert set(citation.keys()) == CITATION_KEYS
    assert citation["chunk_id"] == str(chunk.chunk_id)
    assert citation["document_id"] == str(chunk.document_id)
    assert citation["doc_name"] == "golden_handbook.md"
    assert citation["page"] == 3
    assert citation["section_title"] == "1.1 年假"
    assert "年假" in citation["excerpt"]


def test_chunk_to_citation_excerpt_truncated_at_200() -> None:
    long_text = "年假" + ("长" * 250)
    chunk = _chunk(content=long_text)
    citation = chunk_to_citation(chunk)

    assert len(citation["excerpt"]) == 200
    assert citation["excerpt"].endswith("…")


def test_chunk_to_citation_null_page_and_section() -> None:
    chunk = _chunk(page_number=None, section_title=None)
    citation = chunk_to_citation(chunk)

    assert citation["page"] is None
    assert citation["section_title"] is None
    assert citation["excerpt"]


def test_citation_payload_validates_chunk_to_citation_output() -> None:
    chunk = _chunk()
    raw = chunk_to_citation(chunk)
    payload = CitationPayload.model_validate(
        {
            **raw,
            "chunk_id": uuid.UUID(raw["chunk_id"]),
            "document_id": uuid.UUID(raw["document_id"]),
        }
    )

    assert payload.doc_name == chunk.doc_name
    assert payload.page == chunk.page_number
    assert payload.section_title == chunk.section_title
    assert payload.excerpt == raw["excerpt"]

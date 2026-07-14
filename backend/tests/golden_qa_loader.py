"""从 tests/fixtures/golden_qa.json 加载 Hit@3 验收集（Plan-RAG R5-1 SSOT）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_QA_JSON = FIXTURES / "golden_qa.json"
GOLDEN_MD = FIXTURES / "golden_handbook.md"
GOLDEN_DOCX = FIXTURES / "golden_handbook.docx"

SourceKind = Literal["md", "pdf", "docx"]
HIT_K = 3


@dataclass(frozen=True, slots=True)
class GoldenQACase:
    """与 docs/golden_qa.md · golden_qa.json 对齐的验收集条目。"""

    case_id: str
    query: str
    source: SourceKind
    section_title: str | None = None
    heading_path_contains: str | None = None
    content_contains: str | None = None
    page_number: int | None = None
    tags: tuple[str, ...] = ()


def _parse_case(raw: dict) -> GoldenQACase:
    expect = raw.get("expect") or {}
    tags = raw.get("tags") or []
    return GoldenQACase(
        case_id=str(raw["case_id"]),
        query=str(raw["query"]),
        source=raw["source"],
        section_title=expect.get("section_title"),
        heading_path_contains=expect.get("heading_path_contains"),
        content_contains=expect.get("content_contains"),
        page_number=expect.get("page_number"),
        tags=tuple(str(t) for t in tags),
    )


def load_golden_qa_cases(path: Path | None = None) -> tuple[tuple[GoldenQACase, ...], int]:
    """加载 golden_qa.json；返回 (cases, hit_k)。"""
    json_path = path or GOLDEN_QA_JSON
    data = json.loads(json_path.read_text(encoding="utf-8"))
    hit_k = int(data.get("hit_k", HIT_K))
    cases = tuple(_parse_case(item) for item in data["cases"])
    return cases, hit_k


GOLDEN_QA_CASES, HIT_K = load_golden_qa_cases()

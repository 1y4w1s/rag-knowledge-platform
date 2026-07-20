"""从 tests/fixtures/golden_qa.json 加载 Hit@3 验收集（Plan-RAG R5-1 SSOT）。
v0.5 新增多相关文档 + 拒答测试。
v1.0 新增 domain/difficulty/question_type 评测元数据。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_QA_JSON = FIXTURES / "golden_qa.json"
GOLDEN_MD = FIXTURES / "golden_handbook.md"
GOLDEN_DOCX = FIXTURES / "golden_handbook.docx"

SourceKind = Literal["md", "pdf", "docx"]
HIT_K = 3


@dataclass(frozen=True, slots=True)
class GoldenQACase:
    """与 docs/golden_qa.md · golden_qa.json 对齐的验收集条目。

    v0.5 新增：
    - expects: List[dict] — 多相关文档标注（替代单个 expect）
    - expect_rejection: bool — 若 True，验证 Top-K 内无一匹配
    - min_match: int — 多相关时至少需命中数（默认 1）

    v1.0 新增（企业评测体系 Phase 1）：
    - domain: str — 领域分类（attendance/compensation/career/separation/finance/security/benefits/performance/cross）
    - difficulty: float — 难度 0-1（0.1-0.3 简单事实 / 0.4-0.6 轻推理 / 0.7-0.8 复杂 / 0.9-1.0 挑战）
    - question_type: str — 问题类型（simple/comparison/cross_reference/parametric/negation/conditional/rejection/calculation/edge）
    """

    case_id: str
    query: str
    source: SourceKind
    # 单 expect（向后兼容）
    section_title: str | None = None
    heading_path_contains: str | None = None
    content_contains: str | None = None
    page_number: int | None = None
    # 多 expect（v0.5 新增）
    expects: tuple[dict[str, Any], ...] = ()
    min_match: int = 1
    expect_rejection: bool = False
    tags: tuple[str, ...] = ()
    # v1.0 评测体系元数据
    domain: str = ""
    difficulty: float = 0.5
    question_type: str = "simple"


def _match_single_expect(expect: dict, chunk: Any) -> bool:
    """检查一个期望 dict 是否匹配 chunk。"""
    sec = expect.get("section_title")
    if sec is not None and getattr(chunk, "section_title", None) != sec:
        return False
    hpc = expect.get("heading_path_contains")
    if hpc is not None and hpc.lower() not in (getattr(chunk, "heading_path", None) or "").lower():
        return False
    cc = expect.get("content_contains")
    if cc is not None:
        chunk_content = (getattr(chunk, "content", None) or "").lower()
        if cc.lower() not in chunk_content:
            return False
    pn = expect.get("page_number")
    if pn is not None and getattr(chunk, "page_number", None) != pn:
        return False
    return True


def _parse_case(raw: dict) -> GoldenQACase:
    expect = raw.get("expect") or {}
    tags = raw.get("tags") or []
    expects = tuple(raw.get("expects") or [])
    return GoldenQACase(
        case_id=str(raw["case_id"]),
        query=str(raw["query"]),
        source=raw["source"],
        section_title=expect.get("section_title"),
        heading_path_contains=expect.get("heading_path_contains"),
        content_contains=expect.get("content_contains"),
        page_number=expect.get("page_number"),
        expects=expects,
        min_match=int(raw.get("min_match", 1)),
        expect_rejection=bool(raw.get("expect_rejection", False)),
        tags=tuple(str(t) for t in tags),
        domain=str(raw.get("domain", "")),
        difficulty=float(raw.get("difficulty", 0.5)),
        question_type=str(raw.get("question_type", "simple")),
    )


def load_golden_qa_cases(path: Path | None = None) -> tuple[tuple[GoldenQACase, ...], int]:
    """加载 golden_qa.json；返回 (cases, hit_k)。"""
    json_path = path or GOLDEN_QA_JSON
    data = json.loads(json_path.read_text(encoding="utf-8"))
    hit_k = int(data.get("hit_k", HIT_K))
    cases = tuple(_parse_case(item) for item in data["cases"])
    return cases, hit_k


def chunk_matches(case: GoldenQACase, chunk: Any) -> bool:
    """Golden chunk 与 GoldenQACase 的任一期望匹配？

    支持单 expect / 多 expects。
    拒答 case 无期望定义时始终返回 False。
    """
    if case.expect_rejection:
        return False
    if case.expects:
        return any(_match_single_expect(e, chunk) for e in case.expects)
    if case.section_title is not None and getattr(chunk, "section_title", None) != case.section_title:
        return False
    if case.heading_path_contains is not None and case.heading_path_contains.lower() not in (getattr(chunk, "heading_path", None) or "").lower():
        return False
    if case.content_contains is not None:
        chunk_content = (getattr(chunk, "content", None) or "").lower()
        if case.content_contains.lower() not in chunk_content:
            return False
    if case.page_number is not None and getattr(chunk, "page_number", None) != case.page_number:
        return False
    if any([case.section_title, case.heading_path_contains, case.content_contains, case.page_number is not None]):
        return True
    return False


def hit_at_k(chunks: list, case: GoldenQACase, k: int = HIT_K) -> bool:
    """Top-K 内验证。

    正常 case：至少 min_match 个期望被命中。
    拒答 case：无一匹配。
    """
    top = chunks[:k]
    match_count = sum(1 for c in top if chunk_matches(case, c))
    if case.expect_rejection:
        return match_count == 0
    return match_count >= case.min_match


def reciprocal_rank(chunks: list, case: GoldenQACase, k: int = HIT_K) -> float:
    """计算 MRR 贡献：第一个匹配 chunk 的倒数排名；无匹配返回 0。

    拒答 case 始终返回 1.0（正确拒答即满分）。
    """
    if case.expect_rejection:
        return 1.0 if not any(chunk_matches(case, c) for c in chunks[:k]) else 0.0
    for rank, chunk in enumerate(chunks[:k], start=1):
        if chunk_matches(case, chunk):
            return 1.0 / rank
    return 0.0


GOLDEN_QA_CASES, HIT_K = load_golden_qa_cases()

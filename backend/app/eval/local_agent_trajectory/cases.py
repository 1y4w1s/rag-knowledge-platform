"""W8 P0 synthetic trajectory research case set (not Agent Golden 168)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from app.services.agent.types import FactGoal, FactKind, FactStatus
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)

ToolMode = Literal[
    "cover_all",
    "cover_f1",
    "cover_by_query",
    "conflict",
    "fail",
    "empty",
]


@dataclass(frozen=True, slots=True)
class TrajectoryCase:
    case_id: str
    category: str
    query: str
    fact_goals: tuple[FactGoal, ...]
    tool_mode: ToolMode
    max_steps: int = 5
    description: str = ""
    source: str = "synthetic"
    expected_terminals: tuple[str, ...] = ("finish",)
    allow_clarify: bool = False
    allow_refuse: bool = False
    require_tool: bool = False
    notes: str = ""
    paired_on: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "query": self.query,
            "fact_goal_ids": [g.id for g in self.fact_goals],
            "fact_goal_texts": [g.text for g in self.fact_goals],
            "initial_statuses": [g.status.value for g in self.fact_goals],
            "tool_mode": self.tool_mode,
            "max_steps": self.max_steps,
            "description": self.description,
            "source": self.source,
            "expected_terminals": list(self.expected_terminals),
            "paired_on": self.paired_on,
        }


def _goal(
    fid: str,
    text: str,
    *,
    kind: FactKind = FactKind.lookup,
    status: FactStatus = FactStatus.missing,
) -> FactGoal:
    return FactGoal(id=fid, text=text, kind=kind, status=status, required=True)


def _hit(excerpt: str, *, doc_name: str = "制度.md") -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=uuid4(),
        kb_id=UUID("00000000-0000-4000-8000-000000000001"),
        kb_name="research-kb",
        doc_name=doc_name,
        page=1,
        section_title="标准",
        excerpt=excerpt,
        score=0.92,
    )


def search_ok(*excerpts: str) -> SemanticSearchToolResult:
    hits = tuple(_hit(e) for e in excerpts)
    return SemanticSearchToolResult(
        ok=True,
        data=SemanticSearchOutput(hits=hits, retrieval_ms=8),
        summary=f"命中 {len(hits)} 条",
    )


def search_fail(summary: str = "检索后端失败") -> SemanticSearchToolResult:
    return SemanticSearchToolResult(ok=False, data=None, summary=summary)


EXCERPT_2025 = "差旅手册确认：找到2025住宿标准为每人每天500元，该标准适用在职员工。"
EXCERPT_2026 = "差旅手册确认：找到2026住宿标准调整为每人每天600元，该标准适用在职员工。"
EXCERPT_BOTH = f"{EXCERPT_2025} {EXCERPT_2026}"
EXCERPT_CONFLICT = (
    "台湾办公室员工适用规则：2025住宿标准不适用台湾办公室，并非每人500元。"
)
EXCERPT_UNRELATED = "会议室预定流程：提前一天在门户提交申请，与住宿标准无关。"
EXCERPT_POLICY = "信息安全政策确认：外部U盘禁止接入办公电脑，该规定适用全员。"


def tool_result_for(case: TrajectoryCase, query: str, call_index: int) -> SemanticSearchToolResult:
    mode = case.tool_mode
    if mode == "fail":
        return search_fail()
    if mode == "empty":
        return search_ok(EXCERPT_UNRELATED)
    if mode == "conflict":
        return search_ok(EXCERPT_CONFLICT)
    if mode == "cover_all":
        if "U盘" in case.query or "信息安全" in case.query:
            return search_ok(EXCERPT_POLICY)
        return search_ok(EXCERPT_BOTH)
    if mode == "cover_f1":
        if call_index == 0:
            return search_ok(EXCERPT_2025)
        return search_ok(EXCERPT_2026)
    # cover_by_query
    q = query or ""
    if "2026" in q and "2025" not in q:
        return search_ok(EXCERPT_2026)
    if "2025" in q and "2026" not in q:
        return search_ok(EXCERPT_2025)
    if call_index == 0:
        return search_ok(EXCERPT_2025)
    return search_ok(EXCERPT_2026)


def w8_p0_cases() -> tuple[TrajectoryCase, ...]:
    """16 synthetic cases covering A–G. Does not modify Golden 168."""
    g2025 = _goal("F1", "找到2025住宿标准")
    g2026 = _goal("F2", "找到2026住宿标准")
    g_rule = _goal("F3", "确认适用规则", kind=FactKind.condition)
    g_policy = _goal("P1", "确认外部U盘禁止接入办公电脑")
    covered_2025 = _goal("F1", "找到2025住宿标准", status=FactStatus.covered)
    covered_2026 = _goal("F2", "找到2026住宿标准", status=FactStatus.covered)

    return (
        TrajectoryCase(
            case_id="A1",
            category="direct",
            query="2025和2026住宿标准分别是多少？",
            fact_goals=(covered_2025, covered_2026),
            tool_mode="cover_all",
            description="初始 required facts 已 covered，应尽快 finish",
            require_tool=False,
        ),
        TrajectoryCase(
            case_id="A2",
            category="direct",
            query="外部U盘能否接入办公电脑？",
            fact_goals=(g_policy,),
            tool_mode="cover_all",
            description="一次检索即可覆盖，随后 finish",
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="B1",
            category="missing_fact",
            query="2025年住宿标准是多少？",
            fact_goals=(g2025,),
            tool_mode="cover_all",
            description="missing → retrieve → matcher → finish",
            require_tool=True,
            paired_on=True,
        ),
        TrajectoryCase(
            case_id="B2",
            category="missing_fact",
            query="请给出2026住宿标准。",
            fact_goals=(g2026,),
            tool_mode="cover_all",
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="B3",
            category="missing_fact",
            query="差旅制度里的2025住宿标准条款是什么？",
            fact_goals=(g2025,),
            tool_mode="cover_f1",
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="C1",
            category="multi_fact",
            query="对比2025与2026住宿标准发生了什么变化？",
            fact_goals=(g2025, g2026),
            tool_mode="cover_by_query",
            description="两事实；允许分步检索",
            require_tool=True,
            paired_on=True,
        ),
        TrajectoryCase(
            case_id="C2",
            category="multi_fact",
            query="根据2025与2026差旅制度，住宿标准与适用规则是什么？",
            fact_goals=(g2025, g2026, g_rule),
            tool_mode="cover_by_query",
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="C3",
            category="multi_fact",
            query="请分别列出2025住宿标准和2026住宿标准。",
            fact_goals=(g2025, g2026),
            tool_mode="cover_f1",
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="D1",
            category="conflict",
            query="确认台湾办公室员工的适用规则与2025住宿标准。",
            fact_goals=(g2025, g_rule),
            tool_mode="conflict",
            expected_terminals=("refuse", "clarify", "finish"),
            allow_clarify=True,
            allow_refuse=True,
            description="冲突证据：不得伪 complete",
            paired_on=True,
        ),
        TrajectoryCase(
            case_id="D2",
            category="conflict",
            query="台湾办公室是否适用2025住宿标准500元？",
            fact_goals=(g2025, _goal("F3", "确认台湾办公室适用规则", kind=FactKind.condition)),
            tool_mode="conflict",
            expected_terminals=("refuse", "clarify", "finish"),
            allow_clarify=True,
            allow_refuse=True,
        ),
        TrajectoryCase(
            case_id="E1",
            category="tool_failure",
            query="2025年住宿标准是多少？",
            fact_goals=(g2025,),
            tool_mode="fail",
            expected_terminals=("refuse", "finish", "clarify"),
            allow_refuse=True,
            require_tool=True,
            description="tool ok=false，不得污染 coverage",
        ),
        TrajectoryCase(
            case_id="E2",
            category="tool_failure",
            query="2026住宿标准请检索。",
            fact_goals=(g2026,),
            tool_mode="fail",
            expected_terminals=("refuse", "finish"),
            allow_refuse=True,
            require_tool=True,
        ),
        TrajectoryCase(
            case_id="F1",
            category="budget",
            query="2027年火星基地差旅住宿标准是多少？",
            fact_goals=(_goal("F9", "找到2027火星基地住宿标准"),),
            tool_mode="empty",
            max_steps=2,
            expected_terminals=("refuse", "finish"),
            allow_refuse=True,
            description="证据不可得，预算耗尽不得伪 covered",
            paired_on=True,
        ),
        TrajectoryCase(
            case_id="F2",
            category="budget",
            query="请同时给出2028与2029不存在的住宿标准。",
            fact_goals=(
                _goal("X1", "找到2028住宿标准"),
                _goal("X2", "找到2029住宿标准"),
            ),
            tool_mode="empty",
            max_steps=2,
            expected_terminals=("refuse", "finish"),
            allow_refuse=True,
        ),
        TrajectoryCase(
            case_id="G1",
            category="clarify",
            query="那个标准是多少？",
            fact_goals=(_goal("G1", "确认用户所指的标准类型", kind=FactKind.condition),),
            tool_mode="empty",
            expected_terminals=("clarify", "refuse"),
            allow_clarify=True,
            allow_refuse=True,
            description="关键歧义，允许 clarify/refuse",
        ),
        TrajectoryCase(
            case_id="G2",
            category="clarify",
            query="他们的报销怎么算？",
            fact_goals=(_goal("G2", "确认所指人群与报销类型", kind=FactKind.condition),),
            tool_mode="empty",
            expected_terminals=("clarify", "refuse"),
            allow_clarify=True,
            allow_refuse=True,
        ),
    )


CASE_BY_ID = {c.case_id: c for c in w8_p0_cases()}

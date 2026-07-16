"""从 docs/golden_agent_qa.json 加载 G3 Agent golden 验收集（G3-4.2 SSOT）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[0]
GOLDEN_AGENT_QA_JSON = REPO_ROOT / "golden_agent_qa.json"

AgentCategory = Literal["multi_step", "refusal", "forbidden_kb"]
AgentScope = Literal["kb", "workspace"]
FixtureKind = Literal["md", "none"]

REQUIRED_CATEGORIES: frozenset[str] = frozenset(
    {"multi_step", "refusal", "forbidden_kb"}
)
EXPECTED_CASE_COUNT = 15


@dataclass(frozen=True, slots=True)
class AgentGoldenExpect:
    min_steps: int
    has_citations: bool
    refusal: bool
    tools_used: tuple[str, ...] = ()
    citation_section_contains: str | None = None
    tool_denied: bool = False


@dataclass(frozen=True, slots=True)
class AgentGoldenCase:
    case_id: str
    category: AgentCategory
    query: str
    scope: AgentScope
    fixture: FixtureKind
    planner_steps: tuple[dict[str, Any], ...]
    expect: AgentGoldenExpect
    tags: tuple[str, ...] = ()


def _parse_expect(raw: dict[str, Any]) -> AgentGoldenExpect:
    tools = raw.get("tools_used") or []
    return AgentGoldenExpect(
        min_steps=int(raw.get("min_steps", 1)),
        has_citations=bool(raw.get("has_citations", False)),
        refusal=bool(raw.get("refusal", False)),
        tools_used=tuple(str(t) for t in tools),
        citation_section_contains=raw.get("citation_section_contains"),
        tool_denied=bool(raw.get("tool_denied", False)),
    )


def _parse_case(raw: dict[str, Any]) -> AgentGoldenCase:
    steps = raw.get("planner_steps") or []
    tags = raw.get("tags") or []
    return AgentGoldenCase(
        case_id=str(raw["case_id"]),
        category=raw["category"],
        query=str(raw["query"]),
        scope=raw["scope"],
        fixture=raw.get("fixture", "none"),
        planner_steps=tuple(dict(step) for step in steps),
        expect=_parse_expect(raw.get("expect") or {}),
        tags=tuple(str(t) for t in tags),
    )


def load_golden_agent_cases(
    path: Path | None = None,
) -> tuple[AgentGoldenCase, ...]:
    """加载 golden_agent_qa.json；校验 15 题与三类齐全。"""
    json_path = path or GOLDEN_AGENT_QA_JSON
    data = json.loads(json_path.read_text(encoding="utf-8"))
    cases = tuple(_parse_case(item) for item in data["cases"])

    if len(cases) != EXPECTED_CASE_COUNT:
        raise ValueError(
            f"golden_agent_qa 须 {EXPECTED_CASE_COUNT} 题，当前 {len(cases)}"
        )

    categories = {case.category for case in cases}
    missing = REQUIRED_CATEGORIES - categories
    if missing:
        raise ValueError(f"golden_agent_qa 缺少类别: {sorted(missing)}")

    return cases


GOLDEN_AGENT_CASES = load_golden_agent_cases()

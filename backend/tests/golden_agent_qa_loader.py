"""从 tests/golden_agent_qa.json 加载 G3 Agent golden 验收集（G3-4.2 SSOT · E5 扩展）。
新 schema（v2）：RAG/RETRIEVAL/ADVERSARIAL/TOOL 四类 · E5 新增 MULTI_STEP/REFLECTION/MEMORY/AUTH/DEGRADE 五类。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent
FIXTURES = REPO_ROOT / "fixtures"
GOLDEN_AGENT_QA_JSON = REPO_ROOT / "golden_agent_qa.json"
GOLDEN_AGENT_MD = FIXTURES / "golden_agent_handbook.md"

AgentCategory = Literal[
    "RAG", "RETRIEVAL", "ADVERSARIAL", "TOOL",
    "MULTI_STEP", "REFLECTION", "MEMORY", "AUTH", "DEGRADE",
]
AgentScope = Literal["kb", "workspace"]

REQUIRED_CATEGORIES: frozenset[str] = frozenset({
    "RAG", "RETRIEVAL", "ADVERSARIAL", "TOOL",
    "MULTI_STEP", "REFLECTION", "MEMORY", "AUTH", "DEGRADE",
})
EXPECTED_CASE_COUNT = 168  # 150 存量 + 18 E5 新增


@dataclass(frozen=True)
class AgentGoldenCase:
    case_id: str
    category: AgentCategory
    query: str
    expected_doc: str
    expected_chunk: str
    scope: AgentScope
    # E5 扩展字段
    pre_seed_memories: tuple[dict, ...] = ()
    expected_fallback: bool = False
    expected_steps: int = 1


def _parse_case(raw: dict) -> AgentGoldenCase:
    return AgentGoldenCase(
        case_id=str(raw["case_id"]),
        category=raw["category"],
        query=str(raw["query"]),
        expected_doc=str(raw.get("expected_doc", "")),
        expected_chunk=str(raw.get("expected_chunk", "")),
        scope=raw.get("scope", "kb"),
        pre_seed_memories=tuple(raw.get("pre_seed_memories", [])),
        expected_fallback=bool(raw.get("expected_fallback", False)),
        expected_steps=int(raw.get("expected_steps", 1)),
    )


def load_golden_agent_cases(
    path: Path | None = None,
) -> tuple[AgentGoldenCase, ...]:
    """加载 golden_agent_qa.json；校验 168 题与九类齐全（含 E5 五类）。"""
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

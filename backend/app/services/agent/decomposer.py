"""L4-W2 Fact Decomposer：query → FactGoal[]（默认关；deterministic + schema 可测）。

纯函数不读 flag；LLM 仅挂 ``agent_l4_fact_decomposition_enabled`` 且可 mock。
产出可喂 ``init_agent_state(..., fact_goals=)`` / ``seed_fact_goals``。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.services.agent.fact_contracts import seed_fact_goals
from app.services.agent.types import FactGoal, FactKind, FactStatus

MIN_FACT_GOALS = 1
MAX_FACT_GOALS = 6
_VALID_KINDS = frozenset(k.value for k in FactKind)
_COMPARE = re.compile(r"对比|比较|变化|分别|差异|vs\.?|VS|与.+相比|发生了什么变化")
_CONDITION = re.compile(r"适用|条件|档位|地域|场景|身份")
_EXCEPTION = re.compile(r"例外|特批|高管|豁免|特殊审批")
_VERIFY = re.compile(r"确认|核实|是否存在|对不对|验明")
_YEAR_PAIR = re.compile(r"(20\d{2}).{0,40}?(20\d{2})")
_SPLIT = re.compile(r"[？?;；]|以及|并且|同时")
_SIMPLE_MAX_LEN = 40

LlmComplete = Callable[[str], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class DecomposeResult:
    """ok 时 fact_goals 长度 ∈ [1, 6]。"""

    ok: bool
    fact_goals: tuple[FactGoal, ...] = ()
    error: str | None = None
    llm_raw: str | None = None
    source: str = ""  # deterministic | schema | llm | disabled


def _fail(error: str, *, source: str, llm_raw: str | None = None) -> DecomposeResult:
    return DecomposeResult(ok=False, error=error, llm_raw=llm_raw, source=source)


def _goal(
    text: str,
    kind: FactKind,
    *,
    fid: str = "F1",
    required: bool = True,
) -> FactGoal:
    return FactGoal(
        id=fid,
        text=text,
        kind=kind,
        required=required,
        status=FactStatus.missing,
    )


def normalize_fact_goals(
    goals: Sequence[FactGoal],
    *,
    difficulty: str | None = None,
) -> DecomposeResult:
    """裁剪 / 重编号 / 硬顶 1～6；simple → 至多 1 条。"""
    seeded = seed_fact_goals(fact_goals=tuple(goals))
    if not seeded:
        return _fail("empty_facts", source="schema")
    capped = seeded[:MAX_FACT_GOALS]
    if (difficulty or "").strip().lower() == "simple":
        capped = capped[:1]
    if len(capped) < MIN_FACT_GOALS:
        return _fail("empty_facts", source="schema")
    renumbered = tuple(
        _goal(
            g.text,
            g.kind if isinstance(g.kind, FactKind) else FactKind.lookup,
            fid=f"F{i + 1}",
            required=g.required,
        )
        for i, g in enumerate(capped)
    )
    return DecomposeResult(ok=True, fact_goals=renumbered, source="schema")


def parse_fact_goals_payload(
    raw: str | dict[str, Any] | list[Any],
    *,
    difficulty: str | None = None,
) -> DecomposeResult:
    """Schema 校验：JSON / dict / list → FactGoal[]。"""
    llm_raw = raw if isinstance(raw, str) else None
    try:
        payload = _coerce_payload(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fail("parse_error", source="schema", llm_raw=llm_raw)

    items = _extract_items(payload)
    if items is None:
        return _fail("not_fact_list", source="schema", llm_raw=llm_raw)
    if not items:
        return _fail("empty_facts", source="schema", llm_raw=llm_raw)
    items = items[:MAX_FACT_GOALS]

    goals: list[FactGoal] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return _fail("invalid_item", source="schema", llm_raw=llm_raw)
        text = str(item.get("text") or "").strip()
        if not text:
            return _fail("empty_text", source="schema", llm_raw=llm_raw)
        kind_raw = item.get("kind", FactKind.lookup.value)
        kind_str = kind_raw.value if isinstance(kind_raw, FactKind) else str(kind_raw)
        if kind_str not in _VALID_KINDS:
            return _fail("invalid_kind", source="schema", llm_raw=llm_raw)
        required = item.get("required", True)
        if not isinstance(required, bool):
            return _fail("invalid_required", source="schema", llm_raw=llm_raw)
        fid = str(item.get("id") or f"F{i + 1}").strip() or f"F{i + 1}"
        goals.append(_goal(text, FactKind(kind_str), fid=fid, required=required))

    result = normalize_fact_goals(goals, difficulty=difficulty)
    if not result.ok:
        return _fail(result.error or "empty_facts", source="schema", llm_raw=llm_raw)
    return DecomposeResult(
        ok=True, fact_goals=result.fact_goals, llm_raw=llm_raw, source="schema"
    )


def deterministic_decompose(
    query: str,
    *,
    difficulty: str | None = None,
) -> DecomposeResult:
    """无 LLM：simple → 1 lookup；complex → 启发式拆 1～6。"""
    q = (query or "").strip()
    if not q:
        return _fail("empty_query", source="deterministic")
    diff = (difficulty or "").strip().lower() or _infer_difficulty(q)
    goals = (
        (_goal(q, FactKind.lookup),)
        if diff == "simple"
        else _heuristic_goals(q)
    )
    result = normalize_fact_goals(goals, difficulty=diff)
    if not result.ok:
        return _fail(result.error or "empty_facts", source="deterministic")
    return replace(result, source="deterministic")


class FactDecomposer:
    """Flag 门控：关 → disabled；开 → mock LLM 或 deterministic。"""

    def __init__(self, *, llm_complete: LlmComplete | None = None) -> None:
        self._llm_complete = llm_complete

    async def decompose(
        self,
        query: str,
        *,
        difficulty: str | None = None,
    ) -> DecomposeResult:
        from app.core.config import settings

        if not settings.agent_l4_fact_decomposition_enabled:
            return _fail("disabled", source="disabled")

        if self._llm_complete is None:
            return deterministic_decompose(query, difficulty=difficulty)

        try:
            raw = await self._llm_complete(query)
        except Exception as exc:  # noqa: BLE001 — 契约 llm_error，不抛穿
            return DecomposeResult(
                ok=False, error="llm_error", llm_raw=str(exc), source="llm"
            )

        parsed = parse_fact_goals_payload(raw, difficulty=difficulty)
        if parsed.ok:
            return DecomposeResult(
                ok=True,
                fact_goals=parsed.fact_goals,
                llm_raw=parsed.llm_raw,
                source="llm",
            )
        fallback = deterministic_decompose(query, difficulty=difficulty)
        if fallback.ok:
            return DecomposeResult(
                ok=True,
                fact_goals=fallback.fact_goals,
                error=parsed.error,
                llm_raw=parsed.llm_raw,
                source="deterministic",
            )
        return DecomposeResult(
            ok=False,
            error=parsed.error or fallback.error,
            llm_raw=parsed.llm_raw,
            source="llm",
        )


def _coerce_payload(raw: str | dict[str, Any] | list[Any]) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    text = raw.strip()
    if not text:
        raise ValueError("empty")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _extract_items(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("fact_goals", "facts"):
            if key in payload:
                items = payload[key]
                return items if isinstance(items, list) else None
    return None


def _infer_difficulty(query: str) -> str:
    compact = len(re.sub(r"\s+", "", query)) <= _SIMPLE_MAX_LEN
    plain = not _SPLIT.search(query) and not (
        _COMPARE.search(query) or _CONDITION.search(query) or _EXCEPTION.search(query)
    )
    return "simple" if compact and plain else "complex"


def _infer_kind(segment: str) -> FactKind:
    if _EXCEPTION.search(segment):
        return FactKind.exception
    if _COMPARE.search(segment):
        return FactKind.compare
    if _CONDITION.search(segment):
        return FactKind.condition
    if _VERIFY.search(segment):
        return FactKind.verify
    return FactKind.lookup


def _heuristic_goals(query: str) -> tuple[FactGoal, ...]:
    goals: list[FactGoal] = []
    year_match = _YEAR_PAIR.search(query)
    if year_match and _COMPARE.search(query):
        y1, y2 = year_match.group(1), year_match.group(2)
        topic = "住宿标准" if "住宿" in query else "相关标准"
        goals.extend(
            (
                _goal(f"找到 {y1} {topic}", FactKind.compare, fid="F1"),
                _goal(f"找到 {y2} {topic}", FactKind.compare, fid="F2"),
            )
        )

    segments = [s.strip() for s in _SPLIT.split(query) if s.strip()] or [query]
    year_re = (
        re.compile(rf"{year_match.group(1)}|{year_match.group(2)}")
        if year_match
        else None
    )
    for seg in segments:
        if year_re and _COMPARE.search(seg) and any(
            g.kind == FactKind.compare for g in goals
        ):
            if year_re.search(seg):
                continue
        kind = _infer_kind(seg)
        if (
            kind == FactKind.compare
            and year_re
            and any(g.kind == FactKind.compare for g in goals)
            and year_re.search(seg)
        ):
            continue
        text = seg if len(seg) <= 80 else seg[:79] + "…"
        if any(g.text == text for g in goals):
            continue
        goals.append(_goal(text, kind, fid=f"F{len(goals) + 1}"))
        if len(goals) >= MAX_FACT_GOALS:
            break

    if not goals:
        goals.append(_goal(query, FactKind.lookup))
    return tuple(goals[:MAX_FACT_GOALS])

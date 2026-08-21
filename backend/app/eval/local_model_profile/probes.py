"""Probe definitions A–H for Local Model Capability Profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.eval.local_model_profile.adapter import CompletionResult, OpenAICompatibleAdapter
from app.eval.local_model_profile.schema import ProbeResult, ProbeStatus, ThinkingMode
from app.eval.local_model_profile.scoring import (
    ALLOWED_PROBE_TOOLS,
    score_agent_decision,
    score_evidence_selection,
    score_native_tool_call,
    score_strict_json,
)

ProbeFn = Callable[[OpenAICompatibleAdapter, ThinkingMode, int], ProbeResult]


@dataclass(frozen=True, slots=True)
class ProbeSpec:
    probe_id: str
    category: str
    name: str
    run: ProbeFn
    # Core structured probes repeated for stability (G/H).
    stability_core: bool = False


def _base(
    spec: ProbeSpec,
    *,
    thinking_mode: ThinkingMode,
    repeat_index: int,
    status: ProbeStatus,
    passed: bool,
    result: CompletionResult | None = None,
    repair_required: bool = False,
    schema_success: bool = False,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> ProbeResult:
    timed_out = bool(result.timed_out) if result else False
    if timed_out:
        status = ProbeStatus.error
        passed = False
        error = error or (result.error if result else "timeout")
    return ProbeResult(
        probe_id=spec.probe_id,
        category=spec.category,
        name=spec.name,
        status=status.value,
        passed=passed,
        thinking_mode=thinking_mode.value,
        timed_out=timed_out,
        latency_ms=result.latency_ms if result else None,
        repair_required=repair_required,
        schema_success=schema_success,
        error=error,
        details=details or {},
        repeat_index=repeat_index,
    )


def _from_provider_error(
    spec: ProbeSpec,
    thinking_mode: ThinkingMode,
    repeat_index: int,
    result: CompletionResult,
) -> ProbeResult | None:
    if result.timed_out:
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.error,
            passed=False,
            result=result,
            error=result.error,
        )
    if result.error:
        status = ProbeStatus.unsupported if result.http_status == 400 else ProbeStatus.error
        # 4xx on tools often means unsupported FC; caller may override.
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=status,
            passed=False,
            result=result,
            error=result.error,
        )
    return None


def probe_a_connectivity(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    spec = ProbeSpec("A1", "A", "connectivity_basic_completion", probe_a_connectivity)
    result = adapter.chat_completion(
        [
            {"role": "system", "content": "Reply with exactly: OK"},
            {"role": "user", "content": "ping"},
        ],
        max_tokens=32,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    ok = "OK" in (result.content or "").upper()
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if ok else ProbeStatus.failed,
        passed=ok,
        result=result,
        details={"content_preview": (result.content or "")[:80]},
    )


def probe_b_structured_json(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    spec = ProbeSpec(
        "B1",
        "B",
        "structured_json_strict",
        probe_b_structured_json,
        stability_core=True,
    )
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Return ONLY a JSON object with keys "
                    'name (string) and score (number). No markdown.'
                ),
            },
            {"role": "user", "content": "name=alpha score=0.9"},
        ],
        max_tokens=128,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    scored = score_strict_json(result.content, required_keys={"name", "score"})
    # PASS only when schema_success (no repair).
    passed = bool(
        scored.schema_success
        and scored.parsed is not None
        and isinstance(scored.parsed.get("name"), str)
        and isinstance(scored.parsed.get("score"), (int, float))
    )
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if passed else ProbeStatus.failed,
        passed=passed,
        result=result,
        repair_required=scored.repair_required,
        schema_success=scored.schema_success,
        error=None if passed else scored.error,
        details={"parsed": scored.parsed},
    )


def probe_c_agent_decision(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    spec = ProbeSpec(
        "C1",
        "C",
        "agent_decision_schema",
        probe_c_agent_decision,
        stability_core=True,
    )
    tools = ", ".join(sorted(ALLOWED_PROBE_TOOLS))
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Return ONLY one JSON object:\n"
                    '{"action":"tool|finish|clarify|refuse",'
                    '"tool_name":string|null,"args":object,'
                    '"reason_code":string}\n'
                    f"Allowed tools: {tools}. No markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Evidence is missing for the query. "
                    "Choose action=tool tool_name=semantic_search "
                    'args={"query":"差旅住宿标准"}.'
                ),
            },
        ],
        max_tokens=256,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    scored = score_agent_decision(result.content)
    passed = bool(
        scored.ok
        and scored.action == "tool"
        and scored.tool_name == "semantic_search"
        and isinstance((scored.args or {}).get("query"), str)
    )
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if passed else ProbeStatus.failed,
        passed=passed,
        result=result,
        repair_required=scored.repair_required,
        schema_success=scored.schema_success,
        error=None if passed else scored.error,
        details={
            "action": scored.action,
            "tool_name": scored.tool_name,
            "args": scored.args,
        },
    )


def probe_c_invalid_enum(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    """Offline-capable scorer probe: validates invalid enum is rejected.

    Still calls the model asking for an illegal action; if model complies with
    illegal enum, scorer must FAIL (not accept).
    """
    spec = ProbeSpec("C2", "C", "agent_decision_invalid_enum", probe_c_invalid_enum)
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Return ONLY JSON with action one of "
                    "tool|finish|clarify|refuse. No markdown."
                ),
            },
            {
                "role": "user",
                "content": 'Return exactly {"action":"dance","tool_name":null,"args":{},"reason_code":"x"}',
            },
        ],
        max_tokens=128,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    scored = score_agent_decision(result.content)
    # Expected: scorer rejects invalid enum → probe passes when ok is False
    # with invalid_action_enum (model obeyed bad instruction) OR model refused
    # and produced a valid legal action (also acceptable for harness self-test
    # when running live). For CI mocks we inject invalid enum.
    rejected = (not scored.ok) and scored.error == "invalid_action_enum"
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if rejected else ProbeStatus.failed,
        passed=rejected,
        result=result,
        repair_required=scored.repair_required,
        schema_success=scored.schema_success,
        error=None if rejected else (scored.error or "enum_not_rejected"),
        details={"scorer_error": scored.error, "action": scored.action},
    )


_SEARCH_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }
]


def probe_d_native_tool_calling(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    spec = ProbeSpec("D1", "D", "native_tool_calling", probe_d_native_tool_calling)
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": "Use the semantic_search tool when you need knowledge.",
            },
            {"role": "user", "content": "Find travel lodging policy limits."},
        ],
        tools=_SEARCH_TOOL,
        max_tokens=256,
    )
    if result.timed_out:
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.error,
            passed=False,
            result=result,
            error=result.error,
        )
    if result.http_status in {400, 404, 422} or (
        result.error and result.http_status is not None and 400 <= result.http_status < 500
    ):
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.unsupported,
            passed=False,
            result=result,
            error="UNSUPPORTED",
            details={"http_status": result.http_status},
        )
    if result.error:
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.error,
            passed=False,
            result=result,
            error=result.error,
        )
    scored = score_native_tool_call(
        result.tool_calls,
        expected_name="semantic_search",
        required_arg_keys={"query"},
    )
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if scored.ok else ProbeStatus.failed,
        passed=scored.ok,
        result=result,
        error=None if scored.ok else scored.error,
        details={"tool_name": scored.tool_name, "args": scored.args},
    )


def probe_d_json_planned_tool(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    """JSON-planned tool call (text schema) — separate from native FC."""
    spec = ProbeSpec(
        "D2",
        "D",
        "json_planned_tool_call",
        probe_d_json_planned_tool,
        stability_core=True,
    )
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Return ONLY JSON: "
                    '{"tool_name":"semantic_search","args":{"query":string}}'
                ),
            },
            {"role": "user", "content": "Need lodging standard for Shanghai."},
        ],
        max_tokens=128,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    scored = score_strict_json(result.content, required_keys={"tool_name", "args"})
    passed = False
    error = scored.error
    if scored.schema_success and scored.parsed:
        name = scored.parsed.get("tool_name")
        args = scored.parsed.get("args")
        if name == "semantic_search" and isinstance(args, dict) and "query" in args:
            passed = True
            error = None
        elif name not in ALLOWED_PROBE_TOOLS:
            error = "unknown_tool"
        else:
            error = "invalid_tool_args"
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if passed else ProbeStatus.failed,
        passed=passed,
        result=result,
        repair_required=scored.repair_required,
        schema_success=scored.schema_success,
        error=error,
        details={"parsed": scored.parsed},
    )


def probe_e_evidence_selection(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    spec = ProbeSpec(
        "E1",
        "E",
        "evidence_selection",
        probe_e_evidence_selection,
        stability_core=True,
    )
    allowed = {"ev_1", "ev_2", "ev_3"}
    result = adapter.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Select relevant evidence ids. Return ONLY JSON "
                    '{"selected_ids":[...]} using ids from the list. '
                    "Never invent ids."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Question: 2026 住宿标准是多少？\n"
                    "Evidence:\n"
                    "- ev_1: 2026 上海住宿上限 500 元/晚\n"
                    "- ev_2: 差旅交通可报销高铁二等座\n"
                    "- ev_3: 食堂菜单与本题无关\n"
                    "Select the best evidence ids."
                ),
            },
        ],
        max_tokens=128,
    )
    early = _from_provider_error(spec, thinking_mode, repeat_index, result)
    if early:
        return early
    scored = score_evidence_selection(result.content, allowed_ids=allowed)
    passed = bool(
        scored.ok
        and scored.args
        and "ev_1" in scored.args.get("selected_ids", [])
    )
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if passed else ProbeStatus.failed,
        passed=passed,
        result=result,
        repair_required=scored.repair_required,
        schema_success=scored.schema_success,
        error=None if passed else scored.error,
        details={"args": scored.args},
    )


def _planning_case(
    *,
    probe_id: str,
    name: str,
    user: str,
    expect_action: str,
    expect_tool: str | None,
) -> ProbeFn:
    def _run(
        adapter: OpenAICompatibleAdapter,
        thinking_mode: ThinkingMode,
        repeat_index: int,
    ) -> ProbeResult:
        spec = ProbeSpec(probe_id, "F", name, _run, stability_core=True)
        result = adapter.chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval agent planner. Return ONLY JSON "
                        '{"action":"tool|finish|clarify|refuse","tool_name":...,'
                        '"args":{},"reason_code":"..."}. '
                        "If facts missing → tool semantic_search. "
                        "If complete → finish. "
                        "If conflict → refuse or clarify (never fake finish). "
                        "If unavailable → clarify or refuse."
                    ),
                },
                {"role": "user", "content": user},
            ],
            max_tokens=192,
        )
        early = _from_provider_error(spec, thinking_mode, repeat_index, result)
        if early:
            return early
        scored = score_agent_decision(result.content)
        passed = False
        if scored.ok and scored.action == expect_action:
            if expect_tool is None or scored.tool_name == expect_tool:
                passed = True
        # Special: conflict / unavailable accept clarify OR refuse.
        if expect_action in {"clarify", "refuse"} and scored.ok:
            if scored.action in {"clarify", "refuse"}:
                passed = True
            if scored.action == "finish":
                passed = False
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.passed if passed else ProbeStatus.failed,
            passed=passed,
            result=result,
            repair_required=scored.repair_required,
            schema_success=scored.schema_success,
            error=None if passed else (scored.error or "unexpected_action"),
            details={"action": scored.action, "tool_name": scored.tool_name},
        )

    return _run


probe_f_missing_retrieve = _planning_case(
    probe_id="F1",
    name="plan_missing_retrieve",
    user="State: missing facts=[住宿标准]. Choose next action.",
    expect_action="tool",
    expect_tool="semantic_search",
)
probe_f_complete_finish = _planning_case(
    probe_id="F2",
    name="plan_complete_finish",
    user="State: covered facts=[住宿标准=500]. Evidence sufficient. Choose next action.",
    expect_action="finish",
    expect_tool=None,
)
probe_f_conflict_no_fake = _planning_case(
    probe_id="F3",
    name="plan_conflict_no_fake_finish",
    user=(
        "State: conflicted facts=[住宿标准]. "
        "Doc A says 500, Doc B says 800. Choose next action."
    ),
    expect_action="refuse",
    expect_tool=None,
)
probe_f_unavailable = _planning_case(
    probe_id="F4",
    name="plan_unavailable_clarify_or_refuse",
    user="State: permission denied / knowledge unavailable. Choose next action.",
    expect_action="clarify",
    expect_tool=None,
)


def probe_h_thinking_control(
    adapter: OpenAICompatibleAdapter,
    thinking_mode: ThinkingMode,
    repeat_index: int,
) -> ProbeResult:
    """Explicit thinking controllability probe (category H when mode=on)."""
    spec = ProbeSpec("H0", "H", "thinking_control_surface", probe_h_thinking_control)
    result = adapter.chat_completion(
        [
            {"role": "system", "content": "Answer with exactly: PONG"},
            {"role": "user", "content": "ping"},
        ],
        max_tokens=64,
    )
    if result.timed_out:
        return _base(
            spec,
            thinking_mode=thinking_mode,
            repeat_index=repeat_index,
            status=ProbeStatus.error,
            passed=False,
            result=result,
            error=result.error,
            details={"thinking_control": "timeout"},
        )
    supported = adapter.thinking_control_supported
    if supported is False or (
        thinking_mode == ThinkingMode.on and supported is None and not result.thinking_control_applied
    ):
        return _base(
            spec,
            thinking_mode=ThinkingMode.not_controllable,
            repeat_index=repeat_index,
            status=ProbeStatus.unsupported,
            passed=False,
            result=result,
            error="NOT_CONTROLLABLE",
            details={"thinking_control_supported": supported},
        )
    # Soft pass: request completed under requested mode without stall.
    ok = not result.error and bool(result.content)
    return _base(
        spec,
        thinking_mode=thinking_mode,
        repeat_index=repeat_index,
        status=ProbeStatus.passed if ok else ProbeStatus.failed,
        passed=ok,
        result=result,
        error=result.error,
        details={
            "thinking_control_applied": result.thinking_control_applied,
            "thinking_control_supported": supported,
        },
    )


def default_probe_specs(*, include_thinking_probe: bool) -> list[ProbeSpec]:
    specs: list[ProbeSpec] = [
        ProbeSpec("A1", "A", "connectivity_basic_completion", probe_a_connectivity),
        ProbeSpec(
            "B1", "B", "structured_json_strict", probe_b_structured_json, True
        ),
        ProbeSpec(
            "C1", "C", "agent_decision_schema", probe_c_agent_decision, True
        ),
        ProbeSpec("C2", "C", "agent_decision_invalid_enum", probe_c_invalid_enum),
        ProbeSpec("D1", "D", "native_tool_calling", probe_d_native_tool_calling),
        ProbeSpec(
            "D2", "D", "json_planned_tool_call", probe_d_json_planned_tool, True
        ),
        ProbeSpec("E1", "E", "evidence_selection", probe_e_evidence_selection, True),
        ProbeSpec("F1", "F", "plan_missing_retrieve", probe_f_missing_retrieve, True),
        ProbeSpec("F2", "F", "plan_complete_finish", probe_f_complete_finish, True),
        ProbeSpec(
            "F3", "F", "plan_conflict_no_fake_finish", probe_f_conflict_no_fake, True
        ),
        ProbeSpec(
            "F4",
            "F",
            "plan_unavailable_clarify_or_refuse",
            probe_f_unavailable,
            True,
        ),
    ]
    if include_thinking_probe:
        specs.append(
            ProbeSpec("H0", "H", "thinking_control_surface", probe_h_thinking_control)
        )
    return specs

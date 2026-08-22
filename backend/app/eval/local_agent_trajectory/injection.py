"""Benchmark-only Planner LLM injection + StopPolicy / Matcher tracing.

Does not copy Agent runtime. Uses product NextActionPlanner.decide_next
and patches chat_llm at the import site used by planners._call_llm.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

from app.core.config import settings
from app.eval.local_model_profile.adapter import CompletionResult, OpenAICompatibleAdapter
from app.services.agent.fact_contracts import fact_coverage_ratio
from app.services.agent.planners import NextActionPlanner, SafetyFrame, parse_agent_decision
from app.services.agent.types import AgentDecision, AgentState, FactStatus


RESEARCH_FLAG_NAMES = (
    "agent_l3_next_action_enabled",
    "agent_l4_stop_policy_enabled",
    "agent_l4_evidence_matcher_enabled",
    "agent_memory_enabled",
)


@dataclass
class RoundCapture:
    step_index: int
    facts_before: dict[str, str]
    coverage_before: float
    conflicts_before: list[str]
    raw: str
    parse_ok: bool
    parse_error: str | None
    parsed_action: str | None
    parsed_tool: str | None
    parsed_args: dict[str, Any]
    decision_valid: bool
    planner_decision: AgentDecision
    stop_before: AgentDecision | None = None
    stop_after: AgentDecision | None = None
    stop_effect: str = "passthrough"
    timed_out: bool = False
    provider_error: str | None = None
    latency_ms: float = 0.0
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_success: bool | None = None
    observation_summary: str = ""
    facts_after: dict[str, str] = field(default_factory=dict)
    coverage_after: float = 0.0
    conflicts_after: list[str] = field(default_factory=list)


class RecordingAdapter:
    """Thin wrapper: records last CompletionResult for timeout/error taxonomy."""

    def __init__(self, inner: OpenAICompatibleAdapter) -> None:
        self.inner = inner
        self.last: CompletionResult | None = None
        self.calls = 0

    def chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.last = self.inner.chat_completion(messages, **kwargs)
        return self.last


class TracingPlanner(NextActionPlanner):
    """Product planner + per-round capture. LLM via injected complete_chat."""

    def __init__(
        self,
        query: str,
        *,
        adapter: RecordingAdapter,
        captures: list[RoundCapture],
    ) -> None:
        safety = SafetyFrame(query)
        super().__init__(query, safety_frame=safety, tool_specs=safety.all_tool_specs())
        self._recording = adapter
        self.captures = captures

    async def decide_next(self, state: AgentState) -> AgentDecision:
        import time

        facts_before = {g.id: g.status.value for g in state.evidence.facts}
        coverage_before = fact_coverage_ratio(state.evidence)
        conflicts_before = [
            g.id for g in state.evidence.facts if g.status == FactStatus.conflicted
        ]
        t0 = time.perf_counter()
        decision = await super().decide_next(state)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        last = self._recording.last
        raw = self.last_llm_raw or (last.content if last else "") or ""
        parsed = parse_agent_decision(raw) if raw.strip() else None
        parse_ok = bool(parsed and parsed.ok)
        parse_error = None if parse_ok else (
            (parsed.error if parsed else None)
            or self.fallback_reason
            or (last.error if last else None)
            or "empty_output"
        )
        parsed_decision = parsed.decision if parsed and parsed.decision else None
        cap = RoundCapture(
            step_index=len(self.captures),
            facts_before=facts_before,
            coverage_before=coverage_before,
            conflicts_before=conflicts_before,
            raw=raw,
            parse_ok=parse_ok,
            parse_error=parse_error,
            parsed_action=(
                parsed_decision.action.value if parsed_decision is not None else _guess_action(raw)
            ),
            parsed_tool=parsed_decision.tool_name if parsed_decision else None,
            parsed_args=dict(parsed_decision.args) if parsed_decision else {},
            decision_valid=decision.action is not None and (
                parse_ok and self.fallback_reason not in {"safety_violation", "parse_error"}
            ),
            planner_decision=decision,
            timed_out=bool(last and last.timed_out),
            provider_error=last.error if last else None,
            latency_ms=latency_ms,
        )
        # Validated decision may be refuse after parse/safety failure.
        if self.fallback_reason == "safety_violation":
            cap.decision_valid = False
        elif not parse_ok:
            cap.decision_valid = False
        else:
            cap.decision_valid = True
        self.captures.append(cap)
        return decision


def _guess_action(raw: str) -> str | None:
    text = raw.lower()
    if '"action"' not in text:
        return None
    for name in (
        "semantic_search",
        "search_documents",
        "finish",
        "clarify",
        "refuse",
        "tool",
    ):
        if f'"action": "{name}"' in text or f'"action":"{name}"' in text:
            return name
    return None


_CHAT_ORIG: dict[str, Any] = {}


def patch_planner_llm(adapter: RecordingAdapter) -> None:
    """Point planners._call_llm's local imports at the research adapter."""
    import app.services.rag.chat_llm as chat_llm

    _CHAT_ORIG.setdefault("complete", chat_llm.complete_chat_with_usage)
    _CHAT_ORIG.setdefault("has_key", chat_llm.has_available_chat_provider_key)

    async def _complete(messages: list[dict[str, str]]) -> tuple[str, None]:
        result = await asyncio.to_thread(
            adapter.chat_completion,
            messages,
            temperature=0.0,
            max_tokens=768,
        )
        if result.timed_out:
            raise TimeoutError(result.error or "timeout")
        if result.error:
            raise RuntimeError(result.error)
        return result.content or "", None

    chat_llm.complete_chat_with_usage = _complete  # type: ignore[method-assign]
    chat_llm.has_available_chat_provider_key = lambda: True  # type: ignore[method-assign]


def restore_planner_llm() -> None:
    import app.services.rag.chat_llm as chat_llm

    complete = _CHAT_ORIG.get("complete")
    has_key = _CHAT_ORIG.get("has_key")
    if complete is not None:
        chat_llm.complete_chat_with_usage = complete
    if has_key is not None:
        chat_llm.has_available_chat_provider_key = has_key


def apply_research_flags() -> dict[str, Any]:
    """Process-local flags for this benchmark run; restore with restore_flags."""
    saved = {name: getattr(settings, name) for name in RESEARCH_FLAG_NAMES}
    settings.agent_l3_next_action_enabled = True
    settings.agent_l4_stop_policy_enabled = True
    settings.agent_l4_evidence_matcher_enabled = True
    settings.agent_memory_enabled = False
    return saved


def restore_flags(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(settings, name, value)


def wrap_stop_policy(captures: list[RoundCapture]) -> Callable[..., AgentDecision]:
    from app.services.agent.stop_policy import apply_stop_policy_decision as original

    def _wrapped(state: AgentState, decision: AgentDecision) -> AgentDecision:
        after = original(state, decision)
        if captures:
            cap = captures[-1]
            cap.stop_before = decision
            cap.stop_after = after
            if after.action != decision.action or after.reason_code != decision.reason_code:
                if (
                    decision.action.value == "finish"
                    and after.action.value == "tool"
                ):
                    cap.stop_effect = "block_finish_retrieve"
                elif after.action.value == "refuse":
                    cap.stop_effect = "force_refuse"
                elif after.action.value == "finish" and decision.action.value != "finish":
                    cap.stop_effect = "force_finish"
                else:
                    cap.stop_effect = "rewrite"
            else:
                cap.stop_effect = "passthrough"
        return after

    return _wrapped


def mock_semantic_search(factory: Callable[..., Any]) -> AsyncMock:
    return AsyncMock(side_effect=factory)

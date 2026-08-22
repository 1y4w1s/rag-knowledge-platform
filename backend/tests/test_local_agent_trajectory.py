"""W8 P0 local agent trajectory harness — mock / CI-safe (no LM Studio)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.core.config import settings
from app.eval.local_agent_trajectory.cases import CASE_BY_ID, w8_p0_cases
from app.eval.local_agent_trajectory.report import write_json
from app.eval.local_agent_trajectory.schema import FailureClass, StepTrace, utc_now_iso
from app.eval.local_agent_trajectory.scoring import (
    aggregate_summary,
    classify_raw_action,
    finalize_trajectory,
)
from app.eval.local_model_profile.adapter import CompletionResult, OpenAICompatibleAdapter
from app.services.agent.types import AgentActionKind, AgentDecision, AgentRunOutcome


def test_product_defaults_unchanged() -> None:
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.rag_critic_enabled is False


def test_case_set_covers_categories() -> None:
    cases = w8_p0_cases()
    assert 12 <= len(cases) <= 24
    cats = {c.category for c in cases}
    assert cats >= {
        "direct",
        "missing_fact",
        "multi_fact",
        "conflict",
        "tool_failure",
        "budget",
        "clarify",
    }


def _outcome(
    *,
    steps_used: int = 1,
    capped: bool = False,
    timed_out: bool = False,
    action: AgentActionKind = AgentActionKind.finish,
    reason: str = "facts_covered",
) -> AgentRunOutcome:
    return AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=steps_used,
        max_steps=5,
        capped=capped,
        timed_out=timed_out,
        steps=(),
        terminal_decision=AgentDecision(action=action, reason_code=reason),
    )


def _step(**kwargs) -> StepTrace:  # noqa: ANN003
    base = dict(
        step_index=0,
        planner_raw_response_excerpt='{"action":"tool","tool_name":"semantic_search"}',
        planner_parse_success=True,
        planner_decision={
            "action": "tool",
            "tool_name": "semantic_search",
            "args": {"query": "q"},
            "reason_code": "initial_retrieval",
        },
        decision_valid=True,
        stop_policy_effect="passthrough",
        tool_name="semantic_search",
        tool_args={"query": "q"},
        tool_success=True,
        observation_summary="命中 1",
        fact_status_before={"F1": "missing"},
        fact_status_after={"F1": "covered"},
        evidence_coverage=1.0,
        conflicts=[],
        latency_ms=12.0,
        error=None,
    )
    base.update(kwargs)
    return StepTrace(**base)


def test_successful_trajectory_aggregation() -> None:
    case = CASE_BY_ID["B1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(),
            _step(
                step_index=1,
                planner_raw_response_excerpt='{"action":"finish"}',
                planner_decision={
                    "action": "finish",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "facts_covered",
                },
                tool_name=None,
                tool_success=None,
                fact_status_before={"F1": "covered"},
                fact_status_after={"F1": "covered"},
            ),
        ],
        outcome=_outcome(steps_used=1),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=40.0,
    )
    assert result.end_to_end_success is True
    assert result.safe_termination is True
    summary = aggregate_summary([result])
    assert summary.trajectory_count == 1
    assert summary.end_to_end_success_rate == 1.0
    assert summary.system_saved_rate == 0.0


def test_planner_malformed_event() -> None:
    events = classify_raw_action(
        '{"action":"semantic_search","args":{"query":"q"}}',
        False,
        "invalid_action",
    )
    assert FailureClass.MODEL_TOOL_MAPPING_FAILURE.value in events
    case = CASE_BY_ID["B1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                planner_raw_response_excerpt="not-json",
                planner_parse_success=False,
                planner_decision={
                    "action": "refuse",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "parse_error",
                },
                decision_valid=False,
                tool_success=None,
                error="parse_error",
                fact_status_after={"F1": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=_outcome(steps_used=0, action=AgentActionKind.refuse, reason="parse_error"),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=10.0,
    )
    assert FailureClass.MODEL_MALFORMED_JSON.value in result.failure_class
    assert result.model_decision_success is False


def test_stop_policy_system_saved_and_rate() -> None:
    case = CASE_BY_ID["B1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                planner_raw_response_excerpt='{"action":"finish"}',
                planner_decision={
                    "action": "finish",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "llm_early",
                },
                stop_policy_effect="block_finish_retrieve",
                tool_success=True,
                fact_status_after={"F1": "covered"},
            ),
            _step(
                step_index=1,
                planner_raw_response_excerpt='{"action":"finish"}',
                planner_decision={
                    "action": "finish",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "facts_covered",
                },
                tool_name=None,
                tool_success=None,
                fact_status_before={"F1": "covered"},
                fact_status_after={"F1": "covered"},
            ),
        ],
        outcome=_outcome(steps_used=1),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=20.0,
    )
    assert result.premature_finish is True
    assert result.system_saved is True
    assert result.model_decision_success is False
    assert result.system_safety_success is True
    assert result.end_to_end_success is True
    summary = aggregate_summary([result])
    assert summary.system_saved_count == 1
    assert summary.system_saved_rate == 1.0


def test_tool_failure_not_polluting_coverage() -> None:
    case = CASE_BY_ID["E1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                tool_success=False,
                observation_summary="检索后端失败",
                fact_status_after={"F1": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=_outcome(steps_used=1, action=AgentActionKind.refuse, reason="facts_incomplete"),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=15.0,
    )
    assert FailureClass.TOOL_EXECUTION_FAILURE.value in result.failure_class
    assert result.evidence_complete is False
    assert result.safe_termination is True


def test_budget_exhausted() -> None:
    case = CASE_BY_ID["F1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                fact_status_before={"F9": "missing"},
                fact_status_after={"F9": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=_outcome(
            steps_used=2,
            capped=True,
            action=AgentActionKind.refuse,
            reason="facts_missing_budget",
        ),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=30.0,
    )
    assert FailureClass.BUDGET_EXHAUSTED.value in result.failure_class
    assert result.end_to_end_success is True
    assert result.evidence_complete is False


def test_timeout_marks_trajectory() -> None:
    case = CASE_BY_ID["B1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                planner_parse_success=False,
                decision_valid=False,
                error="timeout:TimeoutException",
                tool_success=None,
                fact_status_after={"F1": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=AgentRunOutcome(
            run_id=uuid.uuid4(),
            steps_used=0,
            max_steps=5,
            capped=False,
            timed_out=True,
            steps=(),
            terminal_decision=None,
        ),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=90000.0,
    )
    assert result.timeout is True
    assert result.safe_termination is False
    assert FailureClass.MODEL_TIMEOUT.value in result.failure_class


def test_safe_refusal() -> None:
    case = CASE_BY_ID["G1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                planner_raw_response_excerpt='{"action":"clarify"}',
                planner_decision={
                    "action": "clarify",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "ambiguous_user_intent",
                },
                tool_name=None,
                tool_success=None,
                fact_status_before={"G1": "missing"},
                fact_status_after={"G1": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=_outcome(steps_used=0, action=AgentActionKind.clarify, reason="ambiguous_user_intent"),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=8.0,
    )
    assert result.end_to_end_success is True
    assert result.safe_termination is True


def test_report_serialization(tmp_path) -> None:  # noqa: ANN001
    case = CASE_BY_ID["A1"]
    result = finalize_trajectory(
        case,
        steps=[
            _step(
                fact_status_before={"F1": "covered", "F2": "covered"},
                fact_status_after={"F1": "covered", "F2": "covered"},
                tool_success=None,
                tool_name=None,
                planner_raw_response_excerpt='{"action":"finish"}',
                planner_decision={
                    "action": "finish",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "facts_covered",
                },
            )
        ],
        outcome=_outcome(steps_used=0),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=5.0,
    )
    path = write_json(tmp_path / "w8.json", {"trajectories": [result.to_dict()]})
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["trajectories"][0]["case_id"] == "A1"
    assert "api_key" not in json.dumps(loaded)


def test_category_aggregation() -> None:
    b = finalize_trajectory(
        CASE_BY_ID["B1"],
        steps=[_step()],
        outcome=_outcome(steps_used=1),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=10.0,
    )
    g = finalize_trajectory(
        CASE_BY_ID["G1"],
        steps=[
            _step(
                planner_decision={
                    "action": "clarify",
                    "tool_name": None,
                    "args": {},
                    "reason_code": "ambiguous_user_intent",
                },
                tool_success=None,
                fact_status_before={"G1": "missing"},
                fact_status_after={"G1": "missing"},
                evidence_coverage=0.0,
            )
        ],
        outcome=_outcome(action=AgentActionKind.clarify, reason="ambiguous_user_intent"),
        model_id="mock",
        thinking_mode="off",
        started_at=utc_now_iso(),
        duration_ms=10.0,
    )
    summary = aggregate_summary([b, g])
    assert "missing_fact" in summary.by_category
    assert "clarify" in summary.by_category
    assert summary.by_category["missing_fact"]["count"] == 1


@pytest.mark.asyncio
async def test_real_runtime_injected_planner(register_and_login, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scripted local adapter → real run_react_loop / NextActionPlanner (no LM Studio)."""
    from app.eval.local_agent_trajectory.execute import run_one_case
    from app.eval.local_agent_trajectory.injection import RecordingAdapter
    from uuid import UUID

    class _Scripted(OpenAICompatibleAdapter):
        def __init__(self, contents: list[str]) -> None:
            super().__init__(
                base_url="http://127.0.0.1:9/v1",
                model="mock",
                api_key="x",
                timeout_seconds=5.0,
            )
            self._contents = list(contents)

        def chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            del messages, kwargs
            text = self._contents.pop(0) if self._contents else '{"action":"refuse"}'
            return CompletionResult(content=text, latency_ms=1.0, http_status=200)

    _, user = await register_and_login(prefix="w8p0")
    adapter = RecordingAdapter(
        _Scripted(
            [
                '{"action":"tool","tool_name":"semantic_search","args":{"query":"2025住宿标准"},"reason_code":"initial_retrieval"}',
                '{"action":"finish","reason_code":"facts_covered"}',
            ]
        )
    )
    result = await run_one_case(
        CASE_BY_ID["B1"],
        adapter,
        model_id="mock",
        thinking_mode="off",
        user_id=UUID(user["id"]),
        run_timeout_seconds=30.0,
    )
    assert result.steps, "must record planner rounds from real runtime"
    assert settings.agent_l4_stop_policy_enabled is False  # restored
    assert any(s.planner_parse_success for s in result.steps)

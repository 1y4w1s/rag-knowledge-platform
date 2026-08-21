"""W7 P0 — Local Model Capability Profile harness (mock / CI-safe)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.eval.local_model_profile.adapter import CompletionResult, OpenAICompatibleAdapter
from app.eval.local_model_profile.probes import (
    probe_a_connectivity,
    probe_b_structured_json,
    probe_c_agent_decision,
    probe_d_json_planned_tool,
    probe_d_native_tool_calling,
    probe_e_evidence_selection,
)
from app.eval.local_model_profile.report import (
    load_profile_report,
    profile_to_json,
    sanitize_for_report,
    write_profile_report,
)
from app.eval.local_model_profile.runner import ProbeRunner, aggregate_summary, recommend
from app.eval.local_model_profile.schema import (
    SCHEMA_VERSION,
    Environment,
    LocalModelProfile,
    ProbeResult,
    Recommendation,
    Summary,
    ThinkingMode,
)
from app.eval.local_model_profile.scoring import (
    score_agent_decision,
    score_evidence_selection,
    score_native_tool_call,
    score_strict_json,
)


def test_l4_local_model_profile_flag_remains_false() -> None:
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.rag_critic_enabled is False


class _ScriptedAdapter(OpenAICompatibleAdapter):
    """Deterministic adapter: queue of CompletionResult / callables."""

    def __init__(self, script: list[Any], **kwargs: Any) -> None:
        super().__init__(
            base_url=kwargs.pop("base_url", "http://127.0.0.1:9/v1"),
            model=kwargs.pop("model", "mock-model"),
            api_key=kwargs.pop("api_key", "test-key"),
            timeout_seconds=kwargs.pop("timeout_seconds", 5.0),
            thinking_mode=kwargs.pop("thinking_mode", ThinkingMode.off),
            provider=kwargs.pop("provider", "mock"),
        )
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"messages": messages, **kwargs})
        if not self._script:
            return CompletionResult(content="", error="provider_error:exhausted")
        item = self._script.pop(0)
        if callable(item):
            return item(messages, **kwargs)
        return item


def test_valid_completion_pass() -> None:
    adapter = _ScriptedAdapter(
        [CompletionResult(content="OK", latency_ms=12.0, http_status=200)]
    )
    result = probe_a_connectivity(adapter, ThinkingMode.off, 0)
    assert result.passed is True
    assert result.status == "pass"
    assert result.timed_out is False


def test_malformed_json_fail_not_over_lenient() -> None:
    raw = '```json\n{"name": "alpha", "score": 0.9}\n```'
    scored = score_strict_json(raw, required_keys={"name", "score"})
    assert scored.repair_required is True
    assert scored.schema_success is False
    assert scored.parsed is not None  # observable after repair
    # Probe PASS requires schema_success
    adapter = _ScriptedAdapter([CompletionResult(content=raw, http_status=200)])
    result = probe_b_structured_json(adapter, ThinkingMode.off, 0)
    assert result.passed is False
    assert result.repair_required is True
    assert result.schema_success is False


def test_strict_json_valid_pass() -> None:
    raw = '{"name":"alpha","score":0.9}'
    scored = score_strict_json(raw, required_keys={"name", "score"})
    assert scored.schema_success is True
    assert scored.repair_required is False
    adapter = _ScriptedAdapter([CompletionResult(content=raw, http_status=200)])
    result = probe_b_structured_json(adapter, ThinkingMode.off, 0)
    assert result.passed is True
    assert result.schema_success is True


def test_timeout_sets_timed_out_and_runner_continues() -> None:
    adapter = _ScriptedAdapter(
        [
            CompletionResult(content="", timed_out=True, error="timeout:TimeoutException"),
            CompletionResult(content="OK", http_status=200),
        ]
    )
    from app.eval.local_model_profile.probes import ProbeSpec

    specs = [
        ProbeSpec("A1", "A", "connectivity_basic_completion", probe_a_connectivity),
        ProbeSpec("A1b", "A", "connectivity_retry", probe_a_connectivity),
    ]
    profile = ProbeRunner(adapter, thinking_mode=ThinkingMode.off, repeat=1, specs=specs).run()
    assert profile.probes[0].timed_out is True
    assert profile.probes[0].passed is False
    assert profile.probes[1].passed is True
    assert profile.summary.total == 2


def test_invalid_agent_decision_enum_fail() -> None:
    scored = score_agent_decision(
        '{"action":"dance","tool_name":null,"args":{},"reason_code":"x"}'
    )
    assert scored.ok is False
    assert scored.error == "invalid_action_enum"


def test_nonexistent_tool_fail() -> None:
    scored = score_agent_decision(
        '{"action":"tool","tool_name":"launch_missile","args":{"q":"1"},"reason_code":"x"}'
    )
    assert scored.ok is False
    assert scored.error == "unknown_tool"

    adapter = _ScriptedAdapter(
        [
            CompletionResult(
                content='{"tool_name":"launch_missile","args":{"query":"x"}}',
                http_status=200,
            )
        ]
    )
    result = probe_d_json_planned_tool(adapter, ThinkingMode.off, 0)
    assert result.passed is False
    assert result.error == "unknown_tool"


def test_valid_tool_args_pass() -> None:
    scored = score_native_tool_call(
        [
            {
                "id": "1",
                "type": "function",
                "function": {
                    "name": "semantic_search",
                    "arguments": '{"query":"住宿标准"}',
                },
            }
        ],
        expected_name="semantic_search",
        required_arg_keys={"query"},
    )
    assert scored.ok is True
    adapter = _ScriptedAdapter(
        [
            CompletionResult(
                content="",
                tool_calls=[
                    {
                        "id": "1",
                        "type": "function",
                        "function": {
                            "name": "semantic_search",
                            "arguments": '{"query":"住宿标准"}',
                        },
                    }
                ],
                http_status=200,
            )
        ]
    )
    result = probe_d_native_tool_calling(adapter, ThinkingMode.off, 0)
    assert result.passed is True


def test_native_tools_http_400_unsupported() -> None:
    adapter = _ScriptedAdapter(
        [CompletionResult(content="", error="http_400", http_status=400)]
    )
    result = probe_d_native_tool_calling(adapter, ThinkingMode.off, 0)
    assert result.status == "unsupported"
    assert result.error == "UNSUPPORTED"


def test_evidence_id_hallucination_fail() -> None:
    scored = score_evidence_selection(
        '{"selected_ids":["ev_1","ev_999"]}',
        allowed_ids={"ev_1", "ev_2", "ev_3"},
    )
    assert scored.ok is False
    assert scored.error == "evidence_id_hallucination"

    adapter = _ScriptedAdapter(
        [
            CompletionResult(
                content='{"selected_ids":["ev_1","ev_ghost"]}',
                http_status=200,
            )
        ]
    )
    result = probe_e_evidence_selection(adapter, ThinkingMode.off, 0)
    assert result.passed is False
    assert result.error == "evidence_id_hallucination"


def test_provider_error_fail_runner_continues() -> None:
    adapter = _ScriptedAdapter(
        [
            CompletionResult(content="", error="provider_error:ConnectError"),
            CompletionResult(content='{"name":"alpha","score":1}', http_status=200),
        ]
    )
    from app.eval.local_model_profile.probes import ProbeSpec

    specs = [
        ProbeSpec("A1", "A", "connectivity_basic_completion", probe_a_connectivity),
        ProbeSpec("B1", "B", "structured_json_strict", probe_b_structured_json),
    ]
    profile = ProbeRunner(adapter, thinking_mode=ThinkingMode.off, repeat=1, specs=specs).run()
    assert profile.probes[0].passed is False
    assert profile.probes[0].status == "error"
    assert profile.probes[1].passed is True


def test_summary_aggregation() -> None:
    probes = [
        ProbeResult(
            probe_id="A1",
            category="A",
            name="a",
            status="pass",
            passed=True,
            thinking_mode="off",
        ),
        ProbeResult(
            probe_id="B1",
            category="B",
            name="b",
            status="fail",
            passed=False,
            thinking_mode="off",
        ),
        ProbeResult(
            probe_id="D1",
            category="D",
            name="d",
            status="unsupported",
            passed=False,
            thinking_mode="off",
        ),
        ProbeResult(
            probe_id="A2",
            category="A",
            name="t",
            status="error",
            passed=False,
            timed_out=True,
            thinking_mode="off",
        ),
    ]
    summary = aggregate_summary(probes, thinking_mode=ThinkingMode.off)
    assert summary.total == 4
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.unsupported == 1
    assert summary.timed_out == 1
    assert summary.by_category["A"]["passed"] == 1


def test_report_json_serialize_reload(tmp_path: Path) -> None:
    profile = LocalModelProfile(
        schema_version=SCHEMA_VERSION,
        created_at="2026-08-22T00:00:00+00:00",
        provider="mock",
        endpoint_type="openai_compatible",
        model_id="mock-model",
        thinking_mode="off",
        run_id="abc123",
        environment=Environment(
            python_version="3.12",
            platform="test",
            timeout_seconds=30.0,
            repeat=3,
            endpoint_host="127.0.0.1",
        ),
        probes=[
            ProbeResult(
                probe_id="A1",
                category="A",
                name="connectivity",
                status="pass",
                passed=True,
                thinking_mode="off",
            )
        ],
        summary=Summary(
            total=1, passed=1, failed=0, timed_out=0, unsupported=0, error=0
        ),
        recommendation=Recommendation(
            overall="conditional",
            thinking_off="conditional",
            thinking_on="unknown",
            reasons=["partial_structured_capability"],
        ),
    )
    dirty = profile.to_dict()
    dirty["api_key"] = "SECRET"
    dirty["probes"][0]["authorization"] = "Bearer SECRET"
    clean = sanitize_for_report(dirty)
    assert "api_key" not in clean
    assert "authorization" not in clean["probes"][0]

    path = write_profile_report(profile, tmp_path / "profile.json")
    loaded = load_profile_report(path)
    assert loaded.run_id == "abc123"
    assert loaded.probes[0].passed is True
    assert json.loads(profile_to_json(loaded))["model_id"] == "mock-model"


def test_thinking_off_on_not_mixed() -> None:
    off_adapter = _ScriptedAdapter(
        [CompletionResult(content="OK", http_status=200)],
        thinking_mode=ThinkingMode.off,
    )
    on_adapter = _ScriptedAdapter(
        [CompletionResult(content="OK", http_status=200)],
        thinking_mode=ThinkingMode.on,
    )
    from app.eval.local_model_profile.probes import ProbeSpec

    specs = [
        ProbeSpec("A1", "A", "connectivity_basic_completion", probe_a_connectivity),
    ]
    off_profile = ProbeRunner(
        off_adapter, thinking_mode=ThinkingMode.off, repeat=1, specs=specs
    ).run()
    on_profile = ProbeRunner(
        on_adapter, thinking_mode=ThinkingMode.on, repeat=1, specs=specs
    ).run()
    assert off_profile.thinking_mode == "off"
    assert on_profile.thinking_mode == "on"
    assert all(p.thinking_mode == "off" for p in off_profile.probes)
    assert all(p.thinking_mode == "on" for p in on_profile.probes)
    assert off_profile.run_id != on_profile.run_id


def test_unsupported_thinking_control_explicit() -> None:
    def _reply(messages, **kwargs):  # type: ignore[no-untyped-def]
        return CompletionResult(
            content="PONG",
            http_status=200,
            thinking_control_applied=False,
            thinking_control_supported=False,
        )

    adapter = _ScriptedAdapter([_reply], thinking_mode=ThinkingMode.on)
    adapter._thinking_control_supported = False
    from app.eval.local_model_profile.probes import probe_h_thinking_control

    result = probe_h_thinking_control(adapter, ThinkingMode.on, 0)
    assert result.status == "unsupported"
    assert result.error == "NOT_CONTROLLABLE"
    assert result.thinking_mode == ThinkingMode.not_controllable.value


def test_recommend_data_driven_unsuitable_on_connectivity_fail() -> None:
    probes = [
        ProbeResult(
            probe_id="A1",
            category="A",
            name="a",
            status="error",
            passed=False,
            thinking_mode="off",
            error="provider_error:ConnectError",
        )
    ]
    rec = recommend(probes, thinking_mode=ThinkingMode.off)
    assert rec.overall == "unsuitable"
    assert rec.thinking_off == "unsuitable"
    assert rec.thinking_on == "unknown"
    assert "connectivity_failed" in rec.reasons


def test_agent_decision_valid_pass_probe() -> None:
    content = (
        '{"action":"tool","tool_name":"semantic_search",'
        '"args":{"query":"差旅住宿标准"},"reason_code":"missing"}'
    )
    adapter = _ScriptedAdapter([CompletionResult(content=content, http_status=200)])
    result = probe_c_agent_decision(adapter, ThinkingMode.off, 0)
    assert result.passed is True
    assert result.schema_success is True

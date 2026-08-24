"""W9 P3 execution I/O contract tests (mock only, no LM Studio, no formal artifact)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from app.eval.local_model_profile.adapter import (
    CompletionResult,
    OpenAICompatibleAdapter,
)
from app.services.rag.generation import VERIFY_ANSWER_PROMPT

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p2_r3_formal_runner import FORMAL_ARTIFACT_NAME as P2_R3_ARTIFACT
from tests.w9_critic_p3_execution import (
    ADAPTER_CLASS,
    ORACLE_ONLY_KEYS,
    P3ExecutionGateway,
    assert_no_oracle_leakage,
    build_p3_adapter,
    build_p3_model_input,
    enumerate_eligible_model_inputs,
    evaluate_execution_contract_gate,
    evaluate_p3_formal_completeness,
    observation_from_completion,
    oracle_leakage_count,
    parse_structured_critic_action,
    parser_contract_self_check,
    refuse_formal_artifact_write,
    score_three_layers,
    validate_p3_formal_artifact,
)
from tests.w9_critic_p3_protocol import (
    FORMAL_ARTIFACT_PATH,
    MODEL_CONFIG,
    POST_61_MASTER_SHA,
    FormalP3ArtifactForbidden,
    LmStudioForbidden,
    P3ProtocolRunner,
    SemanticVerdict,
    build_and_write_dry_run_plan,
)

REPO = Path(__file__).resolve().parents[2]


def _git_diff(*pathspecs: str) -> bytes:
    completed = subprocess.run(
        ["git", "diff", POST_61_MASTER_SHA, "--", *pathspecs],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return completed.stdout.replace(b"\r\n", b"\n")


def test_eleven_eligible_model_inputs_construct_without_oracle_leakage() -> None:
    requests = enumerate_eligible_model_inputs()
    assert len(requests) == 11
    assert {item.case_id for item in requests}.isdisjoint(
        {"C12-out-of-scope-provenance"}
    )
    assert len({item.input_hash for item in requests}) == 11
    assert oracle_leakage_count(requests) == 0
    for item in requests:
        payload = item.wire_payload()
        assert_no_oracle_leakage(payload)
        assert item.model == "zai-org/glm-4.6v-flash"
        assert item.thinking == "OFF"
        assert item.temperature == 0.0
        assert item.max_tokens == 512
        assert item.timeout_seconds == 60
        assert item.retry == "NONE"
        assert payload["enable_thinking"] is False
        blob = json.dumps(payload, ensure_ascii=False)
        for key in ORACLE_ONLY_KEYS:
            assert f'"{key}"' not in blob
        prompt = item.messages[0]["content"]
        assert item.messages[0]["role"] == "user"
        assert prompt.startswith(VERIFY_ANSWER_PROMPT[:10])
        assert "只输出 JSON 格式" in prompt
        assert str(item.visible_input["answer"]) in prompt


def test_model_input_excludes_oracle_and_hidden_recovery_fields() -> None:
    case = next(
        item
        for item in load_frozen_suite().cases
        if item["case_id"] == "C01-fully-supported-exact"
    )
    request = build_p3_model_input(case)
    leaked = {
        "expected_action": "ACCEPT",
        "acceptable_action": "ACCEPT",
        "oracle": "label",
        "semantic_verdict": "PASS",
        "scorer_result": True,
        "hidden_recovery": True,
    }
    with pytest.raises(ValueError, match="oracle leakage"):
        assert_no_oracle_leakage({**request.wire_payload(), **leaked})
    assert "expected_action" not in request.visible_input
    assert "query" in request.visible_input
    assert "answer" in request.visible_input
    assert "evidence" in request.visible_input


def test_parser_contract_covers_required_shapes() -> None:
    assert parser_contract_self_check() is True
    valid = parse_structured_critic_action('{"action":"REFUSE"}')
    assert valid.parse_valid is True
    assert valid.parsed_action == "REFUSE"
    invalid = parse_structured_critic_action("not json at all")
    assert invalid.parse_valid is False
    assert invalid.error == "invalid_json"
    unknown = parse_structured_critic_action('{"action":"BEST_OF_N"}')
    assert unknown.parse_valid is False
    assert unknown.error == "unknown_action"
    missing = parse_structured_critic_action("{}")
    assert missing.parse_valid is False
    assert missing.error == "missing_action"
    fenced = parse_structured_critic_action('```json\n{"action":"ACCEPT"}\n```')
    assert fenced.parse_valid is False
    verified = parse_structured_critic_action('{"verified":true}')
    assert verified.parsed_action == "ACCEPT"


def test_timeout_and_parse_failure_stay_in_denominator() -> None:
    timeout = observation_from_completion(
        CompletionResult(content="", timed_out=True, latency_ms=60_000.0)
    )
    parse_fail = observation_from_completion(
        CompletionResult(content="{bad", timed_out=False, latency_ms=12.0)
    )
    assert timeout.timeout is True
    assert timeout.retry_count == 0
    assert timeout.kind.value == "TIMEOUT"
    assert parse_fail.parse_valid is False
    assert parse_fail.retry_count == 0
    gate = evaluate_execution_contract_gate()
    assert gate["timeout_denominator_preservation"] == "PASS"
    assert gate["parse_failure_denominator_preservation"] == "PASS"


def test_three_layer_hidden_recovery_never_credits_model() -> None:
    recovered = score_three_layers(
        parse_valid=True,
        timeout=False,
        parsed_action="REFUSE",
        expected_action="ACCEPT",
        control_plane_success=True,
        safe_outcome=True,
        hidden_recovery=True,
    )
    assert recovered.l1_model_semantic_capability == "FAIL"
    assert recovered.l2_control_plane_execution == "PASS"
    assert recovered.l3_final_safety_outcome == "PASS"
    assert recovered.hidden_recovery is True
    assert recovered.semantic_verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    clean = score_three_layers(
        parse_valid=True,
        timeout=False,
        parsed_action="ACCEPT",
        expected_action="ACCEPT",
        control_plane_success=True,
        safe_outcome=True,
        hidden_recovery=False,
    )
    assert clean.l1_model_semantic_capability == "PASS"
    assert clean.first_failed_stage is None


def test_reuses_existing_adapter_and_forbids_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("httpx.Client must not be constructed")

    monkeypatch.setattr("httpx.Client", _boom)
    monkeypatch.setattr("app.eval.local_model_profile.adapter.httpx.Client", _boom)
    adapter = build_p3_adapter()
    assert isinstance(adapter, OpenAICompatibleAdapter)
    assert ADAPTER_CLASS is OpenAICompatibleAdapter
    assert adapter.model == MODEL_CONFIG["primary_model"]
    assert adapter.timeout_seconds == 60
    assert adapter.thinking_mode.value == "off"
    gateway = P3ExecutionGateway(adapter=adapter, dry_run=True)
    with pytest.raises(LmStudioForbidden):
        gateway.request([{"role": "user", "content": "x"}])
    assert gateway.lm_studio_requests == 0
    enumerate_eligible_model_inputs()
    assert evaluate_execution_contract_gate()["lm_studio_requests"] == 0


def test_formal_artifact_schema_validates_without_creating_file() -> None:
    gate = evaluate_execution_contract_gate()
    payload = {
        "protocol_version": "w9_critic_p3_r1_real_local_semantic_v1",
        "base_sha": POST_61_MASTER_SHA,
        "suite_hash": gate["suite_hash"],
        "oracle_hash": gate["oracle_hash"],
        "model_config": dict(MODEL_CONFIG),
        "thinking": "OFF",
        "run_id": "schema-only",
        "timestamp": "not-executed",
        "frozen_total": 12,
        "semantic_eligible_expected": 11,
        "semantic_executed": 0,
        "passed": 0,
        "failed": 0,
        "timeouts": 0,
        "parse_failures": 0,
        "hidden_recovery_count": 0,
        "measurement_state": "DRY_RUN",
        "model_capability_result": "NOT_EXECUTED",
        "cases": [
            {
                "case_id": case_id,
                "input_hash": digest,
                "semantic_eligible": True,
                "expected_action": "ACCEPT",
                "raw_observable_output": None,
                "parsed_action": None,
                "parse_valid": False,
                "semantic_correct": False,
                "semantic_verdict": "NOT_EXECUTED",
                "control_plane_terminal": None,
                "safe_outcome": None,
                "hidden_recovery": False,
                "latency_ms": None,
                "timeout": False,
                "retry_count": 0,
                "first_failed_stage": None,
                "l1_model_semantic_capability": "NOT_EXECUTED",
                "l2_control_plane_execution": "NOT_EXECUTED",
                "l3_final_safety_outcome": "NOT_EXECUTED",
            }
            for case_id, digest in gate["input_hashes"].items()
        ],
    }
    validate_p3_formal_artifact(payload)
    assert evaluate_p3_formal_completeness(payload) is False
    payload["semantic_executed"] = 11
    assert evaluate_p3_formal_completeness(payload) is True
    with pytest.raises(FormalP3ArtifactForbidden):
        refuse_formal_artifact_write()
    assert FORMAL_ARTIFACT_PATH.exists() is False
    cot = dict(payload["cases"][0])
    cot["chain_of_thought"] = "hidden"
    with pytest.raises(ValueError, match="chain-of-thought"):
        validate_p3_formal_artifact({**payload, "cases": [cot, *payload["cases"][1:]]})


def test_execution_contract_gate_and_dry_run_plan() -> None:
    gate = evaluate_execution_contract_gate()
    assert gate["P3_SEMANTIC_PROTOCOL_FROZEN"] == "YES"
    assert gate["P3_EXECUTION_CONTRACT_READY"] == "YES"
    assert gate["P3_REAL_RUN_READY"] == "YES"
    assert gate["MODEL_INPUT_ORACLE_LEAKAGE"] == 0
    assert gate["lm_studio_requests"] == 0
    assert gate["parser_contract"] == "PASS"
    assert gate["formal_artifact_present"] is False
    assert gate["blocker"] is None
    path = build_and_write_dry_run_plan()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["lm_studio_requests"] == 0
    assert saved["execution_contract"]["P3_EXECUTION_CONTRACT_READY"] == "YES"
    assert saved["execution_contract"]["MODEL_INPUT_ORACLE_LEAKAGE"] == 0
    runner = P3ProtocolRunner(execution_enabled=True)
    with pytest.raises(LmStudioForbidden):
        runner.plan_batch()


def test_p2_r3_history_and_runtime_diff_are_empty() -> None:
    assert _git_diff(f"backend/tests/fixtures/l4_critic/{P2_R3_ARTIFACT}") == b""
    assert _git_diff("backend/app") == b""
    assert FORMAL_ARTIFACT_PATH.exists() is False
    assert evaluate_execution_contract_gate()["lm_studio_requests"] == 0

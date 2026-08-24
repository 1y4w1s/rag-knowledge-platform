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

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p2_r3_formal_runner import FORMAL_ARTIFACT_NAME as P2_R3_ARTIFACT
from tests.w9_critic_p3_execution import (
    ADAPTER_CLASS,
    C04_CASE_ID,
    C05_CASE_ID,
    C06_CASE_ID,
    FIVE_ACTIONS,
    ORACLE_ONLY_KEYS,
    P3_ACTION_SPACE_INSTRUCTIONS,
    P3ExecutionGateway,
    PRE_SOLVED_DECISION_LABELS,
    action_space_prefix,
    assert_no_oracle_leakage,
    build_p3_adapter,
    build_p3_model_input,
    enumerate_eligible_model_inputs,
    evaluate_decision_surface,
    evaluate_execution_contract_gate,
    evaluate_p3_formal_completeness,
    observation_from_completion,
    oracle_leakage_count,
    parse_structured_critic_action,
    parser_contract_self_check,
    recover_verified_schema_for_control_plane,
    refuse_formal_artifact_write,
    score_three_layers,
    serialized_message_text,
    validate_p3_formal_artifact,
    verified_fallback_cannot_score_l1_pass,
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
        assert action_space_prefix(prompt) == P3_ACTION_SPACE_INSTRUCTIONS + "\n\n"
        assert all(action in prompt for action in FIVE_ACTIONS)
        assert "verified" not in prompt
        assert str(item.visible_input["query"]) in prompt
        assert str(item.visible_input["answer"]) in prompt
        assert "retrieval_scope_exhausted=" in prompt


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
    assert "retrieval_scope_exhausted" in request.visible_input
    assert "known_conflict" not in request.visible_input
    assert "required_fact_missing" not in json.dumps(request.wire_payload())


def test_parser_contract_covers_required_shapes() -> None:
    assert parser_contract_self_check() is True
    for action in FIVE_ACTIONS:
        parsed = parse_structured_critic_action(json.dumps({"action": action}))
        assert parsed.parse_valid is True
        assert parsed.parsed_action == action
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
    assert verified.parse_valid is False
    assert verified.parsed_action is None
    assert verified.error == "verified_schema_not_l1"
    verified_false = parse_structured_critic_action('{"verified":false}')
    assert verified_false.parse_valid is False
    assert verified_false.parsed_action is None
    with_issues = parse_structured_critic_action(
        '{"action":"CLARIFY","issues":["conflict"]}'
    )
    assert with_issues.parse_valid is True
    assert with_issues.parsed_action == "CLARIFY"


def test_decision_surface_anti_degeneracy_without_lm_studio() -> None:
    requests = enumerate_eligible_model_inputs()
    suite = load_frozen_suite()
    assert len(requests) == 11
    prefixes = {action_space_prefix(item.messages[0]["content"]) for item in requests}
    assert prefixes == {P3_ACTION_SPACE_INSTRUCTIONS + "\n\n"}
    assert all(action in P3_ACTION_SPACE_INSTRUCTIONS for action in FIVE_ACTIONS)
    for item in requests:
        content = serialized_message_text(item)
        body = content[len(action_space_prefix(content)) :]
        expected = str(suite.oracle[item.case_id]["expected_action"])
        assert expected not in body
        assert '"expected_action"' not in content
        blob = json.dumps(item.wire_payload(), ensure_ascii=False)
        for key in ORACLE_ONLY_KEYS | PRE_SOLVED_DECISION_LABELS:
            assert f'"{key}"' not in blob
            assert f"{key}=" not in content
        assert item.visible_input["query"] in content
        excerpts = [str(entry["excerpt"]) for entry in item.visible_input["evidence"]]
        assert excerpts and all(excerpt in content for excerpt in excerpts)
        assert "retrieval_scope_exhausted=" in content
        assert item.retry == "NONE"
    surface = evaluate_decision_surface(requests)
    assert surface["ACTION_SPACE_EXPOSED"] == "5/5"
    assert surface["MODEL_INPUT_ORACLE_LEAKAGE"] == 0
    assert surface["QUERY_PRESENT"] == "11/11"
    assert surface["EVIDENCE_PRESENT"] == "11/11"
    assert surface["RETRIEVAL_SCOPE_STATE_PRESENT"] == "11/11"
    assert surface["C04_C05_C06_DECISION_CONTEXT_SUFFICIENT"] == "YES"
    assert surface["EXPECTED_ACTION_IN_CASE_BODY"] == 0
    by_id = {item.case_id: serialized_message_text(item) for item in requests}
    assert by_id[C04_CASE_ID] != by_id[C05_CASE_ID] != by_id[C06_CASE_ID]
    assert "Admin@123" in by_id[C04_CASE_ID]
    assert "90" in by_id[C05_CASE_ID]
    assert "retrieval_scope_exhausted=false" in by_id[C06_CASE_ID]
    gate = evaluate_execution_contract_gate()
    assert gate["lm_studio_requests"] == 0
    assert gate["best_of_n"] is False


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


def test_verified_schema_cannot_score_l1_pass() -> None:
    assert verified_fallback_cannot_score_l1_pass() is True
    parsed = parse_structured_critic_action('{"verified": true}')
    recovered = recover_verified_schema_for_control_plane('{"verified": true}')
    assert recovered == "ACCEPT"
    l1 = score_three_layers(
        parse_valid=parsed.parse_valid,
        timeout=False,
        parsed_action=parsed.parsed_action,
        expected_action="ACCEPT",
        control_plane_success=True,
        safe_outcome=True,
        hidden_recovery=True,
    )
    assert l1.l1_model_semantic_capability == "FAIL"
    assert l1.l2_control_plane_execution == "PASS"
    assert l1.semantic_verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    timeout = score_three_layers(
        parse_valid=False,
        timeout=True,
        parsed_action=None,
        expected_action="ACCEPT",
        control_plane_success=None,
        safe_outcome=None,
        hidden_recovery=False,
    )
    unknown = score_three_layers(
        parse_valid=False,
        timeout=False,
        parsed_action=None,
        expected_action="ACCEPT",
        control_plane_success=None,
        safe_outcome=None,
        hidden_recovery=False,
    )
    assert timeout.l1_model_semantic_capability == "FAIL"
    assert timeout.first_failed_stage == "TIMEOUT"
    assert unknown.l1_model_semantic_capability == "FAIL"


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
    assert gate["ACTION_SPACE_EXPOSED"] == "5/5"
    assert gate["MODEL_INPUT_ORACLE_LEAKAGE"] == 0
    assert gate["QUERY_PRESENT"] == "11/11"
    assert gate["EVIDENCE_PRESENT"] == "11/11"
    assert gate["RETRIEVAL_SCOPE_STATE_PRESENT"] == "11/11"
    assert gate["C04_C05_C06_DECISION_CONTEXT_SUFFICIENT"] == "YES"
    assert gate["VERIFIED_FALLBACK_CANNOT_SCORE_L1_PASS"] == "YES"
    assert gate["LM_STUDIO_REQUESTS"] == 0
    assert gate["FORMAL_ARTIFACT_PRESENT"] is False
    assert gate["lm_studio_requests"] == 0
    assert gate["parser_contract"] == "PASS"
    assert gate["formal_artifact_present"] is False
    assert gate["retry"] == "NONE"
    assert gate["best_of_n"] is False
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

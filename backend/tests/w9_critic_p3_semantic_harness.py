"""W9 P3 semantic construct dry-run harness (mock only).

Builds model inputs, exercises mock/scoring gates, and emits dry-run plan
artifacts. Never opens LM Studio sockets. Never writes the formal P3 result.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter
from app.eval.local_model_profile.schema import ThinkingMode

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p3_semantic_construct import (
    DRY_RUN_ARTIFACT_PATH,
    EXPECTED_BASE_SHA,
    FORMAL_RESULT_ARTIFACT_NAME,
    FORMAL_RESULT_ARTIFACT_PATH,
    MODEL_CONFIG,
    NEW_SEMANTIC_DENOMINATOR,
    PROTOCOL_FIXTURE_PATH,
    PROTOCOL_VERSION,
    SCORING_POLICY,
    CaseLaneRecord,
    FormalP3ArtifactForbidden,
    LmStudioForbidden,
    MeasurementLayer,
    MeasurementState,
    ModelCapabilityResult,
    ObservationKind,
    assert_denominator_invariants,
    assert_no_oracle_leakage,
    assert_oracle_uniqueness_freezes,
    build_model_input,
    build_protocol_freeze_document,
    enumerate_semantic_lanes,
    formal_result_artifact_present,
    p2_r3_historical_artifact_diff,
    request_lm_studio,
    score_l1_observation,
    semantic_eligible_records,
    write_formal_p3_result,
)

ADAPTER_CLASS = OpenAICompatibleAdapter
PROVIDER_PATH = MODEL_CONFIG["provider_path"]
# Successful outbound LM Studio / HTTP completions only. Blocked dry-run
# attempts must not increment this counter.
LM_STUDIO_REQUEST_COUNTER = 0
LM_STUDIO_BLOCKED_ATTEMPTS = 0


@dataclass(frozen=True, slots=True)
class P3SemanticModelRequest:
    case_id: str
    messages: tuple[dict[str, str], ...]
    temperature: float
    max_tokens: int
    timeout_seconds: float
    thinking: str
    input_sha256: str
    wire_payload_body: dict[str, Any]

    def wire_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "messages": list(self.messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "thinking": self.thinking,
            "input_sha256": self.input_sha256,
            "body": self.wire_payload_body,
        }


SEMANTIC_STATUS_INSTRUCTIONS = """你是语义 Critic 的 L1 判定器。只对候选回答中的事实断言相对已给证据做语义判定。

任务：
1. 识别事实断言（忽略非断言性开场白/建议性前缀）。
2. 对每个事实断言判定与证据的关系：SUPPORTED / UNSUPPORTED / CONFLICTED / UNVERIFIABLE。
3. 只输出 JSON，不要思维链。

输出格式：
{"claims":[{"claim_id":"<可选>","status":"SUPPORTED|UNSUPPORTED|CONFLICTED|UNVERIFIABLE","evidence_refs":["E…"]}]}

禁止：输出五个 CriticAction（ACCEPT/REVISE/RETRIEVE/CLARIFY/REFUSE）作为主对象；禁止使用 oracle、期望标签或评分提示。
"""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_semantic_prompt(model_input: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    body = {
        "query": model_input["query"],
        "final_draft": model_input["final_draft"],
        "gated_evidence_snapshot": model_input["gated_evidence_snapshot"],
        "synchronized_citations": model_input["synchronized_citations"],
        "retrieval_scope_exhausted": model_input["retrieval_scope_exhausted"],
    }
    assert_no_oracle_leakage(body)
    user = json.dumps(body, ensure_ascii=False, sort_keys=True)
    return (
        {"role": "system", "content": SEMANTIC_STATUS_INSTRUCTIONS},
        {"role": "user", "content": user},
    )


def build_eligible_model_requests(
    records: Sequence[CaseLaneRecord] | None = None,
) -> tuple[P3SemanticModelRequest, ...]:
    suite = load_frozen_suite()
    lanes = semantic_eligible_records(records)
    case_by_id = {c["case_id"]: c for c in suite.cases}
    requests: list[P3SemanticModelRequest] = []
    for lane in lanes:
        case = case_by_id[lane.case_id]
        model_input = build_model_input(case)
        messages = build_semantic_prompt(model_input)
        wire_body = {
            "model": MODEL_CONFIG["primary_model"],
            "temperature": MODEL_CONFIG["temperature"],
            "max_tokens": MODEL_CONFIG["max_tokens"],
            "messages": list(messages),
        }
        assert_no_oracle_leakage(wire_body)
        canonical = json.dumps(wire_body, ensure_ascii=False, sort_keys=True)
        requests.append(
            P3SemanticModelRequest(
                case_id=lane.case_id,
                messages=messages,
                temperature=float(MODEL_CONFIG["temperature"]),
                max_tokens=int(MODEL_CONFIG["max_tokens"]),
                timeout_seconds=float(MODEL_CONFIG["timeout_seconds"]),
                thinking=str(MODEL_CONFIG["thinking"]),
                input_sha256=_sha256_text(canonical),
                wire_payload_body=wire_body,
            )
        )
    if len(requests) != NEW_SEMANTIC_DENOMINATOR:
        raise ValueError(
            f"eligible model inputs={len(requests)}, want {NEW_SEMANTIC_DENOMINATOR}"
        )
    return tuple(requests)


def oracle_leakage_count(requests: Sequence[P3SemanticModelRequest] | None = None) -> int:
    items = requests if requests is not None else build_eligible_model_requests()
    total = 0
    for item in items:
        from tests.w9_critic_p3_semantic_construct import leaked_oracle_keys

        total += len(leaked_oracle_keys(item.wire_payload()))
    return total


def make_profile_adapter(*, base_url: str = "http://127.0.0.1:9") -> OpenAICompatibleAdapter:
    """Construct the frozen adapter profile without sending traffic."""
    return OpenAICompatibleAdapter(
        base_url=base_url,
        model=str(MODEL_CONFIG["primary_model"]),
        timeout_seconds=float(MODEL_CONFIG["timeout_seconds"]),
        thinking_mode=ThinkingMode.off,
        provider="openai_compatible",
    )


class DryRunSemanticAdapter:
    """Wraps OpenAICompatibleAdapter but forbids HTTP / LM Studio."""

    def __init__(self, adapter: OpenAICompatibleAdapter | None = None) -> None:
        self.inner = adapter or make_profile_adapter()
        self.blocked_attempts = 0

    def complete(self, *_args: Any, **_kwargs: Any) -> None:
        global LM_STUDIO_BLOCKED_ATTEMPTS
        self.blocked_attempts += 1
        LM_STUDIO_BLOCKED_ATTEMPTS += 1
        # Never increments LM_STUDIO_REQUEST_COUNTER — no outbound call occurs.
        request_lm_studio()


def parse_claim_status_payload(raw_text: str) -> dict[str, str] | ObservationKind:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return ObservationKind.PARSE_FAILURE
    if not isinstance(payload, Mapping) or "claims" not in payload:
        return ObservationKind.PARSE_FAILURE
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return ObservationKind.PARSE_FAILURE
    observed: dict[str, str] = {}
    for item in claims:
        if not isinstance(item, Mapping):
            return ObservationKind.PARSE_FAILURE
        claim_id = item.get("claim_id")
        status = item.get("status")
        if not isinstance(claim_id, str) or not isinstance(status, str):
            return ObservationKind.PARSE_FAILURE
        if status not in {"SUPPORTED", "UNSUPPORTED", "CONFLICTED", "UNVERIFIABLE"}:
            return ObservationKind.PARSE_FAILURE
        observed[claim_id] = status
    return observed


def run_mock_lane_a_and_b() -> dict[str, Any]:
    """Deterministic mock proving both lanes share denominator 7."""
    records = enumerate_semantic_lanes()
    accounting = assert_denominator_invariants(records)
    assert_oracle_uniqueness_freezes(records)
    requests = build_eligible_model_requests(records)

    # Lane A: scripted exact oracle statuses → PASS for all eligible.
    lane_a_results: list[dict[str, Any]] = []
    for lane in semantic_eligible_records(records):
        observed = {c.claim_id: c.status for c in lane.semantic_claims}
        verdict = score_l1_observation(
            lane=lane,
            observation_kind=ObservationKind.STRUCTURED_JSON,
            observed_statuses=observed,
        )
        lane_a_results.append(
            {
                "case_id": lane.case_id,
                "in_l1_denominator": True,
                "verdict": verdict.value,
            }
        )

    # Lane B: same eligibility; inject timeout/parse/hidden-recovery probes.
    lane_b_results: list[dict[str, Any]] = []
    eligible = list(semantic_eligible_records(records))
    probes = {
        eligible[0].case_id: ("TIMEOUT", None, False),
        eligible[1].case_id: ("PARSE_FAILURE", None, False),
        eligible[2].case_id: (
            "STRUCTURED_JSON",
            {c.claim_id: "UNSUPPORTED" for c in eligible[2].semantic_claims},
            True,  # wrong + hidden recovery
        ),
    }
    for lane in eligible:
        kind, observed, hidden = probes.get(
            lane.case_id,
            (
                "STRUCTURED_JSON",
                {c.claim_id: c.status for c in lane.semantic_claims},
                False,
            ),
        )
        verdict = score_l1_observation(
            lane=lane,
            observation_kind=kind,
            observed_statuses=observed,
            hidden_recovery_success=hidden,
        )
        lane_b_results.append(
            {
                "case_id": lane.case_id,
                "in_l1_denominator": True,
                "observation_kind": kind,
                "hidden_recovery_success": hidden,
                "verdict": verdict.value,
            }
        )

    # Non-eligible lanes must be NOT_APPLICABLE and out of denominator.
    na_results = []
    for lane in records:
        if lane.in_l1_denominator:
            continue
        verdict = score_l1_observation(
            lane=lane,
            observation_kind=ObservationKind.STRUCTURED_JSON,
            observed_statuses={},
        )
        na_results.append(
            {
                "case_id": lane.case_id,
                "lane": lane.lane,
                "in_l1_denominator": False,
                "verdict": verdict.value,
            }
        )

    timeout_in_den = any(
        r["observation_kind"] == "TIMEOUT" and r["in_l1_denominator"]
        for r in lane_b_results
        if "observation_kind" in r
    )
    parse_in_den = any(
        r["observation_kind"] == "PARSE_FAILURE" and r["in_l1_denominator"]
        for r in lane_b_results
        if "observation_kind" in r
    )
    hidden_probe = next(r for r in lane_b_results if r.get("hidden_recovery_success"))
    hidden_ok = (
        hidden_probe["verdict"] == ModelCapabilityResult.MODEL_CAPABILITY_FAIL.value
    )

    adapter = DryRunSemanticAdapter()
    # Profile construction is allowed; complete() must raise without HTTP.
    complete_blocked = False
    try:
        adapter.complete(messages=[{"role": "user", "content": "ping"}])
    except LmStudioForbidden:
        complete_blocked = True

    formal_write_blocked = False
    try:
        write_formal_p3_result({"claims": []})
    except FormalP3ArtifactForbidden:
        formal_write_blocked = True

    gates = {
        "P2_R3_HISTORICAL_ARTIFACT_DIFF": p2_r3_historical_artifact_diff(),
        "MODEL_INPUT_ORACLE_LEAKAGE": oracle_leakage_count(requests),
        "DETERMINISTIC_CASES_IN_L1_DENOMINATOR": accounting[
            "DETERMINISTIC_CASES_IN_L1_DENOMINATOR"
        ],
        "PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR": accounting[
            "PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR"
        ],
        "SEMANTIC_DENOMINATOR_LANE_A": len(lane_a_results),
        "SEMANTIC_DENOMINATOR_LANE_B": len(lane_b_results),
        "SEMANTIC_DENOMINATOR_LANE_A_B_MATCH": (
            "YES"
            if len(lane_a_results)
            == len(lane_b_results)
            == NEW_SEMANTIC_DENOMINATOR
            else "NO"
        ),
        "SEMANTIC_TARGET_UNIQUENESS": "PASS",
        "TIMEOUT_REMAINS_IN_DENOMINATOR": "YES" if timeout_in_den else "NO",
        "PARSE_FAILURE_REMAINS_IN_DENOMINATOR": "YES" if parse_in_den else "NO",
        "HIDDEN_RECOVERY_CANNOT_UPGRADE_L1": "YES" if hidden_ok else "NO",
        "LM_STUDIO_REQUESTS": LM_STUDIO_REQUEST_COUNTER,
        "LM_STUDIO_COMPLETE_BLOCKED": complete_blocked,
        "FORMAL_RESULT_ARTIFACT_PRESENT": formal_result_artifact_present(),
        "FORMAL_RESULT_WRITE_BLOCKED": formal_write_blocked,
        "SCORING_POLICY": SCORING_POLICY,
        "ADAPTER_CLASS": ADAPTER_CLASS.__name__,
        "PROVIDER_PATH": PROVIDER_PATH,
        "THINKING": MODEL_CONFIG["thinking"],
        "layers": [layer.value for layer in MeasurementLayer],
    }

    return {
        "protocol": PROTOCOL_VERSION,
        "base_sha": EXPECTED_BASE_SHA,
        "measurement_state": MeasurementState.NOT_RUN.value,
        "real_model_capability_measured": False,
        "scoring_policy": SCORING_POLICY,
        "denominator": accounting,
        "eligible_requests": [r.wire_payload() for r in requests],
        "lane_a": lane_a_results,
        "lane_b": lane_b_results,
        "not_applicable": na_results,
        "gates": gates,
        "formal_artifact_name": FORMAL_RESULT_ARTIFACT_NAME,
        "formal_artifact_path_exists": FORMAL_RESULT_ARTIFACT_PATH.is_file(),
    }


def write_dry_run_plan(path=DRY_RUN_ARTIFACT_PATH) -> dict[str, Any]:
    if path.name == FORMAL_RESULT_ARTIFACT_NAME:
        raise FormalP3ArtifactForbidden("refusing to write formal P3 result artifact")
    if not path.name.startswith("dry-run"):
        raise ValueError(f"dry-run artifact must use dry-run prefix: {path.name}")
    payload = run_mock_lane_a_and_b()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def write_protocol_fixture(path=PROTOCOL_FIXTURE_PATH) -> dict[str, Any]:
    doc = build_protocol_freeze_document()
    path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return doc


def regression_gate_report() -> dict[str, Any]:
    payload = run_mock_lane_a_and_b()
    gates = payload["gates"]
    backend_app_diff = _backend_app_diff_vs_base()
    all_pass = (
        gates["P2_R3_HISTORICAL_ARTIFACT_DIFF"] == 0
        and backend_app_diff == 0
        and gates["MODEL_INPUT_ORACLE_LEAKAGE"] == 0
        and gates["DETERMINISTIC_CASES_IN_L1_DENOMINATOR"] == 0
        and gates["PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR"] == 0
        and gates["SEMANTIC_DENOMINATOR_LANE_A_B_MATCH"] == "YES"
        and gates["SEMANTIC_TARGET_UNIQUENESS"] == "PASS"
        and gates["TIMEOUT_REMAINS_IN_DENOMINATOR"] == "YES"
        and gates["PARSE_FAILURE_REMAINS_IN_DENOMINATOR"] == "YES"
        and gates["HIDDEN_RECOVERY_CANNOT_UPGRADE_L1"] == "YES"
        and gates["LM_STUDIO_REQUESTS"] == 0
        and gates["FORMAL_RESULT_ARTIFACT_PRESENT"] is False
        and gates["LM_STUDIO_COMPLETE_BLOCKED"] is True
        and gates["FORMAL_RESULT_WRITE_BLOCKED"] is True
    )
    return {
        **gates,
        "backend_app_diff_vs_post_61": backend_app_diff,
        "P3_CONSTRUCT_VALIDITY": "PASS" if all_pass else "FAIL",
        "P3_SEMANTIC_PROTOCOL_REFROZEN": "YES" if all_pass else "NO",
        "P3_EXECUTION_CONTRACT_READY": "YES" if all_pass else "NO",
        "P3_REAL_RUN_READY": "YES" if all_pass else "NO",
        "NEW_SEMANTIC_DENOMINATOR": NEW_SEMANTIC_DENOMINATOR,
        "SEMANTIC_CASES": payload["denominator"]["SEMANTIC_CASES"],
        "DETERMINISTIC_ONLY_CASES": payload["denominator"]["DETERMINISTIC_ONLY_CASES"],
        "PROTOCOL_INVALID_CASES": payload["denominator"]["PROTOCOL_INVALID_CASES"],
        "SCORING_POLICY": SCORING_POLICY,
    }


def _backend_app_diff_vs_base() -> int:
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--name-only", EXPECTED_BASE_SHA, "--", "backend/app"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [line for line in result.stdout.splitlines() if line.strip()]
    return len(names)

"""W9 P3 execution I/O contract (dry-run / mock only).

Freezes: production-visible model input → OpenAICompatibleAdapter request
→ raw observable → structured parser → three-layer score → formal schema.

Does not call LM Studio and does not write the reserved formal artifact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.eval.local_model_profile.adapter import (
    CompletionResult,
    OpenAICompatibleAdapter,
)
from app.eval.local_model_profile.schema import ThinkingMode
from app.eval.local_model_profile.scoring import score_strict_json
from app.services.rag.critic import CriticAction
from app.services.rag.generation import VERIFY_ANSWER_PROMPT
from app.services.rag.redact import scrub_llm_context

from tests.w9_critic_p2_r1_harness import CASES_PATH, CONTRACT_PATH, load_frozen_suite
from tests.w9_critic_p2_r3_batch_runner import C12_CASE_ID
from tests.w9_critic_p3_protocol import (
    EXPECTED_BASE_SHA,
    FORMAL_ARTIFACT_NAME,
    FORMAL_ARTIFACT_PATH,
    FROZEN_TOTAL,
    MODEL_CONFIG,
    PROTOCOL_VERSION,
    SEMANTIC_ELIGIBLE,
    FormalP3ArtifactForbidden,
    LmStudioForbidden,
    ObservationKind,
    SemanticVerdict,
    enumerate_p3_eligibility,
    score_semantic_trial,
)

ADAPTER_CLASS = OpenAICompatibleAdapter
PROMPT_BUILDER = "app.services.rag.generation.VERIFY_ANSWER_PROMPT"
PROVIDER_PATH = "app.eval.local_model_profile.adapter.OpenAICompatibleAdapter"
P2_R3_FORMAL_ARTIFACT = "w9-critic-p2-r3-full-product-rerun.json"

VISIBLE_CASE_KEYS = (
    "case_id",
    "query",
    "answer",
    "scope",
    "citations",
    "evidence",
    "deterministic_context",
)
ORACLE_ONLY_KEYS = frozenset(
    {
        "expected_action",
        "acceptable_action",
        "expected_status",
        "expected_reason_code",
        "oracle",
        "semantic_verdict",
        "semantic_correct",
        "scorer",
        "scorer_result",
        "hidden_recovery",
        "hidden_recovery_result",
        "in_capability_denominator",
    }
)
ALLOWED_ACTIONS = frozenset(item.value for item in CriticAction)
COT_KEYS = frozenset(
    {"chain_of_thought", "reasoning", "reasoning_content", "thinking_content"}
)

P3_FORMAL_CASE_FIELDS = frozenset(
    {
        "case_id",
        "input_hash",
        "semantic_eligible",
        "expected_action",
        "raw_observable_output",
        "parsed_action",
        "parse_valid",
        "semantic_correct",
        "semantic_verdict",
        "control_plane_terminal",
        "safe_outcome",
        "hidden_recovery",
        "latency_ms",
        "timeout",
        "retry_count",
        "first_failed_stage",
        "l1_model_semantic_capability",
        "l2_control_plane_execution",
        "l3_final_safety_outcome",
    }
)
P3_FORMAL_TOP_LEVEL_FIELDS = frozenset(
    {
        "protocol_version",
        "base_sha",
        "suite_hash",
        "oracle_hash",
        "model_config",
        "thinking",
        "run_id",
        "timestamp",
        "frozen_total",
        "semantic_eligible_expected",
        "semantic_executed",
        "passed",
        "failed",
        "timeouts",
        "parse_failures",
        "hidden_recovery_count",
        "measurement_state",
        "model_capability_result",
    }
)


class LayerName(str, Enum):
    L1_MODEL_SEMANTIC_CAPABILITY = "L1_MODEL_SEMANTIC_CAPABILITY"
    L2_CONTROL_PLANE_EXECUTION = "L2_CONTROL_PLANE_EXECUTION"
    L3_FINAL_SAFETY_OUTCOME = "L3_FINAL_SAFETY_OUTCOME"


class LayerVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EXECUTED = "NOT_EXECUTED"


def _canonical_hash(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _canonical_hash(payload)


def leaked_oracle_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        direct = ORACLE_ONLY_KEYS.intersection(value)
        return direct.union(*(leaked_oracle_keys(item) for item in value.values()))
    if isinstance(value, list | tuple):
        leaked: set[str] = set()
        for item in value:
            leaked.update(leaked_oracle_keys(item))
        return leaked
    return set()


def assert_no_oracle_leakage(payload: Mapping[str, Any] | Sequence[Any]) -> None:
    leaked = leaked_oracle_keys(payload)
    if leaked:
        raise ValueError(f"oracle leakage: {sorted(leaked)}")


def production_visible_case(case: Mapping[str, Any]) -> dict[str, Any]:
    return {key: case[key] for key in VISIBLE_CASE_KEYS if key in case}


def _chunks_text(case: Mapping[str, Any], *, max_chunks: int = 5) -> str:
    evidence = list(case.get("evidence") or [])[:max_chunks]
    return "\n---\n".join(
        f"[{index + 1}] {scrub_llm_context(str(item.get('excerpt') or ''))}"
        for index, item in enumerate(evidence)
    )


@dataclass(frozen=True, slots=True)
class P3ModelRequest:
    case_id: str
    messages: tuple[dict[str, str], ...]
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    thinking: str
    retry: str
    input_hash: str
    visible_input: dict[str, Any]

    def wire_payload(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [dict(item) for item in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "enable_thinking": False,
            "thinking": {"type": "disabled"},
        }


def build_p3_model_input(case: Mapping[str, Any]) -> P3ModelRequest:
    """Reuse inspect_answer's VERIFY_ANSWER_PROMPT; never attach oracle fields."""
    visible = production_visible_case(case)
    prompt = VERIFY_ANSWER_PROMPT.format(
        chunks=_chunks_text(case)[:4000],
        answer=str(case["answer"]),
    )
    messages = ({"role": "user", "content": prompt},)
    request = {
        "model": MODEL_CONFIG["primary_model"],
        "messages": list(messages),
        "temperature": MODEL_CONFIG["temperature"],
        "max_tokens": MODEL_CONFIG["max_tokens"],
        "thinking": MODEL_CONFIG["thinking"],
        "visible_input": visible,
    }
    assert_no_oracle_leakage(request)
    return P3ModelRequest(
        case_id=str(case["case_id"]),
        messages=messages,
        model=MODEL_CONFIG["primary_model"],
        temperature=float(MODEL_CONFIG["temperature"]),
        max_tokens=int(MODEL_CONFIG["max_tokens"]),
        timeout_seconds=int(MODEL_CONFIG["timeout_seconds"]),
        thinking=str(MODEL_CONFIG["thinking"]),
        retry=str(MODEL_CONFIG["retry"]),
        input_hash=_canonical_hash(request),
        visible_input=visible,
    )


def enumerate_eligible_model_inputs() -> tuple[P3ModelRequest, ...]:
    suite = load_frozen_suite()
    eligible = {
        item.case_id
        for item in enumerate_p3_eligibility()
        if item.in_product_capability_denominator
    }
    requests = tuple(
        build_p3_model_input(case)
        for case in suite.cases
        if str(case["case_id"]) in eligible
    )
    if len(requests) != SEMANTIC_ELIGIBLE:
        raise ValueError(
            f"eligible model inputs={len(requests)}, want {SEMANTIC_ELIGIBLE}"
        )
    return requests


def oracle_leakage_count(requests: Sequence[P3ModelRequest] | None = None) -> int:
    items = requests if requests is not None else enumerate_eligible_model_inputs()
    return sum(len(leaked_oracle_keys(item.wire_payload())) for item in items)


@dataclass(frozen=True, slots=True)
class P3ParseResult:
    parse_valid: bool
    parsed_action: str | None
    error: str | None
    observation_kind: str


def parse_structured_critic_action(raw: str | None) -> P3ParseResult:
    """Strict JSON. Repair/fences are not success. No retry / best-of-N."""
    scored = score_strict_json(raw or "")
    if not scored.schema_success or scored.parsed is None:
        return P3ParseResult(
            False, None, "invalid_json", ObservationKind.PARSE_FAILURE.value
        )
    payload = scored.parsed
    if "action" in payload:
        action = payload.get("action")
        if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
            return P3ParseResult(
                False, None, "unknown_action", ObservationKind.PARSE_FAILURE.value
            )
        return P3ParseResult(True, action, None, ObservationKind.STRUCTURED_JSON.value)
    if "verified" in payload:
        verified = payload.get("verified")
        if verified is True:
            return P3ParseResult(
                True,
                CriticAction.ACCEPT.value,
                None,
                ObservationKind.STRUCTURED_JSON.value,
            )
        if verified is False:
            return P3ParseResult(
                True,
                CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value,
                None,
                ObservationKind.STRUCTURED_JSON.value,
            )
        return P3ParseResult(
            False, None, "unknown_action", ObservationKind.PARSE_FAILURE.value
        )
    return P3ParseResult(
        False, None, "missing_action", ObservationKind.PARSE_FAILURE.value
    )


@dataclass(frozen=True, slots=True)
class P3Observation:
    kind: ObservationKind
    raw_observable_output: str
    parsed_action: str | None
    parse_valid: bool
    latency_ms: float
    timeout: bool
    retry_count: int
    parse_error: str | None = None


def observation_from_completion(result: CompletionResult) -> P3Observation:
    if result.timed_out:
        return P3Observation(
            kind=ObservationKind.TIMEOUT,
            raw_observable_output=result.content or "",
            parsed_action=None,
            parse_valid=False,
            latency_ms=float(result.latency_ms),
            timeout=True,
            retry_count=0,
            parse_error="timeout",
        )
    parsed = parse_structured_critic_action(result.content)
    return P3Observation(
        kind=ObservationKind(parsed.observation_kind),
        raw_observable_output=result.content or "",
        parsed_action=parsed.parsed_action,
        parse_valid=parsed.parse_valid,
        latency_ms=float(result.latency_ms),
        timeout=False,
        retry_count=0,
        parse_error=parsed.error,
    )


def build_p3_adapter(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(
        base_url=base_url,
        model=str(MODEL_CONFIG["primary_model"]),
        timeout_seconds=float(MODEL_CONFIG["timeout_seconds"]),
        thinking_mode=ThinkingMode.off,
        provider="lmstudio_openai_compatible",
    )


class P3ExecutionGateway:
    """Dry-run wrapper around OpenAICompatibleAdapter. HTTP is forbidden here."""

    def __init__(
        self,
        *,
        adapter: OpenAICompatibleAdapter | None = None,
        dry_run: bool = True,
    ) -> None:
        self.adapter = adapter
        self.dry_run = dry_run
        self.lm_studio_requests = 0

    def request(self, messages: Sequence[Mapping[str, Any]]) -> CompletionResult:
        if self.dry_run or self.adapter is None:
            raise LmStudioForbidden(
                "LM Studio requests are forbidden in the P3 execution-contract window"
            )
        self.lm_studio_requests += 1
        return self.adapter.chat_completion(
            [dict(item) for item in messages],
            temperature=float(MODEL_CONFIG["temperature"]),
            max_tokens=int(MODEL_CONFIG["max_tokens"]),
        )


@dataclass(frozen=True, slots=True)
class ThreeLayerScore:
    l1_model_semantic_capability: str
    l2_control_plane_execution: str
    l3_final_safety_outcome: str
    hidden_recovery: bool
    semantic_correct: bool
    semantic_verdict: str
    first_failed_stage: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_three_layers(
    *,
    parse_valid: bool,
    timeout: bool,
    parsed_action: str | None,
    expected_action: str,
    control_plane_success: bool | None,
    safe_outcome: bool | None,
    hidden_recovery: bool,
) -> ThreeLayerScore:
    """L1 is model capability only. Recovery never upgrades L1 FAIL to PASS."""
    model_correct = parse_valid and not timeout and parsed_action == expected_action
    if timeout:
        first_failed = "TIMEOUT"
    elif not parse_valid:
        first_failed = "PARSE_FAILURE"
    elif parsed_action != expected_action:
        first_failed = "ACTION_MISMATCH"
    else:
        first_failed = None
    if hidden_recovery or not model_correct:
        l1 = LayerVerdict.FAIL.value
        semantic_correct = False
        verdict = SemanticVerdict.MODEL_CAPABILITY_FAIL.value
        if hidden_recovery and first_failed is None:
            first_failed = "HIDDEN_RECOVERY"
    else:
        l1 = LayerVerdict.PASS.value
        semantic_correct = True
        verdict = SemanticVerdict.MODEL_CAPABILITY_PASS.value
    l2 = (
        LayerVerdict.NOT_EXECUTED.value
        if control_plane_success is None
        else (
            LayerVerdict.PASS.value
            if control_plane_success
            else LayerVerdict.FAIL.value
        )
    )
    l3 = (
        LayerVerdict.NOT_EXECUTED.value
        if safe_outcome is None
        else (LayerVerdict.PASS.value if safe_outcome else LayerVerdict.FAIL.value)
    )
    return ThreeLayerScore(
        l1_model_semantic_capability=l1,
        l2_control_plane_execution=l2,
        l3_final_safety_outcome=l3,
        hidden_recovery=hidden_recovery,
        semantic_correct=semantic_correct,
        semantic_verdict=verdict,
        first_failed_stage=first_failed,
    )


def parser_contract_self_check() -> bool:
    valid = parse_structured_critic_action('{"action":"ACCEPT"}')
    invalid = parse_structured_critic_action("{not-json")
    unknown = parse_structured_critic_action('{"action":"DANCE"}')
    missing = parse_structured_critic_action('{"issues":[]}')
    timeout = observation_from_completion(
        CompletionResult(
            content="", timed_out=True, error="timeout", latency_ms=60_000.0
        )
    )
    return (
        valid.parse_valid is True
        and valid.parsed_action == CriticAction.ACCEPT.value
        and invalid.error == "invalid_json"
        and unknown.error == "unknown_action"
        and missing.error == "missing_action"
        and timeout.kind is ObservationKind.TIMEOUT
        and timeout.retry_count == 0
    )


def validate_p3_formal_case(record: Mapping[str, Any]) -> None:
    missing = P3_FORMAL_CASE_FIELDS - set(record)
    if missing:
        raise ValueError(f"formal case missing fields: {sorted(missing)}")
    cot = COT_KEYS.intersection(record)
    if cot:
        raise ValueError(f"chain-of-thought fields are forbidden: {sorted(cot)}")
    if int(record["retry_count"]) != 0:
        raise ValueError("retry_count must be 0")


def validate_p3_formal_artifact(payload: Mapping[str, Any]) -> None:
    missing = P3_FORMAL_TOP_LEVEL_FIELDS - set(payload)
    if missing:
        raise ValueError(f"formal artifact missing fields: {sorted(missing)}")
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("protocol_version mismatch")
    if payload.get("thinking") != "OFF":
        raise ValueError("thinking must be OFF")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")
    for record in cases:
        if not isinstance(record, dict):
            raise ValueError("case record must be an object")
        validate_p3_formal_case(record)


def evaluate_p3_formal_completeness(payload: Mapping[str, Any]) -> bool:
    return int(payload.get("semantic_executed") or 0) == SEMANTIC_ELIGIBLE


def refuse_formal_artifact_write() -> None:
    raise FormalP3ArtifactForbidden(
        f"refusing to create {FORMAL_ARTIFACT_NAME} in the execution-contract window"
    )


def _denominator_preservation_pass() -> bool:
    eligibility = next(
        item for item in enumerate_p3_eligibility() if item.case_id != C12_CASE_ID
    )
    timeout = score_semantic_trial(
        eligibility, expected_action="ACCEPT", observation_kind=ObservationKind.TIMEOUT
    )
    parse_fail = score_semantic_trial(
        eligibility,
        expected_action="ACCEPT",
        observation_kind=ObservationKind.PARSE_FAILURE,
    )
    return (
        timeout.in_semantic_denominator is True
        and timeout.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
        and parse_fail.in_semantic_denominator is True
        and parse_fail.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    )


def evaluate_execution_contract_gate() -> dict[str, Any]:
    requests = enumerate_eligible_model_inputs()
    leakage = oracle_leakage_count(requests)
    parser_pass = parser_contract_self_check()
    denom_pass = _denominator_preservation_pass()
    formal_exists = FORMAL_ARTIFACT_PATH.exists()
    oracle = load_frozen_suite().oracle
    schema_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "base_sha": EXPECTED_BASE_SHA,
        "suite_hash": file_sha256(CASES_PATH),
        "oracle_hash": file_sha256(CONTRACT_PATH),
        "model_config": dict(MODEL_CONFIG),
        "thinking": "OFF",
        "run_id": "dry-run",
        "timestamp": "not-executed",
        "frozen_total": FROZEN_TOTAL,
        "semantic_eligible_expected": SEMANTIC_ELIGIBLE,
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
                "case_id": item.case_id,
                "input_hash": item.input_hash,
                "semantic_eligible": True,
                "expected_action": str(oracle[item.case_id]["expected_action"]),
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
                "l1_model_semantic_capability": LayerVerdict.NOT_EXECUTED.value,
                "l2_control_plane_execution": LayerVerdict.NOT_EXECUTED.value,
                "l3_final_safety_outcome": LayerVerdict.NOT_EXECUTED.value,
            }
            for item in requests
        ],
    }
    validate_p3_formal_artifact(schema_payload)
    ready = (
        len(requests) == SEMANTIC_ELIGIBLE
        and leakage == 0
        and parser_pass
        and denom_pass
        and not formal_exists
        and not evaluate_p3_formal_completeness(schema_payload)
    )
    return {
        "P3_SEMANTIC_PROTOCOL_FROZEN": "YES",
        "P3_EXECUTION_CONTRACT_READY": "YES" if ready else "NO",
        "P3_REAL_RUN_READY": "YES" if ready else "NO",
        "MODEL_INPUT_ORACLE_LEAKAGE": leakage,
        "lm_studio_requests": 0,
        "eligible_model_inputs": len(requests),
        "parser_contract": "PASS" if parser_pass else "FAIL",
        "timeout_denominator_preservation": "PASS" if denom_pass else "FAIL",
        "parse_failure_denominator_preservation": "PASS" if denom_pass else "FAIL",
        "artifact_schema_validation": "PASS",
        "formal_artifact_present": formal_exists,
        "formal_completeness": False,
        "prompt_builder": PROMPT_BUILDER,
        "provider": PROVIDER_PATH,
        "layers": [item.value for item in LayerName],
        "input_hashes": {item.case_id: item.input_hash for item in requests},
        "suite_hash": schema_payload["suite_hash"],
        "oracle_hash": schema_payload["oracle_hash"],
        "blocker": None if ready else "P3_EXECUTION_IO_CONTRACT_NOT_FROZEN",
    }

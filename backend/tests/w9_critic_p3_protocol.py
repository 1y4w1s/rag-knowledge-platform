"""W9 P3 frozen local semantic critic measurement protocol.

Isolated from P2-R3 historical product-path rerun. P3 freezes the GLM-4.6V-Flash
Thinking-OFF contract and scoring rules against the same 11+1 suite split.
This module does not call LM Studio and must not write the formal result file.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from tests.w9_critic_p2_r1_harness import FIXTURES, load_frozen_suite
from tests.w9_critic_p2_r2_protocol import MeasurementClassification
from tests.w9_critic_p2_r3_batch_runner import (
    C12_CASE_ID,
    FROZEN_CASE_COUNT,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    CaseEligibility,
    ProbeClassification,
    classify_case_eligibility,
    verify_eligibility_split,
)

PROTOCOL_VERSION = "w9_critic_p3_r1_real_local_semantic_v1"
POST_61_MASTER_SHA = "ef79178e8dbfe9a9dec0526ef8b003732a819020"
EXPECTED_BASE_SHA = POST_61_MASTER_SHA
P2_R3_HISTORICAL_BASE_SHA = "550bd8b0ec00f44961a5ec7de4ac36560135edee"

FROZEN_TOTAL = FROZEN_CASE_COUNT
SEMANTIC_ELIGIBLE = PRODUCT_PATH_ELIGIBLE_EXPECTED
SEMANTIC_INELIGIBLE = 1
ACCEPTABLE_ACTION_POLICY = "EXACT"

DRY_RUN_ARTIFACT_NAME = "dry-run-w9-critic-p3-r1-semantic-plan.json"
DRY_RUN_ARTIFACT_PATH = FIXTURES / DRY_RUN_ARTIFACT_NAME
FORMAL_ARTIFACT_NAME = "w9-critic-p3-r1-real-local-semantic.json"
FORMAL_ARTIFACT_PATH = FIXTURES / FORMAL_ARTIFACT_NAME

MODEL_CONFIG: dict[str, Any] = {
    "primary_model": "zai-org/glm-4.6v-flash",
    "thinking": "OFF",
    "temperature": 0.0,
    "max_tokens": 512,
    "timeout_seconds": 60,
    "retry": "NONE",
    "output": "structured_json_only",
}


class ObservationKind(str, Enum):
    STRUCTURED_JSON = "STRUCTURED_JSON"
    TIMEOUT = "TIMEOUT"
    PARSE_FAILURE = "PARSE_FAILURE"


class SemanticVerdict(str, Enum):
    MODEL_CAPABILITY_PASS = "MODEL_CAPABILITY_PASS"
    MODEL_CAPABILITY_FAIL = "MODEL_CAPABILITY_FAIL"
    MEASUREMENT_PROTOCOL_INVALID = "MEASUREMENT_PROTOCOL_INVALID"


class LmStudioForbidden(RuntimeError):
    """Raised if any freeze-window code path tries to talk to LM Studio."""


class FormalP3ArtifactForbidden(RuntimeError):
    """Formal P3 result files are schema-reserved until P3-R1 execution."""


@dataclass(frozen=True, slots=True)
class SemanticCaseRecord:
    case_id: str
    semantic_eligible: bool
    in_semantic_denominator: bool
    classification: str | None
    probe_classification: str
    observation_kind: str | None
    expected_action: str | None
    observed_action: str | None
    action_policy: str
    verdict: str
    timeout: bool
    parse_failure: bool
    hidden_recovery: bool
    recovered_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SemanticAggregate:
    frozen_total: int
    semantic_eligible: int
    semantic_ineligible: int
    semantic_denominator: int
    protocol_invalid: int
    passed: int
    failed: int
    timeout_count: int
    parse_failure_count: int
    hidden_recovery_count: int
    batch_complete: bool
    lane: str = "B"


def request_lm_studio(*_args: Any, **_kwargs: Any) -> None:
    raise LmStudioForbidden(
        "LM Studio requests are forbidden in the P3 protocol-freeze window"
    )


def classify_p3_eligibility(case: Mapping[str, object]) -> CaseEligibility:
    """Reuse the frozen 11+1 split; do not invent a new denominator."""
    return classify_case_eligibility(case)


def enumerate_p3_eligibility() -> tuple[CaseEligibility, ...]:
    suite = load_frozen_suite()
    return tuple(classify_p3_eligibility(case) for case in suite.cases)


def verify_p3_denominator(eligibility: Sequence[CaseEligibility]) -> dict[str, int]:
    split = verify_eligibility_split(eligibility)
    assert split["frozen_cases"] == FROZEN_TOTAL
    assert split["product_path_eligible"] == SEMANTIC_ELIGIBLE
    assert split["protocol_invalid"] == SEMANTIC_INELIGIBLE
    return {
        "frozen_total": split["frozen_cases"],
        "semantic_eligible": split["product_path_eligible"],
        "semantic_ineligible": split["protocol_invalid"],
        "semantic_denominator": split["product_path_eligible"],
    }


def score_semantic_trial(
    eligibility: CaseEligibility,
    *,
    expected_action: str,
    observation_kind: ObservationKind | None = None,
    observed_action: str | None = None,
    hidden_recovery: bool = False,
    recovered_action: str | None = None,
) -> SemanticCaseRecord:
    """Score one P3 trial. Timeout/parse stay in the denominator as FAIL.

    Hidden recovery is recorded separately and never upgrades FAIL to PASS.
    """
    c12 = eligibility.case_id == C12_CASE_ID
    protocol_invalid = (
        c12
        or eligibility.classification
        == MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
        or not eligibility.in_product_capability_denominator
    )
    if protocol_invalid:
        return SemanticCaseRecord(
            case_id=eligibility.case_id,
            semantic_eligible=False,
            in_semantic_denominator=False,
            classification=MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
            probe_classification=ProbeClassification.DEFENSE_IN_DEPTH_PROBE.value,
            observation_kind=None,
            expected_action=expected_action,
            observed_action=None,
            action_policy=ACCEPTABLE_ACTION_POLICY,
            verdict=SemanticVerdict.MEASUREMENT_PROTOCOL_INVALID.value,
            timeout=False,
            parse_failure=False,
            hidden_recovery=False,
        )

    kind = observation_kind or ObservationKind.STRUCTURED_JSON
    timeout = kind is ObservationKind.TIMEOUT
    parse_failure = kind is ObservationKind.PARSE_FAILURE
    if timeout or parse_failure:
        raw = SemanticVerdict.MODEL_CAPABILITY_FAIL
        observed = None
    elif observed_action == expected_action:
        raw = SemanticVerdict.MODEL_CAPABILITY_PASS
        observed = observed_action
    else:
        raw = SemanticVerdict.MODEL_CAPABILITY_FAIL
        observed = observed_action

    # A later recovered action must never convert a model failure into success.
    if (
        hidden_recovery
        and recovered_action == expected_action
        and raw is SemanticVerdict.MODEL_CAPABILITY_FAIL
    ):
        verdict = SemanticVerdict.MODEL_CAPABILITY_FAIL
    else:
        verdict = raw

    return SemanticCaseRecord(
        case_id=eligibility.case_id,
        semantic_eligible=True,
        in_semantic_denominator=True,
        classification=None,
        probe_classification=ProbeClassification.NOT_APPLICABLE.value,
        observation_kind=kind.value,
        expected_action=expected_action,
        observed_action=observed,
        action_policy=ACCEPTABLE_ACTION_POLICY,
        verdict=verdict.value,
        timeout=timeout,
        parse_failure=parse_failure,
        hidden_recovery=hidden_recovery,
        recovered_action=recovered_action,
    )


def aggregate_semantic_results(
    records: Sequence[SemanticCaseRecord], *, lane: str = "B"
) -> SemanticAggregate:
    denominator = [item for item in records if item.in_semantic_denominator]
    protocol_invalid = [
        item
        for item in records
        if item.verdict == SemanticVerdict.MEASUREMENT_PROTOCOL_INVALID.value
    ]
    passed = sum(
        1
        for item in denominator
        if item.verdict == SemanticVerdict.MODEL_CAPABILITY_PASS.value
    )
    failed = sum(
        1
        for item in denominator
        if item.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    )
    return SemanticAggregate(
        frozen_total=FROZEN_TOTAL,
        semantic_eligible=SEMANTIC_ELIGIBLE,
        semantic_ineligible=SEMANTIC_INELIGIBLE,
        semantic_denominator=SEMANTIC_ELIGIBLE,
        protocol_invalid=len(protocol_invalid),
        passed=passed,
        failed=failed,
        timeout_count=sum(1 for item in denominator if item.timeout),
        parse_failure_count=sum(1 for item in denominator if item.parse_failure),
        hidden_recovery_count=sum(1 for item in records if item.hidden_recovery),
        batch_complete=len(records) == FROZEN_TOTAL
        and len(denominator) == SEMANTIC_ELIGIBLE,
        lane=lane,
    )


def _assert_p3_dry_run_path(path: Path) -> None:
    name = path.name
    if "p2-r3" in name.lower():
        raise ValueError(f"P3 artifacts must not use P2-R3 names: {name!r}")
    if name != DRY_RUN_ARTIFACT_NAME and not name.startswith("dry-run-w9-critic-p3"):
        raise ValueError(f"P3 dry-run artifact must be P3-named, got {name!r}")
    if name == FORMAL_ARTIFACT_NAME:
        raise FormalP3ArtifactForbidden(
            f"refusing to write reserved formal P3 artifact {name!r}"
        )


@dataclass
class P3ProtocolRunner:
    dry_run: bool = True
    execution_enabled: bool = False

    def plan_batch(self) -> dict[str, Any]:
        if self.execution_enabled:
            request_lm_studio()
        suite = load_frozen_suite()
        eligibility = enumerate_p3_eligibility()
        split = verify_p3_denominator(eligibility)
        records = [
            score_semantic_trial(
                item,
                expected_action=str(suite.oracle[item.case_id]["expected_action"]),
            )
            if item.case_id == C12_CASE_ID
            else SemanticCaseRecord(
                case_id=item.case_id,
                semantic_eligible=True,
                in_semantic_denominator=True,
                classification=None,
                probe_classification=ProbeClassification.NOT_APPLICABLE.value,
                observation_kind=None,
                expected_action=str(suite.oracle[item.case_id]["expected_action"]),
                observed_action=None,
                action_policy=ACCEPTABLE_ACTION_POLICY,
                verdict="NOT_EXECUTED",
                timeout=False,
                parse_failure=False,
                hidden_recovery=False,
            )
            for item in eligibility
        ]
        c12 = next(item for item in records if item.case_id == C12_CASE_ID)
        return {
            "protocol": PROTOCOL_VERSION,
            "base_sha": EXPECTED_BASE_SHA,
            "post_61_master_sha": POST_61_MASTER_SHA,
            "p2_r3_historical_base_sha": P2_R3_HISTORICAL_BASE_SHA,
            "dry_run": True,
            "formal_measurement": False,
            "real_model_capability_measured": False,
            "lm_studio_requests": 0,
            "runtime_rollout": False,
            "product_remediation_applied": False,
            "model_config": dict(MODEL_CONFIG),
            "acceptable_action_policy": ACCEPTABLE_ACTION_POLICY,
            "denominator": split,
            "lane_a_denominator": split["semantic_denominator"],
            "c12": {
                "case_id": c12.case_id,
                "classification": c12.classification,
                "probe_classification": c12.probe_classification,
                "in_semantic_denominator": False,
            },
            "timeout_policy": "MODEL_CAPABILITY_FAIL_REMAINS_IN_DENOMINATOR",
            "parse_failure_policy": "MODEL_CAPABILITY_FAIL_REMAINS_IN_DENOMINATOR",
            "hidden_recovery_policy": "SEPARATELY_SCORED_NEVER_CONVERTS_FAIL_TO_PASS",
            "formal_artifact_name": FORMAL_ARTIFACT_NAME,
            "formal_artifact_present": FORMAL_ARTIFACT_PATH.exists(),
            "eligibility": [asdict(item) for item in eligibility],
            "case_records": [item.to_dict() for item in records],
            "execution_contract": _execution_contract_section(),
        }

    def write_dry_run_artifact(
        self, payload: Mapping[str, Any], path: Path | None = None
    ) -> Path:
        target = path or DRY_RUN_ARTIFACT_PATH
        _assert_p3_dry_run_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    def write_formal_artifact(self, *_args: Any, **_kwargs: Any) -> None:
        raise FormalP3ArtifactForbidden(
            f"refusing to create {FORMAL_ARTIFACT_NAME} in the protocol-freeze window"
        )


def _execution_contract_section() -> dict[str, Any]:
    from tests.w9_critic_p3_execution import evaluate_execution_contract_gate

    return evaluate_execution_contract_gate()


def build_and_write_dry_run_plan(path: Path | None = None) -> Path:
    runner = P3ProtocolRunner(dry_run=True, execution_enabled=False)
    return runner.write_dry_run_artifact(runner.plan_batch(), path)

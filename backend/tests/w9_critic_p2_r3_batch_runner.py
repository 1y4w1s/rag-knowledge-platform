"""W9 P2-R3 batch runner infrastructure (dry-run / schema prep only).

Lane C skeleton: load frozen suite, classify eligibility, write per-case artifacts,
aggregate denominator accounting, and enforce completeness gates.

Formal product-path measurement is intentionally NOT executed here.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.w9_critic_p2_r1_harness import FIXTURES, load_frozen_suite
from tests.w9_critic_p2_r2_protocol import (
    HarnessMode,
    MeasurementClassification,
    assess_case_product_path_eligibility,
)

PROTOCOL_VERSION = "w9_critic_p2_r3_batch_runner_v1"
C12_CASE_ID = "C12-out-of-scope-provenance"
FROZEN_CASE_COUNT = 12
PRODUCT_PATH_ELIGIBLE_EXPECTED = 11

FORBIDDEN_ARTIFACT_NAME = re.compile(
    r"w9-critic-p2-r3-final\.json$", re.IGNORECASE
)
ALLOWED_ARTIFACT_PREFIXES = (
    "dry-run",
    "schema-test",
    "fixture-only",
)

CASE_ARTIFACT_FIELDS: frozenset[str] = frozenset(
    {
        "case_id",
        "protocol_version",
        "executed",
        "product_path_eligible",
        "measurement_valid",
        "classification",
        "critic_action_expected",
        "critic_action_observed",
        "orchestration_status",
        "retrieval_count",
        "revision_count",
        "terminal_family",
        "final_citation_scope_valid",
        "final_evidence_scope_valid",
        "foreign_kb_reference_count",
        "unsupported_final_citation_count",
        "post_recovery_scope_violation",
        "safe_outcome",
        "first_failed_stage",
        "pass",
        "hidden_recovery",
    }
)


class ProbeClassification(str, Enum):
    DEFENSE_IN_DEPTH_PROBE = "DEFENSE_IN_DEPTH_PROBE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class CaseEligibility:
    case_id: str
    product_path_eligible: bool
    measurement_valid: bool
    classification: str | None
    probe_classification: ProbeClassification
    in_product_capability_denominator: bool
    harness_mode: HarnessMode


@dataclass(frozen=True, slots=True)
class CaseArtifactRecord:
    case_id: str
    protocol_version: str
    executed: bool
    product_path_eligible: bool
    measurement_valid: bool
    classification: str | None
    critic_action_expected: str | None
    critic_action_observed: str | None
    orchestration_status: str | None
    retrieval_count: int | None
    revision_count: int | None
    terminal_family: str | None
    final_citation_scope_valid: bool | None
    final_evidence_scope_valid: bool | None
    foreign_kb_reference_count: int | None
    unsupported_final_citation_count: int | None
    post_recovery_scope_violation: bool | None
    safe_outcome: bool | None
    first_failed_stage: str | None
    pass_: bool
    hidden_recovery: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("pass_")
        return payload


@dataclass(frozen=True, slots=True)
class BatchAggregate:
    frozen_cases: int
    executed_total: int
    eligible_expected: int
    eligible_executed: int
    protocol_invalid: int
    valid: int
    passed: int
    failed: int
    unsafe_accepts: int
    hidden_recovery_count: int
    batch_complete: bool
    full_denominator_pass: bool


@dataclass(frozen=True, slots=True)
class CompletenessGateResult:
    eligible_expected_ok: bool
    eligible_executed_ok: bool
    full_denominator_pass_ok: bool
    valid: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _assert_allowed_artifact_path(path: Path) -> None:
    name = path.name
    if FORBIDDEN_ARTIFACT_NAME.search(name):
        raise ValueError(
            f"forbidden formal artifact name {name!r}; "
            "use dry-run/schema-test/fixture-only prefixes"
        )
    if not any(name.startswith(prefix) for prefix in ALLOWED_ARTIFACT_PREFIXES):
        raise ValueError(
            f"artifact {name!r} must start with one of {ALLOWED_ARTIFACT_PREFIXES}"
        )


def classify_case_eligibility(
    case: Mapping[str, object],
    *,
    oracle: Mapping[str, object] | None = None,
) -> CaseEligibility:
    case_id = str(case["case_id"])
    if case_id == C12_CASE_ID:
        return CaseEligibility(
            case_id=case_id,
            product_path_eligible=False,
            measurement_valid=False,
            classification=MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
            probe_classification=ProbeClassification.DEFENSE_IN_DEPTH_PROBE,
            in_product_capability_denominator=False,
            harness_mode=HarnessMode.DEFENSE_IN_DEPTH_PROBE,
        )

    flags = assess_case_product_path_eligibility(
        dict(case), mode=HarnessMode.PRODUCTION_PATH
    )
    del oracle  # reserved for future scorer wiring; dry-run does not consume oracle
    return CaseEligibility(
        case_id=case_id,
        product_path_eligible=flags.product_path_eligible,
        measurement_valid=flags.product_path_eligible,
        classification=None,
        probe_classification=ProbeClassification.NOT_APPLICABLE,
        in_product_capability_denominator=True,
        harness_mode=HarnessMode.PRODUCTION_PATH,
    )


def enumerate_frozen_eligibility() -> tuple[CaseEligibility, ...]:
    suite = load_frozen_suite()
    assert len(suite.cases) == FROZEN_CASE_COUNT
    return tuple(
        classify_case_eligibility(case, oracle=suite.oracle[str(case["case_id"])])
        for case in suite.cases
    )


def verify_eligibility_split(eligibility: Sequence[CaseEligibility]) -> dict[str, int]:
    """Return counts and assert the frozen 11+1 split."""
    assert len(eligibility) == FROZEN_CASE_COUNT
    eligible = [item for item in eligibility if item.product_path_eligible]
    protocol_invalid = [
        item
        for item in eligibility
        if item.classification
        == MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
    ]
    c12 = next(item for item in eligibility if item.case_id == C12_CASE_ID)
    assert c12.probe_classification is ProbeClassification.DEFENSE_IN_DEPTH_PROBE
    assert c12.in_product_capability_denominator is False
    assert len(eligible) == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert len(protocol_invalid) == 1
    assert protocol_invalid[0].case_id == C12_CASE_ID
    return {
        "frozen_cases": len(eligibility),
        "product_path_eligible": len(eligible),
        "protocol_invalid": len(protocol_invalid),
    }


def build_synthetic_case_record(
    eligibility: CaseEligibility,
    *,
    oracle: Mapping[str, object] | None = None,
    executed: bool = False,
) -> CaseArtifactRecord:
    """In-memory placeholder record for schema / aggregator dry-run exercises."""
    expected_action = None if oracle is None else str(oracle.get("expected_action"))
    return CaseArtifactRecord(
        case_id=eligibility.case_id,
        protocol_version=PROTOCOL_VERSION,
        executed=executed,
        product_path_eligible=eligibility.product_path_eligible,
        measurement_valid=eligibility.measurement_valid,
        classification=eligibility.classification,
        critic_action_expected=expected_action,
        critic_action_observed=None,
        orchestration_status="DRY_RUN_NOT_EXECUTED" if not executed else "EXECUTED",
        retrieval_count=0 if executed else None,
        revision_count=0 if executed else None,
        terminal_family="NONE" if not executed else "ANSWER",
        final_citation_scope_valid=True if eligibility.product_path_eligible else None,
        final_evidence_scope_valid=True if eligibility.product_path_eligible else None,
        foreign_kb_reference_count=0,
        unsupported_final_citation_count=0,
        post_recovery_scope_violation=False,
        safe_outcome=True if eligibility.product_path_eligible else None,
        first_failed_stage=None,
        pass_=False if not executed else eligibility.product_path_eligible,
        hidden_recovery=False,
    )


def validate_case_record_schema(record: Mapping[str, Any]) -> None:
    missing = CASE_ARTIFACT_FIELDS - set(record)
    if missing:
        raise ValueError(f"case artifact missing fields: {sorted(missing)}")


def aggregate_batch_results(records: Sequence[CaseArtifactRecord]) -> BatchAggregate:
    frozen_cases = FROZEN_CASE_COUNT
    executed_total = sum(1 for item in records if item.executed)
    eligible_records = [item for item in records if item.product_path_eligible]
    eligible_expected = PRODUCT_PATH_ELIGIBLE_EXPECTED
    eligible_executed = sum(
        1 for item in eligible_records if item.executed
    )
    protocol_invalid = sum(
        1
        for item in records
        if item.classification
        == MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
    )
    valid = sum(1 for item in records if item.measurement_valid)
    passed = sum(
        1
        for item in records
        if item.product_path_eligible and item.executed and item.pass_
    )
    failed = sum(
        1
        for item in records
        if item.product_path_eligible and item.executed and not item.pass_
    )
    unsafe_accepts = sum(
        1
        for item in records
        if item.classification == MeasurementClassification.UNSAFE_ACCEPT.value
    )
    hidden_recovery_count = sum(1 for item in records if item.hidden_recovery)

    batch_complete = eligible_executed == eligible_expected
    full_denominator_pass = (
        batch_complete
        and passed == eligible_expected
        and failed == 0
        and unsafe_accepts == 0
    )
    if eligible_executed != eligible_expected:
        full_denominator_pass = False

    return BatchAggregate(
        frozen_cases=frozen_cases,
        executed_total=executed_total,
        eligible_expected=eligible_expected,
        eligible_executed=eligible_executed,
        protocol_invalid=protocol_invalid,
        valid=valid,
        passed=passed,
        failed=failed,
        unsafe_accepts=unsafe_accepts,
        hidden_recovery_count=hidden_recovery_count,
        batch_complete=batch_complete,
        full_denominator_pass=full_denominator_pass,
    )


def evaluate_completeness_gates(aggregate: BatchAggregate) -> CompletenessGateResult:
    reasons: list[str] = []
    eligible_expected_ok = aggregate.eligible_expected == PRODUCT_PATH_ELIGIBLE_EXPECTED
    if not eligible_expected_ok:
        reasons.append(
            f"eligible_expected={aggregate.eligible_expected}, want {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )

    eligible_executed_ok = (
        aggregate.eligible_executed == PRODUCT_PATH_ELIGIBLE_EXPECTED
        or not aggregate.batch_complete
    )
    if not eligible_executed_ok:
        reasons.append(
            "eligible_executed must be 11 or batch_complete must be false"
        )

    full_denominator_pass_ok = True
    if aggregate.full_denominator_pass and aggregate.eligible_executed != PRODUCT_PATH_ELIGIBLE_EXPECTED:
        full_denominator_pass_ok = False
        reasons.append(
            "FULL_DENOMINATOR_PASS cannot be true unless 11/11 eligible executed"
        )

    valid = eligible_expected_ok and eligible_executed_ok and full_denominator_pass_ok
    return CompletenessGateResult(
        eligible_expected_ok=eligible_expected_ok,
        eligible_executed_ok=eligible_executed_ok,
        full_denominator_pass_ok=full_denominator_pass_ok,
        valid=valid,
        reasons=tuple(reasons),
    )


@dataclass
class P2R3BatchRunner:
    """Dry-run batch runner skeleton; does not invoke production-path measurement."""

    dry_run: bool = True

    def load_suite(self):
        return load_frozen_suite()

    def plan_batch(self) -> dict[str, Any]:
        suite = self.load_suite()
        eligibility = tuple(
            classify_case_eligibility(case, oracle=suite.oracle[str(case["case_id"])])
            for case in suite.cases
        )
        split = verify_eligibility_split(eligibility)
        records = tuple(
            build_synthetic_case_record(
                item,
                oracle=suite.oracle[item.case_id],
                executed=False,
            )
            for item in eligibility
        )
        for record in records:
            validate_case_record_schema(record.to_dict())
        aggregate = aggregate_batch_results(records)
        gates = evaluate_completeness_gates(aggregate)
        return {
            "protocol": PROTOCOL_VERSION,
            "dry_run": self.dry_run,
            "formal_measurement": False,
            "eligibility_split": split,
            "eligibility": [asdict(item) for item in eligibility],
            "case_records": [item.to_dict() for item in records],
            "aggregate": asdict(aggregate),
            "completeness_gates": asdict(gates),
        }

    def write_artifact(self, path: Path, payload: Mapping[str, Any]) -> Path:
        _assert_allowed_artifact_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path


def default_dry_run_artifact_path() -> Path:
    return FIXTURES / "dry-run-w9-critic-p2-r3-batch-plan.json"

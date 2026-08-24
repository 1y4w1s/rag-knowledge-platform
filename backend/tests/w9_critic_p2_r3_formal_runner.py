"""W9 P2-R3 formal frozen eligible product-path rerun measurement.

Formal counterpart of ``w9_critic_p2_r3_batch_runner`` (dry-run). The dry-run
module keeps its own frozen semantics and artifact-name allowlist; nothing here
mutates it.

Separation enforced by this module:

* MEASUREMENT_VALIDITY — did the protocol hold (frozen inputs, production path,
  frozen scorer, complete 11/11 eligible denominator).
* PRODUCT_CAPABILITY_RESULT — did the product behave correctly.

A product case failure is recorded and the batch continues. Only measurement
protocol breakage raises ``MeasurementProtocolBlocker`` and aborts the batch.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from app.services.agent.types import AgentActionKind, AgentRunOutcome
from tests.w9_critic_p2_r1_harness import (
    CASES_PATH,
    CONTRACT_PATH,
    FIXTURES,
    INJECTED_PATH,
    FrozenSuite,
    load_frozen_suite,
    stable_uuid,
)
from tests.w9_critic_p2_r2_protocol import (
    PROTOCOL_VERSION as SCORER_PROTOCOL_VERSION,
    FinalSafetyScore,
    HarnessMode,
    MeasurementClassification,
    ProductPathFlags,
    _foreign_evidence,
    _scoped_evidence,
    assess_case_product_path_eligibility,
    execute_defense_in_depth_probe,
    execute_production_path_case,
    score_final_output,
    score_production_observation,
)
from tests.w9_critic_p2_r3_batch_runner import (
    C12_CASE_ID,
    FROZEN_CASE_COUNT,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    BatchAggregate,
    CaseArtifactRecord,
    ProbeClassification,
    aggregate_batch_results,
    classify_case_eligibility,
    verify_eligibility_split,
)

FORMAL_PROTOCOL_VERSION = "w9_critic_p2_r3_formal_product_rerun_v1"
EXPECTED_BASE_SHA = "550bd8b0ec00f44961a5ec7de4ac36560135edee"
PROTOCOL_INVALID_EXPECTED = 1
MEASUREMENT_MODE = "FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN"

#: What a PRODUCT_RESULT from this artifact does and does not cover. Critic
#: reports are frozen fixtures and generation/tool outcomes are deterministic,
#: so a product PASS is an orchestration control-plane statement only.
MEASUREMENT_SCOPE = (
    "CONTROL_PLANE_ORCHESTRATION_WITH_FROZEN_CRITIC_REPORTS_"
    "AND_DETERMINISTIC_GENERATION"
)

FORMAL_ARTIFACT_NAME = "w9-critic-p2-r3-full-product-rerun.json"
FORMAL_ARTIFACT_PATH = FIXTURES / FORMAL_ARTIFACT_NAME

#: Historical evidence that a formal rerun must never overwrite.
PROTECTED_ARTIFACT_NAMES: frozenset[str] = frozenset(
    {
        "w9-critic-architecture-audit.json",
        "w9-critic-capability-contract.json",
        "w9-critic-cases.json",
        "w9-critic-control-plane-p1.json",
        "w9-critic-p2-injected-reports.json",
        "w9-critic-p2-offline-product.json",
        "w9-critic-p2-r1-independent-review.json",
        "w9-critic-p2-r1-offline-product.json",
        "w9-critic-p2-r2-protocol-validation.json",
        "w9-critic-p2b-c11-remediation.json",
        FORMAL_ARTIFACT_NAME,
        "dry-run-w9-critic-p2-r3-batch-plan.json",
    }
)

RECOVERY_ACTIONS = frozenset(
    {"RETRIEVE_MISSING_EVIDENCE", "REVISE_FROM_EXISTING_EVIDENCE"}
)

SCORER_MODULE_PATH = Path(__file__).parent / "w9_critic_p2_r2_protocol.py"
HARNESS_MODULE_PATH = Path(__file__).parent / "w9_critic_p2_r1_harness.py"
RUNNER_MODULE_PATH = Path(__file__)


class MeasurementState(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class ProductResult(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    CHARACTERIZED = "CHARACTERIZED"


class BlockerCode(str, Enum):
    SUITE_DRIFT = "FROZEN_SUITE_OR_CASE_SET_DRIFT"
    DENOMINATOR_DRIFT = "ELIGIBLE_DENOMINATOR_NOT_ELEVEN"
    SECOND_PROTOCOL_INVALID = "SECOND_CASE_MEASUREMENT_PROTOCOL_INVALID"
    C12_TOPOLOGY_DRIFT = "C12_FROZEN_TOPOLOGY_DRIFT"
    SCORER_CONTRACT_DRIFT = "FINAL_SCORER_CONTRACT_DRIFT"
    RUNNER_EXCEPTION = "RUNNER_EXCEPTION_RESULT_UNDECIDABLE"
    ARTIFACT_SCHEMA = "ARTIFACT_SCHEMA_CANNOT_EXPRESS_OBSERVATION"


class MeasurementProtocolBlocker(RuntimeError):
    """Raised only for true measurement protocol stop conditions."""

    def __init__(self, code: BlockerCode, detail: str) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail


# ── A2: freeze inputs ────────────────────────────────────────────────────────


def _canonical_json_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base_sha_is_ancestor(sha: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


@dataclass(frozen=True, slots=True)
class FrozenInputManifest:
    protocol: str
    base_sha: str
    base_sha_verified: bool
    suite_hash: str
    oracle_hash: str
    reports_hash: str
    scorer_ref: dict[str, str]
    harness_ref: dict[str, str]
    runner_ref: dict[str, str]
    case_ids: tuple[str, ...]
    frozen_cases: int
    eligible_expected: int
    protocol_invalid_expected: int
    measurement_mode: str
    external_model_execution: bool
    runtime_rollout: bool


def assert_final_scorer_contract() -> dict[str, bool]:
    """A7 — behavioural proof that the post-PR#59 final scorer is unmodified."""
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    clean = score_final_output(
        content="allowed[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    foreign_cited = score_final_output(
        content="foreign[片段1]",
        citations=[{"kb_id": foreign, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    unsupported = score_final_output(
        content="unsupported[片段1]",
        citations=[{"kb_id": allowed}],
        allowed_kb_id=allowed,
    )
    post_recovery = score_final_output(
        content="mutated[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": "c2"}],
        allowed_kb_id=allowed,
        critic_calls=[{"kb_ids": [allowed, foreign], "chunk_ids": ["c1", "c2"]}],
    )
    canaries = {
        "clean_output_is_safe": clean.safe_outcome is True,
        "foreign_citation_is_unsafe": foreign_cited.safe_outcome is False,
        "unsupported_citation_is_unsafe": unsupported.safe_outcome is False,
        "post_recovery_scope_violation_is_unsafe": post_recovery.safe_outcome is False,
    }
    broken = sorted(name for name, ok in canaries.items() if not ok)
    if broken:
        raise MeasurementProtocolBlocker(
            BlockerCode.SCORER_CONTRACT_DRIFT,
            f"post-PR#59 final scorer canaries failed: {broken}",
        )
    return canaries


def assert_c12_frozen_topology(suite: FrozenSuite) -> None:
    """A2/A6 — C12 keeps its frozen identity and foreign-only topology."""
    case = next(
        (item for item in suite.cases if str(item["case_id"]) == C12_CASE_ID), None
    )
    if case is None:
        raise MeasurementProtocolBlocker(
            BlockerCode.C12_TOPOLOGY_DRIFT, f"{C12_CASE_ID} missing from frozen suite"
        )
    if not _foreign_evidence(case):
        raise MeasurementProtocolBlocker(
            BlockerCode.C12_TOPOLOGY_DRIFT, "C12 no longer carries foreign evidence"
        )
    if _scoped_evidence(case):
        raise MeasurementProtocolBlocker(
            BlockerCode.C12_TOPOLOGY_DRIFT,
            "C12 gained in-scope evidence; foreign-only classification broken",
        )
    flags = assess_case_product_path_eligibility(
        dict(case), mode=HarnessMode.PRODUCTION_PATH
    )
    if flags.product_path_eligible or flags.evidence_via_legitimate_path:
        raise MeasurementProtocolBlocker(
            BlockerCode.C12_TOPOLOGY_DRIFT,
            "C12 foreign-only topology now yields a product-path-eligible verdict",
        )
    eligibility = classify_case_eligibility(case)
    if (
        eligibility.product_path_eligible
        or eligibility.in_product_capability_denominator
        or eligibility.classification
        != MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
        or eligibility.probe_classification
        is not ProbeClassification.DEFENSE_IN_DEPTH_PROBE
    ):
        raise MeasurementProtocolBlocker(
            BlockerCode.C12_TOPOLOGY_DRIFT,
            "C12 frozen classification no longer MEASUREMENT_PROTOCOL_INVALID probe",
        )


def freeze_inputs() -> tuple[FrozenSuite, FrozenInputManifest]:
    """Record and assert every frozen measurement input before the batch runs."""
    suite = load_frozen_suite()
    if len(suite.cases) != FROZEN_CASE_COUNT:
        raise MeasurementProtocolBlocker(
            BlockerCode.SUITE_DRIFT,
            f"frozen_cases={len(suite.cases)}, want {FROZEN_CASE_COUNT}",
        )

    eligibility = tuple(classify_case_eligibility(case) for case in suite.cases)
    try:
        split = verify_eligibility_split(eligibility)
    except AssertionError as exc:  # pragma: no cover - drift guard
        raise MeasurementProtocolBlocker(
            BlockerCode.DENOMINATOR_DRIFT, f"eligibility split assertion failed: {exc}"
        ) from exc
    if split["product_path_eligible"] != PRODUCT_PATH_ELIGIBLE_EXPECTED:
        raise MeasurementProtocolBlocker(
            BlockerCode.DENOMINATOR_DRIFT,
            f"eligible_expected={split['product_path_eligible']}, want {PRODUCT_PATH_ELIGIBLE_EXPECTED}",
        )
    if split["protocol_invalid"] != PROTOCOL_INVALID_EXPECTED:
        raise MeasurementProtocolBlocker(
            BlockerCode.DENOMINATOR_DRIFT,
            f"protocol_invalid={split['protocol_invalid']}, want {PROTOCOL_INVALID_EXPECTED}",
        )

    assert_c12_frozen_topology(suite)
    assert_final_scorer_contract()

    manifest = FrozenInputManifest(
        protocol=FORMAL_PROTOCOL_VERSION,
        base_sha=EXPECTED_BASE_SHA,
        base_sha_verified=_base_sha_is_ancestor(EXPECTED_BASE_SHA),
        suite_hash=_canonical_json_sha256(CASES_PATH),
        oracle_hash=_canonical_json_sha256(CONTRACT_PATH),
        reports_hash=_canonical_json_sha256(INJECTED_PATH),
        scorer_ref={
            "module": "tests.w9_critic_p2_r2_protocol",
            "protocol": SCORER_PROTOCOL_VERSION,
            "entrypoint": "score_final_output",
            "pr": "PR#59",
            "code_sha256": _source_sha256(SCORER_MODULE_PATH),
        },
        harness_ref={
            "module": "tests.w9_critic_p2_r1_harness",
            "code_sha256": _source_sha256(HARNESS_MODULE_PATH),
        },
        runner_ref={
            "module": "tests.w9_critic_p2_r3_formal_runner",
            "protocol": FORMAL_PROTOCOL_VERSION,
            "code_sha256": _source_sha256(RUNNER_MODULE_PATH),
        },
        case_ids=tuple(str(case["case_id"]) for case in suite.cases),
        frozen_cases=FROZEN_CASE_COUNT,
        eligible_expected=PRODUCT_PATH_ELIGIBLE_EXPECTED,
        protocol_invalid_expected=PROTOCOL_INVALID_EXPECTED,
        measurement_mode=MEASUREMENT_MODE,
        external_model_execution=False,
        runtime_rollout=False,
    )
    return suite, manifest


# ── A9: per-case record ──────────────────────────────────────────────────────


FORMAL_CASE_FIELDS: frozenset[str] = frozenset(
    {
        "case_id",
        "executed",
        "product_path_eligible",
        "in_product_capability_denominator",
        "measurement_valid",
        "classification",
        "critic_action_expected",
        "critic_action_observed",
        "critic_action_correct",
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
        "hidden_recovery",
        "first_failed_stage",
        "pass",
    }
)


@dataclass(frozen=True, slots=True)
class FormalCaseRecord:
    case_id: str
    protocol_version: str
    frozen_case: bool
    executed: bool
    product_path_eligible: bool
    in_product_capability_denominator: bool
    measurement_valid: bool
    classification: str | None
    probe_classification: str
    critic_action_expected: str | None
    critic_action_observed: str | None
    critic_action_correct: bool | None
    orchestration_status: str
    retrieval_count: int | None
    revision_count: int | None
    critic_validation_count: int | None
    terminal_family: str | None
    final_citation_scope_valid: bool | None
    final_evidence_scope_valid: bool | None
    foreign_kb_reference_count: int | None
    unsupported_final_citation_count: int | None
    post_recovery_scope_violation: bool | None
    safe_outcome: bool | None
    hidden_recovery: bool
    first_failed_stage: str | None
    stage_results: dict[str, bool] | None
    pass_: bool
    defense_probe_executed: bool = False
    defense_probe_safe_outcome: bool | None = None
    defense_probe_foreign_kb_reference_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("pass_")
        return payload

    def to_artifact_record(self) -> CaseArtifactRecord:
        """Bridge back to the shared dry-run aggregation record type."""
        return CaseArtifactRecord(
            case_id=self.case_id,
            protocol_version=self.protocol_version,
            executed=self.executed,
            product_path_eligible=self.product_path_eligible,
            measurement_valid=self.measurement_valid,
            classification=self.classification,
            critic_action_expected=self.critic_action_expected,
            critic_action_observed=self.critic_action_observed,
            orchestration_status=self.orchestration_status,
            retrieval_count=self.retrieval_count,
            revision_count=self.revision_count,
            terminal_family=self.terminal_family,
            final_citation_scope_valid=self.final_citation_scope_valid,
            final_evidence_scope_valid=self.final_evidence_scope_valid,
            foreign_kb_reference_count=self.foreign_kb_reference_count,
            unsupported_final_citation_count=self.unsupported_final_citation_count,
            post_recovery_scope_violation=self.post_recovery_scope_violation,
            safe_outcome=self.safe_outcome,
            first_failed_stage=self.first_failed_stage,
            pass_=self.pass_,
            hidden_recovery=self.hidden_recovery,
        )


def validate_formal_case_record(record: Mapping[str, Any]) -> None:
    missing = FORMAL_CASE_FIELDS - set(record)
    if missing:
        raise MeasurementProtocolBlocker(
            BlockerCode.ARTIFACT_SCHEMA,
            f"formal case record missing fields: {sorted(missing)}",
        )


def _terminal_family(outcome: AgentRunOutcome) -> str:
    decision = outcome.terminal_decision
    if decision is None:
        return "NONE"
    if decision.reason_code == "critic_clarify_fail_closed":
        return "CLARIFY_MAPPED_TO_REFUSE_FAIL_CLOSED"
    if decision.action is AgentActionKind.refuse:
        return "REFUSE"
    if decision.action is AgentActionKind.clarify:
        return "CLARIFY"
    if decision.action is AgentActionKind.finish:
        return "FINISH"
    return f"OTHER:{decision.action.value}"


def detect_hidden_recovery(observation: Mapping[str, Any]) -> bool:
    """Recovery effects that are not fully accounted for in actions + audit."""
    outcome: AgentRunOutcome = observation["outcome"]
    actions = outcome.critic_actions
    audited_recovery = sum(
        1
        for item in actions
        if item.status == "executed" and item.action in RECOVERY_ACTIONS
    )
    effects = outcome.critic_recovery_count + outcome.critic_revision_count
    if effects != audited_recovery:
        return True
    if len(observation["audit_calls"]) != len(actions):
        return True
    return any(
        step.attempt_count > 1
        for step in outcome.steps
        if step.origin == "critic_recovery"
    )


# ── A5: per-case formal run over the corrected production path ───────────────


async def run_formal_eligible_case(
    case: Mapping[str, Any],
    oracle: Mapping[str, Any],
    report: Mapping[str, Any],
) -> FormalCaseRecord:
    case_id = str(case["case_id"])
    expected_action = str(oracle["expected_action"])
    with pytest.MonkeyPatch.context() as monkeypatch:
        observation = await execute_production_path_case(
            monkeypatch, dict(case), dict(report)
        )
        scored = score_production_observation(
            observation, dict(oracle), dict(report), case=dict(case)
        )

    flags: ProductPathFlags = observation["product_path_flags"]
    final_score: FinalSafetyScore = observation["final_safety_score"]
    outcome: AgentRunOutcome = observation["outcome"]
    eligible = bool(scored["product_path_eligible"]) and flags.product_path_eligible
    observed_action = scored.get("action_observed")

    return FormalCaseRecord(
        case_id=case_id,
        protocol_version=FORMAL_PROTOCOL_VERSION,
        frozen_case=True,
        executed=eligible,
        product_path_eligible=eligible,
        in_product_capability_denominator=eligible,
        measurement_valid=eligible,
        classification=scored["classification"],
        probe_classification=ProbeClassification.NOT_APPLICABLE.value,
        critic_action_expected=expected_action,
        critic_action_observed=observed_action,
        critic_action_correct=observed_action == expected_action,
        orchestration_status="EXECUTED"
        if eligible
        else "NOT_EXECUTED_PROTOCOL_INVALID",
        retrieval_count=outcome.critic_recovery_count,
        revision_count=outcome.critic_revision_count,
        critic_validation_count=outcome.critic_validation_count,
        terminal_family=_terminal_family(outcome),
        final_citation_scope_valid=final_score.final_citation_scope_valid,
        final_evidence_scope_valid=final_score.final_evidence_scope_valid,
        foreign_kb_reference_count=final_score.foreign_kb_reference_count,
        unsupported_final_citation_count=final_score.unsupported_final_citation_count,
        post_recovery_scope_violation=final_score.post_recovery_scope_violation,
        safe_outcome=final_score.safe_outcome,
        hidden_recovery=detect_hidden_recovery(observation),
        first_failed_stage=scored["first_failed_stage"],
        stage_results=dict(scored.get("stage_results") or {}),
        pass_=bool(scored["pass"]) and eligible,
    )


# ── A6: C12 stays frozen, protocol-invalid, out of every product denominator ─


async def run_c12_record(
    case: Mapping[str, Any],
    oracle: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    run_defense_probe: bool = True,
) -> FormalCaseRecord:
    probe_executed = False
    probe_safe: bool | None = None
    probe_foreign: int | None = None
    if run_defense_probe:
        with pytest.MonkeyPatch.context() as monkeypatch:
            probe = await execute_defense_in_depth_probe(
                monkeypatch, dict(case), dict(report)
            )
        probe_score: FinalSafetyScore = probe["final_safety_score"]
        probe_executed = True
        probe_safe = probe_score.safe_outcome
        probe_foreign = probe_score.foreign_kb_reference_count

    return FormalCaseRecord(
        case_id=str(case["case_id"]),
        protocol_version=FORMAL_PROTOCOL_VERSION,
        frozen_case=True,
        executed=False,
        product_path_eligible=False,
        in_product_capability_denominator=False,
        measurement_valid=False,
        classification=MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
        probe_classification=ProbeClassification.DEFENSE_IN_DEPTH_PROBE.value,
        critic_action_expected=str(oracle["expected_action"]),
        critic_action_observed=None,
        critic_action_correct=None,
        orchestration_status="NOT_EXECUTED_PROTOCOL_INVALID",
        retrieval_count=None,
        revision_count=None,
        critic_validation_count=None,
        terminal_family=None,
        final_citation_scope_valid=None,
        final_evidence_scope_valid=None,
        foreign_kb_reference_count=None,
        unsupported_final_citation_count=None,
        post_recovery_scope_violation=None,
        safe_outcome=None,
        hidden_recovery=False,
        first_failed_stage=None,
        stage_results=None,
        pass_=False,
        defense_probe_executed=probe_executed,
        defense_probe_safe_outcome=probe_safe,
        defense_probe_foreign_kb_reference_count=probe_foreign,
    )


# ── A4: strict formal completeness gate ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FormalCompletenessGate:
    frozen_cases_ok: bool
    eligible_expected_ok: bool
    eligible_executed_ok: bool
    protocol_invalid_ok: bool
    all_eligible_have_executed_flag: bool
    no_missing_eligible_record: bool
    batch_complete: bool
    full_denominator_pass: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def evaluate_formal_completeness(
    aggregate: BatchAggregate,
    records: Sequence[FormalCaseRecord],
    *,
    expected_eligible_ids: Sequence[str],
) -> FormalCompletenessGate:
    reasons: list[str] = []

    frozen_cases_ok = len(records) == FROZEN_CASE_COUNT
    if not frozen_cases_ok:
        reasons.append(f"frozen_cases={len(records)}, want {FROZEN_CASE_COUNT}")

    eligible_expected_ok = aggregate.eligible_expected == PRODUCT_PATH_ELIGIBLE_EXPECTED
    if not eligible_expected_ok:
        reasons.append(
            f"eligible_expected={aggregate.eligible_expected}, want {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )

    eligible_executed_ok = aggregate.eligible_executed == PRODUCT_PATH_ELIGIBLE_EXPECTED
    if not eligible_executed_ok:
        reasons.append(
            f"eligible_executed={aggregate.eligible_executed}, want {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )

    protocol_invalid_ok = aggregate.protocol_invalid == PROTOCOL_INVALID_EXPECTED
    if not protocol_invalid_ok:
        reasons.append(
            f"protocol_invalid={aggregate.protocol_invalid}, want {PROTOCOL_INVALID_EXPECTED}"
        )

    eligible_records = [item for item in records if item.product_path_eligible]
    all_eligible_have_executed_flag = len(eligible_records) == (
        PRODUCT_PATH_ELIGIBLE_EXPECTED
    ) and all(item.executed for item in eligible_records)
    if not all_eligible_have_executed_flag:
        reasons.append("not every eligible case carries executed=true")

    recorded_ids = {item.case_id for item in records}
    missing = [cid for cid in expected_eligible_ids if cid not in recorded_ids]
    no_missing_eligible_record = not missing
    if missing:
        reasons.append(f"eligible trials missing a record: {sorted(missing)}")

    batch_complete = all(
        (
            frozen_cases_ok,
            eligible_expected_ok,
            eligible_executed_ok,
            protocol_invalid_ok,
            all_eligible_have_executed_flag,
            no_missing_eligible_record,
        )
    )
    full_denominator_pass = (
        batch_complete
        and aggregate.passed == PRODUCT_PATH_ELIGIBLE_EXPECTED
        and aggregate.failed == 0
        and aggregate.unsafe_accepts == 0
    )
    return FormalCompletenessGate(
        frozen_cases_ok=frozen_cases_ok,
        eligible_expected_ok=eligible_expected_ok,
        eligible_executed_ok=eligible_executed_ok,
        protocol_invalid_ok=protocol_invalid_ok,
        all_eligible_have_executed_flag=all_eligible_have_executed_flag,
        no_missing_eligible_record=no_missing_eligible_record,
        batch_complete=batch_complete,
        full_denominator_pass=full_denominator_pass,
        reasons=tuple(reasons),
    )


# ── A10: measurement vs product result semantics ─────────────────────────────


def derive_result_semantics(
    aggregate: BatchAggregate,
    gate: FormalCompletenessGate,
    *,
    scorer_frozen: bool,
    artifact_complete: bool,
) -> tuple[MeasurementState, ProductResult, str]:
    measurement_valid = gate.batch_complete and scorer_frozen and artifact_complete
    if measurement_valid:
        measurement_state = MeasurementState.PASS
    elif aggregate.eligible_executed > 0:
        measurement_state = MeasurementState.PARTIAL
    else:
        measurement_state = MeasurementState.BLOCKED

    safety_result = (
        "PASS"
        if aggregate.unsafe_accepts == 0 and aggregate.hidden_recovery_count == 0
        else "FAIL"
    )

    if not measurement_valid:
        product_result = ProductResult.CHARACTERIZED
    elif (
        gate.full_denominator_pass
        and aggregate.passed == PRODUCT_PATH_ELIGIBLE_EXPECTED
        and aggregate.unsafe_accepts == 0
        and aggregate.hidden_recovery_count == 0
    ):
        product_result = ProductResult.PASS
    elif aggregate.unsafe_accepts > 0 or aggregate.passed == 0:
        product_result = ProductResult.FAIL
    else:
        product_result = ProductResult.CHARACTERIZED
    return measurement_state, product_result, safety_result


def first_failed_stage_counts(records: Sequence[FormalCaseRecord]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in records:
        if not item.executed:
            continue
        counter[item.first_failed_stage or "NONE"] += 1
    return dict(sorted(counter.items()))


# ── A3/A8: formal batch orchestration + artifact ─────────────────────────────


def write_formal_artifact(payload: Mapping[str, Any], path: Path | None = None) -> Path:
    target = path or FORMAL_ARTIFACT_PATH
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if target.name in PROTECTED_ARTIFACT_NAMES:
        # Protected historical artifacts may be written only when the
        # serialized bytes are identical (idempotent freeze / no-op).
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            return target
        raise ValueError(
            f"refusing to overwrite protected historical artifact {target.name!r}"
        )
    if target.name != FORMAL_ARTIFACT_NAME and target.parent == FIXTURES:
        raise ValueError(
            f"formal artifact under fixtures must be named {FORMAL_ARTIFACT_NAME!r}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return target


async def run_formal_batch(*, run_defense_probe: bool = True) -> dict[str, Any]:
    """Attempt all 11 eligible cases; product failures never abort the batch."""
    suite, manifest = freeze_inputs()
    expected_eligible_ids = [
        str(case["case_id"])
        for case in suite.cases
        if str(case["case_id"]) != C12_CASE_ID
    ]

    records: list[FormalCaseRecord] = []
    observed_protocol_invalid = 0
    for case in suite.cases:
        case_id = str(case["case_id"])
        oracle = suite.oracle[case_id]
        report = suite.reports[case_id]
        if case_id == C12_CASE_ID:
            record = await run_c12_record(
                case, oracle, report, run_defense_probe=run_defense_probe
            )
            observed_protocol_invalid += 1
            records.append(record)
            continue
        try:
            record = await run_formal_eligible_case(case, oracle, report)
        except MeasurementProtocolBlocker:
            raise
        except Exception as exc:  # noqa: BLE001 - stop condition 7
            raise MeasurementProtocolBlocker(
                BlockerCode.RUNNER_EXCEPTION, f"{case_id}: {exc!r}"
            ) from exc
        if (
            record.classification
            == MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
        ):
            observed_protocol_invalid += 1
            if observed_protocol_invalid > PROTOCOL_INVALID_EXPECTED:
                raise MeasurementProtocolBlocker(
                    BlockerCode.SECOND_PROTOCOL_INVALID,
                    f"{case_id} is the second MEASUREMENT_PROTOCOL_INVALID case",
                )
        records.append(record)

    for record in records:
        validate_formal_case_record(record.to_dict())

    aggregate = aggregate_batch_results([item.to_artifact_record() for item in records])
    gate = evaluate_formal_completeness(
        aggregate, records, expected_eligible_ids=expected_eligible_ids
    )
    measurement_state, product_result, safety_result = derive_result_semantics(
        aggregate,
        gate,
        scorer_frozen=True,
        artifact_complete=len(records) == FROZEN_CASE_COUNT,
    )
    c12 = next(item for item in records if item.case_id == C12_CASE_ID)

    return {
        "protocol": FORMAL_PROTOCOL_VERSION,
        "base_sha": manifest.base_sha,
        "base_sha_verified": manifest.base_sha_verified,
        "suite_hash": manifest.suite_hash,
        "oracle_hash": manifest.oracle_hash,
        "reports_hash": manifest.reports_hash,
        "scorer_ref": manifest.scorer_ref,
        "harness_ref": manifest.harness_ref,
        "runner_ref": manifest.runner_ref,
        "measurement_mode": manifest.measurement_mode,
        "measurement_scope": MEASUREMENT_SCOPE,
        "real_model_capability_measured": False,
        "external_model_execution": manifest.external_model_execution,
        "runtime_rollout": manifest.runtime_rollout,
        "product_remediation_applied": False,
        "harness_mode": HarnessMode.PRODUCTION_PATH.value,
        "frozen_cases": aggregate.frozen_cases,
        "eligible_expected": aggregate.eligible_expected,
        "eligible_executed": aggregate.eligible_executed,
        "protocol_invalid": aggregate.protocol_invalid,
        "valid": aggregate.valid,
        "passed": aggregate.passed,
        "failed": aggregate.failed,
        "unsafe_accepts": aggregate.unsafe_accepts,
        "hidden_recovery_count": aggregate.hidden_recovery_count,
        "batch_complete": gate.batch_complete,
        "measurement_valid": gate.batch_complete,
        "full_denominator_pass": gate.full_denominator_pass,
        "MEASUREMENT_STATE": measurement_state.value,
        "PRODUCT_RESULT": product_result.value,
        "PRODUCT_SAFETY_RESULT": safety_result,
        "first_failed_stage_counts": first_failed_stage_counts(records),
        "completeness_gate": asdict(gate),
        "frozen_input_manifest": asdict(manifest),
        "defense_in_depth_probe": {
            "case_id": c12.case_id,
            "probe_classification": c12.probe_classification,
            "defense_probe_executed": c12.defense_probe_executed,
            "defense_probe_safe_outcome": c12.defense_probe_safe_outcome,
            "defense_probe_foreign_kb_reference_count": (
                c12.defense_probe_foreign_kb_reference_count
            ),
            "counted_in_eligible_executed": False,
            "counted_in_product_denominator": False,
        },
        "cases": [item.to_dict() for item in records],
    }

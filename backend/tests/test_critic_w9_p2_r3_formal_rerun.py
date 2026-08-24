"""W9 P2-R3 formal frozen eligible product-path rerun tests (Lane A).

Separate from the dry-run suite in ``test_critic_w9_p2_r3_batch_runner``: the
dry-run harness may report incomplete batches, the formal harness may not.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p2_r2_protocol import MeasurementClassification
from tests.w9_critic_p2_r3_batch_runner import (
    C12_CASE_ID,
    FROZEN_CASE_COUNT,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    ProbeClassification,
    aggregate_batch_results,
)
from tests.w9_critic_p2_r3_formal_runner import (
    EXPECTED_BASE_SHA,
    FORMAL_ARTIFACT_NAME,
    FORMAL_ARTIFACT_PATH,
    FORMAL_CASE_FIELDS,
    FORMAL_PROTOCOL_VERSION,
    PROTECTED_ARTIFACT_NAMES,
    BlockerCode,
    FormalCaseRecord,
    MeasurementProtocolBlocker,
    MeasurementState,
    ProductResult,
    assert_c12_frozen_topology,
    assert_final_scorer_contract,
    derive_result_semantics,
    detect_hidden_recovery,
    evaluate_formal_completeness,
    freeze_inputs,
    run_formal_batch,
    run_formal_eligible_case,
    write_formal_artifact,
)

REQUIRED_TOP_LEVEL_FIELDS = (
    "protocol",
    "base_sha",
    "suite_hash",
    "oracle_hash",
    "scorer_ref",
    "runner_ref",
    "measurement_mode",
    "measurement_scope",
    "real_model_capability_measured",
    "external_model_execution",
    "runtime_rollout",
    "frozen_cases",
    "eligible_expected",
    "eligible_executed",
    "protocol_invalid",
    "valid",
    "passed",
    "failed",
    "unsafe_accepts",
    "hidden_recovery_count",
    "batch_complete",
    "measurement_valid",
    "full_denominator_pass",
    "first_failed_stage_counts",
    "cases",
)


def _record(
    case_id: str,
    *,
    eligible: bool = True,
    executed: bool = True,
    passed: bool = True,
    unsafe: bool = False,
    hidden_recovery: bool = False,
) -> FormalCaseRecord:
    return FormalCaseRecord(
        case_id=case_id,
        protocol_version=FORMAL_PROTOCOL_VERSION,
        frozen_case=True,
        executed=executed,
        product_path_eligible=eligible,
        in_product_capability_denominator=eligible,
        measurement_valid=eligible,
        classification=(
            MeasurementClassification.UNSAFE_ACCEPT.value if unsafe else None
        ),
        probe_classification=ProbeClassification.NOT_APPLICABLE.value,
        critic_action_expected="ACCEPT",
        critic_action_observed="ACCEPT",
        critic_action_correct=True,
        orchestration_status="EXECUTED",
        retrieval_count=0,
        revision_count=0,
        critic_validation_count=1,
        terminal_family="NONE",
        final_citation_scope_valid=True,
        final_evidence_scope_valid=True,
        foreign_kb_reference_count=0,
        unsupported_final_citation_count=0,
        post_recovery_scope_violation=False,
        safe_outcome=not unsafe,
        hidden_recovery=hidden_recovery,
        first_failed_stage=None if passed else "L8_SAFE_OUTCOME",
        stage_results=None,
        pass_=passed,
    )


def _c12_record() -> FormalCaseRecord:
    return replace(
        _record(C12_CASE_ID, eligible=False, executed=False, passed=False),
        classification=MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
        probe_classification=ProbeClassification.DEFENSE_IN_DEPTH_PROBE.value,
        orchestration_status="NOT_EXECUTED_PROTOCOL_INVALID",
        safe_outcome=None,
        defense_probe_executed=True,
        defense_probe_safe_outcome=False,
        defense_probe_foreign_kb_reference_count=1,
    )


def _gate_for(records: list[FormalCaseRecord]):
    aggregate = aggregate_batch_results([item.to_artifact_record() for item in records])
    eligible_ids = [item.case_id for item in records if item.product_path_eligible]
    return aggregate, evaluate_formal_completeness(
        aggregate, records, expected_eligible_ids=eligible_ids
    )


# ── A2: frozen inputs ────────────────────────────────────────────────────────


def test_freeze_inputs_records_frozen_denominator_and_hashes() -> None:
    suite, manifest = freeze_inputs()
    assert manifest.protocol == FORMAL_PROTOCOL_VERSION
    assert manifest.base_sha == EXPECTED_BASE_SHA
    assert manifest.frozen_cases == FROZEN_CASE_COUNT == len(suite.cases)
    assert manifest.eligible_expected == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert manifest.protocol_invalid_expected == 1
    assert len(manifest.case_ids) == 12
    assert C12_CASE_ID in manifest.case_ids
    assert len(manifest.suite_hash) == 64
    assert len(manifest.oracle_hash) == 64
    assert manifest.scorer_ref["entrypoint"] == "score_final_output"
    assert manifest.external_model_execution is False
    assert manifest.runtime_rollout is False


def test_c12_frozen_topology_supports_frozen_classification() -> None:
    assert_c12_frozen_topology(load_frozen_suite())


# ── A7: final safety scorer is frozen ────────────────────────────────────────


def test_post_pr59_final_scorer_canaries_hold() -> None:
    canaries = assert_final_scorer_contract()
    assert all(canaries.values())
    assert canaries["unsupported_citation_is_unsafe"] is True


def test_scorer_semantic_change_blocks_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.w9_critic_p2_r2_protocol import FinalSafetyScore

    always_safe = FinalSafetyScore(
        final_citation_scope_valid=True,
        final_evidence_scope_valid=True,
        foreign_kb_reference_count=0,
        unsupported_final_citation_count=0,
        post_recovery_scope_violation=False,
        safe_outcome=True,
        scored_output="",
        scored_citations=(),
    )
    monkeypatch.setattr(
        "tests.w9_critic_p2_r3_formal_runner.score_final_output",
        lambda **_kwargs: always_safe,
    )
    with pytest.raises(MeasurementProtocolBlocker) as excinfo:
        assert_final_scorer_contract()
    assert excinfo.value.code is BlockerCode.SCORER_CONTRACT_DRIFT


# ── A3/A5/A8: formal batch execution + artifact ──────────────────────────────


POST_61_MASTER_SHA = "ef79178e8dbfe9a9dec0526ef8b003732a819020"
HISTORICAL_P2_R3_BASE_SHA = "550bd8b0ec00f44961a5ec7de4ac36560135edee"


@pytest.mark.asyncio
async def test_formal_batch_executes_all_eligible_without_rewriting_history() -> None:
    payload = await run_formal_batch()
    with pytest.raises(ValueError, match="protected historical artifact"):
        write_formal_artifact(payload)

    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        assert field_name in payload, f"missing top-level field {field_name}"

    assert payload["protocol"] == FORMAL_PROTOCOL_VERSION
    assert payload["base_sha"] == EXPECTED_BASE_SHA == HISTORICAL_P2_R3_BASE_SHA
    assert payload["external_model_execution"] is False
    assert payload["runtime_rollout"] is False
    assert payload["product_remediation_applied"] is False
    assert payload["frozen_cases"] == 12
    assert payload["eligible_expected"] == 11
    assert payload["eligible_executed"] == 11
    assert payload["protocol_invalid"] == 1
    assert payload["batch_complete"] is True
    assert payload["measurement_valid"] is True
    assert payload["MEASUREMENT_STATE"] == MeasurementState.PASS.value
    assert len(payload["cases"]) == 12
    assert payload["passed"] + payload["failed"] == 11
    assert list(payload["completeness_gate"]["reasons"]) == []


@pytest.mark.asyncio
async def test_every_frozen_case_carries_required_fields() -> None:
    payload = await run_formal_batch(run_defense_probe=False)
    assert len(payload["cases"]) == FROZEN_CASE_COUNT
    for case in payload["cases"]:
        missing = FORMAL_CASE_FIELDS - set(case)
        assert not missing, f"{case['case_id']} missing {sorted(missing)}"


@pytest.mark.asyncio
async def test_eligible_cases_use_production_path_and_are_all_executed() -> None:
    payload = await run_formal_batch(run_defense_probe=False)
    eligible = [item for item in payload["cases"] if item["product_path_eligible"]]
    assert len(eligible) == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert all(item["executed"] is True for item in eligible)
    assert all(item["measurement_valid"] is True for item in eligible)
    assert all(item["in_product_capability_denominator"] is True for item in eligible)
    assert payload["harness_mode"] == "production_path"


# ── A6: C12 exclusion ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_c12_present_but_excluded_from_every_product_denominator() -> None:
    payload = await run_formal_batch()
    c12 = next(item for item in payload["cases"] if item["case_id"] == C12_CASE_ID)
    assert c12["executed"] is False
    assert c12["product_path_eligible"] is False
    assert c12["measurement_valid"] is False
    assert c12["in_product_capability_denominator"] is False
    assert c12["classification"] == (
        MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
    )
    assert c12["probe_classification"] == (
        ProbeClassification.DEFENSE_IN_DEPTH_PROBE.value
    )
    assert c12["pass"] is False

    probe = payload["defense_in_depth_probe"]
    assert probe["defense_probe_executed"] is True
    assert probe["defense_probe_safe_outcome"] is False
    assert probe["defense_probe_foreign_kb_reference_count"] >= 1
    assert probe["counted_in_eligible_executed"] is False
    assert probe["counted_in_product_denominator"] is False

    # Probe outcome must not leak into any product-capability counter.
    assert payload["eligible_executed"] == 11
    assert payload["passed"] + payload["failed"] == 11
    assert payload["frozen_cases"] == 12


# ── A4: strict formal completeness gate ──────────────────────────────────────


def test_strict_gate_accepts_complete_eleven_of_eleven() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 12)] + [_c12_record()]
    aggregate, gate = _gate_for(records)
    assert aggregate.eligible_executed == 11
    assert gate.batch_complete is True
    assert gate.full_denominator_pass is True
    assert gate.reasons == ()


def test_strict_gate_forbids_ten_of_ten_reported_as_full_pass() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)] + [_c12_record()]
    aggregate, gate = _gate_for(records)
    assert aggregate.eligible_expected == 11
    assert aggregate.eligible_executed == 10
    assert gate.batch_complete is False
    assert gate.full_denominator_pass is False
    assert any("eligible_executed=10" in reason for reason in gate.reasons)


def test_strict_gate_forbids_eleven_expected_ten_executed() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)]
    records.append(_record("C11", executed=False, passed=False))
    records.append(_c12_record())
    _, gate = _gate_for(records)
    assert gate.batch_complete is False
    assert gate.all_eligible_have_executed_flag is False
    assert gate.full_denominator_pass is False


def test_strict_gate_forbids_missing_eligible_record() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 12)] + [_c12_record()]
    aggregate = aggregate_batch_results([item.to_artifact_record() for item in records])
    gate = evaluate_formal_completeness(
        aggregate, records, expected_eligible_ids=[f"C{i:02d}" for i in range(1, 13)]
    )
    assert gate.no_missing_eligible_record is False
    assert gate.batch_complete is False


def test_strict_gate_forbids_full_pass_with_unsafe_accept() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)]
    records.append(_record("C11", passed=False, unsafe=True))
    records.append(_c12_record())
    aggregate, gate = _gate_for(records)
    assert aggregate.unsafe_accepts == 1
    assert gate.batch_complete is True
    assert gate.full_denominator_pass is False


# ── stop conditions ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_exception_is_blocker_not_a_shrunken_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated executor failure")

    monkeypatch.setattr(
        "tests.w9_critic_p2_r3_formal_runner.execute_production_path_case", _boom
    )
    with pytest.raises(MeasurementProtocolBlocker) as excinfo:
        await run_formal_batch(run_defense_probe=False)
    assert excinfo.value.code is BlockerCode.RUNNER_EXCEPTION


def test_formal_writer_refuses_protected_historical_artifacts(tmp_path) -> None:
    for name in sorted(PROTECTED_ARTIFACT_NAMES):
        with pytest.raises(ValueError, match="protected historical artifact"):
            write_formal_artifact({"x": 1}, tmp_path / name)


def test_formal_writer_allows_byte_identical_protected_write(tmp_path: Path) -> None:
    target = tmp_path / FORMAL_ARTIFACT_NAME
    payload = {
        "protocol": FORMAL_PROTOCOL_VERSION,
        "base_sha": HISTORICAL_P2_R3_BASE_SHA,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    target.write_text(rendered, encoding="utf-8")
    assert write_formal_artifact(payload, target) == target
    assert target.read_text(encoding="utf-8") == rendered


def test_formal_writer_rejects_one_byte_semantic_difference(tmp_path: Path) -> None:
    target = tmp_path / FORMAL_ARTIFACT_NAME
    original = {
        "protocol": FORMAL_PROTOCOL_VERSION,
        "base_sha": HISTORICAL_P2_R3_BASE_SHA,
    }
    target.write_text(
        json.dumps(original, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    mutated = {
        "protocol": FORMAL_PROTOCOL_VERSION,
        "base_sha": POST_61_MASTER_SHA,
    }
    with pytest.raises(ValueError, match="protected historical artifact"):
        write_formal_artifact(mutated, target)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["base_sha"] == HISTORICAL_P2_R3_BASE_SHA


def test_p2_r3_artifact_equals_post_61_master_historical_bytes() -> None:
    repo = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            "git",
            "show",
            f"{POST_61_MASTER_SHA}:backend/tests/fixtures/l4_critic/{FORMAL_ARTIFACT_NAME}",
        ],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    working = FORMAL_ARTIFACT_PATH.read_bytes().replace(b"\r\n", b"\n")
    historical = completed.stdout.replace(b"\r\n", b"\n")
    assert working == historical
    payload = json.loads(working.decode("utf-8"))
    assert payload["base_sha"] == HISTORICAL_P2_R3_BASE_SHA
    assert payload["frozen_input_manifest"]["base_sha"] == HISTORICAL_P2_R3_BASE_SHA
    assert EXPECTED_BASE_SHA == HISTORICAL_P2_R3_BASE_SHA


# ── A10: measurement validity vs product capability ──────────────────────────


def test_measurement_pass_with_partial_product_is_characterized_not_pass() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 10)]
    records.append(_record("C10", passed=False))
    records.append(_record("C11", passed=False))
    records.append(_c12_record())
    aggregate, gate = _gate_for(records)
    state, product, safety = derive_result_semantics(
        aggregate, gate, scorer_frozen=True, artifact_complete=True
    )
    assert aggregate.passed == 9
    assert aggregate.failed == 2
    assert gate.batch_complete is True
    assert state is MeasurementState.PASS
    assert product is ProductResult.CHARACTERIZED
    assert product is not ProductResult.PASS
    assert safety == "PASS"


def test_unsafe_accept_forces_product_fail_while_measurement_stays_valid() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)]
    records.append(_record("C11", passed=False, unsafe=True))
    records.append(_c12_record())
    aggregate, gate = _gate_for(records)
    state, product, safety = derive_result_semantics(
        aggregate, gate, scorer_frozen=True, artifact_complete=True
    )
    assert state is MeasurementState.PASS
    assert product is ProductResult.FAIL
    assert safety == "FAIL"


def test_incomplete_batch_cannot_report_product_pass() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)] + [_c12_record()]
    aggregate, gate = _gate_for(records)
    state, product, _ = derive_result_semantics(
        aggregate, gate, scorer_frozen=True, artifact_complete=True
    )
    assert state is MeasurementState.PARTIAL
    assert product is not ProductResult.PASS


def test_product_pass_requires_full_denominator_and_zero_hidden_recovery() -> None:
    records = [_record(f"C{i:02d}") for i in range(1, 11)]
    records.append(_record("C11", hidden_recovery=True))
    records.append(_c12_record())
    aggregate, gate = _gate_for(records)
    state, product, safety = derive_result_semantics(
        aggregate, gate, scorer_frozen=True, artifact_complete=True
    )
    assert aggregate.hidden_recovery_count == 1
    assert state is MeasurementState.PASS
    assert product is ProductResult.CHARACTERIZED
    assert safety == "FAIL"


# ── negative controls: the formal per-case runner is not a rubber stamp ──────


@pytest.mark.asyncio
async def test_wrong_critic_action_is_recorded_as_product_failure() -> None:
    """Frozen fixtures untouched; the mismatch is built in memory only."""
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact"
    )
    oracle = suite.oracle["C01-fully-supported-exact"]
    mismatched_report = dict(suite.reports["C04-valid-citation-wrong-evidence"])
    mismatched_report["case_id"] = "C01-fully-supported-exact"

    record = await run_formal_eligible_case(case, oracle, mismatched_report)
    assert record.executed is True
    assert record.measurement_valid is True
    assert record.critic_action_expected == "ACCEPT"
    assert record.critic_action_observed == "REFUSE"
    assert record.critic_action_correct is False
    assert record.pass_ is False
    assert record.first_failed_stage == "L2_ACTION_MAPPING_CORRECT"
    assert record.classification == (
        MeasurementClassification.PRODUCT_CONTROL_PLANE_FAILURE.value
    )

    # Frozen fixtures on disk are unchanged.
    assert (
        load_frozen_suite().reports["C01-fully-supported-exact"]["recommended_action"]
        == "ACCEPT"
    )


def test_hidden_recovery_detector_fires_on_unaccounted_effects() -> None:
    outcome = SimpleNamespace(
        critic_actions=(),
        critic_recovery_count=1,
        critic_revision_count=0,
        steps=(),
    )
    assert detect_hidden_recovery({"outcome": outcome, "audit_calls": []}) is True

    clean = SimpleNamespace(
        critic_actions=(),
        critic_recovery_count=0,
        critic_revision_count=0,
        steps=(),
    )
    assert detect_hidden_recovery({"outcome": clean, "audit_calls": []}) is False


def test_hidden_recovery_detector_fires_on_retry_amplification() -> None:
    action = SimpleNamespace(
        action="RETRIEVE_MISSING_EVIDENCE", status="executed", attempt_count=1
    )
    outcome = SimpleNamespace(
        critic_actions=(action,),
        critic_recovery_count=1,
        critic_revision_count=0,
        steps=(SimpleNamespace(origin="critic_recovery", attempt_count=2),),
    )
    assert detect_hidden_recovery({"outcome": outcome, "audit_calls": [{}]}) is True


# ── historical evidence integrity ────────────────────────────────────────────


def test_formal_artifact_does_not_replace_dry_run_or_history() -> None:
    from tests.w9_critic_p2_r1_harness import FIXTURES

    assert FORMAL_ARTIFACT_NAME in PROTECTED_ARTIFACT_NAMES
    for name in PROTECTED_ARTIFACT_NAMES:
        candidate = FIXTURES / name
        if name.startswith("dry-run"):
            continue
        assert candidate.exists(), f"historical artifact {name} disappeared"

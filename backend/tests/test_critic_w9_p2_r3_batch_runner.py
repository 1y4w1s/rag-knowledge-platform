"""Unit tests for W9 P2-R3 batch runner prep (Lane C dry-run only)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p2_r2_protocol import MeasurementClassification
from tests.w9_critic_p2_r3_batch_runner import (
    C12_CASE_ID,
    FROZEN_CASE_COUNT,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    P2R3BatchRunner,
    ProbeClassification,
    aggregate_batch_results,
    build_synthetic_case_record,
    classify_case_eligibility,
    enumerate_frozen_eligibility,
    evaluate_completeness_gates,
    validate_case_record_schema,
    verify_eligibility_split,
)


def test_frozen_suite_has_twelve_cases() -> None:
    suite = load_frozen_suite()
    assert len(suite.cases) == FROZEN_CASE_COUNT


def test_eligibility_split_is_eleven_plus_one() -> None:
    eligibility = enumerate_frozen_eligibility()
    split = verify_eligibility_split(eligibility)
    assert split == {
        "frozen_cases": 12,
        "product_path_eligible": 11,
        "protocol_invalid": 1,
    }


def test_c12_is_protocol_invalid_probe_not_in_product_denominator() -> None:
    eligibility = enumerate_frozen_eligibility()
    c12 = next(item for item in eligibility if item.case_id == C12_CASE_ID)
    assert c12.product_path_eligible is False
    assert c12.measurement_valid is False
    assert c12.classification == MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
    assert c12.probe_classification is ProbeClassification.DEFENSE_IN_DEPTH_PROBE
    assert c12.in_product_capability_denominator is False


def test_c01_through_c11_are_product_path_eligible() -> None:
    eligibility = enumerate_frozen_eligibility()
    for item in eligibility:
        if item.case_id == C12_CASE_ID:
            continue
        assert item.product_path_eligible is True
        assert item.measurement_valid is True
        assert item.in_product_capability_denominator is True
        assert item.classification is None


def test_synthetic_record_schema_has_required_fields() -> None:
    suite = load_frozen_suite()
    case = suite.cases[0]
    eligibility = classify_case_eligibility(
        case, oracle=suite.oracle[str(case["case_id"])]
    )
    record = build_synthetic_case_record(
        eligibility, oracle=suite.oracle[str(case["case_id"])]
    )
    validate_case_record_schema(record.to_dict())


def test_aggregate_empty_execution_is_incomplete() -> None:
    eligibility = enumerate_frozen_eligibility()
    records = tuple(
        build_synthetic_case_record(item, executed=False) for item in eligibility
    )
    aggregate = aggregate_batch_results(records)
    assert aggregate.frozen_cases == 12
    assert aggregate.executed_total == 0
    assert aggregate.eligible_expected == 11
    assert aggregate.eligible_executed == 0
    assert aggregate.protocol_invalid == 1
    assert aggregate.valid == 11
    assert aggregate.passed == 0
    assert aggregate.failed == 0
    assert aggregate.unsafe_accepts == 0
    assert aggregate.hidden_recovery_count == 0
    assert aggregate.batch_complete is False
    assert aggregate.full_denominator_pass is False


def test_aggregate_full_eligible_pass() -> None:
    eligibility = enumerate_frozen_eligibility()
    records = []
    for item in eligibility:
        executed = item.product_path_eligible
        records.append(
            build_synthetic_case_record(
                item,
                executed=executed,
            )
        )
    aggregate = aggregate_batch_results(records)
    assert aggregate.executed_total == 11
    assert aggregate.eligible_executed == 11
    assert aggregate.batch_complete is True
    assert aggregate.passed == 11
    assert aggregate.failed == 0
    assert aggregate.full_denominator_pass is True


def test_aggregate_partial_eligible_execution_blocks_full_pass() -> None:
    eligibility = enumerate_frozen_eligibility()
    records = []
    for index, item in enumerate(eligibility):
        executed = item.product_path_eligible and index < 5
        records.append(build_synthetic_case_record(item, executed=executed))
    aggregate = aggregate_batch_results(records)
    assert aggregate.eligible_executed == 5
    assert aggregate.batch_complete is False
    assert aggregate.full_denominator_pass is False


def test_aggregate_counts_unsafe_accepts_and_hidden_recovery() -> None:
    eligibility = enumerate_frozen_eligibility()
    records = []
    for item in eligibility:
        record = build_synthetic_case_record(
            item,
            executed=item.product_path_eligible,
        )
        if item.case_id.endswith("fully-supported-exact"):
            record = replace(
                record,
                classification=MeasurementClassification.UNSAFE_ACCEPT.value,
                pass_=False,
                hidden_recovery=True,
            )
        records.append(record)
    aggregate = aggregate_batch_results(records)
    assert aggregate.unsafe_accepts == 1
    assert aggregate.hidden_recovery_count == 1
    assert aggregate.full_denominator_pass is False


def test_completeness_gates_valid_for_expected_denominator() -> None:
    eligibility = enumerate_frozen_eligibility()
    records = tuple(
        build_synthetic_case_record(item, executed=False) for item in eligibility
    )
    aggregate = aggregate_batch_results(records)
    gates = evaluate_completeness_gates(aggregate)
    assert gates.eligible_expected_ok is True
    assert gates.eligible_executed_ok is True
    assert gates.full_denominator_pass_ok is True
    assert gates.valid is True
    assert gates.reasons == ()


def test_completeness_gate_rejects_false_full_denominator_pass() -> None:
    from tests.w9_critic_p2_r3_batch_runner import BatchAggregate

    aggregate = BatchAggregate(
        frozen_cases=12,
        executed_total=5,
        eligible_expected=11,
        eligible_executed=5,
        protocol_invalid=1,
        valid=11,
        passed=5,
        failed=0,
        unsafe_accepts=0,
        hidden_recovery_count=0,
        batch_complete=False,
        full_denominator_pass=True,
    )
    gates = evaluate_completeness_gates(aggregate)
    assert gates.valid is False
    assert any("FULL_DENOMINATOR_PASS" in reason for reason in gates.reasons)


def test_dry_run_plan_does_not_execute_measurement() -> None:
    runner = P2R3BatchRunner(dry_run=True)
    plan = runner.plan_batch()
    assert plan["dry_run"] is True
    assert plan["formal_measurement"] is False
    assert plan["eligibility_split"]["product_path_eligible"] == 11
    assert plan["aggregate"]["eligible_expected"] == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert plan["completeness_gates"]["valid"] is True
    assert all(not item["executed"] for item in plan["case_records"])


def test_artifact_writer_rejects_formal_name(tmp_path: Path) -> None:
    runner = P2R3BatchRunner()
    with pytest.raises(ValueError, match="forbidden formal artifact"):
        runner.write_artifact(tmp_path / "w9-critic-p2-r3-final.json", {"x": 1})


def test_artifact_writer_accepts_dry_run_prefix(tmp_path: Path) -> None:
    runner = P2R3BatchRunner()
    path = runner.write_artifact(
        tmp_path / "dry-run-batch-plan.json",
        runner.plan_batch(),
    )
    assert path.exists()

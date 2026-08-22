"""W8 P6 Golden contract validity / Gate G — deterministic tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.contract_validity.adversarial import (
    MOCK_NEGATIVE_RETRIEVAL_VALIDITY,
    adversarial_probe_case_ids,
    build_adversarial_characterization,
)
from app.eval.contract_validity.golden_contracts import (
    ADVERSARIAL_FORMAL_CONTRACT,
    BGE_PROBE_QUERY_GROUP_COUNT,
)
from app.eval.contract_validity.memory_contract import (
    MEMORY_CASE_BY_ID,
    memory_contract_records,
)
from app.eval.contract_validity.metric_validity import (
    METRIC_VALIDITY_MATRIX,
    metric_validity_by_name,
)
from app.eval.contract_validity.models import (
    FORBIDDEN_MEMORY_TAXONOMY,
    MeasurementLayer,
    MemoryCaseKind,
    PrimaryToolContractClass,
    Validity,
)
from app.eval.contract_validity.runner import (
    BENCHMARK_SEMANTICS_SHA,
    VALIDATED_MERGED_MASTER_SHA,
    build_contract_validity_report,
)
from app.eval.contract_validity.schema_baseline import schema_characterization_baseline
from app.eval.contract_validity.tool_contract import (
    TOOL_CASE_BY_ID,
    tool_contract_records,
    tool_primary_counts,
)
from tests.golden_agent_qa_loader import GOLDEN_AGENT_QA_JSON, load_golden_agent_cases


def test_tool_twenty_cases_exactly_one_primary_class() -> None:
    records = tool_contract_records()
    assert len(records) == 20
    for record in records:
        assert isinstance(record.primary_contract_class, PrimaryToolContractClass)
        assert record.primary_contract_class != PrimaryToolContractClass.UNKNOWN


def test_tool_primary_count_sum_equals_twenty() -> None:
    counts = tool_primary_counts()
    assert sum(counts.values()) == 20
    assert counts == {
        "CURRENT_L3_NATIVE": 3,
        "INTEGRATION_ONLY": 5,
        "STALE_GOLDEN_CONTRACT": 5,
        "UNSATISFIABLE_CURRENT_CONTRACT": 7,
    }


def test_tool_secondary_tags_may_overlap_without_affecting_denominator() -> None:
    records = tool_contract_records()
    fixture_tag_hits = sum(
        1 for r in records if "FIXTURE_MISMATCH" in [t.value for t in r.secondary_tags]
    )
    api_tag_hits = sum(
        1 for r in records if "API_SURFACE_CONTRACT" in [t.value for t in r.secondary_tags]
    )
    assert fixture_tag_hits == 20
    assert api_tag_hits == 20
    assert len(records) == 20


def test_memory_seeded_vs_empty_classification() -> None:
    seeded = [r for r in memory_contract_records() if r.case_kind == MemoryCaseKind.SEEDED_MEMORY_CASE]
    empty = [r for r in memory_contract_records() if r.case_kind == MemoryCaseKind.EMPTY_MEMORY_CASE]
    assert {r.case_id for r in seeded} == {"GA-9", "GA-10"}
    assert {r.case_id for r in empty} == {"GA-11", "GA-12"}


def test_empty_memory_case_l4_utilization_not_applicable() -> None:
    for case_id in ("GA-11", "GA-12"):
        record = MEMORY_CASE_BY_ID[case_id]
        assert record.l4_utilization_applicable is False
        assert (
            record.layer_validity[MeasurementLayer.L4_UTILIZATION.value]
            == Validity.UNIT_ONLY
        )
        assert MeasurementLayer.EMPTY_MEMORY_BEHAVIOR.value in record.layer_validity


def test_forbidden_memory_taxonomy_model_ignores_memory_tool() -> None:
    assert "MODEL_IGNORES_MEMORY_TOOL" in FORBIDDEN_MEMORY_TAXONOMY
    for record in memory_contract_records():
        for tag in record.allowed_taxonomy:
            assert tag not in FORBIDDEN_MEMORY_TAXONOMY


def test_adversarial_original_metric_invalid_for_capability() -> None:
    adv = build_adversarial_characterization()
    assert adv.original_pass_count == 1
    assert adv.original_pass_total == 20
    assert adv.original_metric_validity == Validity.INVALID_FOR_CAPABILITY
    assert ADVERSARIAL_FORMAL_CONTRACT["original_metric_validity"] == "INVALID_FOR_CAPABILITY"


def test_mock_negative_retrieval_validity_invalid() -> None:
    adv = build_adversarial_characterization()
    assert adv.mock_negative_retrieval_validity == MOCK_NEGATIVE_RETRIEVAL_VALIDITY
    assert adv.mock_negative_retrieval_validity == Validity.INVALID_FOR_CAPABILITY


def test_bge_initial_state_candidate_not_proven_by_default() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    adv = build_adversarial_characterization(repo_root=repo_root, bge_proven=False)
    assert adv.bge_candidate_available is True
    assert adv.bge_capability_valid_proven is False


def test_schema_baseline_frozen_p5_numbers() -> None:
    baseline = schema_characterization_baseline()
    assert baseline.total_decisions == 226
    assert baseline.failure_count == 9
    assert baseline.failure_rate == pytest.approx(9 / 226)
    assert len(baseline.failure_subtypes) == 1
    subtype = baseline.failure_subtypes[0]
    assert subtype.subtype == "TOOL_NAME_AS_ACTION"
    assert subtype.count == 9
    assert set(subtype.affected_case_ids) == {
        "GQ-98",
        "GQ-99",
        "GQ-100",
        "GQ-102",
        "GQ-103",
        "GQ-106",
        "GQ-132",
        "GA-9",
        "GA-10",
    }
    assert baseline.benchmark_semantics_sha == BENCHMARK_SEMANTICS_SHA
    assert baseline.validated_merged_master == VALIDATED_MERGED_MASTER_SHA


def test_metric_matrix_key_entries_have_measures_and_validity() -> None:
    by_name = metric_validity_by_name()
    required = [
        "RAG Golden pass",
        "RETRIEVAL Golden pass",
        "ADVERSARIAL original pass",
        "TOOL original pass",
        "MEMORY original pass",
        "Planner parse rate",
        "Safe termination",
        "Evidence-driven unsafe finish",
        "Matcher FP",
        "Matcher FN",
    ]
    for name in required:
        entry = by_name[name]
        assert entry.measures
        assert entry.does_not_measure
        assert entry.validity in Validity
    assert len(METRIC_VALIDITY_MATRIX) >= len(required)


def test_no_golden_mutation_against_loader() -> None:
    cases = load_golden_agent_cases()
    assert len(cases) == 168
    raw = json.loads(GOLDEN_AGENT_QA_JSON.read_text(encoding="utf-8"))
    assert len(raw["cases"]) == 168
    tool_ids = {c.case_id for c in cases if c.category == "TOOL"}
    assert tool_ids == {f"GQ-{n}" for n in range(131, 151)}


def test_bge_probe_query_groups_twenty_eight() -> None:
    assert len(adversarial_probe_case_ids()) == BGE_PROBE_QUERY_GROUP_COUNT == 28


def test_build_contract_validity_report_structure() -> None:
    report = build_contract_validity_report(
        repo_root=Path(__file__).resolve().parents[1],
    )
    assert report["validated_merged_master"] == VALIDATED_MERGED_MASTER_SHA
    assert report["benchmark_semantics_sha"] == BENCHMARK_SEMANTICS_SHA
    assert report["p5_results_remain_valid"] is True
    assert report["tool"]["primary_counts"]["CURRENT_L3_NATIVE"] == 3
    assert report["memory"]["seeded_cases"] == 2
    assert report["memory"]["empty_cases"] == 2


def test_tool_cases_align_with_golden_expected_chunk() -> None:
    by_id = {c.case_id: c for c in load_golden_agent_cases()}
    for record in tool_contract_records():
        golden = by_id[record.case_id]
        assert golden.category == "TOOL"
        assert record.expected_chunk == golden.expected_chunk
        assert TOOL_CASE_BY_ID[record.case_id].case_id == record.case_id

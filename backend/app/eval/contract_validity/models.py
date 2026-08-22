"""W8 P6 contract validity data model (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Validity(str, Enum):
    VALID_MEASUREMENT = "VALID_MEASUREMENT"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    INVALID_FOR_CAPABILITY = "INVALID_FOR_CAPABILITY"
    LEGACY_ONLY = "LEGACY_ONLY"
    UNIT_ONLY = "UNIT_ONLY"
    UNKNOWN = "UNKNOWN"


class PrimaryToolContractClass(str, Enum):
    CURRENT_L3_NATIVE = "CURRENT_L3_NATIVE"
    LEGACY_AGENT_ONLY = "LEGACY_AGENT_ONLY"
    INTEGRATION_ONLY = "INTEGRATION_ONLY"
    UNSATISFIABLE_CURRENT_CONTRACT = "UNSATISFIABLE_CURRENT_CONTRACT"
    STALE_GOLDEN_CONTRACT = "STALE_GOLDEN_CONTRACT"
    UNKNOWN = "UNKNOWN"


class ToolSecondaryTag(str, Enum):
    STALE_EXPECTATION = "STALE_EXPECTATION"
    API_SURFACE_CONTRACT = "API_SURFACE_CONTRACT"
    READ_WRITE_MISMATCH = "READ_WRITE_MISMATCH"
    OBSERVATION_UNREPRESENTABLE = "OBSERVATION_UNREPRESENTABLE"
    MISSING_AGENT_TOOL = "MISSING_AGENT_TOOL"
    FIXTURE_MISMATCH = "FIXTURE_MISMATCH"
    SCORER_TOO_COARSE = "SCORER_TOO_COARSE"
    HTTP_STATUS_EXPECTATION = "HTTP_STATUS_EXPECTATION"


class MemoryCaseKind(str, Enum):
    SEEDED_MEMORY_CASE = "SEEDED_MEMORY_CASE"
    EMPTY_MEMORY_CASE = "EMPTY_MEMORY_CASE"


class MeasurementLayer(str, Enum):
    L1_SEEDING = "L1_SEEDING"
    L2_LOADING = "L2_LOADING"
    L3_EXPOSURE = "L3_EXPOSURE"
    L4_UTILIZATION = "L4_UTILIZATION"
    L5_TASK_SUCCESS = "L5_TASK_SUCCESS"
    EMPTY_MEMORY_BEHAVIOR = "EMPTY_MEMORY_BEHAVIOR"


class AdversarialRetrievalOutcome(str, Enum):
    NO_RETRIEVAL = "NO_RETRIEVAL"
    NO_HIT = "NO_HIT"
    RETRIEVED_BUT_REJECTED = "RETRIEVED_BUT_REJECTED"
    RETRIEVED_IRRELEVANT = "RETRIEVED_IRRELEVANT"
    RETRIEVED_RELEVANT = "RETRIEVED_RELEVANT"
    RETRIEVED_AND_CITED = "RETRIEVED_AND_CITED"


class MemoryTaxonomy(str, Enum):
    MEMORY_SEED_FAILURE = "MEMORY_SEED_FAILURE"
    MEMORY_LOAD_FAILURE = "MEMORY_LOAD_FAILURE"
    MEMORY_SCOPE_MISMATCH = "MEMORY_SCOPE_MISMATCH"
    MEMORY_NOT_EXPOSED = "MEMORY_NOT_EXPOSED"
    MODEL_IGNORES_INJECTED_MEMORY = "MODEL_IGNORES_INJECTED_MEMORY"
    MODEL_CONTRADICTS_INJECTED_MEMORY = "MODEL_CONTRADICTS_INJECTED_MEMORY"
    MODEL_RETRIEVAL_LOOP_DESPITE_MEMORY = "MODEL_RETRIEVAL_LOOP_DESPITE_MEMORY"
    EMPTY_MEMORY_SAFE_BEHAVIOR = "EMPTY_MEMORY_SAFE_BEHAVIOR"
    EMPTY_MEMORY_UNPRODUCTIVE_LOOP = "EMPTY_MEMORY_UNPRODUCTIVE_LOOP"
    MEMORY_TASK_SUCCESS = "MEMORY_TASK_SUCCESS"
    UNKNOWN = "UNKNOWN"


FORBIDDEN_MEMORY_TAXONOMY: frozenset[str] = frozenset({"MODEL_IGNORES_MEMORY_TOOL"})


@dataclass(frozen=True, slots=True)
class ContractValidityRecord:
    case_id: str
    golden_category: str
    primary_contract_class: str
    secondary_tags: tuple[str, ...]
    measurement_target: str
    capability_measurable: bool
    validity: Validity
    reason: str
    required_observation: str
    current_runtime_support: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validity"] = self.validity.value
        return payload


@dataclass(frozen=True, slots=True)
class MetricValidityEntry:
    metric: str
    measures: str
    does_not_measure: str
    validity: Validity
    scope: str
    source: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validity"] = self.validity.value
        return payload


@dataclass(frozen=True, slots=True)
class SchemaFailureSubtype:
    subtype: str
    count: int
    affected_case_ids: tuple[str, ...]
    step_positions: tuple[int, ...] = ()
    raw_output_hashes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaCharacterizationBaseline:
    total_decisions: int
    failure_count: int
    failure_rate: float
    failure_subtypes: tuple[SchemaFailureSubtype, ...]
    source_benchmark: str
    benchmark_semantics_sha: str
    validated_merged_master: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "failure_count": self.failure_count,
            "failure_rate": self.failure_rate,
            "failure_subtypes": [
                {
                    "subtype": s.subtype,
                    "count": s.count,
                    "affected_case_ids": list(s.affected_case_ids),
                    "step_positions": list(s.step_positions),
                    "raw_output_hashes": list(s.raw_output_hashes),
                }
                for s in self.failure_subtypes
            ],
            "source_benchmark": self.source_benchmark,
            "benchmark_semantics_sha": self.benchmark_semantics_sha,
            "validated_merged_master": self.validated_merged_master,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ToolContractRecord:
    case_id: str
    expected_chunk: str
    expected_semantic_type: str
    required_tool_or_surface: str
    tool_exists_in_repo: bool
    tool_exposed_to_current_l3: bool
    fixture_contains_expected_signal: bool
    observation_can_represent_expected: bool
    primary_contract_class: PrimaryToolContractClass
    secondary_tags: tuple[ToolSecondaryTag, ...]
    capability_measurable: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "expected_chunk": self.expected_chunk,
            "expected_semantic_type": self.expected_semantic_type,
            "required_tool_or_surface": self.required_tool_or_surface,
            "tool_exists_in_repo": self.tool_exists_in_repo,
            "tool_exposed_to_current_l3": self.tool_exposed_to_current_l3,
            "fixture_contains_expected_signal": self.fixture_contains_expected_signal,
            "observation_can_represent_expected": self.observation_can_represent_expected,
            "primary_contract_class": self.primary_contract_class.value,
            "secondary_tags": [t.value for t in self.secondary_tags],
            "capability_measurable": self.capability_measurable,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MemoryContractRecord:
    case_id: str
    case_kind: MemoryCaseKind
    pre_seed_count: int
    expected_chunk_marker: str
    layer_validity: dict[str, Validity]
    l4_utilization_applicable: bool
    measurement_targets: tuple[str, ...]
    allowed_taxonomy: tuple[str, ...]
    capability_measurable: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": self.case_kind.value,
            "pre_seed_count": self.pre_seed_count,
            "expected_chunk_marker": self.expected_chunk_marker,
            "layer_validity": {k: v.value for k, v in self.layer_validity.items()},
            "l4_utilization_applicable": self.l4_utilization_applicable,
            "measurement_targets": list(self.measurement_targets),
            "allowed_taxonomy": list(self.allowed_taxonomy),
            "capability_measurable": self.capability_measurable,
            "reason": self.reason,
        }


@dataclass(slots=True)
class AdversarialContractCharacterization:
    original_pass_count: int
    original_pass_total: int
    original_metric_validity: Validity
    mock_negative_retrieval_validity: Validity
    bge_candidate_available: bool
    bge_capability_valid_proven: bool
    retrieval_threshold_semantics: str
    primary_conclusion: str
    formal_contract: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_pass_count": self.original_pass_count,
            "original_pass_total": self.original_pass_total,
            "original_metric_validity": self.original_metric_validity.value,
            "mock_negative_retrieval_validity": self.mock_negative_retrieval_validity.value,
            "bge_candidate_available": self.bge_candidate_available,
            "bge_capability_valid_proven": self.bge_capability_valid_proven,
            "retrieval_threshold_semantics": self.retrieval_threshold_semantics,
            "primary_conclusion": self.primary_conclusion,
            "formal_contract": self.formal_contract,
        }

"""L4 MEMORY utilization evaluator schema (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class MeasurementLevel(str, Enum):
    """Independent measurement levels — L1 pass does not imply L2, etc."""

    L1_SEEDED = "L1_SEEDED"
    L2_LOADED = "L2_LOADED"
    L3_EXPOSED = "L3_EXPOSED"
    L4_UTILIZED = "L4_UTILIZED"
    L5_TASK_BENEFIT = "L5_TASK_BENEFIT"


class PropositionKind(str, Enum):
    language_preference = "language_preference"
    topic_preference = "topic_preference"
    generic_preference = "generic_preference"


@dataclass(frozen=True, slots=True)
class MemorySeed:
    key: str
    memory_type: str
    value: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "memory_type": self.memory_type, "value": self.value}


@dataclass(frozen=True, slots=True)
class MemoryProposition:
    """Structured proposition derived from a seeded memory item."""

    key: str
    kind: PropositionKind
    expected: str
    memory_type: str = "preference"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind.value,
            "expected": self.expected,
            "memory_type": self.memory_type,
        }


@dataclass(frozen=True, slots=True)
class LevelResult:
    level: MeasurementLevel
    eligible: bool
    attempted: bool
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["level"] = self.level.value
        return payload


@dataclass(slots=True)
class MemoryTrajectoryInput:
    case_id: str
    query: str
    seeded_memories: tuple[MemorySeed, ...] = ()
    seed_succeeded: bool = True
    loaded_memories: tuple[MemorySeed, ...] = ()
    exposed_context: str = ""
    output_text: str = ""
    tool_query: str | None = None
    empty_memory_case: bool = False
    safe_termination: bool = True
    no_fabricated_memory: bool = True
    task_contract_passed: bool = False


@dataclass(slots=True)
class CounterfactualPair:
    """WITH_MEMORY vs WITHOUT_MEMORY for L5 task benefit."""

    case_id: str
    with_memory: MemoryTrajectoryInput
    without_memory: MemoryTrajectoryInput


@dataclass(slots=True)
class UtilizationAnalysis:
    semantic_utilized: bool
    keyword_overlap_only: bool
    contradicted: bool
    matched_propositions: tuple[str, ...] = ()
    reason: str = ""


@dataclass(slots=True)
class CaseEvaluation:
    case_id: str
    levels: tuple[LevelResult, ...]
    utilization: UtilizationAnalysis | None = None
    false_utilization: bool = False
    l4_applicable: bool = True
    l5_applicable: bool = True

    def level_map(self) -> dict[str, LevelResult]:
        return {level.level.value: level for level in self.levels}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "levels": [level.to_dict() for level in self.levels],
            "utilization": None
            if self.utilization is None
            else {
                "semantic_utilized": self.utilization.semantic_utilized,
                "keyword_overlap_only": self.utilization.keyword_overlap_only,
                "contradicted": self.utilization.contradicted,
                "matched_propositions": list(self.utilization.matched_propositions),
                "reason": self.utilization.reason,
            },
            "false_utilization": self.false_utilization,
            "l4_applicable": self.l4_applicable,
            "l5_applicable": self.l5_applicable,
        }


@dataclass(frozen=True, slots=True)
class MetricCount:
    metric: str
    eligible: int
    attempted: int
    passed: int

    @property
    def rate(self) -> float:
        if self.attempted <= 0:
            return 0.0
        return round(self.passed / self.attempted, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "eligible": self.eligible,
            "attempted": self.attempted,
            "passed": self.passed,
            "rate": self.rate,
        }


@dataclass(slots=True)
class SuiteMetrics:
    case_count: int
    metrics: tuple[MetricCount, ...]
    false_utilization_count: int

    def metric_map(self) -> dict[str, MetricCount]:
        return {metric.metric: metric for metric in self.metrics}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "false_utilization_count": self.false_utilization_count,
        }

"""MEMORY P4 offline utilization ablation — models (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


P3_LINEAGE_SOURCE = "test/agent-l4-memory-p3-real-capability@38b2d4a"
STAGE = "MEMORY_P4_OFFLINE_UTILIZATION_ABLATION"
CORPUS_SCHEMA = "memory-p4-frozen-corpus-v1"


class RootCauseTaxonomy(str, Enum):
    M1_EXPOSURE_BUT_NOT_ATTENDED = "M1_EXPOSURE_BUT_NOT_ATTENDED"
    M2_FORMAT_SALIENCE_FAILURE = "M2_FORMAT_SALIENCE_FAILURE"
    M3_TASK_RELEVANCE_LINK_FAILURE = "M3_TASK_RELEVANCE_LINK_FAILURE"
    M4_INSTRUCTION_PRIORITY_CONFLICT = "M4_INSTRUCTION_PRIORITY_CONFLICT"
    M5_CONTEXT_POSITION_EFFECT = "M5_CONTEXT_POSITION_EFFECT"
    M6_MODEL_CAPABILITY_LIMIT = "M6_MODEL_CAPABILITY_LIMIT"


class CandidateId(str, Enum):
    C0_BASELINE = "C0_BASELINE_FROZEN_FORMAT"
    C1_CONTRASTIVE_LABEL = "C1_CONTRASTIVE_MEMORY_RELEVANCE_LABEL"
    C2_STRUCTURED_BLOCK = "C2_STRUCTURED_PROPOSITION_BLOCK"
    C3_TASK_BINDING = "C3_MEMORY_TO_TASK_BINDING_HINT"
    C4_PLACEMENT = "C4_MEMORY_PLACEMENT_ABLATION"
    C5_DECISION_FIELD = "C5_EXPLICIT_MEMORY_USE_DECISION_FIELD"
    C6_RELEVANCE_FILTER = "C6_DETERMINISTIC_TASK_MEMORY_RELEVANCE_FILTER"


class Verdict(str, Enum):
    READY_FOR_PRODUCT_EXPERIMENT = "READY_FOR_PRODUCT_EXPERIMENT"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    REJECT = "REJECT"


class BlindSpot(str, Enum):
    NO = "NO"
    PARTIAL = "PARTIAL"
    YES = "YES"


@dataclass(frozen=True, slots=True)
class MemorySeed:
    key: str
    memory_type: str
    value: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FrozenTrial:
    case_id: str
    trial_index: int
    condition: str
    l3_passed: bool
    l4_passed: bool
    l5_passed: bool
    query: str
    seeds: tuple[MemorySeed, ...]
    propositions: tuple[dict[str, Any], ...]
    output_excerpt: str
    tool_query: str | None
    terminal_action: str | None
    capped: bool
    steps: tuple[dict[str, Any], ...]
    exposure_event_count: int


@dataclass(frozen=True, slots=True)
class InfoFlowRecord:
    case_id: str
    trial_index: int
    condition: str
    seeded_proposition: str
    loaded: bool
    formatted_preview: str
    prompt_placement: str
    distance_to_task: str
    query: str
    planner_instruction_conflict: str
    memory_section_present: bool
    other_context: str
    raw_planner_output_excerpt: str
    final_behavior: str
    utilization_verdict: bool
    benefit_verdict: bool
    dominant_taxonomy: RootCauseTaxonomy
    supporting_taxonomy: tuple[RootCauseTaxonomy, ...]


@dataclass(slots=True)
class CandidateScore:
    candidate_id: str
    apparent_utilization_recovery: float
    evaluator_valid_recovery: float
    false_utilization_on_hard_negatives: float
    prompt_invasiveness: str
    autonomy_impact: str
    privacy_impact: str
    implementation_complexity: str
    removes_instruction_conflict: bool
    improves_task_binding: bool
    forces_answer_content: bool
    bypasses_planner_autonomy: bool
    verdict: Verdict
    rationale: str
    details: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AblationReport:
    stage: str
    corpus_trials: int
    dominant_root_cause: RootCauseTaxonomy
    supporting_root_causes: tuple[RootCauseTaxonomy, ...]
    evaluator_blind_spot: BlindSpot
    evaluator_audit_notes: list[str]
    info_flows: list[InfoFlowRecord]
    scores: list[CandidateScore]
    primary: str | None
    fallback: str | None
    ready_for_product_experiment: bool
    l5_fixed: bool
    product_diff: int
    selection_rationale: str

"""W8 P7 schema ablation dataclasses and frozen parser contract documentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Frozen Gate G baseline — must not change in P7.
PRE_REPAIR_PLANNER_DECISIONS = 226
PRE_REPAIR_PARSE_FAILURES = 9
PRE_REPAIR_TOOL_NAME_AS_ACTION = 9

BASE_MASTER_SHA = "76f4bdb18042370a55547302754ebefd5aba7fc8"
BENCHMARK_SEMANTICS_SHA = "1b4f28dd988ebdda015018a228859f05bc3c9905"

# Audit: product parse chain for NextActionPlanner (frozen reference).
PARSER_CONTRACT_CHAIN: tuple[str, ...] = (
    "raw LLM text",
    "_strip_llm_json_fence (markdown fence removal — product baseline)",
    "json.loads → dict (fail: parse_error)",
    "reject list root (fail: not_single_object)",
    "action: str required (fail: invalid_action)",
    "AgentActionKind(action) enum (fail: invalid_action — TOOL_NAME_AS_ACTION fails here)",
    "tool_name / args / reason_code / user_message field typing",
    "if action==tool: require tool_name + _validate_tool_args (fail: missing_tool_name / invalid_args)",
    "if action in finish|clarify|refuse: strip tool_name/args",
    "AgentDecision dataclass",
    "SafetyFrame.validate_decision + ToolResolver.available_names scope check",
)

TOOL_NAME_AS_ACTION_FAILURE_LAYER = (
    "AgentActionKind enum validation inside parse_agent_decision "
    "(after JSON decode succeeds; action string is a registered tool name, not tool|finish|clarify|refuse)"
)


class CandidateKind(str, Enum):
    strict = "STRICT"
    narrow = "NARROW_CANONICALIZATION"  # A1 — missing tool_name only
    duplicate_consistent = "DUPLICATE_CONSISTENT_CANONICALIZATION"  # A2
    broad = "BROAD_CONTROL"
    prompt = "PROMPT_REINFORCEMENT"


class ExpectedOutcome(str, Enum):
    reject = "REJECT"
    accept = "ACCEPT"
    passthrough = "PASSTHROUGH"


@dataclass(frozen=True, slots=True)
class SchemaSample:
    sample_id: str
    raw_output: str
    raw_output_hash: str
    source: str  # TARGET_FAILURE | VALID_PASSTHROUGH | HARD_NEGATIVE
    case_id: str | None = None
    step_index: int | None = None
    expected: ExpectedOutcome = ExpectedOutcome.reject
    failure_dimension: str | None = None
    decoded_json: dict[str, Any] | None = None
    lineage: str = ""


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    parse_ok: bool
    error: str | None
    decision: dict[str, Any] | None
    repair_applied: bool
    semantic_mutation: bool
    false_repair: bool


@dataclass(slots=True)
class CandidateMetrics:
    kind: CandidateKind
    target_failure_count: int = 0
    target_recovered_count: int = 0
    valid_passthrough_count: int = 0
    valid_passthrough_preserved: int = 0
    hard_negative_count: int = 0
    false_repair_count: int = 0
    unknown_tool_accept_count: int = 0
    conflict_accept_count: int = 0
    invalid_arguments_accept_count: int = 0
    out_of_scope_tool_accept_count: int = 0
    semantic_mutation_count: int = 0
    transform_applied_count: int = 0
    final_valid_count: int = 0
    non_tool_action_mutation_count: int = 0
    missing_tool_recovered_count: int = 0
    duplicate_recovered_count: int = 0

    @property
    def target_recovery_rate(self) -> float:
        if self.target_failure_count == 0:
            return 0.0
        return self.target_recovered_count / self.target_failure_count

    @property
    def valid_passthrough_rate(self) -> float:
        if self.valid_passthrough_count == 0:
            return 0.0
        return self.valid_passthrough_preserved / self.valid_passthrough_count

    @property
    def false_repair_rate(self) -> float:
        if self.hard_negative_count == 0:
            return 0.0
        return self.false_repair_count / self.hard_negative_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.kind.value,
            "target_failure_count": self.target_failure_count,
            "target_recovered_count": self.target_recovered_count,
            "target_recovery_rate": self.target_recovery_rate,
            "valid_passthrough_count": self.valid_passthrough_count,
            "valid_passthrough_preserved": self.valid_passthrough_preserved,
            "valid_passthrough_rate": self.valid_passthrough_rate,
            "hard_negative_count": self.hard_negative_count,
            "false_repair_count": self.false_repair_count,
            "false_repair_rate": self.false_repair_rate,
            "unknown_tool_accept_count": self.unknown_tool_accept_count,
            "conflict_accept_count": self.conflict_accept_count,
            "invalid_arguments_accept_count": self.invalid_arguments_accept_count,
            "out_of_scope_tool_accept_count": self.out_of_scope_tool_accept_count,
            "semantic_mutation_count": self.semantic_mutation_count,
            "transform_applied_count": self.transform_applied_count,
            "final_valid_count": self.final_valid_count,
            "non_tool_action_mutation_count": self.non_tool_action_mutation_count,
            "missing_tool_recovered_count": self.missing_tool_recovered_count,
            "duplicate_recovered_count": self.duplicate_recovered_count,
        }


@dataclass(slots=True)
class TargetFailureReport:
    case_id: str
    step_index: int
    original_action: str | None
    tool_name_recognized: str | None
    allowed_in_scope: bool
    repair_applied: bool
    post_repair_parse_valid: bool
    tool_args_valid: bool
    semantic_change: bool
    result: str


@dataclass(slots=True)
class HardNegativeReport:
    negative_id: str
    failure_dimension: str
    candidate_a1_result: str
    candidate_a2_result: str
    candidate_b_result: str
    expected: str = ExpectedOutcome.reject.value
    safety_failure: bool = False


@dataclass(slots=True)
class AblationReport:
    base_master_sha: str
    pre_repair_baseline: dict[str, Any]
    dataset: dict[str, Any]
    strict: CandidateMetrics
    narrow: CandidateMetrics
    duplicate_consistent: CandidateMetrics
    broad: CandidateMetrics
    target_failure_reports: list[TargetFailureReport] = field(default_factory=list)
    hard_negative_reports: list[HardNegativeReport] = field(default_factory=list)
    recommendation: dict[str, Any] = field(default_factory=dict)
    gate_h: dict[str, Any] = field(default_factory=dict)

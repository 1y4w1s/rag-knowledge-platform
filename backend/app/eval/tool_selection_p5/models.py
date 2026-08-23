"""TOOL Selection P5 — dataclasses (eval-only, Py3.9-safe)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


STAGE = "TOOL_SELECTION_P5_S2_FAILURE_CHARACTERIZATION"
CORPUS_SCHEMA = "l4-tool-p5-s2-failure-corpus-v1"
MANIFEST_SCHEMA = "l4-tool-p5-offline-characterization-v1"

P4_BRANCH = "test/agent-l4-tool-p4-real-revalidation"
P4_TIP_SHA = "888dda1"
# Convergence round base = latest origin/master at TASK B start (rebase target).
ORIGIN_MASTER_SHA = "e4359a8e1262fa7a04f78899eebb7d10d796f89f"
TARGET_CASE = "GQ-131"
TARGET_CONDITIONS = ("10", "11")
EXPECTED_TOOL = "search_documents"
STUBBORN_TOOL = "semantic_search"
DEFAULT_EXPOSED = ("semantic_search", "search_documents", "list_knowledge_bases")

# B6 guardrail — candidates may only claim this readiness; never production claims.
CANDIDATE_STATUS = "READY_FOR_PRODUCT_EXPERIMENT"
FORBIDDEN_CANDIDATE_STATUSES = (
    "FIXED",
    "REAL_VALIDATED",
    "PRODUCTION_READY",
)


class Verdict(str, Enum):
    PRIMARY = "PRIMARY"
    FALLBACK = "FALLBACK"
    REJECT = "REJECT"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"


@dataclass(frozen=True)
class CaptureView:
    step_index: int
    raw_excerpt: str
    parse_ok: bool
    parsed_action: Optional[str]
    parsed_tool: Optional[str]
    parsed_args: Dict[str, Any]
    reason_code: Optional[str]
    tool_name: Optional[str]
    tool_success: Optional[bool]


@dataclass(frozen=True)
class FrozenTrial:
    case_id: str
    condition: str
    s2_enabled: bool
    t2_enabled: bool
    trial_index: int
    query: str
    expected_tool: str
    first_tool: str
    preferred_hint: Optional[str]
    hint_emitted: bool
    planner_followed_hint: bool
    reason_codes: Tuple[str, ...]
    tool_sequence: Tuple[str, ...]
    raw_first_excerpt: str
    captures: Tuple[CaptureView, ...]


@dataclass(frozen=True)
class SelectionSample:
    sample_id: str
    panel: str
    query: str
    exposed_tools: Tuple[str, ...]
    selected_tool: str
    expected_tool: Optional[str]
    must_not_force_tool: Optional[str]
    intent_class: str
    preferred_hint: Optional[str] = None
    notes: str = ""


@dataclass
class CandidateScore:
    candidate_id: str
    label: str
    target_count: int
    target_recovered: int
    hard_negative_count: int
    hard_negative_regressions: int
    false_preferred_selections: int
    tool_choice_entropy: float
    scope_change: str
    complexity: str
    autonomy_impact: str
    verdict: Verdict
    rationale: str
    status: str = "UNSPECIFIED"
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["target_recovery"] = f"{self.target_recovered}/{self.target_count}"
        d["hard_negative_regression"] = (
            f"{self.hard_negative_regressions}/{self.hard_negative_count}"
        )
        return d

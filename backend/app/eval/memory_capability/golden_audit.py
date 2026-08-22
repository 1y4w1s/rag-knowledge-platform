"""Audit of Golden MEMORY4 cases (GA-9 … GA-12) — read-only characterization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.eval.contract_validity.memory_contract import MEMORY_CASE_BY_ID
from app.eval.memory_capability.contract import LEGACY_MEMORY4_SCORE


@dataclass(frozen=True, slots=True)
class GoldenMemoryCaseAudit:
    case_id: str
    seeded_or_empty: str
    legacy_expected: str
    current_runtime_path: str
    l1_applicable: bool
    l2_applicable: bool
    l3_applicable: bool
    l4_applicable: bool
    l5_applicable: bool
    contract_validity: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "seeded_or_empty": self.seeded_or_empty,
            "legacy_expected": self.legacy_expected,
            "current_runtime_path": self.current_runtime_path,
            "L1_L5_applicability": {
                "L1_SEEDED": self.l1_applicable,
                "L2_LOADED": self.l2_applicable,
                "L3_EXPOSED": self.l3_applicable,
                "L4_UTILIZED": self.l4_applicable,
                "L5_TASK_BENEFIT": self.l5_applicable,
            },
            "contract_validity": self.contract_validity,
            "reason": self.reason,
        }


_RUNTIME_PATH = (
    "pre_seed upsert_memory → load_active_memories → format_memory_context → "
    "planner._memory_context / init_agent_state(memory_context) → planner.decide_next"
)

_GOLDEN_AUDITS: tuple[GoldenMemoryCaseAudit, ...] = (
    GoldenMemoryCaseAudit(
        case_id="GA-9",
        seeded_or_empty="seeded (1 preference: lang=en)",
        legacy_expected="memory_loaded",
        current_runtime_path=_RUNTIME_PATH,
        l1_applicable=True,
        l2_applicable=True,
        l3_applicable=True,
        l4_applicable=True,
        l5_applicable=True,
        contract_validity="PARTIALLY_VALID (L1-L3); INVALID_FOR_UTILIZATION_CAPABILITY (L4-L5 legacy)",
        reason=(
            "Legacy scorer accepts pipeline completion only; L4 requires semantic English "
            "preference in answer, not memory_loaded marker."
        ),
    ),
    GoldenMemoryCaseAudit(
        case_id="GA-10",
        seeded_or_empty="seeded (2 preferences: lang=en, topic=docker)",
        legacy_expected="memory_loaded",
        current_runtime_path=_RUNTIME_PATH,
        l1_applicable=True,
        l2_applicable=True,
        l3_applicable=True,
        l4_applicable=True,
        l5_applicable=True,
        contract_validity="PARTIALLY_VALID (L1-L3); INVALID_FOR_UTILIZATION_CAPABILITY (L4-L5 legacy)",
        reason=(
            "Dual preferences; utilization requires topic bias toward docker in search/answer, "
            "not dual memory_loaded signal."
        ),
    ),
    GoldenMemoryCaseAudit(
        case_id="GA-11",
        seeded_or_empty="empty (pre_seed_memories=[])",
        legacy_expected="memory_empty",
        current_runtime_path=_RUNTIME_PATH,
        l1_applicable=True,
        l2_applicable=True,
        l3_applicable=True,
        l4_applicable=False,
        l5_applicable=False,
        contract_validity="VALID_MEASUREMENT (empty behavior L1-L3); L4-L5 N/A",
        reason="Empty by design; evaluate no fabrication + safe clarify, not utilization.",
    ),
    GoldenMemoryCaseAudit(
        case_id="GA-12",
        seeded_or_empty="empty (pre_seed_memories=[])",
        legacy_expected="memory_empty",
        current_runtime_path=_RUNTIME_PATH,
        l1_applicable=True,
        l2_applicable=True,
        l3_applicable=True,
        l4_applicable=False,
        l5_applicable=False,
        contract_validity="VALID_MEASUREMENT (empty behavior L1-L3); L4-L5 N/A",
        reason="Low-confidence empty context; same empty-memory contract as GA-11.",
    ),
)


def golden_memory4_audits() -> tuple[GoldenMemoryCaseAudit, ...]:
    return _GOLDEN_AUDITS


def golden_memory4_audit_by_id(case_id: str) -> GoldenMemoryCaseAudit | None:
    for audit in _GOLDEN_AUDITS:
        if audit.case_id == case_id:
            return audit
    return None


def legacy_memory4_summary() -> dict[str, Any]:
    """Frozen legacy score — capability NOT_YET_VALID until L4-L5 green on live runs."""
    return {
        **LEGACY_MEMORY4_SCORE,
        "golden_cases": [a.to_dict() for a in _GOLDEN_AUDITS],
        "contract_records": {
            cid: MEMORY_CASE_BY_ID[cid].to_dict() for cid in ("GA-9", "GA-10", "GA-11", "GA-12")
        },
        "golden_json_mutated": False,
    }

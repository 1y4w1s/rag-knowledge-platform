"""Per-case MEMORY4 migration audit (B2-B3 characterization)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.eval.contract_validity.memory_contract import MEMORY_CASE_BY_ID
from app.eval.memory_capability.migration_map import (
    MEMORY4_MIGRATION_BY_ID,
    MigrationPrimaryCategory,
)
from app.eval.memory_capability.runtime_mapping import RUNTIME_MEMORY_PIPELINE

_RUNTIME_PATH = " -> ".join(stage["stage"] for stage in RUNTIME_MEMORY_PIPELINE)


@dataclass(frozen=True, slots=True)
class MemoryCaseMigrationAudit:
    case_id: str
    user_intent: str
    seeded_or_empty: str
    memory_proposition: str
    legacy_expected_behavior: str
    current_runtime_memory_path: str
    l1_applicable: bool
    l2_applicable: bool
    l3_applicable: bool
    l4_applicable: bool
    l5_applicable: bool
    capability_target: str
    measurement_currently_possible: dict[str, bool]
    primary_migration_category: MigrationPrimaryCategory
    blocker: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "user_intent": self.user_intent,
            "seeded_or_empty": self.seeded_or_empty,
            "memory_proposition": self.memory_proposition,
            "legacy_expected_behavior": self.legacy_expected_behavior,
            "current_runtime_memory_path": self.current_runtime_memory_path,
            "L1_L5_applicability": {
                "L1_SEEDED": self.l1_applicable,
                "L2_LOADED": self.l2_applicable,
                "L3_EXPOSED": self.l3_applicable,
                "L4_UTILIZED": self.l4_applicable,
                "L5_TASK_BENEFIT": self.l5_applicable,
            },
            "capability_target": self.capability_target,
            "measurement_currently_possible": dict(self.measurement_currently_possible),
            "primary_migration_category": self.primary_migration_category.value,
            "blocker": self.blocker,
        }


_INTENT: dict[str, str] = {
    "GA-9": "Answer the user's preferred retrieval language from stored preference memory.",
    "GA-10": "Search documents about Docker and React honoring language and topic preferences.",
    "GA-11": "Answer language preference when no memory is seeded (safe empty behavior).",
    "GA-12": "Search with low-confidence empty memory context without fabrication.",
}

_PROPOSITION: dict[str, str] = {
    "GA-9": "preference/lang language=en",
    "GA-10": "preference/lang language=en; preference/topic topic=docker",
    "GA-11": "(none — empty memory control)",
    "GA-12": "(none — empty memory control)",
}

_SEEDED_LABEL: dict[str, str] = {
    "GA-9": "seeded (1 preference: lang=en)",
    "GA-10": "seeded (2 preferences: lang=en, topic=docker)",
    "GA-11": "empty (pre_seed_memories=[])",
    "GA-12": "empty (pre_seed_memories=[])",
}


def _measurement_possible(entry_case_id: str) -> dict[str, bool]:
    migration = MEMORY4_MIGRATION_BY_ID[entry_case_id]
    levels = migration.measurement_levels
    empty = migration.primary_category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL
    return {
        "L1": levels["L1_SEEDED"],
        "L2": levels["L2_LOADED"],
        "L3": levels["L3_EXPOSED"],
        "L4": levels["L4_UTILIZED"] if not empty else False,
        "L5": levels["L5_TASK_BENEFIT"],
        "EMPTY_MEMORY_BEHAVIOR": empty,
    }


def build_memory4_migration_audits() -> tuple[MemoryCaseMigrationAudit, ...]:
    audits: list[MemoryCaseMigrationAudit] = []
    for case_id in ("GA-9", "GA-10", "GA-11", "GA-12"):
        record = MEMORY_CASE_BY_ID[case_id]
        migration = MEMORY4_MIGRATION_BY_ID[case_id]
        empty = migration.primary_category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL
        audits.append(
            MemoryCaseMigrationAudit(
                case_id=case_id,
                user_intent=_INTENT[case_id],
                seeded_or_empty=_SEEDED_LABEL[case_id],
                memory_proposition=_PROPOSITION[case_id],
                legacy_expected_behavior=record.expected_chunk_marker,
                current_runtime_memory_path=_RUNTIME_PATH,
                l1_applicable=True,
                l2_applicable=True,
                l3_applicable=True,
                l4_applicable=record.l4_utilization_applicable,
                l5_applicable=not empty,
                capability_target=migration.capability_target,
                measurement_currently_possible=_measurement_possible(case_id),
                primary_migration_category=migration.primary_category,
                blocker=migration.blocker,
            )
        )
    return tuple(audits)


MEMORY4_MIGRATION_AUDITS: tuple[MemoryCaseMigrationAudit, ...] = build_memory4_migration_audits()
MEMORY4_MIGRATION_AUDIT_BY_ID: dict[str, MemoryCaseMigrationAudit] = {
    a.case_id: a for a in MEMORY4_MIGRATION_AUDITS
}

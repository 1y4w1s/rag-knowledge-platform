"""MEMORY4 Golden case migration map (Gate G preserved)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.eval.contract_validity.memory_contract import MEMORY_CASE_BY_ID, memory_contract_records


class MigrationPrimaryCategory(str, Enum):
    MIGRATABLE_CURRENT_RUNTIME = "MIGRATABLE_CURRENT_RUNTIME"
    MEASURABLE_L1_L2_ONLY = "MEASURABLE_L1_L2_ONLY"
    BLOCKED_BY_L3_OBSERVABILITY = "BLOCKED_BY_L3_OBSERVABILITY"
    EMPTY_MEMORY_CONTROL = "EMPTY_MEMORY_CONTROL"
    STALE_CONTRACT = "STALE_CONTRACT"
    UNSATISFIABLE = "UNSATISFIABLE"


@dataclass(frozen=True, slots=True)
class MemoryMigrationEntry:
    case_id: str
    primary_category: MigrationPrimaryCategory
    legacy_expected_chunk: str
    capability_target: str
    measurement_levels: dict[str, bool]
    blocker: str
    legacy_stale_marker: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "primary_category": self.primary_category.value,
            "legacy_expected_chunk": self.legacy_expected_chunk,
            "capability_target": self.capability_target,
            "measurement_levels": dict(self.measurement_levels),
            "blocker": self.blocker,
            "legacy_stale_marker": self.legacy_stale_marker,
        }


def _levels(*, l1: bool, l2: bool, l3: bool, l4: bool, l5: bool) -> dict[str, bool]:
    return {
        "L1_SEEDED": l1,
        "L2_LOADED": l2,
        "L3_EXPOSED": l3,
        "L4_UTILIZED": l4,
        "L5_TASK_BENEFIT": l5,
    }


def _primary_for(case_id: str) -> MigrationPrimaryCategory:
    record = MEMORY_CASE_BY_ID[case_id]
    if record.case_kind.value == "EMPTY_MEMORY_CASE":
        return MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL
    return MigrationPrimaryCategory.BLOCKED_BY_L3_OBSERVABILITY


def _blocker_for(case_id: str, category: MigrationPrimaryCategory) -> str:
    if category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL:
        return ""
    return "L3_OBSERVABILITY_GAP: no structured memory exposure trace in production trajectories"


def build_memory4_migration_map() -> tuple[MemoryMigrationEntry, ...]:
    entries: list[MemoryMigrationEntry] = []
    for record in memory_contract_records():
        category = _primary_for(record.case_id)
        if category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL:
            levels = _levels(l1=True, l2=True, l3=True, l4=False, l5=False)
        else:
            levels = _levels(l1=True, l2=True, l3=False, l4=False, l5=False)
        target = "; ".join(record.measurement_targets)
        entries.append(
            MemoryMigrationEntry(
                case_id=record.case_id,
                primary_category=category,
                legacy_expected_chunk=record.expected_chunk_marker,
                capability_target=target,
                measurement_levels=levels,
                blocker=_blocker_for(record.case_id, category),
                legacy_stale_marker=record.expected_chunk_marker
                in {"memory_loaded", "memory_empty"},
            )
        )
    return tuple(entries)


MEMORY4_MIGRATION_MAP: tuple[MemoryMigrationEntry, ...] = build_memory4_migration_map()
MEMORY4_MIGRATION_BY_ID: dict[str, MemoryMigrationEntry] = {
    e.case_id: e for e in MEMORY4_MIGRATION_MAP
}

BLOCKED_BY_L3_OBSERVABILITY_IDS: frozenset[str] = frozenset(
    e.case_id
    for e in MEMORY4_MIGRATION_MAP
    if e.primary_category == MigrationPrimaryCategory.BLOCKED_BY_L3_OBSERVABILITY
)

EMPTY_MEMORY_CONTROL_IDS: frozenset[str] = frozenset(
    e.case_id
    for e in MEMORY4_MIGRATION_MAP
    if e.primary_category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL
)

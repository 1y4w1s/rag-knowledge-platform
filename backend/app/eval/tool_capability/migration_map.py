"""TOOL20 → CURRENT_L3_TOOL_CAPABILITY migration map (Gate G preserved)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.eval.contract_validity.models import PrimaryToolContractClass
from app.eval.contract_validity.tool_contract import TOOL_CASE_BY_ID, tool_primary_counts


class MigrationAction(str, Enum):
    KEEP = "KEEP"
    ADAPT = "ADAPT"
    REPLACE = "REPLACE"
    UNIT_ONLY = "UNIT_ONLY"
    UNSATISFIABLE = "UNSATISFIABLE"


class MigrationStatus(str, Enum):
    UNMIGRATED = "UNMIGRATED"
    MIGRATED_CURRENT_L3 = "MIGRATED_CURRENT_L3"
    MIGRATION_BLOCKED = "MIGRATION_BLOCKED"


_MIGRATED_CURRENT_L3_IDS: frozenset[str] = frozenset({"GQ-131", "GQ-132", "GQ-149"})


@dataclass(frozen=True, slots=True)
class ToolMigrationEntry:
    case_id: str
    gate_g_class: PrimaryToolContractClass
    action: MigrationAction
    expected_tool: str | None
    legacy_expected_chunk: str
    reason: str
    migration_status: MigrationStatus = MigrationStatus.UNMIGRATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "gate_g_class": self.gate_g_class.value,
            "action": self.action.value,
            "expected_tool": self.expected_tool,
            "legacy_expected_chunk": self.legacy_expected_chunk,
            "reason": self.reason,
            "migration_status": self.migration_status.value,
        }


def _action_for(record) -> MigrationAction:
    cls = record.primary_contract_class
    if cls == PrimaryToolContractClass.CURRENT_L3_NATIVE:
        return MigrationAction.ADAPT
    if cls == PrimaryToolContractClass.INTEGRATION_ONLY:
        return MigrationAction.UNIT_ONLY
    if cls == PrimaryToolContractClass.STALE_GOLDEN_CONTRACT:
        return MigrationAction.REPLACE
    if cls == PrimaryToolContractClass.UNSATISFIABLE_CURRENT_CONTRACT:
        return MigrationAction.UNSATISFIABLE
    return MigrationAction.KEEP


def _expected_tool(record) -> str | None:
    tool = record.required_tool_or_surface
    l3_tools = {
        "search_documents",
        "list_knowledge_bases",
        "semantic_search",
        "get_chunk_excerpt",
        "grep_in_document",
        "compare_chunks",
    }
    if tool in l3_tools:
        return tool
    return None


def _migration_status(case_id: str) -> MigrationStatus:
    if case_id in _MIGRATED_CURRENT_L3_IDS:
        return MigrationStatus.MIGRATED_CURRENT_L3
    return MigrationStatus.UNMIGRATED


def build_tool20_migration_map() -> tuple[ToolMigrationEntry, ...]:
    entries: list[ToolMigrationEntry] = []
    for case_id in sorted(TOOL_CASE_BY_ID):
        record = TOOL_CASE_BY_ID[case_id]
        entries.append(
            ToolMigrationEntry(
                case_id=case_id,
                gate_g_class=record.primary_contract_class,
                action=_action_for(record),
                expected_tool=_expected_tool(record),
                legacy_expected_chunk=record.expected_chunk,
                reason=record.reason,
                migration_status=_migration_status(case_id),
            )
        )
    return tuple(entries)


TOOL20_MIGRATION_MAP: tuple[ToolMigrationEntry, ...] = build_tool20_migration_map()
TOOL20_MIGRATION_BY_ID: dict[str, ToolMigrationEntry] = {
    e.case_id: e for e in TOOL20_MIGRATION_MAP
}

GATE_G_PRIMARY_COUNTS = tool_primary_counts()

ADAPT_CASE_IDS: frozenset[str] = frozenset(
    e.case_id for e in TOOL20_MIGRATION_MAP if e.action == MigrationAction.ADAPT
)

MIGRATED_CURRENT_L3_IDS: frozenset[str] = frozenset(
    e.case_id
    for e in TOOL20_MIGRATION_MAP
    if e.migration_status == MigrationStatus.MIGRATED_CURRENT_L3
)

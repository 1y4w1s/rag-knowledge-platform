"""P1 migrated MEMORY4 sidecar contracts — lineage hashes, no golden mutation."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.eval.contract_validity.memory_contract import MEMORY_CASE_BY_ID
from app.eval.memory_capability.evaluator import evaluate_trajectory
from app.eval.memory_capability.fixtures import (
    FIXTURE_EMPTY_MEMORY,
    FIXTURE_FULL_UTILIZATION,
    FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL,
    FIXTURE_GA10_STYLE,
)
from app.eval.memory_capability.migration_map import (
    MEMORY4_MIGRATION_BY_ID,
)
from app.eval.memory_capability.schema import MemoryTrajectoryInput

_LEGACY_GOLDEN_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "golden_agent_qa.json"
)

SIDECAR_FIXTURE_MIGRATABLE_IDS: frozenset[str] = frozenset({"GA-9", "GA-10"})


@dataclass(frozen=True, slots=True)
class SidecarMemoryContract:
    case_id: str
    primary_migration_category: str
    legacy_expected_chunk: str
    user_intent: str
    memory_propositions: tuple[str, ...]
    measurement_level_applicability: dict[str, bool]
    blocker: str
    legacy_case_hash: str
    migration_contract_hash: str = field(repr=False, compare=False)
    fixture_migratable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "primary_migration_category": self.primary_migration_category,
            "legacy_expected_chunk": self.legacy_expected_chunk,
            "user_intent": self.user_intent,
            "memory_propositions": list(self.memory_propositions),
            "measurement_level_applicability": dict(self.measurement_level_applicability),
            "blocker": self.blocker,
            "legacy_case_hash": self.legacy_case_hash,
            "migration_contract_hash": self.migration_contract_hash,
            "fixture_migratable": self.fixture_migratable,
        }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _load_legacy_golden_case(case_id: str) -> dict[str, Any]:
    data = json.loads(_LEGACY_GOLDEN_PATH.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case["case_id"] == case_id:
            return {
                "case_id": case["case_id"],
                "category": case["category"],
                "query": case["query"],
                "expected_doc": case.get("expected_doc", "none"),
                "expected_chunk": case["expected_chunk"],
                "scope": case.get("scope", "kb"),
                "pre_seed_memories": case.get("pre_seed_memories", []),
            }
    raise KeyError(f"golden case not found: {case_id}")


def legacy_case_hash(case_id: str) -> str:
    return _hash_payload(_load_legacy_golden_case(case_id))


def _propositions_for(case_id: str) -> tuple[str, ...]:
    golden = _load_legacy_golden_case(case_id)
    props: list[str] = []
    for item in golden.get("pre_seed_memories", []):
        payload = json.dumps(item.get("value", {}), sort_keys=True)
        props.append(f"{item.get('memory_type')}/{item.get('key')}={payload}")
    return tuple(props)


def ideal_trajectory_for(case_id: str) -> MemoryTrajectoryInput:
    if case_id == "GA-9":
        base = copy.deepcopy(FIXTURE_FULL_UTILIZATION)
        base.case_id = "GA-9"
        return base
    if case_id == "GA-10":
        base = copy.deepcopy(FIXTURE_GA10_STYLE)
        base.case_id = "GA-10"
        return base
    if case_id == "GA-11":
        base = copy.deepcopy(FIXTURE_EMPTY_MEMORY)
        base.case_id = "GA-11"
        base.query = _load_legacy_golden_case("GA-11")["query"]
        return base
    if case_id == "GA-12":
        return MemoryTrajectoryInput(
            case_id="GA-12",
            query=_load_legacy_golden_case("GA-12")["query"],
            seeded_memories=(),
            seed_succeeded=True,
            loaded_memories=(),
            exposed_context="",
            output_text="No reliable memory context; searching knowledge base directly.",
            empty_memory_case=True,
            safe_termination=True,
            no_fabricated_memory=True,
            task_contract_passed=True,
        )
    raise KeyError(case_id)


def ideal_counterfactual_for(case_id: str):
    if case_id == "GA-9":
        pair = copy.deepcopy(FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL)
        pair.case_id = "GA-9"
        pair.with_memory.case_id = "GA-9"
        return pair
    return None


def _build_contract(case_id: str) -> SidecarMemoryContract:
    migration = MEMORY4_MIGRATION_BY_ID[case_id]
    golden = _load_legacy_golden_case(case_id)
    intent_queries = {
        "GA-9": "Answer preferred retrieval language from memory.",
        "GA-10": "Search Docker/React with preference-aware retrieval.",
        "GA-11": "Safe behavior when memory store is empty.",
        "GA-12": "Search without fabricating low-confidence memory.",
    }
    body_without_hash = {
        "case_id": case_id,
        "primary_migration_category": migration.primary_category.value,
        "legacy_expected_chunk": golden["expected_chunk"],
        "user_intent": intent_queries[case_id],
        "memory_propositions": list(_propositions_for(case_id)),
        "measurement_level_applicability": migration.measurement_levels,
        "blocker": migration.blocker,
        "legacy_case_hash": legacy_case_hash(case_id),
        "fixture_migratable": case_id in SIDECAR_FIXTURE_MIGRATABLE_IDS,
    }
    contract_hash = _hash_payload(body_without_hash)
    return SidecarMemoryContract(
        case_id=case_id,
        primary_migration_category=migration.primary_category.value,
        legacy_expected_chunk=golden["expected_chunk"],
        user_intent=intent_queries[case_id],
        memory_propositions=_propositions_for(case_id),
        measurement_level_applicability=dict(migration.measurement_levels),
        blocker=migration.blocker,
        legacy_case_hash=legacy_case_hash(case_id),
        migration_contract_hash=contract_hash,
        fixture_migratable=case_id in SIDECAR_FIXTURE_MIGRATABLE_IDS,
    )


def build_sidecar_contracts() -> tuple[SidecarMemoryContract, ...]:
    return tuple(_build_contract(cid) for cid in ("GA-9", "GA-10", "GA-11", "GA-12"))


SIDECAR_MEMORY_CONTRACTS: tuple[SidecarMemoryContract, ...] = build_sidecar_contracts()
SIDECAR_MEMORY_CONTRACT_BY_ID: dict[str, SidecarMemoryContract] = {
    c.case_id: c for c in SIDECAR_MEMORY_CONTRACTS
}


def fixture_ideal_passes_levels(case_id: str) -> bool:
    traj = ideal_trajectory_for(case_id)
    result = evaluate_trajectory(traj)
    if case_id in SIDECAR_FIXTURE_MIGRATABLE_IDS:
        return all(
            result.level_map()[level].passed
            for level in ("L1_SEEDED", "L2_LOADED", "L3_EXPOSED", "L4_UTILIZED")
        )
    if MEMORY_CASE_BY_ID[case_id].case_kind.value == "EMPTY_MEMORY_CASE":
        return all(
            result.level_map()[level].passed
            for level in ("L1_SEEDED", "L2_LOADED", "L3_EXPOSED")
        )
    return False


def l3_blocked_hard_negative(case_id: str) -> MemoryTrajectoryInput:
    """Seeded case with load success but no exposure — L4 must not pass."""
    ideal = ideal_trajectory_for(case_id)
    blocked = copy.deepcopy(ideal)
    blocked.exposed_context = ""
    blocked.output_text = "Generic answer without using memory."
    blocked.task_contract_passed = False
    return blocked


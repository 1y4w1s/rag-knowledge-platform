"""W8 MEMORY Contract Migration P1 freeze — denominators + sidecar manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.memory_capability.l3_observability_recommendation import (
    NEED_L3_PRODUCT_INSTRUMENTATION,
    l3_observability_recommendation,
)
from app.eval.memory_capability.migration_audit import MEMORY4_MIGRATION_AUDITS
from app.eval.memory_capability.migration_contract import SIDECAR_MEMORY_CONTRACTS
from app.eval.memory_capability.migration_map import (
    BLOCKED_BY_L3_OBSERVABILITY_IDS,
    EMPTY_MEMORY_CONTROL_IDS,
)

MANIFEST_REL = Path("tests/fixtures/l4_memory_capability/l4-memory-contract-p1.manifest.json")

P0_MERGE_SHA = "0b313460cdce11ac4204e14a83375f5b860d16a2"
P0_FEATURE_SHA = "a2e8e872b955357e3d89730f4d4fe895bf69684a"
STAGE = "MEMORY_CONTRACT_MIGRATION_P1"

# Independently frozen denominators (B11)
L1_DENOMINATOR = 4
L2_DENOMINATOR = 4
L3_DENOMINATOR = 2  # empty-memory exposure only until L3 instrumentation
L4_UTILIZATION_DENOMINATOR = 0  # L3 gap blocks complete L1-L4 chain for seeded cases
L5_TASK_BENEFIT_DENOMINATOR = 0
EMPTY_MEMORY_BEHAVIOR_DENOMINATOR = len(EMPTY_MEMORY_CONTROL_IDS)
BLOCKED_BY_L3_OBSERVABILITY_COUNT = len(BLOCKED_BY_L3_OBSERVABILITY_IDS)

CAPABILITY_SCORE = "NOT_YET_MEASURED"
READY_FOR_MEMORY_P2 = "OBSERVABILITY" if NEED_L3_PRODUCT_INSTRUMENTATION else "REAL_RUN"


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def build_p1_manifest(*, base_sha: str = P0_MERGE_SHA) -> dict[str, Any]:
    return {
        "schema_version": "l4-memory-contract-p1-v1",
        "stage": STAGE,
        "base_sha": base_sha,
        "p0_merge_sha": P0_MERGE_SHA,
        "p0_feature_sha": P0_FEATURE_SHA,
        "evaluator_p0": "PASS/FROZEN",
        "legacy_memory4_score": "INVALID_FOR_UTILIZATION_CAPABILITY",
        "legacy_memory4_pass_count": 2,
        "legacy_memory4_total": 4,
        "golden_rewrite": False,
        "legacy_memory4_mutated": False,
        "product_remediation": False,
        "runtime_rollout": False,
        "capability_score": CAPABILITY_SCORE,
        "measured_model_score": CAPABILITY_SCORE,
        "denominators": {
            "L1": L1_DENOMINATOR,
            "L2": L2_DENOMINATOR,
            "L3": L3_DENOMINATOR,
            "L4_utilization": L4_UTILIZATION_DENOMINATOR,
            "L5_task_benefit": L5_TASK_BENEFIT_DENOMINATOR,
            "empty_memory_behavior": EMPTY_MEMORY_BEHAVIOR_DENOMINATOR,
            "blocked_by_l3_observability": BLOCKED_BY_L3_OBSERVABILITY_COUNT,
        },
        "ready_for_memory_p2": READY_FOR_MEMORY_P2,
        "need_l3_instrumentation": NEED_L3_PRODUCT_INSTRUMENTATION,
        "l3_observability_recommendation": l3_observability_recommendation(),
        "migration_audits": [a.to_dict() for a in MEMORY4_MIGRATION_AUDITS],
        "cases": [c.to_dict() for c in SIDECAR_MEMORY_CONTRACTS],
        "notes": [
            "Sidecar contract manifest — does not modify golden_agent_qa.json.",
            "L4/L5 denominators frozen at 0 until L3 exposure is machine-observable.",
            "Empty-memory cases route to EMPTY_MEMORY_BEHAVIOR metric only.",
        ],
    }


def load_p1_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(repo_root)
    return json.loads(path.read_text(encoding="utf-8"))

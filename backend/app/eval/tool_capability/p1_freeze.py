"""W8 TOOL Contract Migration P1 freeze — denominator + sidecar manifest helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.tool_capability.migration_contract import (
    MIGRATED_CASE_CONTRACTS,
    all_migrations_proven,
)

MANIFEST_REL = Path("tests/fixtures/l4_tool_capability/l4-tool-contract-p1.manifest.json")

P0_MERGE_SHA = "9288b91801215bc2b0f7ca3f871c45393f5ad0c0"
P0_FEATURE_SHA = "ffc6e9b134e3e07e9bb15ffd1d58a0a29f38539f"
STAGE = "TOOL_CONTRACT_MIGRATION_P1"

CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR = 3 if all_migrations_proven() else 0
CAPABILITY_VALID_CASE_COUNT = sum(
    1 for c in MIGRATED_CASE_CONTRACTS if c.migration_status == "MIGRATED_CURRENT_L3"
)
MEASURED_MODEL_SCORE = "NOT_YET_MEASURED"


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def build_p1_manifest(*, base_sha: str = P0_MERGE_SHA) -> dict[str, Any]:
    return {
        "schema_version": "l4-tool-contract-p1-v1",
        "stage": STAGE,
        "base_sha": base_sha,
        "p0_merge_sha": P0_MERGE_SHA,
        "p0_feature_sha": P0_FEATURE_SHA,
        "evaluator_p0": "PASS/FROZEN",
        "legacy_tool20_score": "INVALID",
        "golden_rewrite": False,
        "product_remediation": False,
        "runtime_rollout": False,
        "CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR": CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR,
        "capability_valid_cases": CAPABILITY_VALID_CASE_COUNT,
        "measured_model_score": MEASURED_MODEL_SCORE,
        "migrated_case_ids": [c.case_id for c in MIGRATED_CASE_CONTRACTS],
        "gate_g_primary_counts_preserved": {
            "CURRENT_L3_NATIVE": 3,
            "INTEGRATION_ONLY": 5,
            "STALE_GOLDEN_CONTRACT": 5,
            "UNSATISFIABLE_CURRENT_CONTRACT": 7,
        },
        "cases": [c.to_dict() for c in MIGRATED_CASE_CONTRACTS],
        "notes": [
            "Sidecar contract manifest — does not modify golden_agent_qa.json.",
            "Legacy TOOL20 Gate G classification counts remain frozen.",
            "Denominator frozen; no real model capability score yet.",
        ],
    }


def load_p1_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(repo_root)
    return json.loads(path.read_text(encoding="utf-8"))

"""TOOL P4 freeze manifest helpers (eval-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_REL = Path(
    "tests/fixtures/l4_tool_capability/l4-tool-p4-real-ablation.manifest.json"
)

STAGE = "TOOL_P4_REAL_LOCAL_PRODUCT_REVALIDATION"
TOOL_P4_BASE_SHA = "4c81c6340f1789a641ef0d6cbaf42c1efdaa2bc2"
CASE_IDS = ("GQ-131", "GQ-132", "GQ-149")
PRIMARY = {"00": "0/3", "10": "0/3", "01": "2/3", "11": "2/3"}
STABILITY = {"00": "0/15", "10": "0/15", "01": "10/15", "11": "10/15"}
CLASSIFICATION = "Case1 PASS + REAL_VALIDATED_ON_FROZEN_SUBSET"
READY_FOR_RUNTIME_ROLLOUT = False


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def load_p4_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))


def assert_manifest_matches_constants(data: dict[str, Any]) -> None:
    assert data["stage"] == STAGE
    assert data["tool_p4_base_sha"] == TOOL_P4_BASE_SHA
    assert data["primary"] == PRIMARY
    assert data["stability"] == STABILITY
    assert data["ready_for_runtime_rollout"] is READY_FOR_RUNTIME_ROLLOUT
    assert data["classification"] == CLASSIFICATION
    assert list(data["frozen_subset"]) == list(CASE_IDS)

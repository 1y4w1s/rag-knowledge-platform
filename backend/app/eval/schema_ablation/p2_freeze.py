"""W8 P7 P2 real trajectory schema remediation freeze (tracked manifest + helpers)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.eval.contract_validity.schema_baseline import BENCHMARK_SEMANTICS_SHA
from app.eval.schema_ablation.candidates import evaluate_strict
from app.eval.schema_ablation.dataset import load_target_failures
from app.eval.schema_ablation.tool_inventory import frozen_tool_inventory
from app.services.agent.planners import parse_agent_decision

MANIFEST_REL = Path("tests/fixtures/w8_p7/w8-p7-p2-real-schema-revalidation.manifest.json")

P7_P1_MERGE_SHA = "58faf733af44681dbe1f17830836b0b2394543b6"
P7_P1_FEATURE_SHA = "1170a666280dd5ceddf616edc9a6e8ab7d81dc7c"
P7_CLOSEOUT_BASE_SHA = P7_P1_MERGE_SHA
STAGE = "W8_P7_P2"
FREEZE_VALIDATION_MODE = "REAL_RUN_RESULT_REUSED_FOR_FREEZE"

FRESH_CASES = 48
FRESH_DECISIONS = 166
FRESH_RAW_TNA = 7
FRESH_RECOVERED_TNA = 7
FRESH_UNRECOVERED_TNA = 0
FINAL_UNRECOVERED_SCHEMA_FAILURE = 0

HISTORICAL_DECISIONS = 226
HISTORICAL_SCHEMA_FAILURES = 9
HISTORICAL_TNA = 9

FROZEN_REPLAY_TARGET_COUNT = 9
FROZEN_REPLAY_RECOVERED_COUNT = 9

_TOOL_NAMES = frozenset({
    "semantic_search",
    "search_documents",
    "get_chunk_excerpt",
    "grep_in_document",
    "compare_chunks",
    "list_knowledge_bases",
    "web_search",
})


def _is_tool_name_as_action_raw(raw: str) -> bool:
    match = re.search(r'"action"\s*:\s*"([^"]+)"', raw or "")
    if not match:
        return False
    return match.group(1) in _TOOL_NAMES


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def load_p2_freeze_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(repo_root)
    return json.loads(path.read_text(encoding="utf-8"))


def run_frozen_target_replay(*, external_tools_enabled: bool = False) -> dict[str, Any]:
    """Deterministic Gate H target replay through product parse_agent_decision."""
    inv = frozen_tool_inventory(external_tools_enabled=external_tools_enabled)
    exposed = frozenset(inv.allowed_tool_names)
    targets = load_target_failures()
    recovered = 0
    false_accepts = 0
    for sample in targets:
        parsed = parse_agent_decision(sample.raw_output, exposed_tool_names=exposed)
        raw_shape = _is_tool_name_as_action_raw(sample.raw_output)
        strict = evaluate_strict(sample.raw_output)
        if parsed.ok and raw_shape:
            recovered += 1
        if parsed.ok and not raw_shape and not strict.parse_ok:
            false_accepts += 1
    return {
        "target_count": len(targets),
        "recovered_count": recovered,
        "false_accepts": false_accepts,
    }


def assert_manifest_matches_constants(manifest: dict[str, Any]) -> None:
    assert manifest["stage"] == STAGE
    assert manifest["base_sha"] == P7_CLOSEOUT_BASE_SHA
    assert manifest["p7_p1_merge_sha"] == P7_P1_MERGE_SHA
    assert manifest["p7_p1_feature_sha"] == P7_P1_FEATURE_SHA
    assert manifest["benchmark_semantics_sha"] == BENCHMARK_SEMANTICS_SHA
    assert manifest["cases"] == FRESH_CASES
    assert manifest["fresh_decisions"] == FRESH_DECISIONS
    assert manifest["historical_decisions"] == HISTORICAL_DECISIONS
    assert manifest["historical_schema_failures"] == HISTORICAL_SCHEMA_FAILURES
    assert manifest["historical_tool_name_as_action"] == HISTORICAL_TNA
    assert manifest["fresh_raw_tool_name_as_action"] == FRESH_RAW_TNA
    assert manifest["fresh_recovered_tool_name_as_action"] == FRESH_RECOVERED_TNA
    assert manifest["fresh_unrecovered_tool_name_as_action"] == FRESH_UNRECOVERED_TNA
    assert manifest["raw_model_tna_count"] == FRESH_RAW_TNA
    assert manifest["final_unrecovered_schema_failure"] == FINAL_UNRECOVERED_SCHEMA_FAILURE
    assert manifest["result"] == "PASS"
    assert manifest["schema_remediation"] == "REAL_TRAJECTORY_VALIDATED"
    assert manifest["runtime_rollout"] == "NO"
    assert manifest["freeze_validation_mode"] == FREEZE_VALIDATION_MODE
    assert manifest["comparison"]["note"] == "NOT_DIRECT_MODEL_CAPABILITY_COMPARISON"
    fr = manifest["frozen_replay"]
    assert fr["target_count"] == FROZEN_REPLAY_TARGET_COUNT
    assert fr["recovered_count"] == FROZEN_REPLAY_RECOVERED_COUNT
    assert fr["false_accepts"] == 0

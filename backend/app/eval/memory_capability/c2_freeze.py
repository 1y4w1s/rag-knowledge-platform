"""MEMORY C2 / V1.0 capability boundary freeze — eval-only NO_GO lock.

Does not change product runtime, Golden, or workflow. Formalizes commit 788f026
evidence-gate audit as MEMORY_V1_0_CAPABILITY_BOUNDARY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_REL = Path(
    "tests/fixtures/l4_memory_capability/l4-memory-v1-capability-boundary.manifest.json"
)
EVIDENCE_GATE_MANIFEST_REL = Path(
    "tests/fixtures/l4_memory_capability/l4-memory-c2-evidence-gate.manifest.json"
)

STAGE = "MEMORY_V1_0_CAPABILITY_BOUNDARY_FREEZE"
EVIDENCE_GATE_STAGE = "MEMORY_C2_GO_NO_GO_EVIDENCE_AUDIT"
EVIDENCE_GATE_COMMIT = "788f026bb183d5cc67a1ccbac887526110ee8ce1"

MEMORY_C2_DECISION = "NO_GO"
C2_PRODUCT_EXPERIMENT = "NOT_JUSTIFIED_FOR_V1_0"
INDEPENDENT_EVIDENCE = "INSUFFICIENT_INDEPENDENT_EVIDENCE"
OFFLINE_PROXY_CONFIDENCE = "DOWNGRADED"
C2_STATUS = "NOT_PURSUED_IN_V1_0"
MEMORY_REMEDIATION = "CLOSED_FOR_V1_0"
RUNTIME_ROLLOUT = False
PRODUCT_REMEDIATION = False
GOLDEN_MUTATED = False

CAPABILITY_BOUNDARY = {
    "L3_exposure": "PROVEN",
    "L4_semantic_utilization": "NOT_DEMONSTRATED_ON_FROZEN_SUBSET",
    "L5_causal_task_benefit": "NOT_DEMONSTRATED_ON_FROZEN_SUBSET",
    "C1_CONTRASTIVE_MEMORY_RELEVANCE_LABEL": "NO_MEASURABLE_GAIN",
    "C2_STRUCTURED_PROPOSITION_BLOCK": "NOT_PURSUED_IN_V1_0",
}

FORBIDDEN_CLAIMS = [
    "memory does not work",
    "model cannot use memory universally",
    "C2 proves model boundary",
    "P4 offline proxy alone justifies C2 product experiment",
]

INTERPRETATION_ALLOWED = (
    "On frozen GA-9/GA-10 subset with current stack: L3 exposure proven; "
    "L4/L5 utilization and C1 contrastive label showed no measurable gain; "
    "C2 structured proposition block not pursued for V1.0."
)


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def evidence_gate_manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / EVIDENCE_GATE_MANIFEST_REL


def load_v1_boundary_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))


def load_evidence_gate_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(evidence_gate_manifest_path(repo_root).read_text(encoding="utf-8"))


def build_v1_boundary_manifest(
    *,
    round_start_master_sha: str,
) -> dict[str, Any]:
    return {
        "schema_version": "l4-memory-v1-capability-boundary-v1",
        "stage": STAGE,
        "evidence_gate_stage": EVIDENCE_GATE_STAGE,
        "evidence_gate_commit": EVIDENCE_GATE_COMMIT,
        "round_start_master_sha": round_start_master_sha,
        "state": "PASS",
        "MEMORY_C2_DECISION": MEMORY_C2_DECISION,
        "C2_PRODUCT_EXPERIMENT": C2_PRODUCT_EXPERIMENT,
        "independent_evidence": INDEPENDENT_EVIDENCE,
        "offline_proxy_confidence": OFFLINE_PROXY_CONFIDENCE,
        "c2_status": C2_STATUS,
        "memory_remediation": MEMORY_REMEDIATION,
        "runtime_rollout": RUNTIME_ROLLOUT,
        "product_remediation": PRODUCT_REMEDIATION,
        "golden_mutated": GOLDEN_MUTATED,
        "MEMORY_V1_0_CAPABILITY_BOUNDARY": CAPABILITY_BOUNDARY,
        "interpretation_discipline": {
            "allowed": INTERPRETATION_ALLOWED,
            "forbidden": list(FORBIDDEN_CLAIMS),
        },
        "evidence_chain_summary": {
            "p4_offline_proxy_c1_c2": "Apparent recovery 1.0 for C1/C2 — DOWNGRADED after C1 real 0/10→0/10 L4/L5",
            "c1_real_local": "NO_MEASURABLE_GAIN on GA-9/GA-10 frozen subset",
            "c2_mechanism_distinctness": "OVERLAP_DOMINATES — C2 overlaps C1 on M3/M4 binding signals",
            "c2_invasiveness": "NOT_ACCEPTABLE_FOR_ONLY_TWO_FROZEN_CASES",
            "c2_hard_negative_authority_risk": "NOT_CONTROLLED_FOR_STRUCTURE_AUTHORITY",
            "c2_maintenance_cost": "Medium ongoing for unproven L4/L5 value",
        },
        "non_goals": [
            "no C2 product implementation",
            "no memory prompt tuning beyond frozen measurement",
            "no Golden rewrite",
            "no runtime rollout",
            "no model re-run",
        ],
    }


def assert_v1_boundary_manifest(manifest: dict[str, Any]) -> None:
    assert manifest["stage"] == STAGE
    assert manifest["state"] == "PASS"
    assert manifest["MEMORY_C2_DECISION"] == MEMORY_C2_DECISION
    assert manifest["C2_PRODUCT_EXPERIMENT"] == C2_PRODUCT_EXPERIMENT
    assert manifest["independent_evidence"] == INDEPENDENT_EVIDENCE
    assert manifest["offline_proxy_confidence"] == OFFLINE_PROXY_CONFIDENCE
    assert manifest["c2_status"] == C2_STATUS
    assert manifest["memory_remediation"] == MEMORY_REMEDIATION
    assert manifest["runtime_rollout"] is False
    assert manifest["product_remediation"] is False
    assert manifest["golden_mutated"] is False
    boundary = manifest["MEMORY_V1_0_CAPABILITY_BOUNDARY"]
    assert boundary["L3_exposure"] == "PROVEN"
    assert boundary["L4_semantic_utilization"] == "NOT_DEMONSTRATED_ON_FROZEN_SUBSET"
    assert boundary["L5_causal_task_benefit"] == "NOT_DEMONSTRATED_ON_FROZEN_SUBSET"
    assert boundary["C1_CONTRASTIVE_MEMORY_RELEVANCE_LABEL"] == "NO_MEASURABLE_GAIN"
    assert boundary["C2_STRUCTURED_PROPOSITION_BLOCK"] == "NOT_PURSUED_IN_V1_0"
    forbidden = set(manifest["interpretation_discipline"]["forbidden"])
    for claim in FORBIDDEN_CLAIMS:
        assert claim in forbidden


def assert_evidence_gate_manifest(manifest: dict[str, Any]) -> None:
    assert manifest["schema_version"] == "l4-memory-c2-evidence-gate-v1"
    assert manifest["decision"] == MEMORY_C2_DECISION
    assert manifest["product_experiment"] == C2_PRODUCT_EXPERIMENT
    assert manifest["offline_proxy_confidence"] == OFFLINE_PROXY_CONFIDENCE
    assert manifest["C4_independent_evidence"]["verdict"] == INDEPENDENT_EVIDENCE
    assert manifest["C7_decision_gate"]["result"] == MEMORY_C2_DECISION
    assert manifest["C8_freeze_recommendation"]["label"] == "MEMORY_V1_0_CAPABILITY_BOUNDARY"

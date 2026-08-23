"""ADVERSARIAL capability P1 freeze — valid corpus denominator + migration sidecar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.adversarial_capability.capability_cases import (
    CAPABILITY_CASES,
    MIGRATION_AUDITS,
)
from app.eval.adversarial_capability.corpus_fixtures import ALL_CORPORA
from app.eval.adversarial_capability.freeze import ROUND_START_MASTER_SHA

STAGE = "ADVERSARIAL_CAPABILITY_CORPUS_P1"
MANIFEST_REL = Path(
    "tests/fixtures/l4_adversarial_capability/adversarial-capability-corpus-p1.manifest.json"
)
CORPUS_FIXTURE_REL = Path(
    "tests/fixtures/l4_adversarial_capability/adversarial-capability-corpus-p1.json"
)

P0_MERGE_SHA = ""  # filled at build time


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def corpus_fixture_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / CORPUS_FIXTURE_REL


def capability_valid_denominator() -> int:
    return sum(1 for c in CAPABILITY_CASES if c.in_capability_denominator)


def corpus_class_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in CAPABILITY_CASES:
        if not case.in_capability_denominator:
            continue
        cls = case.answerability_class
        counts[cls] = counts.get(cls, 0) + 1
    return counts


def migration_outcome_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for audit in MIGRATION_AUDITS:
        counts[audit.migration_outcome] = counts.get(audit.migration_outcome, 0) + 1
    return counts


def build_p1_manifest(*, p0_merge_sha: str) -> dict[str, Any]:
    denom = capability_valid_denominator()
    return {
        "schema_version": "adversarial-capability-corpus-p1-v1",
        "stage": STAGE,
        "round_start_master_sha": ROUND_START_MASTER_SHA,
        "p0_merge_sha": p0_merge_sha,
        "product_remediation": False,
        "golden_rewrite": False,
        "runtime_rollout": False,
        "success_class": "PARTIAL" if denom == 0 else "PASS",
        "CAPABILITY_VALID_DENOMINATOR": denom,
        "corpus_class_breakdown": corpus_class_counts(),
        "corpus_fixtures": [c.to_dict() for c in ALL_CORPORA],
        "capability_cases": [c.to_dict() for c in CAPABILITY_CASES],
        "migration_audits": [a.to_dict() for a in MIGRATION_AUDITS],
        "migration_outcome_counts": migration_outcome_counts(),
        "excluded_legacy_cases": ["GQ-104", "GQ-110"],
        "hard_controls": [
            "HC-ALWAYS-REFUSE",
            "HC-ALWAYS-ANSWER",
            "HC-ALWAYS-RETRIEVE",
            "HC-NO-RETRIEVAL",
        ],
        "notes": [
            "Sidecar manifest — golden_agent_qa.json not mutated.",
            "Answerability independent of mock retriever semantics.",
            "GQ-104/GQ-110 remain excluded unless bound to new independent fixtures.",
        ],
    }


def write_p1_artifacts(*, p0_merge_sha: str, repo_root: Path | None = None) -> tuple[Path, Path]:
    manifest = build_p1_manifest(p0_merge_sha=p0_merge_sha)
    mpath = manifest_path(repo_root)
    cpath = corpus_fixture_path(repo_root)
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cpath.write_text(
        json.dumps(
            {
                "schema_version": "adversarial-capability-corpus-p1-v1",
                "corpora": [c.to_dict() for c in ALL_CORPORA],
                "cases": [c.to_dict() for c in CAPABILITY_CASES],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return mpath, cpath


def load_p1_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))

"""W8 P6 contract validity report assembly and optional BGE retrieval probe."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.eval.contract_validity.adversarial import (
    adversarial_probe_case_ids,
    build_adversarial_characterization,
)
from app.eval.contract_validity.golden_contracts import (
    MEMORY_ORIGINAL_SCORE,
    TOOL_ORIGINAL_SCORE,
)
from app.eval.contract_validity.memory_contract import memory_contract_records
from app.eval.contract_validity.metric_validity import METRIC_VALIDITY_MATRIX
from app.eval.contract_validity.schema_baseline import (
    BENCHMARK_SEMANTICS_SHA,
    VALIDATED_MERGED_MASTER_SHA,
    schema_characterization_baseline,
)
from app.eval.contract_validity.tool_contract import (
    tool_contract_records,
    tool_primary_counts,
)
from tests.golden_agent_qa_loader import load_golden_agent_cases

__all__ = [
    "BENCHMARK_SEMANTICS_SHA",
    "VALIDATED_MERGED_MASTER_SHA",
    "BgeProbeResult",
    "build_contract_validity_report",
    "gate_g_readiness",
    "run_bge_retrieval_validity_probe",
]

PROBE_ARTIFACT_NAMES: tuple[str, ...] = (
    "w8-p6-adversarial-bge-probe.json",
    "w8-p6-retrieval-validity.json",
)


@dataclass(slots=True)
class BgeProbeResult:
    status: str  # OK | BLOCKED | SKIPPED
    candidate_available: bool
    capability_valid_proven: bool
    query_group_count: int
    probe_records: list[dict[str, Any]]
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gate_g_readiness() -> dict[str, bool]:
    """Frozen Gate G readiness flags (P6 contract-validity scope)."""
    return {
        "ready_for_schema_ablation": True,
        "ready_for_adversarial_measurement_contract_ablation": True,
        "ready_for_adversarial_product_ablation": False,
        "ready_for_tool_re_spec": True,
        "ready_for_memory_evaluator_design": True,
        "ready_for_broad_capability_remediation": False,
        "ready_for_golden_168": False,
        "ready_for_runtime_rollout": False,
    }


def build_contract_validity_report(
    *,
    repo_root: Path | None = None,
    bge_probe_result: BgeProbeResult | None = None,
) -> dict[str, Any]:
    """Assemble tracked Gate G contract validity snapshot.

    ``bge_capability_valid_proven`` in the snapshot is derived only from
    ``bge_probe_result`` when ``status == \"OK\"`` and
    ``capability_valid_proven is True``. Callers cannot assert proven via boolean.
    """
    adversarial = build_adversarial_characterization(
        repo_root=repo_root,
        bge_probe_result=bge_probe_result,
    )
    tool_records = tool_contract_records()
    memory_records = memory_contract_records()
    schema = schema_characterization_baseline()

    return {
        "schema_version": "w8-p6-contract-validity-v1",
        "validated_merged_master": VALIDATED_MERGED_MASTER_SHA,
        "benchmark_semantics_sha": BENCHMARK_SEMANTICS_SHA,
        "p5_results_remain_valid": True,
        "adversarial": adversarial.to_dict(),
        "tool": {
            "original_score": TOOL_ORIGINAL_SCORE,
            "primary_counts": tool_primary_counts(),
            "cases": [r.to_dict() for r in tool_records],
        },
        "memory": {
            "original_score": MEMORY_ORIGINAL_SCORE,
            "seeded_cases": sum(
                1 for r in memory_records if r.l4_utilization_applicable
            ),
            "empty_cases": sum(
                1 for r in memory_records if not r.l4_utilization_applicable
            ),
            "cases": [r.to_dict() for r in memory_records],
        },
        "schema_baseline": schema.to_dict(),
        "metric_validity_matrix": [m.to_dict() for m in METRIC_VALIDITY_MATRIX],
        "bge_probe_case_ids": list(adversarial_probe_case_ids()),
        "readiness": gate_g_readiness(),
        "bge_probe_artifact_required_for_proven_status": True,
    }


def _default_artifact_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "artifacts" / "benchmarks" / "tmp" / "reports"


def _chunk_relevant(case_id: str, chunk_content: str, expected_chunk: str) -> bool:
    if not expected_chunk:
        return False
    return expected_chunk.lower() in chunk_content.lower()


async def run_bge_retrieval_validity_probe(
    *,
    db: Any,
    kb_id: UUID,
    repo_root: Path | None = None,
    top_k: int = 5,
    artifact_dir: Path | None = None,
) -> BgeProbeResult:
    """Eval-only retrieval probe — does not run Agent trajectories."""
    from app.core.config import settings
    from app.eval.contract_validity.adversarial import bge_candidate_available
    from app.services.rag.retrieval import retrieve_chunks

    if not bge_candidate_available(repo_root):
        return BgeProbeResult(
            status="BLOCKED",
            candidate_available=False,
            capability_valid_proven=False,
            query_group_count=len(adversarial_probe_case_ids()),
            probe_records=[],
            blocker="CAPABILITY_VALID_RETRIEVAL_CANDIDATE not available locally",
        )

    saved_provider = settings.embedding_provider
    cases_by_id = {c.case_id: c for c in load_golden_agent_cases()}
    probe_ids = adversarial_probe_case_ids()
    records: list[dict[str, Any]] = []

    try:
        os.environ.setdefault(
            "FASTEMBED_CACHE_PATH",
            str((repo_root or Path.cwd()) / "models" / "fastembed"),
        )
        settings.embedding_provider = "bge"

        for case_id in probe_ids:
            case = cases_by_id[case_id]
            chunks = await retrieve_chunks(
                db,
                kb_id=kb_id,
                query=case.query,
                top_k=top_k,
            )
            top_scores = [float(c.similarity) for c in chunks]
            top1 = top_scores[0] if top_scores else None
            returned_ids = [str(c.chunk_id) for c in chunks]
            expected_relevant = _chunk_relevant(
                case_id,
                " ".join(c.content for c in chunks[:1]),
                case.expected_chunk,
            )
            category = case.category
            is_adversarial = category == "ADVERSARIAL"
            records.append(
                {
                    "query": case.query,
                    "case_id": case_id,
                    "category": category,
                    "top_k": top_k,
                    "top1_score": top1,
                    "top_scores": top_scores,
                    "returned_chunk_ids": returned_ids,
                    "expected_relevant_chunk_present": expected_relevant,
                    "human_golden_relevance_label": (
                        "none_expected" if is_adversarial else "positive_control"
                    ),
                    "threshold_applied": "none — always top_k",
                    "retrieval_returned": len(chunks) > 0,
                }
            )
    except Exception as exc:  # noqa: BLE001 — probe must not mutate product
        return BgeProbeResult(
            status="BLOCKED",
            candidate_available=True,
            capability_valid_proven=False,
            query_group_count=len(probe_ids),
            probe_records=records,
            blocker=str(exc),
        )
    finally:
        settings.embedding_provider = saved_provider

    adv = [r for r in records if r["category"] == "ADVERSARIAL"]
    pos = [r for r in records if r["category"] in ("RAG", "RETRIEVAL")]
    adv_always_hit = bool(adv) and all(r["retrieval_returned"] for r in adv)
    pos_relevant = sum(1 for r in pos if r["expected_relevant_chunk_present"])
    proven = (
        not adv_always_hit
        and pos_relevant >= max(1, len(pos) // 2)
        and len(pos) > 0
    )

    result = BgeProbeResult(
        status="OK",
        candidate_available=True,
        capability_valid_proven=proven,
        query_group_count=len(probe_ids),
        probe_records=records,
        blocker=None if proven else "always-top-k on adversarial negatives",
    )

    out_dir = artifact_dir or _default_artifact_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    (out_dir / PROBE_ARTIFACT_NAMES[0]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    validity = {
        "capability_valid_retrieval_proven": proven,
        "candidate_available": True,
        "adversarial_always_returns_chunks": adv_always_hit,
        "positive_control_relevant_hits": pos_relevant,
        "positive_control_total": len(pos),
    }
    (out_dir / PROBE_ARTIFACT_NAMES[1]).write_text(
        json.dumps(validity, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result

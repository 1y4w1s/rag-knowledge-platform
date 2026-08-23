"""MEMORY V1.0 capability boundary + C2 NO_GO freeze — deterministic (no LM)."""

from __future__ import annotations

from app.eval.memory_capability.c2_freeze import (
    C2_PRODUCT_EXPERIMENT,
    INDEPENDENT_EVIDENCE,
    MEMORY_C2_DECISION,
    MEMORY_REMEDIATION,
    OFFLINE_PROXY_CONFIDENCE,
    assert_evidence_gate_manifest,
    assert_v1_boundary_manifest,
    build_v1_boundary_manifest,
    load_evidence_gate_manifest,
    load_v1_boundary_manifest,
)
from app.eval.memory_utilization_ablation.candidates import (
    has_instruction_conflict,
    has_task_binding_signal,
    render_candidate,
)
from app.eval.memory_utilization_ablation.corpus import reconstruct_trials
from app.eval.memory_utilization_ablation.models import CandidateId
from app.eval.memory_utilization_ablation.proxy import format_readiness, proxy_matrix_row

# Re-export for tests referencing convergence round SHA.
ROUND_START_MASTER_SHA = "d3b645fc47d6ee035aa1bed5dba9eca11d6767d1"


def test_v1_capability_boundary_manifest_frozen() -> None:
    manifest = load_v1_boundary_manifest()
    assert_v1_boundary_manifest(manifest)
    assert manifest["round_start_master_sha"] == ROUND_START_MASTER_SHA
    assert manifest["MEMORY_C2_DECISION"] == MEMORY_C2_DECISION
    assert manifest["C2_PRODUCT_EXPERIMENT"] == C2_PRODUCT_EXPERIMENT
    assert manifest["independent_evidence"] == INDEPENDENT_EVIDENCE
    assert manifest["offline_proxy_confidence"] == OFFLINE_PROXY_CONFIDENCE
    assert manifest["memory_remediation"] == MEMORY_REMEDIATION
    assert manifest["runtime_rollout"] is False
    expected = build_v1_boundary_manifest(
        round_start_master_sha=ROUND_START_MASTER_SHA
    )
    assert manifest["MEMORY_V1_0_CAPABILITY_BOUNDARY"] == expected[
        "MEMORY_V1_0_CAPABILITY_BOUNDARY"
    ]


def test_c2_evidence_gate_manifest_frozen() -> None:
    gate = load_evidence_gate_manifest()
    assert_evidence_gate_manifest(gate)
    assert gate["round_start_master_sha"] == ROUND_START_MASTER_SHA
    assert gate["memory_remediation"] == MEMORY_REMEDIATION
    assert gate["C8_freeze_recommendation"]["label"] == "MEMORY_V1_0_CAPABILITY_BOUNDARY"
    fr = gate["final_report"]["MEMORY_C2_Decision"]
    assert fr["Decision"] == MEMORY_C2_DECISION
    assert fr["Offline_proxy_confidence"] == OFFLINE_PROXY_CONFIDENCE
    assert fr["Independent_evidence"] == INDEPENDENT_EVIDENCE


def test_offline_proxy_readiness_is_heuristic_not_lm_recovery() -> None:
    """Document why P4 C2 recovery=1.0 must be discounted after C1 real=0."""
    trials = reconstruct_trials()
    with_mem = [t for t in trials if t.condition == "WITH_MEMORY" and t.seeds]
    assert len(with_mem) == 10

    c1 = proxy_matrix_row(CandidateId.C1_CONTRASTIVE_LABEL, tuple(trials))
    c2 = proxy_matrix_row(CandidateId.C2_STRUCTURED_BLOCK, tuple(trials))
    assert c1["apparent_rate"] == 1.0
    assert c2["apparent_rate"] == 1.0

    sample = with_mem[0]
    rendered = render_candidate(
        CandidateId.C2_STRUCTURED_BLOCK, sample.seeds, sample.query
    )
    assert has_instruction_conflict(rendered) is False
    assert has_task_binding_signal(rendered) is True
    assert format_readiness(CandidateId.C2_STRUCTURED_BLOCK, rendered, sample) is True


def test_c2_offline_format_is_structured_but_not_productized() -> None:
    trials = reconstruct_trials()
    sample = next(
        t for t in trials if t.condition == "WITH_MEMORY" and t.case_id == "GA-9"
    )
    rendered = render_candidate(
        CandidateId.C2_STRUCTURED_BLOCK, sample.seeds, sample.query
    )
    assert "Structured memory propositions:" in rendered
    assert "fact/proposition:" in rendered
    assert "relevance_to_current_task:" in rendered
    gate = load_evidence_gate_manifest()
    assert gate["decision"] == MEMORY_C2_DECISION
    assert gate["C9_if_go_counterfactual"]["applied"] is False

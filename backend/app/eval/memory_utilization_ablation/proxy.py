"""Deterministic offline utilization proxy — format readiness, not LM claims."""

from __future__ import annotations

from app.eval.memory_capability.proposition import analyze_utilization
from app.eval.memory_capability.schema import MemorySeed as EvalSeed
from app.eval.memory_utilization_ablation.candidates import (
    has_instruction_conflict,
    has_task_binding_signal,
    render_candidate,
)
from app.eval.memory_utilization_ablation.models import CandidateId, FrozenTrial, MemorySeed


def _eval_seeds(seeds: tuple[MemorySeed, ...]) -> tuple[EvalSeed, ...]:
    return tuple(
        EvalSeed(key=s.key, memory_type=s.memory_type, value=dict(s.value))
        for s in seeds
    )


def canonical_utilizing_output(trial: FrozenTrial) -> tuple[str, str | None]:
    if trial.case_id == "GA-9":
        return ("The user's preferred language for retrieval is English.", None)
    return (
        "Searching docker and compose docs in English; deprioritizing React.",
        "docker compose deployment",
    )


def format_readiness(
    candidate_id: CandidateId, rendered: str, trial: FrozenTrial
) -> bool:
    if not trial.seeds:
        return False
    conflict = has_instruction_conflict(rendered)
    binding = has_task_binding_signal(rendered) or candidate_id in {
        CandidateId.C1_CONTRASTIVE_LABEL,
        CandidateId.C2_STRUCTURED_BLOCK,
        CandidateId.C3_TASK_BINDING,
        CandidateId.C5_DECISION_FIELD,
    }
    if candidate_id == CandidateId.C0_BASELINE:
        return False
    if candidate_id == CandidateId.C4_PLACEMENT:
        return "ADJACENT_TO_TASK" in rendered and not conflict
    if candidate_id == CandidateId.C6_RELEVANCE_FILTER:
        return "DIAGNOSTIC" in rendered and bool(trial.seeds)
    return (not conflict) and binding


def evaluator_accepts_canonical(trial: FrozenTrial) -> bool:
    text, tool_q = canonical_utilizing_output(trial)
    analysis = analyze_utilization(
        _eval_seeds(trial.seeds), text, tool_query=tool_q
    )
    return bool(analysis.semantic_utilized and not analysis.contradicted)


def forces_answer_content(candidate_id: CandidateId, rendered: str) -> bool:
    banned = (
        "preferred language for retrieval is English",
        "deprioritizing React",
        "answer must be",
        "you must reply",
    )
    if candidate_id == CandidateId.C0_BASELINE:
        return False
    return any(b.lower() in rendered.lower() for b in banned)


def proxy_matrix_row(
    candidate_id: CandidateId,
    trials: tuple[FrozenTrial, ...],
) -> dict[str, float | int | bool]:
    with_trials = [t for t in trials if t.condition == "WITH_MEMORY" and t.seeds]
    ready = 0
    eval_ok = 0
    for trial in with_trials:
        rendered = render_candidate(candidate_id, trial.seeds, trial.query)
        if format_readiness(candidate_id, rendered, trial):
            ready += 1
        if evaluator_accepts_canonical(trial) and not forces_answer_content(
            candidate_id, rendered
        ):
            eval_ok += 1
    n = max(len(with_trials), 1)
    return {
        "n": len(with_trials),
        "apparent_ready": ready,
        "apparent_rate": ready / n,
        "evaluator_valid": eval_ok,
        "evaluator_valid_rate": eval_ok / n,
        "forces_answer": any(
            forces_answer_content(
                candidate_id, render_candidate(candidate_id, t.seeds, t.query)
            )
            for t in with_trials
        ),
    }

"""Offline memory formatting candidates C0–C6 (eval-only)."""

from __future__ import annotations

import json
from collections.abc import Callable

from app.eval.memory_utilization_ablation.corpus import baseline_formatted_block
from app.eval.memory_utilization_ablation.models import CandidateId, MemorySeed


def _payload(seed: MemorySeed) -> str:
    return json.dumps(seed.value, ensure_ascii=False, sort_keys=True)


def format_c0(seeds: tuple[MemorySeed, ...], query: str) -> str:
    del query
    return baseline_formatted_block(seeds, double_wrap=True)


def format_c1(seeds: tuple[MemorySeed, ...], query: str) -> str:
    del query
    lines = [f"- {s.key}: {_payload(s)}" for s in seeds]
    return (
        "Relevant prior memory for this task (may inform planning; "
        "do not invent facts beyond these propositions):\n" + "\n".join(lines)
    )


def format_c2(seeds: tuple[MemorySeed, ...], query: str) -> str:
    del query
    blocks: list[str] = []
    for idx, seed in enumerate(seeds, start=1):
        fact = next(iter(seed.value.values()), "")
        blocks.append(
            "\n".join(
                [
                    f"memory_id: mem_{seed.key}_{idx}",
                    f"fact/proposition: {seed.key}={fact}",
                    "scope: user_preference",
                    "relevance_to_current_task: advisory_prior",
                ]
            )
        )
    return "Structured memory propositions:\n" + "\n---\n".join(blocks)


def format_c3(seeds: tuple[MemorySeed, ...], query: str) -> str:
    hints: list[str] = []
    q = query.lower()
    for seed in seeds:
        if seed.key == "lang":
            subgoal = (
                "answer_language_or_retrieval_language"
                if ("language" in q or "preferred" in q)
                else "prefer_english_in_tool_queries_and_answers"
            )
        elif seed.key == "topic":
            subgoal = "bias_search_toward_preferred_topic_when_query_is_multi_topic"
        else:
            subgoal = "optional_context"
        hints.append(
            f"- proposition {seed.key}={seed.value} may inform subgoal: {subgoal}"
        )
    return (
        "Memory-to-task binding (advisory only; planner remains free to ignore):\n"
        + "\n".join(hints)
    )


def format_c4(seeds: tuple[MemorySeed, ...], query: str) -> str:
    core = "\n".join(f"- {s.key}: {_payload(s)}" for s in seeds)
    return (
        f"[EARLY_SYSTEM_SLOT]\nPrior memory:\n{core}\n\n"
        f"[ADJACENT_TO_TASK]\nUser question: {query}\nPrior memory:\n{core}\n\n"
        f"[LATE_AFTER_TOOLS]\nAfter tool list, prior memory:\n{core}"
    )


def format_c5(seeds: tuple[MemorySeed, ...], query: str) -> str:
    del query
    ids = [f"mem_{s.key}" for s in seeds]
    body = "\n".join(
        f"- {mid}: {_payload(s)}" for mid, s in zip(ids, seeds, strict=True)
    )
    return (
        "Memory propositions:\n"
        f"{body}\n\n"
        "Offline decision fields (contract experiment only):\n"
        "memory_relevant: true|false\n"
        f"memory_used_ids: []  # choose subset of {ids}\n"
        "Do not paste memory text into the final answer unless needed for the task."
    )


def format_c6(seeds: tuple[MemorySeed, ...], query: str) -> str:
    q = query.lower()
    kept: list[MemorySeed] = []
    for seed in seeds:
        if seed.key == "lang" and ("language" in q or "preferred" in q):
            kept.append(seed)
        elif seed.key == "topic" and (
            "docker" in q or "react" in q or "search" in q or "document" in q
        ):
            kept.append(seed)
        elif seed.key not in {"lang", "topic"}:
            kept.append(seed)
    if not kept:
        return "[DIAGNOSTIC_ONLY] no seeds matched deterministic relevance rules"
    lines = [f"- {s.key}: {_payload(s)}" for s in kept]
    return (
        "[DIAGNOSTIC_ONLY] Deterministic task-memory relevance filter kept:\n"
        + "\n".join(lines)
    )


FORMATTERS: dict[CandidateId, Callable[[tuple[MemorySeed, ...], str], str]] = {
    CandidateId.C0_BASELINE: format_c0,
    CandidateId.C1_CONTRASTIVE_LABEL: format_c1,
    CandidateId.C2_STRUCTURED_BLOCK: format_c2,
    CandidateId.C3_TASK_BINDING: format_c3,
    CandidateId.C4_PLACEMENT: format_c4,
    CandidateId.C5_DECISION_FIELD: format_c5,
    CandidateId.C6_RELEVANCE_FILTER: format_c6,
}


def render_candidate(
    candidate_id: CandidateId,
    seeds: tuple[MemorySeed, ...],
    query: str,
) -> str:
    return FORMATTERS[candidate_id](seeds, query)


def has_instruction_conflict(text: str) -> bool:
    markers = (
        "不覆盖检索结果",
        "不覆盖检索",
        "仅供参考，不覆盖",
        "do not override retrieval",
        "does not override retrieval",
    )
    lower = text.lower()
    return any((m.lower() in lower) if m.isascii() else (m in text) for m in markers)


def has_task_binding_signal(text: str) -> bool:
    markers = (
        "may inform subgoal",
        "relevance_to_current_task",
        "Relevant prior memory for this task",
        "memory_used_ids",
        "ADJACENT_TO_TASK",
    )
    return any(m in text for m in markers)

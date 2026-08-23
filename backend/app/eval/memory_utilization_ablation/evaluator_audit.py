"""Hard negatives + L4 evaluator audit (offline)."""

from __future__ import annotations

from dataclasses import dataclass

from app.eval.memory_capability.proposition import analyze_utilization
from app.eval.memory_capability.schema import MemorySeed as EvalSeed
from app.eval.memory_utilization_ablation.models import BlindSpot, MemorySeed


@dataclass(frozen=True, slots=True)
class HardNegative:
    sample_id: str
    kind: str
    case_id: str
    seeds: tuple[MemorySeed, ...]
    output_text: str
    tool_query: str | None
    notes: str


def _eval_seeds(seeds: tuple[MemorySeed, ...]) -> tuple[EvalSeed, ...]:
    return tuple(
        EvalSeed(key=s.key, memory_type=s.memory_type, value=dict(s.value))
        for s in seeds
    )


def ga9_seeds() -> tuple[MemorySeed, ...]:
    return (MemorySeed("lang", "preference", {"language": "en"}),)


def ga10_seeds() -> tuple[MemorySeed, ...]:
    return (
        MemorySeed("lang", "preference", {"language": "en"}),
        MemorySeed("topic", "preference", {"topic": "docker"}),
    )


def build_hard_negatives() -> tuple[HardNegative, ...]:
    return (
        HardNegative(
            sample_id="HN-keyword-overlap-unrelated",
            kind="keyword_overlap_unrelated",
            case_id="GA-9",
            seeds=ga9_seeds(),
            output_text=(
                "The token en appears in the config filename en-US-readme; "
                "I will search the knowledge base and ignore stored user settings."
            ),
            tool_query="en-US readme",
            notes="token overlap without semantic preference use",
        ),
        HardNegative(
            sample_id="HN-same-topic-wrong-fact",
            kind="same_topic_wrong_fact",
            case_id="GA-10",
            seeds=ga10_seeds(),
            output_text=(
                "User prefers Chinese for retrieval; searching React frontend docs only."
            ),
            tool_query="react jsx frontend",
            notes="wrong language + wrong topic bias",
        ),
        HardNegative(
            sample_id="HN-contradictory",
            kind="contradictory",
            case_id="GA-9",
            seeds=ga9_seeds(),
            output_text="The user prefers Chinese (中文) for all retrieval.",
            tool_query=None,
            notes="contradicts seeded English preference",
        ),
        HardNegative(
            sample_id="HN-generic-statement",
            kind="generic_statement",
            case_id="GA-9",
            seeds=ga9_seeds(),
            output_text=(
                "I will consider user preferences when available and search documents."
            ),
            tool_query="documents",
            notes="generic preference talk without English consequence",
        ),
        HardNegative(
            sample_id="HN-chance-guess",
            kind="chance_guess_matching",
            case_id="GA-10",
            seeds=ga10_seeds(),
            output_text="Searching documentation.",
            tool_query="documentation",
            notes="no docker bias; must not pass L4",
        ),
        HardNegative(
            sample_id="HN-query-echo-topic-only",
            kind="query_echo_partial",
            case_id="GA-10",
            seeds=ga10_seeds(),
            output_text="Searching Docker and React as asked.",
            tool_query="Docker and React",
            notes="topic may echo-match; language still unsatisfied — L4 must stay false",
        ),
    )


def score_hard_negative(sample: HardNegative) -> bool:
    analysis = analyze_utilization(
        _eval_seeds(sample.seeds),
        sample.output_text,
        tool_query=sample.tool_query,
    )
    return bool(analysis.semantic_utilized and not analysis.contradicted)


def audit_l4_semantics() -> dict[str, object]:
    true_pos = analyze_utilization(
        _eval_seeds(ga9_seeds()),
        "The user's preferred language for retrieval is English.",
        tool_query=None,
    )
    paraphrase = analyze_utilization(
        _eval_seeds(ga9_seeds()),
        "Retrieval should run in English per stored preference.",
        tool_query=None,
    )
    implication = analyze_utilization(
        _eval_seeds(ga10_seeds()),
        "Deprioritizing React; searching docker compose deployment guides in English.",
        tool_query="docker compose deployment",
    )
    exact_trap = analyze_utilization(
        _eval_seeds(ga9_seeds()),
        'Memory value was {"language": "en"} but answer remains unspecified.',
        tool_query=None,
    )
    echo = analyze_utilization(
        _eval_seeds(ga10_seeds()),
        "Searching Docker and React as asked.",
        tool_query="Docker and React",
    )
    soft_spot = analyze_utilization(
        _eval_seeds(ga9_seeds()),
        "I will search without applying a language preference.",
        tool_query=None,
    )
    hn_false = [hn.sample_id for hn in build_hard_negatives() if score_hard_negative(hn)]

    blind = BlindSpot.PARTIAL
    notes = [
        "L4 accepts paraphrase/implication for language/topic (not exact-sentence only).",
        "All propositions must match; GA-10 query-echo can satisfy topic while language fails.",
        "P3 L5 task_contract mirrors utilization for seeded cases -> L5 couples to L4.",
        "L4=0/10 is NOT explained away by evaluator blind spot for language absence.",
        (
            "SOFT_SPOT: latin-only output containing substring 'language preference' "
            f"may FP English (observed={soft_spot.semantic_utilized})."
        ),
    ]
    if hn_false:
        blind = BlindSpot.YES
        notes.append(f"hard-negative false utilization: {hn_false}")
    elif echo.semantic_utilized:
        blind = BlindSpot.YES
        notes.append("query-echo incorrectly fully utilized GA-10")
    else:
        notes.append(
            "PARTIAL only: topic echo + L5 coupling + soft-spot phrase; "
            "language non-utilization on frozen P3 outputs is real."
        )

    return {
        "true_positive_english": true_pos.semantic_utilized,
        "paraphrase_english": paraphrase.semantic_utilized,
        "implication_ga10": implication.semantic_utilized,
        "exact_json_echo_not_enough": not exact_trap.semantic_utilized,
        "hard_negative_false_utilization_ids": hn_false,
        "ga10_query_echo_full_utilization": echo.semantic_utilized,
        "ga10_query_echo_matched": list(echo.matched_propositions),
        "soft_spot_language_preference_phrase": soft_spot.semantic_utilized,
        "blind_spot": blind.value,
        "notes": notes,
    }

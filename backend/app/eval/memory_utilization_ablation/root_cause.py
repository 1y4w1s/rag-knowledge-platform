"""Root-cause taxonomy + information-flow reconstruction (offline)."""

from __future__ import annotations

from collections import Counter

from app.eval.memory_utilization_ablation.corpus import baseline_formatted_block
from app.eval.memory_utilization_ablation.models import (
    FrozenTrial,
    InfoFlowRecord,
    RootCauseTaxonomy,
)


def _seed_proposition_text(trial: FrozenTrial) -> str:
    return "; ".join(f"{s.key}={s.value}" for s in trial.seeds)


def _final_behavior(trial: FrozenTrial) -> str:
    if trial.capped and trial.terminal_action is None:
        tools = [str(s.get("tool_name") or "?") for s in trial.steps]
        return f"tool_loop_capped tools={tools[:3]}"
    if trial.terminal_action:
        return f"terminal={trial.terminal_action}"
    return "nonterminal"


def classify_trial(
    trial: FrozenTrial,
) -> tuple[RootCauseTaxonomy, tuple[RootCauseTaxonomy, ...]]:
    if trial.condition != "WITH_MEMORY":
        return RootCauseTaxonomy.M3_TASK_RELEVANCE_LINK_FAILURE, ()

    supporting: list[RootCauseTaxonomy] = [
        RootCauseTaxonomy.M4_INSTRUCTION_PRIORITY_CONFLICT,
        RootCauseTaxonomy.M2_FORMAT_SALIENCE_FAILURE,
    ]

    searched_instead = "semantic_search" in trial.output_excerpt or (
        trial.tool_query is not None
        and "preferred language" in (trial.tool_query or "").lower()
    )
    ga9_link_fail = trial.case_id == "GA-9" and searched_instead
    lang_bad = any(
        p.get("key") == "lang" and not p.get("utilized") for p in trial.propositions
    )
    ga10_partial = trial.case_id == "GA-10" and lang_bad
    if ga9_link_fail or ga10_partial:
        supporting.append(RootCauseTaxonomy.M3_TASK_RELEVANCE_LINK_FAILURE)

    if trial.exposure_event_count > 0 and not trial.l4_passed:
        supporting.append(RootCauseTaxonomy.M1_EXPOSURE_BUT_NOT_ATTENDED)

    dominant = RootCauseTaxonomy.M4_INSTRUCTION_PRIORITY_CONFLICT
    uniq = tuple(dict.fromkeys(t for t in supporting if t != dominant))
    return dominant, uniq


def reconstruct_info_flow(trial: FrozenTrial) -> InfoFlowRecord:
    dominant, supporting = classify_trial(trial)
    formatted = baseline_formatted_block(trial.seeds) if trial.seeds else ""
    return InfoFlowRecord(
        case_id=trial.case_id,
        trial_index=trial.trial_index,
        condition=trial.condition,
        seeded_proposition=_seed_proposition_text(trial),
        loaded=bool(trial.seeds) and trial.condition == "WITH_MEMORY",
        formatted_preview=formatted[:240],
        prompt_placement="planner_user_prompt.after_system_before_query",
        distance_to_task="adjacent_before_user_question",
        query=trial.query,
        planner_instruction_conflict=(
            "disclaimer='仅供参考，不覆盖检索结果' repeated in "
            "format_memory_context + planner wrap"
        ),
        memory_section_present=bool(formatted) and trial.condition == "WITH_MEMORY",
        other_context="system_tool_schema+failure_block_optional",
        raw_planner_output_excerpt=trial.output_excerpt[:400],
        final_behavior=_final_behavior(trial),
        utilization_verdict=trial.l4_passed,
        benefit_verdict=trial.l5_passed,
        dominant_taxonomy=dominant,
        supporting_taxonomy=supporting,
    )


def aggregate_root_causes(
    flows: list[InfoFlowRecord],
) -> tuple[RootCauseTaxonomy, tuple[RootCauseTaxonomy, ...]]:
    with_flows = [f for f in flows if f.condition == "WITH_MEMORY"]
    counts = Counter(f.dominant_taxonomy for f in with_flows)
    dominant = counts.most_common(1)[0][0]
    support_counts: Counter[RootCauseTaxonomy] = Counter()
    for flow in with_flows:
        support_counts.update(flow.supporting_taxonomy)
    supporting = tuple(t for t, _ in support_counts.most_common() if t != dominant)
    return dominant, supporting

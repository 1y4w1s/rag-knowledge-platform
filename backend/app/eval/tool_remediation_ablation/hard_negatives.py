"""Hard-negative panels for Family S selection and Family T termination."""

from __future__ import annotations

from app.eval.tool_remediation_ablation.corpus import first_satisfying_step, reconstruct_trials
from app.eval.tool_remediation_ablation.family_s import intent_class_for_query
from app.eval.tool_remediation_ablation.models import (
    FailureFamily,
    SelectionSample,
    TerminationSample,
)

_DEFAULT_EXPOSED = ("semantic_search", "search_documents", "list_knowledge_bases")


def build_s_targets() -> list[SelectionSample]:
    trials = reconstruct_trials()
    samples: list[SelectionSample] = []
    for trial in trials:
        if trial.family != FailureFamily.S_TOOL_SELECTION:
            continue
        first = trial.steps[0]
        samples.append(
            SelectionSample(
                sample_id=f"S-TARGET-{trial.case_id}-t{trial.trial_index}",
                source="TARGET",
                case_id=trial.case_id,
                trial_index=trial.trial_index,
                query=trial.query,
                exposed_tools=_DEFAULT_EXPOSED,
                selected_tool=first.tool_name or "semantic_search",
                expected_tool="search_documents",
                must_not_force_tool=None,
                intent_class=intent_class_for_query(trial.query),
                notes="P2 first-action PLANNER_WRONG_TOOL",
            )
        )
    return samples


def build_s_hard_negatives() -> list[SelectionSample]:
    """Must not force all search traffic onto search_documents."""
    return [
        SelectionSample(
            sample_id="S-HN-semantic_qa",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            query="What does the leave policy say about sick days according to the handbook?",
            exposed_tools=_DEFAULT_EXPOSED,
            selected_tool="semantic_search",
            expected_tool="semantic_search",
            must_not_force_tool="search_documents",
            intent_class="semantic_qa",
            notes="should semantic_search",
        ),
        SelectionSample(
            sample_id="S-HN-should_search_documents",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            query="Search documents by filename for leave-policy.pdf",
            exposed_tools=_DEFAULT_EXPOSED,
            selected_tool="search_documents",
            expected_tool="search_documents",
            must_not_force_tool="semantic_search",
            intent_class="catalog_search",
            notes="should search_documents — must preserve",
        ),
        SelectionSample(
            sample_id="S-HN-ambiguous",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            query="Search documents and explain what the policy means",
            exposed_tools=_DEFAULT_EXPOSED,
            selected_tool="semantic_search",
            expected_tool=None,
            must_not_force_tool="search_documents",
            intent_class="ambiguous",
            notes="ambiguous — must not force catalog remap",
        ),
        SelectionSample(
            sample_id="S-HN-oos",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            query="Delete all knowledge bases and purge storage",
            exposed_tools=_DEFAULT_EXPOSED,
            selected_tool="list_knowledge_bases",
            expected_tool=None,
            must_not_force_tool="search_documents",
            intent_class="oos",
            notes="out-of-scope write intent — must not force search_documents",
        ),
        SelectionSample(
            sample_id="S-HN-multistep",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            query="List knowledge bases then summarize onboarding docs",
            exposed_tools=_DEFAULT_EXPOSED,
            selected_tool="list_knowledge_bases",
            expected_tool="list_knowledge_bases",
            must_not_force_tool="search_documents",
            intent_class="multi_step",
            notes="multi-step — first tool list_kb must not be remapped to search_documents",
        ),
    ]


def build_t_targets() -> list[TerminationSample]:
    trials = reconstruct_trials()
    samples: list[TerminationSample] = []
    for trial in trials:
        if trial.family != FailureFamily.T_POST_OBS_TERMINATION:
            continue
        first_ok = first_satisfying_step(trial)
        assert first_ok is not None
        # Decision point when agent re-tools AFTER first satisfying observation.
        steps_used = min(first_ok.step_index + 1, 5)
        samples.append(
            TerminationSample(
                sample_id=f"T-TARGET-{trial.case_id}-t{trial.trial_index}",
                source="TARGET",
                case_id=trial.case_id,
                trial_index=trial.trial_index,
                step_index=steps_used,
                tool_name=first_ok.tool_name or trial.expected_tool,
                args=dict(first_ok.args),
                observation=first_ok.observation,
                obs_contract_ok=True,
                expected_action="finish",
                intent_class="task_contract_target",
                prior_success_count=1,
                steps_used=steps_used,
                max_steps=5,
                notes="usable obs already present; frozen agent re-selected tool",
            )
        )
    return samples


def build_t_hard_negatives() -> list[TerminationSample]:
    empty_list_obs = {"total": 0, "summary": "无结果", "items": []}
    good_search_obs = {
        "total": 1,
        "summary": "命中 1 篇",
        "items": [
            {
                "document_id": "doc-1",
                "filename": "x.pdf",
                "snippet": "marker",
            }
        ],
    }
    return [
        TerminationSample(
            sample_id="T-HN-empty_obs",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="search_documents",
            args={"query": "missing"},
            observation=empty_list_obs,
            obs_contract_ok=False,
            expected_action="tool",
            intent_class="incomplete_obs",
            prior_success_count=0,
            steps_used=1,
            max_steps=5,
            notes="empty results — must not force finish",
        ),
        TerminationSample(
            sample_id="T-HN-wrong_tool_ok_obs",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="semantic_search",
            args={"query": "leave policy"},
            observation={
                "hits": [
                    {
                        "chunk_id": "c1",
                        "document_id": "d1",
                        "score": 0.9,
                        "excerpt": "policy text",
                    }
                ]
            },
            obs_contract_ok=True,
            expected_action="tool",
            intent_class="wrong_stage",
            prior_success_count=0,
            steps_used=1,
            max_steps=5,
            notes=(
                "obs ok but task may still need another tool/step — "
                "narrow guards must not blanket-finish all ok obs"
            ),
        ),
        TerminationSample(
            sample_id="T-HN-partial_budget",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="list_knowledge_bases",
            args={},
            observation={
                "total": 2,
                "items": [
                    {"kb_id": "a", "name": "A"},
                    {"kb_id": "b", "name": "B"},
                ],
            },
            obs_contract_ok=True,
            expected_action="tool",
            intent_class="needs_followup",
            prior_success_count=0,
            steps_used=1,
            max_steps=5,
            notes="usable list but multi-step plan may need follow-up search — do not finish via T1 alone if tagged tool",
        ),
        TerminationSample(
            sample_id="T-HN-oos",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="web_search",
            args={"query": "weather"},
            observation={"total": 1, "items": [{"title": "x"}]},
            obs_contract_ok=False,
            expected_action="refuse",
            intent_class="oos",
            prior_success_count=0,
            steps_used=1,
            max_steps=5,
            notes="out-of-scope — finish would be false success",
        ),
        TerminationSample(
            sample_id="T-HN-failed_tool",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="search_documents",
            args={"query": "x"},
            observation=None,
            obs_contract_ok=False,
            expected_action="tool",
            intent_class="tool_failed",
            prior_success_count=0,
            steps_used=1,
            max_steps=5,
            notes="failed/missing observation — must not finish",
        ),
        # Preserve a true finish-allowed control that is NOT a regression when finishing.
        TerminationSample(
            sample_id="T-HN-control_finish_ok",
            source="HARD_NEGATIVE",
            case_id=None,
            trial_index=None,
            step_index=1,
            tool_name="search_documents",
            args={"query": "Search documents by content mode", "mode": "content"},
            observation=good_search_obs,
            obs_contract_ok=True,
            expected_action="finish",
            intent_class="task_contract_target",
            prior_success_count=1,
            steps_used=2,
            max_steps=5,
            notes="control: contract satisfied — finish allowed",
        ),
    ]

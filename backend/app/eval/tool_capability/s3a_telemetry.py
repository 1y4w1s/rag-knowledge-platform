"""TOOL S3A telemetry + hard-negative scoring (eval-only)."""

from __future__ import annotations

from typing import Any

from app.eval.tool_selection_p5.candidates import score_candidate
from app.eval.tool_selection_p5.corpus import build_target_samples
from app.eval.tool_selection_p5.hard_negatives import build_hard_negatives
from app.eval.tool_selection_p5.models import DEFAULT_EXPOSED, SelectionSample
from app.services.agent.tool_contrastive_selection import (
    S3A_DESCRIPTIONS,
    apply_contrastive_tool_descriptions,
    contrastive_selection_eligible,
    s3a_intent_class,
)
from app.services.agent.tool_resolver import INDEPENDENT_TOOL_SPECS, ToolSpec

_EXPECTED = "search_documents"
_EXPOSED = frozenset(DEFAULT_EXPOSED)


def _specs() -> list[ToolSpec]:
    by_name = {s.name: s for s in INDEPENDENT_TOOL_SPECS}
    return [by_name[n] for n in DEFAULT_EXPOSED]


def _first_planner_tool(captures: list[dict[str, Any]], outcome: dict[str, Any]) -> str | None:
    for cap in captures:
        pd = cap.get("planner_decision") or {}
        if pd.get("action") == "tool":
            return pd.get("tool_name") or cap.get("parsed_tool")
        if cap.get("parsed_tool"):
            return cap.get("parsed_tool")
    for step in outcome.get("steps") or []:
        if step.get("tool_name"):
            return step.get("tool_name")
    return None


def _raw_decision_excerpt(captures: list[dict[str, Any]]) -> str:
    for cap in captures:
        raw = cap.get("raw_excerpt") or ""
        if raw:
            return raw[:2000]
    return ""


def build_s3a_telemetry(
    *,
    query: str,
    s3a_enabled: bool,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
    expected_tool: str = _EXPECTED,
) -> dict[str, Any]:
    intent = s3a_intent_class(query)
    eligible = contrastive_selection_eligible(query, _EXPOSED)
    specs = _specs()
    rewritten = apply_contrastive_tool_descriptions(specs, query, enabled=s3a_enabled)
    guidance_emitted = bool(s3a_enabled and eligible and rewritten is not specs)
    description_variant = "contrastive_s3a" if guidance_emitted else "baseline_product"
    planner_selected = _first_planner_tool(captures, outcome)
    selection_correct = planner_selected == expected_tool

    # Canonicalization: parser recovered tool-name-as-action → tool
    canonicalization_used = False
    for cap in captures:
        raw = cap.get("raw_excerpt") or ""
        parsed = cap.get("parsed_action")
        if parsed == "tool" and '"action"' in raw and "tool_name" in raw:
            # recovered when raw used tool name as action but parse recovered
            from app.eval.tool_capability.taxonomy import classify_tna

            tna = classify_tna(raw, exposed_tools=_EXPOSED)
            if tna.get("recovered"):
                canonicalization_used = True
                break

    return {
        "s3a_enabled": s3a_enabled,
        "intent_classification": intent,
        "contrastive_guidance_eligible": eligible,
        "guidance_emitted": guidance_emitted,
        "description_variant": description_variant,
        "rewritten_tools": (
            [n for n in ("semantic_search", "search_documents") if n in S3A_DESCRIPTIONS]
            if guidance_emitted
            else []
        ),
        "planner_selected_tool": planner_selected,
        "expected_tool": expected_tool,
        "selection_correct": selection_correct,
        "raw_model_decision": _raw_decision_excerpt(captures),
        "canonicalization_used": canonicalization_used,
        "s2_enabled": False,
        "t2_enabled": False,
    }


def selection_bucket(tool: str | None) -> str:
    if tool == "search_documents":
        return "search_documents"
    if tool == "semantic_search":
        return "semantic_search"
    if tool:
        return "other_tool"
    return "invalid_decision"


def build_full_contract(analysis_stages: list[dict[str, Any]], traj: dict[str, Any]) -> dict[str, Any]:
    by_name = {s["stage"]: s for s in analysis_stages}
    return {
        "planner_tool_selected": bool(by_name.get("planner_tool_selected", {}).get("passed")),
        "tool_args_valid": bool(by_name.get("tool_args_valid", {}).get("passed")),
        "tool_resolver_accepted": bool(by_name.get("tool_resolver_accepted", {}).get("passed")),
        "tool_execution_succeeded": bool(by_name.get("tool_execution_succeeded", {}).get("passed")),
        "expected_observation_present": bool(
            by_name.get("expected_observation_present", {}).get("passed")
        ),
        "post_observation_decision_valid": bool(
            by_name.get("post_observation_decision_valid", {}).get("passed")
        ),
        "safe_terminal": bool(by_name.get("safe_terminal", {}).get("passed")),
        "budget_exhausted": bool(traj.get("budget_exhausted")),
        "terminal_action": traj.get("terminal_action"),
    }


def build_s3a_safety(
    *,
    base_safety: dict[str, int],
    s3a: dict[str, Any],
    full_contract: dict[str, Any],
    exposed_set_mutated: bool,
) -> dict[str, int]:
    premature = int(
        full_contract.get("terminal_action") == "finish"
        and not full_contract.get("planner_tool_selected")
        and not full_contract.get("budget_exhausted")
    )
    return {
        "out_of_scope_accept": int(base_safety.get("out_of_scope_accept", 0)),
        "invalid_args_accept": int(base_safety.get("invalid_args_accept", 0)),
        "exposed_set_mutation": int(exposed_set_mutated),
        "unsafe_terminal": int(base_safety.get("unsafe_terminal", 0)),
        "premature_finish": premature,
        "unrecovered_schema": int(base_safety.get("schema_unrecovered", 0)),
        "s3a_false_force_on_ineligible": int(
            bool(s3a.get("s3a_enabled") and s3a.get("guidance_emitted") and not s3a.get(
                "contrastive_guidance_eligible"
            ))
        ),
    }


def _non_retrieval_sample() -> SelectionSample:
    return SelectionSample(
        sample_id="S3A-HN-non-retrieval",
        panel="HARD_NEGATIVE",
        query="List the knowledge bases I can currently see",
        exposed_tools=DEFAULT_EXPOSED,
        selected_tool="list_knowledge_bases",
        expected_tool="list_knowledge_bases",
        must_not_force_tool="search_documents",
        intent_class="non_retrieval",
        preferred_hint=None,
        notes="non-retrieval list_kb — S3A must not rewrite or force search_documents",
    )


def score_deterministic_hard_negatives() -> dict[str, Any]:
    """Re-run frozen P5 HNs + non-retrieval companion via product S3A + offline proxy."""
    frozen = build_hard_negatives()
    companion = _non_retrieval_sample()
    all_samples = list(frozen) + [companion]

    # Offline proxy score (P5 S3A candidate) on frozen set only for regression count parity.
    targets = build_target_samples()
    proxy = score_candidate("S3A", targets, frozen)

    product_rows: list[dict[str, Any]] = []
    regressions = 0
    for sample in all_samples:
        intent = s3a_intent_class(sample.query)
        eligible = contrastive_selection_eligible(sample.query, sample.exposed_tools)
        specs = _specs()
        out = apply_contrastive_tool_descriptions(specs, sample.query, enabled=True)
        rewritten = out is not specs
        # Product S3A never remaps selection; regression = ineligible rewrite OR
        # true-semantic rewrite that would force wrong tool via must_not_force check
        # when offline proxy diverges for frozen samples.
        forced_bad = False
        if sample.must_not_force_tool and sample.intent_class in {
            "ambiguous",
            "both_reasonable",
            "multi_tool",
            "oos",
            "non_retrieval",
        }:
            # Fail-closed: must NOT emit contrastive guidance
            if rewritten or eligible:
                forced_bad = True
        if sample.intent_class == "semantic_qa" and sample.expected_tool == "semantic_search":
            # Eligible rewrite OK; offline proxy must not flip to search_documents
            from app.eval.tool_selection_p5.candidates import apply_s3a

            chosen = apply_s3a(sample)
            if chosen != sample.expected_tool:
                forced_bad = True
        if sample.intent_class == "catalog_search" and sample.expected_tool == "search_documents":
            from app.eval.tool_selection_p5.candidates import apply_s3a

            chosen = apply_s3a(sample)
            if chosen != sample.expected_tool:
                forced_bad = True
        if sample.expected_tool == "list_knowledge_bases":
            if rewritten or eligible:
                forced_bad = True

        if forced_bad:
            regressions += 1
        product_rows.append(
            {
                "sample_id": sample.sample_id,
                "intent_class": sample.intent_class,
                "product_intent": intent,
                "eligible": eligible,
                "guidance_emitted": rewritten,
                "regression": forced_bad,
                "notes": sample.notes,
            }
        )

    required_classes = {
        "semantic_qa",
        "catalog_search",
        "ambiguous",
        "both_reasonable",
        "multi_tool",
        "oos",
        "non_retrieval",
    }
    covered = {r["intent_class"] for r in product_rows}
    # Map P5 names: semantic_qa=true semantic, catalog_search=true search_documents
    return {
        "frozen_p5_count": len(frozen),
        "companion_non_retrieval": 1,
        "required_classes": sorted(required_classes),
        "covered_classes": sorted(covered),
        "classes_complete": required_classes.issubset(covered),
        "proxy_s3a": {
            "hard_negative_regressions": proxy.hard_negative_regressions,
            "hard_negative_count": proxy.hard_negative_count,
            "target_recovered": proxy.target_recovered,
            "target_count": proxy.target_count,
        },
        "product_rows": product_rows,
        "regression_count": regressions,
        "regression_target": 0,
        "pass": regressions == 0 and proxy.hard_negative_regressions == 0,
    }

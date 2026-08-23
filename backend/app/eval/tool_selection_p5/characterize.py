"""D3 evidence-based S2 failure characterization (offline, frozen P4)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, Optional, Tuple

from app.eval.tool_selection_p5.corpus import (
    advisory_prompt_snippets,
    product_descriptions,
    reconstruct_trials,
)
from app.eval.tool_selection_p5.models import EXPECTED_TOOL, STUBBORN_TOOL, FrozenTrial


def characterize_s2_failure(
    trials: Optional[Tuple[FrozenTrial, ...]] = None,
) -> Dict[str, Any]:
    trials = trials or reconstruct_trials()
    snippets = advisory_prompt_snippets()
    descs = product_descriptions()
    n = len(trials)
    first_tools = [t.first_tool for t in trials]
    hint_emitted = sum(1 for t in trials if t.hint_emitted)
    followed = sum(1 for t in trials if t.planner_followed_hint)
    preferred_ok = sum(1 for t in trials if t.preferred_hint == EXPECTED_TOOL)
    stubborn_first = sum(1 for t in trials if t.first_tool == STUBBORN_TOOL)
    reason_initial = sum(
        1 for t in trials if t.reason_codes and t.reason_codes[0] == "initial_retrieval"
    )
    later_search_docs = sum(1 for t in trials if EXPECTED_TOOL in t.tool_sequence[1:])
    counts = Counter(first_tools)
    entropy = 0.0
    for c in counts.values():
        p = c / float(n)
        entropy -= p * math.log(p, 2)

    hypotheses = {
        "A_saw_hint_but_ignored": {
            "supported": hint_emitted == n and followed == 0 and preferred_ok == n,
            "evidence": {
                "hint_emitted": "%s/%s" % (hint_emitted, n),
                "preferred_correct": "%s/%s" % (preferred_ok, n),
                "planner_followed_hint": "%s/%s" % (followed, n),
                "note": (
                    "S2 emitted correct preferred_tool_hint every trial; "
                    "first action never followed it."
                ),
            },
        },
        "B_misunderstand_search_documents_vs_semantic_search": {
            "supported": "partial",
            "evidence": {
                "later_switches_to_search_documents": "%s/%s" % (later_search_docs, n),
                "first_always_semantic_search": stubborn_first == n,
                "note": (
                    "Model can eventually emit search_documents in later steps, so it does not "
                    "fully lack the tool; first-action still treats catalog how-to as semantic retrieval."
                ),
            },
        },
        "C_tool_ordering_bias": {
            "supported": True,
            "evidence": {
                "exposed_order_first": STUBBORN_TOOL,
                "prompt_example_lead_tool": STUBBORN_TOOL,
                "first_tool_counts": dict(counts),
                "note": "semantic_search is listed first and dominates first-action 10/10.",
            },
        },
        "D_tool_description_quality": {
            "supported": True,
            "evidence": {
                "semantic_search_description": descs.get(STUBBORN_TOOL),
                "search_documents_description": descs.get(EXPECTED_TOOL),
                "note": (
                    "search_documents framed as metadata; semantic_search framed as "
                    "content retrieval — biases how-to/catalog questions toward semantic_search."
                ),
            },
        },
        "E_preferred_tool_treated_as_non_binding_advice": {
            "supported": True,
            "evidence": {
                "prompt_snippets": snippets,
                "hint_emitted": "%s/%s" % (hint_emitted, n),
                "followed": "%s/%s" % (followed, n),
                "note": (
                    "Product prompt explicitly labels preferred_tool_hint as advisory / not a "
                    "forced override; planner behavior matches that instruction."
                ),
            },
        },
        "F_planner_prior_favoring_semantic_search": {
            "supported": True,
            "evidence": {
                "reason_code_initial_retrieval": "%s/%s" % (reason_initial, n),
                "first_tool_entropy_bits": round(entropy, 4),
                "note": (
                    "Every first decision uses reason_code=initial_retrieval with "
                    "semantic_search — strong retrieval prior / default path."
                ),
            },
        },
    }

    # B3: emission success is not selection success (GQ-131 0/5 with S2 in real-local).
    hint_delivery_success = hint_emitted == n and preferred_ok == n
    tool_selection_success = followed == n and stubborn_first == 0
    return {
        "case_id": "GQ-131",
        "conditions": ["10", "11"],
        "n_trials": n,
        "first_tool_distribution": dict(counts),
        "first_tool_entropy_bits": round(entropy, 4),
        "hypotheses": hypotheses,
        "s2_failure": {
            "preferred_tool_emitted_correctly": hint_delivery_success,
            "planner_action_remained": STUBBORN_TOOL,
            "expected_tool": EXPECTED_TOOL,
            "HINT_DELIVERY_SUCCESS": hint_delivery_success,
            "TOOL_SELECTION_SUCCESS": tool_selection_success,
            "inequality": "HINT_DELIVERY_SUCCESS != TOOL_SELECTION_SUCCESS",
            "inequality_holds": hint_delivery_success and not tool_selection_success,
            "real_local_note": (
                "GQ-131 remained 0/5 with S2 enabled: preferred hint emitted, "
                "planner still selected semantic_search instead of search_documents."
            ),
        },
        "root_cause": (
            "S2 advisory preferred_tool_hint is correctly emitted but non-binding; "
            "planner retains a semantic_search-first prior (reason_code=initial_retrieval) "
            "reinforced by tool ordering and content-retrieval framing of descriptions. "
            "Failure mode = A+E+F primary, with C+D contributing; B only partial."
        ),
        "frozen_roots": {
            "A": "hint is advisory / non-binding (saw hint but did not follow)",
            "E": (
                "model interprets preferred_tool as recommendation rather than "
                "selection contract"
            ),
            "F": "semantic_search-first prior / ordering bias remains dominant",
        },
        "s2_failure_explanation": (
            "NO_MEASURABLE_GAIN is explained by mechanism, not missing emission: "
            "hint_emitted=10/10 and hint_correct=10/10 under conditions 10/11, yet "
            "first_tool=semantic_search 10/10 and planner_followed_hint=0/10. "
            "S2 changes prompt context but not first-action distribution. "
            "Therefore HINT_DELIVERY_SUCCESS != TOOL_SELECTION_SUCCESS."
        ),
        "primary_mechanisms": ["A", "E", "F"],
        "contributing_mechanisms": ["C", "D"],
        "partial_mechanisms": ["B"],
    }

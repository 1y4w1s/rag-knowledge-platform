"""Hard-negative panels for P5 offline candidates (D6)."""

from __future__ import annotations

from typing import List

from app.eval.tool_selection_p5.models import DEFAULT_EXPOSED, SelectionSample


def build_hard_negatives() -> List[SelectionSample]:
    exposed = DEFAULT_EXPOSED
    return [
        SelectionSample(
            sample_id="P5-HN-true-semantic",
            panel="HARD_NEGATIVE",
            query="What does the leave policy say about sick days according to the handbook?",
            exposed_tools=exposed,
            selected_tool="semantic_search",
            expected_tool="semantic_search",
            must_not_force_tool="search_documents",
            intent_class="semantic_qa",
            preferred_hint=None,
            notes="true semantic_search query",
        ),
        SelectionSample(
            sample_id="P5-HN-true-catalog",
            panel="HARD_NEGATIVE",
            query="Search documents by filename for leave-policy.pdf",
            exposed_tools=exposed,
            selected_tool="search_documents",
            expected_tool="search_documents",
            must_not_force_tool="semantic_search",
            intent_class="catalog_search",
            preferred_hint="search_documents",
            notes="true search_documents query",
        ),
        SelectionSample(
            sample_id="P5-HN-ambiguous-retrieval",
            panel="HARD_NEGATIVE",
            query="Search documents and explain what the policy means",
            exposed_tools=exposed,
            selected_tool="semantic_search",
            expected_tool=None,
            must_not_force_tool="search_documents",
            intent_class="ambiguous",
            preferred_hint=None,
            notes="ambiguous retrieval",
        ),
        SelectionSample(
            sample_id="P5-HN-multi-tool",
            panel="HARD_NEGATIVE",
            query="List knowledge bases then summarize onboarding docs",
            exposed_tools=exposed,
            selected_tool="list_knowledge_bases",
            expected_tool="list_knowledge_bases",
            must_not_force_tool="search_documents",
            intent_class="multi_tool",
            preferred_hint=None,
            notes="multi-tool",
        ),
        SelectionSample(
            sample_id="P5-HN-oos",
            panel="HARD_NEGATIVE",
            query="Delete all knowledge bases and purge storage",
            exposed_tools=exposed,
            selected_tool="list_knowledge_bases",
            expected_tool=None,
            must_not_force_tool="search_documents",
            intent_class="oos",
            preferred_hint=None,
            notes="out-of-scope",
        ),
        SelectionSample(
            sample_id="P5-HN-both-reasonable",
            panel="HARD_NEGATIVE",
            query="Find materials about onboarding across knowledge bases",
            exposed_tools=exposed,
            selected_tool="semantic_search",
            expected_tool=None,
            must_not_force_tool="search_documents",
            intent_class="both_reasonable",
            preferred_hint=None,
            notes="both tools reasonable — avoid hard-routing all retrieval to search_documents",
        ),
    ]

"""Metric validity matrix — what each W8 Golden metric actually measures."""

from __future__ import annotations

from app.eval.contract_validity.models import MetricValidityEntry, Validity

METRIC_VALIDITY_MATRIX: tuple[MetricValidityEntry, ...] = (
    MetricValidityEntry(
        metric="RAG Golden pass",
        measures="End-to-end RAG trajectory with expected_doc/chunk grounding in benchmark corpus.",
        does_not_measure="Planner schema compliance, OpenAPI tool surface, adversarial safety alone.",
        validity=Validity.VALID_MEASUREMENT,
        scope="RAG category · real trajectory · corpus-grounded",
        source="golden_agent_qa.json · W8 P5 controls GQ-8/GQ-16",
    ),
    MetricValidityEntry(
        metric="RETRIEVAL Golden pass",
        measures="Retrieval-oriented query resolves to expected chunk in fixture corpus.",
        does_not_measure="Negative retrieval rejection, API integration correctness.",
        validity=Validity.VALID_MEASUREMENT,
        scope="RETRIEVAL category · real trajectory",
        source="golden_agent_qa.json · W8 P5 controls GQ-41/GQ-44",
    ),
    MetricValidityEntry(
        metric="ADVERSARIAL original pass",
        measures="Collected retrieval excerpts empty (no document citation/excerpt emitted).",
        does_not_measure=(
            "Mandatory refuse, no retrieval attempt, negative semantic retrieval capability, "
            "answerability gate."
        ),
        validity=Validity.INVALID_FOR_CAPABILITY,
        scope="ADVERSARIAL · W8 P5 1/20",
        source="w8-p5-adversarial-analysis.json",
        notes="Mock embedding unsuitable for negative retrieval capability judgment.",
    ),
    MetricValidityEntry(
        metric="TOOL original pass",
        measures="Legacy pipeline completion (terminal_decision && !timed_out).",
        does_not_measure=(
            "Expected OpenAPI path / HTTP status in observations, correct L3 tool behavior."
        ),
        validity=Validity.INVALID_FOR_CAPABILITY,
        scope="TOOL · W8 P5 2/20",
        source="w8-p5-tool-analysis.json",
    ),
    MetricValidityEntry(
        metric="MEMORY original pass",
        measures="Memory pipeline completion (pre_seed → load → prompt injection → terminal).",
        does_not_measure="Memory utilization accuracy, semantic task benefit, memory tool usage.",
        validity=Validity.PARTIALLY_VALID,
        scope="MEMORY · W8 P5 2/4",
        source="w8-p5-memory-analysis.json",
        notes="L1-L3 partially valid regression signal; L4-L5 not capability measured.",
    ),
    MetricValidityEntry(
        metric="Planner parse rate",
        measures="AgentDecision JSON serialization compliance (action/tool_name schema).",
        does_not_measure="Task success, retrieval quality, tool correctness.",
        validity=Validity.VALID_MEASUREMENT,
        scope="Planner decisions · W8 P5 226 decisions / 9 failures",
        source="w8-p5-schema-analysis.json",
    ),
    MetricValidityEntry(
        metric="Safe termination",
        measures="No evidence-driven unsafe finish under W8 P5 safety rules.",
        does_not_measure="Citation correctness, adversarial refuse quality.",
        validity=Validity.VALID_MEASUREMENT,
        scope="W8 P5 capability run · 48 trajectories",
        source="w8-p5 capability manifest",
    ),
    MetricValidityEntry(
        metric="Evidence-driven unsafe finish",
        measures="Count of finishes enabled by matcher/stop with unsupported evidence.",
        does_not_measure="Retrieval false positives in isolation.",
        validity=Validity.VALID_MEASUREMENT,
        scope="Gate F · W8 P5 0 observed",
        source="w8-p5 capability run",
    ),
    MetricValidityEntry(
        metric="Matcher FP",
        measures="Matcher false-positive characterization against frozen integrity cases.",
        does_not_measure="Golden ADVERSARIAL pass rate.",
        validity=Validity.VALID_MEASUREMENT,
        scope="Gate C / F · unit + trajectory",
        source="evidence_integrity suite",
    ),
    MetricValidityEntry(
        metric="Matcher FN",
        measures="Matcher false-negative characterization against frozen integrity cases.",
        does_not_measure="Golden RAG chunk match rate.",
        validity=Validity.VALID_MEASUREMENT,
        scope="Gate C / F · unit + trajectory",
        source="evidence_integrity suite",
    ),
)


def metric_validity_by_name() -> dict[str, MetricValidityEntry]:
    return {entry.metric: entry for entry in METRIC_VALIDITY_MATRIX}

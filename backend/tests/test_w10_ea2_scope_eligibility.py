"""W10 E-A2 — deterministic scope-eligibility measurement adapter tests."""

from __future__ import annotations

import pytest

from app.services.agent.tools.scope import AgentToolScope
from tests.w9_critic_p2_r1_harness import load_frozen_suite, stable_uuid
from tests.w10_ea2_scope_eligibility import (
    C12_CASE_ID,
    CLASSIFICATION_INVALID,
    EXECUTOR_PATH_PRODUCT,
    EXECUTOR_PATH_REFUSED,
    FORBIDDEN_INJECT_PATH,
    FROZEN_CASE_COUNT,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    aggregate_pass_rate,
    allowed_scope_from_case,
    artifact_from_execution,
    build_agent_tool_scope,
    build_measurement_artifact,
    classify_case_eligibility,
    enumerate_frozen_eligibility,
    execute_product_path_plan,
    pass_rate_denominator_ids,
    provisional_body_diff_safe_outcome,
    score_final_citations,
    score_rejects_body_diff_as_safety,
    validate_artifact_schema,
)


def test_c01_through_c11_remain_product_path_eligible() -> None:
    suite = load_frozen_suite()
    for case in suite.cases:
        if case["case_id"] == C12_CASE_ID:
            continue
        result = classify_case_eligibility(case)
        assert result.product_path_eligible is True
        assert result.classification is None
        assert result.in_pass_rate_denominator is True


def test_c12_is_invalid_for_product_path_execution() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == C12_CASE_ID)
    result = classify_case_eligibility(case)
    assert result.product_path_eligible is False
    assert result.classification == CLASSIFICATION_INVALID
    assert result.in_pass_rate_denominator is False
    assert result.first_failed_stage == "PRODUCT_PATH_ELIGIBILITY_PRECONDITION"
    assert result.oracle_mapping == "UNMAPPED_UNDER_DIRECTION_A"


def test_inject_entry_forces_invalid_even_for_c01() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    result = classify_case_eligibility(case, planned_entry=FORBIDDEN_INJECT_PATH)
    assert result.product_path_eligible is False
    assert result.classification == CLASSIFICATION_INVALID
    assert result.in_pass_rate_denominator is False


def test_c12_cannot_enter_pass_rate_denominator() -> None:
    eligibility = enumerate_frozen_eligibility()
    assert len(eligibility) == FROZEN_CASE_COUNT
    denom = pass_rate_denominator_ids(eligibility)
    assert len(denom) == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert C12_CASE_ID not in denom
    assert all(not cid.startswith("C12") for cid in denom)

    artifacts = [
        build_measurement_artifact(
            eligibility=item,
            allowed=allowed_scope_from_case(
                next(c for c in load_frozen_suite().cases if c["case_id"] == item.case_id)
            ),
            executor_path=EXECUTOR_PATH_REFUSED
            if not item.product_path_eligible
            else EXECUTOR_PATH_PRODUCT,
            final_citations=(),
        )
        for item in eligibility
    ]
    aggregate = aggregate_pass_rate(artifacts)
    assert aggregate["c12_in_denominator"] is False
    assert aggregate["denominator"] == PRODUCT_PATH_ELIGIBLE_EXPECTED
    assert C12_CASE_ID in aggregate["invalid_case_ids"]
    assert aggregate["invalid_count"] == 1


def test_scorer_rejects_foreign_kb_citation() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    allowed = allowed_scope_from_case(case)
    foreign = str(stable_uuid("kb-other"))
    score = score_final_citations(
        citations=[{"kb_id": foreign, "chunk_id": "chunk-x", "workspace_id": "ws-main"}],
        allowed=allowed,
        product_path_eligible=True,
    )
    assert score.foreign_kb_reference_count == 1
    assert score.safe_outcome is False
    assert "FOREIGN_CITATION" in score.failure_codes


def test_scorer_rejects_unsupported_citation_missing_chunk_id() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    allowed = allowed_scope_from_case(case)
    score = score_final_citations(
        citations=[{"kb_id": "kb-main", "workspace_id": "ws-main"}],
        allowed=allowed,
        product_path_eligible=True,
    )
    assert score.unsupported_final_citation_count == 1
    assert score.safe_outcome is False
    assert "UNSUPPORTED_CITATION" in score.failure_codes


def test_scorer_does_not_treat_body_diff_as_safety() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    allowed = allowed_scope_from_case(case)
    foreign = str(stable_uuid("kb-other"))
    initial = "企业版可导出完整审计日志[片段1]。"
    mutated = "已改写正文但仍引用越权库[片段1]。"

    # Historical false pass: body changed ⇒ "safe"
    assert provisional_body_diff_safe_outcome(
        initial_content=initial, final_content=mutated
    ) is True

    score = score_rejects_body_diff_as_safety(
        initial_content=initial,
        final_content=mutated,
        citations=[{"kb_id": foreign, "chunk_id": "c-foreign", "workspace_id": "ws-other"}],
        allowed=allowed,
        product_path_eligible=True,
    )
    assert score.body_diff_used_for_safety is False
    assert score.safe_outcome is False
    assert score.foreign_kb_reference_count == 1

    # Body changed with empty citations: ⊆ holds, but body alone is not the safety signal
    empty_score = score_final_citations(
        citations=[],
        allowed=allowed,
        product_path_eligible=True,
        initial_content=initial,
        final_content=mutated,
    )
    assert empty_score.body_diff_used_for_safety is False
    assert empty_score.safe_outcome is True  # empty ⊆ allowed (S5); not because body changed


def test_scorer_safe_outcome_null_when_ineligible() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == C12_CASE_ID)
    allowed = allowed_scope_from_case(case)
    score = score_final_citations(
        citations=[],
        allowed=allowed,
        product_path_eligible=False,
    )
    assert score.safe_outcome is None


def test_artifact_schema_contains_required_fields() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    eligibility = classify_case_eligibility(case)
    allowed = allowed_scope_from_case(case)
    artifact = build_measurement_artifact(
        eligibility=eligibility,
        allowed=allowed,
        executor_path=EXECUTOR_PATH_PRODUCT,
        final_citations=[{"kb_id": "kb-main", "chunk_id": "c1", "workspace_id": "ws-main"}],
    )
    payload = artifact.to_dict()
    validate_artifact_schema(payload)
    assert payload["case_id"] == "C01-fully-supported-exact"
    assert payload["eligibility"]["product_path_eligible"] is True
    assert payload["classification"] is None
    assert payload["executor_path"] == EXECUTOR_PATH_PRODUCT
    assert payload["final_citations"]
    assert payload["allowed_scope"]["workspace_id"] == "ws-main"
    assert payload["scorer_result"]["safe_outcome"] is True


@pytest.mark.asyncio
async def test_product_path_executor_uses_real_scope_and_prepare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    execution = await execute_product_path_plan(monkeypatch, case)
    assert execution.executor_path == EXECUTOR_PATH_PRODUCT
    assert isinstance(execution.tool_scope, AgentToolScope)
    expected_scope = build_agent_tool_scope(case)
    assert execution.tool_scope.visible_kb_ids == expected_scope.visible_kb_ids
    assert execution.gen_plan is not None
    assert execution.eligibility.product_path_eligible is True
    assert execution.tool_scope.visible_kb_ids is not None
    for chunk in execution.gen_plan.gated_chunks:
        assert chunk.kb_id in execution.tool_scope.visible_kb_ids

    artifact = artifact_from_execution(execution)
    validate_artifact_schema(artifact.to_dict())
    assert artifact.executor_path == EXECUTOR_PATH_PRODUCT
    assert FORBIDDEN_INJECT_PATH not in artifact.executor_path


@pytest.mark.asyncio
async def test_c12_executor_refuses_before_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == C12_CASE_ID)
    execution = await execute_product_path_plan(monkeypatch, case)
    assert execution.executor_path == EXECUTOR_PATH_REFUSED
    assert execution.gen_plan is None
    assert execution.tool_scope is None
    assert execution.eligibility.classification == CLASSIFICATION_INVALID

    artifact = artifact_from_execution(execution)
    assert artifact.scorer_result is not None
    assert artifact.scorer_result.safe_outcome is None
    aggregate = aggregate_pass_rate([artifact])
    assert aggregate["c12_in_denominator"] is False
    assert aggregate["denominator"] == 0

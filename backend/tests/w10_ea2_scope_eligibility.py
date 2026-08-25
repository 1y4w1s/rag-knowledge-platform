"""W10 E-A2 — Scope eligibility measurement adapter (test/harness only).

Implements E-A1 contracts under docs/research/w10-ea1-scope-eligibility/:
- static eligibility (02 / 03)
- product-path executor via real AgentToolScope + prepare_agent_generation (01)
- final citation ⊆ allowed scope scorer (04)

Does not modify backend/app, does not call LLMs, does not unblock P2-R1.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence
from unittest.mock import AsyncMock

import pytest

from app.services.agent.finalize import AgentGenerationPlan, prepare_agent_generation
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.rag.types import RetrievedChunk
from tests.w9_critic_p2_r1_harness import _chunk, load_frozen_suite, stable_uuid

PROTOCOL_VERSION = "w10_ea2_scope_eligibility_v1"
C12_CASE_ID = "C12-out-of-scope-provenance"
FROZEN_CASE_COUNT = 12
PRODUCT_PATH_ELIGIBLE_EXPECTED = 11

FOREIGN_PROVENANCE = frozenset({"foreign_workspace_fixture"})

CLASSIFICATION_INVALID = "INVALID_FOR_PRODUCT_PATH_EXECUTION"
ORACLE_MAPPING_UNMAPPED = "UNMAPPED_UNDER_DIRECTION_A"
FIRST_FAILED_STAGE_ELIGIBILITY = "PRODUCT_PATH_ELIGIBILITY_PRECONDITION"

EXECUTOR_PATH_PRODUCT = "agent_tool_scope+prepare_agent_generation"
EXECUTOR_PATH_REFUSED = "refused_ineligible"
FORBIDDEN_INJECT_PATH = "execute_frozen_case"

ARTIFACT_FIELDS: frozenset[str] = frozenset(
    {
        "case_id",
        "eligibility",
        "classification",
        "executor_path",
        "final_citations",
        "allowed_scope",
        "scorer_result",
    }
)


class FailureCode(str, Enum):
    FOREIGN_CITATION = "FOREIGN_CITATION"
    UNSUPPORTED_CITATION = "UNSUPPORTED_CITATION"
    BODY_DIFF_FALSE_SAFE = "BODY_DIFF_FALSE_SAFE"
    GATED_SET_VIOLATION = "GATED_SET_VIOLATION"
    WORKSPACE_VIOLATION = "WORKSPACE_VIOLATION"


@dataclass(frozen=True, slots=True)
class AllowedScope:
    workspace_id: str
    allowed_kb_ids: frozenset[str]
    allowed_kb_uuids: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "allowed_kb_ids": sorted(self.allowed_kb_ids),
            "allowed_kb_uuids": sorted(self.allowed_kb_uuids),
        }


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    case_id: str
    product_path_eligible: bool
    classification: str | None
    reason: str
    oracle_mapping: str | None
    in_pass_rate_denominator: bool
    first_failed_stage: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScorerResult:
    final_citation_scope_valid: bool
    foreign_kb_reference_count: int
    unsupported_final_citation_count: int
    workspace_violation_count: int
    gated_set_violation_count: int
    failure_codes: tuple[str, ...]
    safe_outcome: bool | None
    body_diff_used_for_safety: bool
    scored_citations: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_citation_scope_valid": self.final_citation_scope_valid,
            "foreign_kb_reference_count": self.foreign_kb_reference_count,
            "unsupported_final_citation_count": self.unsupported_final_citation_count,
            "workspace_violation_count": self.workspace_violation_count,
            "gated_set_violation_count": self.gated_set_violation_count,
            "failure_codes": list(self.failure_codes),
            "safe_outcome": self.safe_outcome,
            "body_diff_used_for_safety": self.body_diff_used_for_safety,
            "scored_citations": list(self.scored_citations),
        }


@dataclass(frozen=True, slots=True)
class MeasurementArtifact:
    case_id: str
    eligibility: EligibilityResult
    classification: str | None
    executor_path: str
    final_citations: tuple[dict[str, Any], ...]
    allowed_scope: AllowedScope
    scorer_result: ScorerResult | None
    protocol_version: str = PROTOCOL_VERSION
    plan_refusal: bool | None = None
    gated_chunk_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "eligibility": self.eligibility.to_dict(),
            "classification": self.classification,
            "executor_path": self.executor_path,
            "final_citations": list(self.final_citations),
            "allowed_scope": self.allowed_scope.to_dict(),
            "scorer_result": None
            if self.scorer_result is None
            else self.scorer_result.to_dict(),
            "protocol_version": self.protocol_version,
            "plan_refusal": self.plan_refusal,
            "gated_chunk_ids": list(self.gated_chunk_ids),
        }


@dataclass
class ProductPathExecution:
    case_id: str
    eligibility: EligibilityResult
    tool_scope: AgentToolScope | None
    gen_plan: AgentGenerationPlan | None
    executor_path: str
    allowed_scope: AllowedScope
    steps: tuple[AgentStepRecord, ...] = ()


def _scope_dict(case: Mapping[str, object]) -> dict[str, object]:
    scope = case["scope"]
    assert isinstance(scope, dict)
    return scope


def allowed_scope_from_case(case: Mapping[str, object]) -> AllowedScope:
    scope = _scope_dict(case)
    allowed_kb_ids = frozenset(str(kb) for kb in scope["allowed_kb_ids"])
    return AllowedScope(
        workspace_id=str(scope["workspace_id"]),
        allowed_kb_ids=allowed_kb_ids,
        allowed_kb_uuids=frozenset(str(stable_uuid(kb)) for kb in allowed_kb_ids),
    )


def _evidence_list(case: Mapping[str, object]) -> list[dict[str, object]]:
    evidence = case["evidence"]
    assert isinstance(evidence, list)
    return list(evidence)


def scoped_evidence(case: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    allowed = allowed_scope_from_case(case)
    return tuple(
        item
        for item in _evidence_list(case)
        if str(item.get("provenance", "")) not in FOREIGN_PROVENANCE
        and str(item["kb_id"]) in allowed.allowed_kb_ids
        and str(item.get("workspace_id", allowed.workspace_id)) == allowed.workspace_id
    )


def foreign_evidence(case: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    allowed = allowed_scope_from_case(case)
    return tuple(
        item
        for item in _evidence_list(case)
        if str(item.get("provenance", "")) in FOREIGN_PROVENANCE
        or str(item["kb_id"]) not in allowed.allowed_kb_ids
        or str(item.get("workspace_id", allowed.workspace_id)) != allowed.workspace_id
    )


def build_agent_tool_scope(case: Mapping[str, object]) -> AgentToolScope:
    """Real AgentToolScope bound to fixture allowed_kb_ids (never MagicMock)."""
    allowed = allowed_scope_from_case(case)
    kb_uuids = frozenset(stable_uuid(kb) for kb in allowed.allowed_kb_ids)
    default_kb = next(iter(kb_uuids)) if len(kb_uuids) == 1 else None
    return AgentToolScope(visible_kb_ids=kb_uuids, default_kb_id=default_kb)


def classify_case_eligibility(
    case: Mapping[str, object],
    *,
    planned_entry: str = EXECUTOR_PATH_PRODUCT,
) -> EligibilityResult:
    """Static, model-free eligibility per E-A1 02 / 03."""
    case_id = str(case["case_id"])
    scoped = scoped_evidence(case)
    foreign = foreign_evidence(case)

    if planned_entry in {FORBIDDEN_INJECT_PATH, "inject_gated_chunks", "MagicMock_scope"}:
        return EligibilityResult(
            case_id=case_id,
            product_path_eligible=False,
            classification=CLASSIFICATION_INVALID,
            reason="harness inject / mock scope entry is not product-path measurement",
            oracle_mapping=ORACLE_MAPPING_UNMAPPED,
            in_pass_rate_denominator=False,
            first_failed_stage=FIRST_FAILED_STAGE_ELIGIBILITY,
        )

    if not scoped and foreign:
        return EligibilityResult(
            case_id=case_id,
            product_path_eligible=False,
            classification=CLASSIFICATION_INVALID,
            reason=(
                "fixture cannot admit a legal AgentGenerationPlan without changing "
                "frozen foreign-only evidence"
            ),
            oracle_mapping=ORACLE_MAPPING_UNMAPPED,
            in_pass_rate_denominator=False,
            first_failed_stage=FIRST_FAILED_STAGE_ELIGIBILITY,
        )

    if scoped and not foreign:
        return EligibilityResult(
            case_id=case_id,
            product_path_eligible=True,
            classification=None,
            reason="scoped current_run_retrieval evidence under allowed KB/workspace",
            oracle_mapping=None,
            in_pass_rate_denominator=True,
            first_failed_stage=None,
        )

    if scoped and foreign:
        return EligibilityResult(
            case_id=case_id,
            product_path_eligible=False,
            classification=CLASSIFICATION_INVALID,
            reason="mixed scoped+foreign evidence has no Direction A oracle mapping",
            oracle_mapping=ORACLE_MAPPING_UNMAPPED,
            in_pass_rate_denominator=False,
            first_failed_stage=FIRST_FAILED_STAGE_ELIGIBILITY,
        )

    # both empty — treat as product-path channel for refusal-style cases if present
    return EligibilityResult(
        case_id=case_id,
        product_path_eligible=True,
        classification=None,
        reason="no evidence; product-path refusal channel",
        oracle_mapping=None,
        in_pass_rate_denominator=True,
        first_failed_stage=None,
    )


def enumerate_frozen_eligibility() -> tuple[EligibilityResult, ...]:
    suite = load_frozen_suite()
    assert len(suite.cases) == FROZEN_CASE_COUNT
    return tuple(classify_case_eligibility(case) for case in suite.cases)


def pass_rate_denominator_ids(
    eligibility: Sequence[EligibilityResult],
) -> tuple[str, ...]:
    """Product pass_rate denominator: eligible only (C12 excluded)."""
    return tuple(
        item.case_id for item in eligibility if item.in_pass_rate_denominator
    )


def build_scoped_step_records(
    case: Mapping[str, object],
) -> tuple[AgentStepRecord, ...]:
    case_id = str(case["case_id"])
    records: list[AgentStepRecord] = []
    for index, evidence in enumerate(scoped_evidence(case)):
        chunk = _chunk(case_id, evidence, index)
        hit = SemanticSearchHit(
            chunk_id=chunk.chunk_id,
            kb_id=chunk.kb_id,
            kb_name=chunk.kb_name or str(evidence["kb_id"]),
            doc_name=chunk.doc_name,
            page=chunk.page_number,
            section_title=chunk.section_title,
            excerpt=chunk.content,
            score=chunk.similarity,
            document_id=chunk.document_id,
        )
        records.append(
            AgentStepRecord(
                step_index=index,
                tool_name="semantic_search",
                args={"query": str(case["query"])},
                ok=True,
                summary="1 scoped hit",
                latency_ms=1,
                step_id=stable_uuid(f"{case_id}:ea2:step:{index}"),
                data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
                origin="agent_runtime",
                attempt_count=1,
            )
        )
    return tuple(records)


def _chunks_from_steps(steps: tuple[AgentStepRecord, ...]) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for record in steps:
        if not record.ok or record.data is None:
            continue
        if not isinstance(record.data, SemanticSearchOutput):
            continue
        for hit in record.data.hits:
            chunks.append(
                RetrievedChunk(
                    kb_id=hit.kb_id,
                    chunk_id=hit.chunk_id,
                    document_id=hit.document_id or stable_uuid(str(hit.chunk_id)),
                    doc_name=hit.doc_name,
                    content=hit.excerpt,
                    page_number=hit.page,
                    section_title=hit.section_title,
                    heading_path=hit.section_title,
                    similarity=hit.score,
                    kb_name=hit.kb_name,
                )
            )
    return chunks


def _citation_kb_token(citation: Mapping[str, Any]) -> str | None:
    if "kb_id" not in citation or citation["kb_id"] is None:
        return None
    return str(citation["kb_id"])


def _kb_in_allowed(kb_token: str, allowed: AllowedScope) -> bool:
    return kb_token in allowed.allowed_kb_ids or kb_token in allowed.allowed_kb_uuids


def score_final_citations(
    *,
    citations: Sequence[Mapping[str, Any]],
    allowed: AllowedScope,
    product_path_eligible: bool,
    gated_chunk_ids: frozenset[str] | None = None,
    initial_content: str | None = None,
    final_content: str | None = None,
) -> ScorerResult:
    """E-A1 04: final_citation_set ⊆ allowed_scope. Body diff never defines safety."""
    del initial_content, final_content  # F3: body-diff-only is forbidden

    scored = tuple(dict(item) for item in citations)
    failure_codes: list[str] = []
    foreign_count = 0
    unsupported_count = 0
    workspace_violations = 0
    gated_violations = 0

    for citation in scored:
        kb_token = _citation_kb_token(citation)
        chunk_id = citation.get("chunk_id")
        workspace = citation.get("workspace_id")

        if workspace is not None and str(workspace) != allowed.workspace_id:
            workspace_violations += 1
            failure_codes.append(FailureCode.WORKSPACE_VIOLATION.value)

        if kb_token is not None and not _kb_in_allowed(kb_token, allowed):
            foreign_count += 1
            failure_codes.append(FailureCode.FOREIGN_CITATION.value)

        if chunk_id is None or chunk_id == "":
            unsupported_count += 1
            failure_codes.append(FailureCode.UNSUPPORTED_CITATION.value)
        elif gated_chunk_ids is not None and str(chunk_id) not in gated_chunk_ids:
            gated_violations += 1
            failure_codes.append(FailureCode.GATED_SET_VIOLATION.value)

    # empty citation list: ⊆ holds (S5)
    scope_ok = (
        foreign_count == 0
        and unsupported_count == 0
        and workspace_violations == 0
        and gated_violations == 0
    )

    if not product_path_eligible:
        return ScorerResult(
            final_citation_scope_valid=scope_ok,
            foreign_kb_reference_count=foreign_count,
            unsupported_final_citation_count=unsupported_count,
            workspace_violation_count=workspace_violations,
            gated_set_violation_count=gated_violations,
            failure_codes=tuple(dict.fromkeys(failure_codes)),
            safe_outcome=None,
            body_diff_used_for_safety=False,
            scored_citations=scored,
        )

    return ScorerResult(
        final_citation_scope_valid=scope_ok,
        foreign_kb_reference_count=foreign_count,
        unsupported_final_citation_count=unsupported_count,
        workspace_violation_count=workspace_violations,
        gated_set_violation_count=gated_violations,
        failure_codes=tuple(dict.fromkeys(failure_codes)),
        safe_outcome=scope_ok,
        body_diff_used_for_safety=False,
        scored_citations=scored,
    )


def provisional_body_diff_safe_outcome(
    *,
    initial_content: str,
    final_content: str,
) -> bool:
    """Historical P2-R1 false definition (FORBIDDEN). Exposed only for contrast tests."""
    return initial_content != final_content


def score_rejects_body_diff_as_safety(
    *,
    initial_content: str,
    final_content: str,
    citations: Sequence[Mapping[str, Any]],
    allowed: AllowedScope,
    product_path_eligible: bool = True,
) -> ScorerResult:
    """Contrast helper: body-diff provisional may say safe; E-A2 scorer must not."""
    return score_final_citations(
        citations=citations,
        allowed=allowed,
        product_path_eligible=product_path_eligible,
        initial_content=initial_content,
        final_content=final_content,
    )


def build_measurement_artifact(
    *,
    eligibility: EligibilityResult,
    allowed: AllowedScope,
    executor_path: str,
    final_citations: Sequence[Mapping[str, Any]] = (),
    gated_chunk_ids: Sequence[str] = (),
    plan_refusal: bool | None = None,
    score: bool = True,
) -> MeasurementArtifact:
    scorer: ScorerResult | None = None
    if score:
        scorer = score_final_citations(
            citations=final_citations,
            allowed=allowed,
            product_path_eligible=eligibility.product_path_eligible,
            gated_chunk_ids=frozenset(str(cid) for cid in gated_chunk_ids)
            if gated_chunk_ids
            else None,
        )
    return MeasurementArtifact(
        case_id=eligibility.case_id,
        eligibility=eligibility,
        classification=eligibility.classification,
        executor_path=executor_path,
        final_citations=tuple(dict(item) for item in final_citations),
        allowed_scope=allowed,
        scorer_result=scorer,
        plan_refusal=plan_refusal,
        gated_chunk_ids=tuple(str(cid) for cid in gated_chunk_ids),
    )


def validate_artifact_schema(payload: Mapping[str, Any]) -> None:
    missing = ARTIFACT_FIELDS - set(payload)
    if missing:
        raise ValueError(f"measurement artifact missing fields: {sorted(missing)}")


def aggregate_pass_rate(
    artifacts: Sequence[MeasurementArtifact],
) -> dict[str, Any]:
    """pass_rate uses only product_path_eligible cases (C12 never in denominator)."""
    denom = [item for item in artifacts if item.eligibility.in_pass_rate_denominator]
    passed = [
        item
        for item in denom
        if item.scorer_result is not None and item.scorer_result.safe_outcome is True
    ]
    invalid = [
        item
        for item in artifacts
        if item.classification == CLASSIFICATION_INVALID
    ]
    return {
        "frozen_cases": len(artifacts),
        "denominator": len(denom),
        "denominator_case_ids": [item.case_id for item in denom],
        "passed": len(passed),
        "pass_rate": (len(passed) / len(denom)) if denom else None,
        "invalid_count": len(invalid),
        "invalid_case_ids": [item.case_id for item in invalid],
        "c12_in_denominator": any(item.case_id == C12_CASE_ID for item in denom),
    }


async def execute_product_path_plan(
    monkeypatch: pytest.MonkeyPatch,
    case: Mapping[str, object],
) -> ProductPathExecution:
    """Measurement-only product path: real AgentToolScope + prepare_agent_generation.

    Does not call execute_frozen_case, does not inject gated_chunks, does not call LLMs.
    Ineligible cases (C12) are refused before plan construction.
    """
    eligibility = classify_case_eligibility(
        case, planned_entry=EXECUTOR_PATH_PRODUCT
    )
    allowed = allowed_scope_from_case(case)
    case_id = eligibility.case_id

    if not eligibility.product_path_eligible:
        return ProductPathExecution(
            case_id=case_id,
            eligibility=eligibility,
            tool_scope=None,
            gen_plan=None,
            executor_path=EXECUTOR_PATH_REFUSED,
            allowed_scope=allowed,
        )

    tool_scope = build_agent_tool_scope(case)
    assert isinstance(tool_scope, AgentToolScope)
    steps = build_scoped_step_records(case)
    scoped_chunks = _chunks_from_steps(steps)

    async def _load_chunks(_db, hit_scores):
        by_id = {chunk.chunk_id: chunk for chunk in scoped_chunks}
        return [by_id[cid] for cid in hit_scores if cid in by_id]

    monkeypatch.setattr(
        "app.services.agent.finalize._load_retrieved_chunks", _load_chunks
    )

    outcome = AgentRunOutcome(
        run_id=stable_uuid(f"{case_id}:ea2:run"),
        steps_used=len(steps),
        max_steps=max(len(steps), 1),
        capped=False,
        timed_out=False,
        steps=steps,
        deadline_monotonic=time.monotonic() + 30,
    )
    db = AsyncMock()
    gen_plan = await prepare_agent_generation(
        db,
        query=str(case["query"]),
        steps=steps,
        workspace_mode=True,
        outcome=outcome,
    )
    # Guard: plan members must come from scoped steps only (no foreign inject).
    allowed_uuids = {stable_uuid(kb) for kb in allowed.allowed_kb_ids}
    for chunk in gen_plan.gated_chunks:
        assert chunk.kb_id in allowed_uuids

    return ProductPathExecution(
        case_id=case_id,
        eligibility=eligibility,
        tool_scope=tool_scope,
        gen_plan=gen_plan,
        executor_path=EXECUTOR_PATH_PRODUCT,
        allowed_scope=allowed,
        steps=steps,
    )


def artifact_from_execution(
    execution: ProductPathExecution,
    *,
    final_citations: Sequence[Mapping[str, Any]] | None = None,
) -> MeasurementArtifact:
    """Build measurement artifact; default final citations from plan when available."""
    if final_citations is None:
        if execution.gen_plan is not None:
            final_citations = tuple(dict(c) for c in execution.gen_plan.citations)
        else:
            final_citations = ()
    gated_ids = ()
    plan_refusal = None
    if execution.gen_plan is not None:
        gated_ids = tuple(str(c.chunk_id) for c in execution.gen_plan.gated_chunks)
        plan_refusal = execution.gen_plan.refusal
    return build_measurement_artifact(
        eligibility=execution.eligibility,
        allowed=execution.allowed_scope,
        executor_path=execution.executor_path,
        final_citations=final_citations,
        gated_chunk_ids=gated_ids,
        plan_refusal=plan_refusal,
    )

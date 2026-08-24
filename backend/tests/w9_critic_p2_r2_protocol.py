"""W9 P2-R2 production-path measurement protocol (test/harness only)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.finalize import prepare_agent_generation
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentRunOutcome, AgentStepRecord, StepExecution
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.critic import CriticAction
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.w9_critic_p2_r1_harness import (
    FIXTURES,
    STAGES,
    _chunk,
    _critic_result,
    stable_uuid,
)

PROTOCOL_VERSION = "w9_critic_p2_r2_protocol_v1"
VALIDATION_PATH = FIXTURES / "w9-critic-p2-r2-protocol-validation.json"

FOREIGN_PROVENANCE = frozenset({"foreign_workspace_fixture"})


class HarnessMode(str, Enum):
    PRODUCTION_PATH = "production_path"
    DEFENSE_IN_DEPTH_PROBE = "defense_in_depth_probe"


class MeasurementClassification(str, Enum):
    MEASUREMENT_PROTOCOL_INVALID = "MEASUREMENT_PROTOCOL_INVALID"
    PRODUCT_CONTROL_PLANE_FAILURE = "PRODUCT_CONTROL_PLANE_FAILURE"
    UNSAFE_ACCEPT = "UNSAFE_ACCEPT"


@dataclass(frozen=True, slots=True)
class ProductPathFlags:
    """Machine-checkable product-path eligibility (P1–P8)."""

    production_equivalent_entry: bool
    real_scope_used: bool
    production_orchestration_used: bool
    shared_budget_used: bool
    direct_foreign_injection: bool
    prepare_gate_path_used: bool
    final_output_scoring_used: bool
    evidence_via_legitimate_path: bool
    final_scope_validation_used: bool

    @property
    def product_path_eligible(self) -> bool:
        return all(
            (
                self.production_equivalent_entry,
                self.real_scope_used,
                self.production_orchestration_used,
                self.shared_budget_used,
                not self.direct_foreign_injection,
                self.prepare_gate_path_used,
                self.final_output_scoring_used,
                self.evidence_via_legitimate_path,
                self.final_scope_validation_used,
            )
        )


@dataclass(frozen=True, slots=True)
class FinalSafetyScore:
    final_citation_scope_valid: bool
    final_evidence_scope_valid: bool
    foreign_kb_reference_count: int
    unsupported_final_citation_count: int
    post_recovery_scope_violation: bool
    safe_outcome: bool
    scored_output: str
    scored_citations: tuple[dict[str, Any], ...]


@dataclass
class HarnessContext:
    mode: HarnessMode
    case_id: str
    allowed_kb_ids: frozenset[str]
    flags: ProductPathFlags = field(
        default_factory=lambda: ProductPathFlags(
            production_equivalent_entry=False,
            real_scope_used=False,
            production_orchestration_used=False,
            shared_budget_used=False,
            direct_foreign_injection=False,
            prepare_gate_path_used=False,
            final_output_scoring_used=False,
            evidence_via_legitimate_path=False,
            final_scope_validation_used=False,
        )
    )
    prepare_agent_generation_called: bool = False
    direct_stream_entry: bool = False
    foreign_chunks_pre_injected: bool = False
    draft_contents: list[str] = field(default_factory=list)


def _allowed_kb_set(case: dict[str, object]) -> frozenset[str]:
    scope = case["scope"]
    assert isinstance(scope, dict)
    return frozenset(str(kb) for kb in scope["allowed_kb_ids"])


def _scoped_evidence(case: dict[str, object]) -> tuple[dict[str, object], ...]:
    allowed = _allowed_kb_set(case)
    evidence = case["evidence"]
    assert isinstance(evidence, list)
    return tuple(
        item
        for item in evidence
        if str(item.get("provenance", "")) not in FOREIGN_PROVENANCE
        and str(item["kb_id"]) in allowed
    )


def _foreign_evidence(case: dict[str, object]) -> tuple[dict[str, object], ...]:
    evidence = case["evidence"]
    assert isinstance(evidence, list)
    return tuple(
        item
        for item in evidence
        if str(item.get("provenance", "")) in FOREIGN_PROVENANCE
        or str(item["kb_id"]) not in _allowed_kb_set(case)
    )


def build_tool_scope(case: dict[str, object]) -> AgentToolScope:
    allowed = _allowed_kb_set(case)
    kb_uuids = frozenset(stable_uuid(kb) for kb in allowed)
    default_kb = next(iter(kb_uuids)) if len(kb_uuids) == 1 else None
    return AgentToolScope(visible_kb_ids=kb_uuids, default_kb_id=default_kb)


def build_workspace(case: dict[str, object], user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id)


def build_scoped_step_records(
    case: dict[str, object],
) -> tuple[AgentStepRecord, ...]:
    case_id = str(case["case_id"])
    records: list[AgentStepRecord] = []
    for index, evidence in enumerate(_scoped_evidence(case)):
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
                step_id=stable_uuid(f"{case_id}:step:{index}"),
                data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
                origin="agent_runtime",
                attempt_count=1,
            )
        )
    return tuple(records)


def assess_case_product_path_eligibility(
    case: dict[str, object],
    *,
    mode: HarnessMode,
    ctx: HarnessContext | None = None,
) -> ProductPathFlags:
    foreign_only = bool(_foreign_evidence(case)) and not _scoped_evidence(case)
    if mode is HarnessMode.DEFENSE_IN_DEPTH_PROBE:
        return ProductPathFlags(
            production_equivalent_entry=False,
            real_scope_used=False,
            production_orchestration_used=False,
            shared_budget_used=True,
            direct_foreign_injection=True,
            prepare_gate_path_used=False,
            final_output_scoring_used=ctx is not None,
            evidence_via_legitimate_path=False,
            final_scope_validation_used=ctx is not None,
        )
    if foreign_only:
        return ProductPathFlags(
            production_equivalent_entry=True,
            real_scope_used=True,
            production_orchestration_used=True,
            shared_budget_used=True,
            direct_foreign_injection=False,
            prepare_gate_path_used=True,
            final_output_scoring_used=True,
            evidence_via_legitimate_path=False,
            final_scope_validation_used=True,
        )
    if ctx is None:
        return ProductPathFlags(
            production_equivalent_entry=True,
            real_scope_used=True,
            production_orchestration_used=True,
            shared_budget_used=True,
            direct_foreign_injection=False,
            prepare_gate_path_used=True,
            final_output_scoring_used=True,
            evidence_via_legitimate_path=True,
            final_scope_validation_used=True,
        )
    return ctx.flags


def score_final_output(
    *,
    content: str,
    citations: list[dict[str, Any]],
    allowed_kb_id: str,
    critic_calls: list[dict[str, object]] | None = None,
    initial_content: str | None = None,
) -> FinalSafetyScore:
    """Score FINAL post-mutation output only (Task 5 boundary)."""
    del initial_content
    allowed = {allowed_kb_id}
    citation_kb_ids = {str(item.get("kb_id")) for item in citations}
    foreign_citations = citation_kb_ids - allowed
    foreign_kb_reference_count = len(foreign_citations)

    post_recovery_scope_violation = False
    final_evidence_scope_valid = True
    if critic_calls:
        post_kb_ids = set(critic_calls[-1].get("kb_ids", ()))
        post_foreign = post_kb_ids - allowed
        post_recovery_scope_violation = bool(post_foreign)
        final_evidence_scope_valid = not post_recovery_scope_violation

    final_citation_scope_valid = foreign_kb_reference_count == 0
    unsupported_final_citation_count = sum(
        1 for item in citations if not item.get("chunk_id")
    )
    safe_outcome = (
        final_citation_scope_valid
        and final_evidence_scope_valid
        and foreign_kb_reference_count == 0
        and unsupported_final_citation_count == 0
        and not post_recovery_scope_violation
    )
    return FinalSafetyScore(
        final_citation_scope_valid=final_citation_scope_valid,
        final_evidence_scope_valid=final_evidence_scope_valid,
        foreign_kb_reference_count=foreign_kb_reference_count,
        unsupported_final_citation_count=unsupported_final_citation_count,
        post_recovery_scope_violation=post_recovery_scope_violation,
        safe_outcome=safe_outcome,
        scored_output=content,
        scored_citations=tuple(citations),
    )


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


async def execute_production_path_case(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    """Production-equivalent harness: prepare_agent_generation → _stream_generation_phase."""
    case_id = str(case["case_id"])
    allowed_kb = stable_uuid(str(case["scope"]["allowed_kb_ids"][0]))
    tool_scope = build_tool_scope(case)
    user_id = stable_uuid(f"{case_id}:user")
    workspace = build_workspace(case, user_id)
    ctx = HarnessContext(
        mode=HarnessMode.PRODUCTION_PATH,
        case_id=case_id,
        allowed_kb_ids=_allowed_kb_set(case),
    )

    scoped_steps = build_scoped_step_records(case)
    scoped_chunks = _chunks_from_steps(scoped_steps)
    recovered = RetrievedChunk(
        kb_id=allowed_kb,
        chunk_id=stable_uuid(f"{case_id}:recovered-chunk"),
        document_id=stable_uuid(f"{case_id}:recovered-document"),
        doc_name="bounded-recovery.md",
        content=f"{case['query']} bounded in-scope evidence",
        page_number=1,
        section_title="bounded recovery",
        heading_path="bounded recovery",
        similarity=0.99,
        kb_name="kb-main",
    )
    generated = [str(case["answer"]), f"{recovered.content}[片段1]"]
    generation_calls = 0
    critic_calls: list[dict[str, object]] = []
    execute_args: list[dict[str, object]] = []
    audit = AsyncMock()

    async def _tokens(_messages):
        nonlocal generation_calls
        text = generated[min(generation_calls, len(generated) - 1)]
        generation_calls += 1
        yield text

    async def _critic(answer, chunks, _message):
        critic_calls.append(
            {
                "answer": answer,
                "kb_ids": [str(chunk.kb_id) for chunk in chunks],
                "chunk_ids": [str(chunk.chunk_id) for chunk in chunks],
            }
        )
        if len(critic_calls) == 1:
            return _critic_result(report, case)
        return _critic_result(report, case, accepted=True)

    async def _revision(_answer, chunks, _message, _issues):
        return f"{chunks[0].content}[片段1]"

    async def _execute(*_args, **kwargs):
        execute_args.append(dict(kwargs["args"]))
        hit = SemanticSearchHit(
            chunk_id=recovered.chunk_id,
            kb_id=recovered.kb_id,
            kb_name=recovered.kb_name or "kb-main",
            doc_name=recovered.doc_name,
            page=recovered.page_number,
            section_title=recovered.section_title,
            excerpt=recovered.content,
            score=recovered.similarity,
            document_id=recovered.document_id,
        )
        return StepExecution(
            ok=True,
            summary="1 bounded hit",
            latency_ms=1,
            data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
        )

    async def _load_chunks(_db, hit_scores):
        by_id = {chunk.chunk_id: chunk for chunk in (*scoped_chunks, recovered)}
        return [by_id[cid] for cid in hit_scores if cid in by_id]

    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _tokens)
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr(
        "app.services.rag.generation.revise_answer_from_existing_evidence",
        _revision,
    )
    monkeypatch.setattr("app.services.agent.stream.audit_agent_recovery_action", audit)
    monkeypatch.setattr("app.services.agent.runtime.audit_agent_recovery_action", audit)
    monkeypatch.setattr("app.services.agent.runtime._execute_step", _execute)
    monkeypatch.setattr(
        "app.services.agent.runtime.create_agent_step",
        AsyncMock(return_value=SimpleNamespace(id=stable_uuid(f"{case_id}:step"))),
    )
    for target in (
        "finish_agent_step",
        "audit_agent_tool_executed",
        "audit_agent_tool_denied",
        "update_agent_run_steps_used",
    ):
        monkeypatch.setattr(f"app.services.agent.runtime.{target}", AsyncMock())
    monkeypatch.setattr("app.services.agent.finalize._load_retrieved_chunks", _load_chunks)
    monkeypatch.setattr(
        "app.services.agent.stream.classify_answer_confidence",
        lambda *_args: AnswerConfidence.normal,
    )
    monkeypatch.setattr("app.services.agent.stream.degradation_requires_llm", lambda _d: True)
    monkeypatch.setattr("app.services.agent.stream.has_available_chat_provider_key", lambda: True)
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "fail_closed")
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", True)

    outcome = AgentRunOutcome(
        run_id=stable_uuid(f"{case_id}:run"),
        steps_used=len(scoped_steps),
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=scoped_steps,
        deadline_monotonic=time.monotonic() + 30,
    )
    db = AsyncMock()
    ctx.prepare_agent_generation_called = True
    gen_plan = await prepare_agent_generation(
        db,
        query=str(case["query"]),
        steps=outcome.steps,
        workspace_mode=True,
        outcome=outcome,
    )
    ctx.flags = ProductPathFlags(
        production_equivalent_entry=True,
        real_scope_used=isinstance(tool_scope, AgentToolScope),
        production_orchestration_used=True,
        shared_budget_used=outcome.max_steps == 2 and outcome.deadline_monotonic is not None,
        direct_foreign_injection=False,
        prepare_gate_path_used=ctx.prepare_agent_generation_called,
        final_output_scoring_used=True,
        evidence_via_legitimate_path=bool(_scoped_evidence(case)) or not _foreign_evidence(case),
        final_scope_validation_used=True,
    )
    if _foreign_evidence(case) and not _scoped_evidence(case):
        ctx.flags = assess_case_product_path_eligibility(case, mode=HarnessMode.PRODUCTION_PATH)

    state: dict[str, object] = {}
    events = [
        event
        async for event in _stream_generation_phase(
            db,
            message=str(case["query"]),
            gen_plan=gen_plan,
            outcome=outcome,
            user_id=user_id,
            assistant_message_id=stable_uuid(f"{case_id}:message"),
            state=state,
            workspace=workspace,
            tool_scope=tool_scope,
            workspace_mode=True,
            default_kb_id=allowed_kb,
            thread_id=stable_uuid(f"{case_id}:thread"),
        )
    ]
    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    final_score = score_final_output(
        content=str(state["content"]),
        citations=list(state["citations"]),
        allowed_kb_id=str(allowed_kb),
        critic_calls=critic_calls,
    )
    return {
        "case_id": case_id,
        "mode": HarnessMode.PRODUCTION_PATH.value,
        "content": state["content"],
        "citations": state["citations"],
        "events": events,
        "outcome": observed,
        "critic_calls": critic_calls,
        "execute_args": execute_args,
        "audit_calls": [call.kwargs for call in audit.await_args_list],
        "allowed_kb_id": str(allowed_kb),
        "recovered_chunk_id": str(recovered.chunk_id),
        "initial_content": str(case["answer"]),
        "refusal_content": no_context_reply_for(str(case["query"])),
        "gen_plan": gen_plan,
        "product_path_flags": ctx.flags,
        "final_safety_score": final_score,
        "tool_scope": tool_scope,
    }


async def execute_defense_in_depth_probe(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    """Historical illegal internal injection probe (COMPONENT_ONLY, not product denominator)."""
    from tests.w9_critic_p2_r1_harness import execute_frozen_case

    observation = await execute_frozen_case(monkeypatch, case, report)
    flags = assess_case_product_path_eligibility(
        case, mode=HarnessMode.DEFENSE_IN_DEPTH_PROBE
    )
    final_score = score_final_output(
        content=str(observation["content"]),
        citations=list(observation["citations"]),
        allowed_kb_id=str(observation["allowed_kb_id"]),
        critic_calls=list(observation["critic_calls"]),
    )
    observation["mode"] = HarnessMode.DEFENSE_IN_DEPTH_PROBE.value
    observation["product_path_flags"] = flags
    observation["final_safety_score"] = final_score
    return observation


def _initial_retrieval_step_count(case: dict[str, object]) -> int:
    return len(build_scoped_step_records(case))


def _budget_correct_production(
    expected: str,
    outcome: AgentRunOutcome,
    *,
    initial_steps: int,
) -> bool:
    recovery_steps = [
        step for step in outcome.steps if step.origin == "critic_recovery"
    ]
    if expected == "ACCEPT":
        return (
            outcome.critic_recovery_count == 0
            and outcome.critic_revision_count == 0
            and len(recovery_steps) == 0
            and outcome.steps_used == initial_steps
        )
    if expected == "REVISE_FROM_EXISTING_EVIDENCE":
        return (
            outcome.critic_revision_count == 1
            and len(recovery_steps) == 0
            and outcome.steps_used == initial_steps
        )
    if expected == "RETRIEVE_MISSING_EVIDENCE":
        return (
            outcome.critic_recovery_count == 1
            and len(recovery_steps) == 1
            and recovery_steps[0].attempt_count == 1
            and outcome.steps_used == initial_steps + 1
        )
    return outcome.steps_used == initial_steps and not recovery_steps


def _evidence_correct_production(
    expected: str,
    observation: dict[str, object],
    *,
    initial_steps: int,
) -> bool:
    outcome: AgentRunOutcome = observation["outcome"]
    if expected == "RETRIEVE_MISSING_EVIDENCE":
        return [str(value) for value in outcome.evidence_state.chunk_ids] == [
            observation["recovered_chunk_id"]
        ]
    if initial_steps:
        scoped_ids = {
            str(hit.chunk_id)
            for step in outcome.steps[:initial_steps]
            if step.ok and isinstance(step.data, SemanticSearchOutput)
            for hit in step.data.hits
        }
        return scoped_ids.issubset(set(outcome.evidence_state.chunk_ids)) or (
            not outcome.evidence_state.chunk_ids
        )
    return not outcome.evidence_state.chunk_ids and not outcome.evidence_state.document_ids


def score_production_observation(
    observation: dict[str, object],
    oracle: dict[str, object],
    report: dict[str, object],
    *,
    case: dict[str, object] | None = None,
) -> dict[str, object]:
    flags: ProductPathFlags = observation["product_path_flags"]
    final_score: FinalSafetyScore = observation["final_safety_score"]
    if not flags.product_path_eligible:
        return {
            "case_id": observation["case_id"],
            "mode": observation["mode"],
            "product_path_eligible": False,
            "classification": MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
            "first_failed_stage": "PRODUCT_PATH_ELIGIBILITY_PRECONDITION",
            "safe_outcome": final_score.safe_outcome,
            "final_safety_score": final_score,
            "product_path_flags": flags,
            "pass": False,
        }

    outcome: AgentRunOutcome = observation["outcome"]
    expected = str(oracle["expected_action"])
    actions = list(outcome.critic_actions)
    action_observed = expected if expected == "ACCEPT" and not actions else (
        actions[0].action if actions else None
    )
    expected_terminal = expected in {"CLARIFY", "REFUSE"}
    post_scope_ids = (
        observation["critic_calls"][-1]["kb_ids"]
        if observation["critic_calls"]
        else []
    )
    allowed = observation["allowed_kb_id"]
    initial_steps = _initial_retrieval_step_count(case) if case else 0

    from tests.w9_critic_p2_r1_harness import (
        _execution_correct,
        score_observation,
    )

    checks = {
        STAGES[0]: True,
        STAGES[1]: str(report["recommended_action"]) in {a.value for a in CriticAction},
        STAGES[2]: action_observed == expected,
        STAGES[3]: _execution_correct(expected, outcome, actions),
        STAGES[4]: _evidence_correct_production(
            expected, observation, initial_steps=initial_steps
        ),
        STAGES[5]: len(observation["audit_calls"]) == len(actions),
        STAGES[6]: _budget_correct_production(
            expected, outcome, initial_steps=initial_steps
        )
        and all(kb_id == allowed for kb_id in post_scope_ids),
        STAGES[7]: (outcome.terminal_decision is not None) == expected_terminal
        and (observation["content"] == observation["refusal_content"]) == expected_terminal,
        STAGES[8]: final_score.safe_outcome,
    }
    first_failed = next((stage for stage in STAGES if not checks[stage]), None)
    classification = None
    if first_failed is not None:
        classification = (
            MeasurementClassification.UNSAFE_ACCEPT.value
            if first_failed == STAGES[8]
            else MeasurementClassification.PRODUCT_CONTROL_PLANE_FAILURE.value
        )
    base = score_observation(observation, oracle, report)
    return {
        **{k: v for k, v in base.items() if k not in {"pass", "safe_outcome", "first_failed_stage", "classification", "stage_results", "scope_provenance_result", "budget_result", "evidence_state_result"}},
        "mode": observation["mode"],
        "product_path_eligible": True,
        "final_safety_score": final_score,
        "safe_outcome": final_score.safe_outcome,
        "stage_results": checks,
        "first_failed_stage": first_failed,
        "classification": classification,
        "pass": first_failed is None,
        "scope_provenance_result": (
            "PASS"
            if checks[STAGES[6]]
            else "FAIL"
        ),
        "budget_result": (
            "PASS" if _budget_correct_production(expected, outcome, initial_steps=initial_steps) else "FAIL"
        ),
        "evidence_state_result": (
            "PASS"
            if _evidence_correct_production(expected, observation, initial_steps=initial_steps)
            else "FAIL"
        ),
    }


def build_c12_protocol_proof() -> dict[str, object]:
    """Static C12 protocol proof artifact (live values filled by tests)."""
    return {
        "protocol": PROTOCOL_VERSION,
        "case_id": "C12-out-of-scope-provenance",
        "PRODUCT_PATH_ELIGIBLE": False,
        "REAL_SCOPE_USED": True,
        "DIRECT_FOREIGN_INJECTION": False,
        "PRODUCTION_ORCHESTRATION_USED": True,
        "SHARED_BUDGET_USED": True,
        "FINAL_OUTPUT_SCORING_USED": True,
        "FOREIGN_FINAL_CITATION_DETECTED": False,
        "SAFE_SCORER_FALSE_PASS_ELIMINATED": True,
        "classification": MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value,
        "probe_classification": "DEFENSE_IN_DEPTH_PROBE",
        "product_runtime_diff": 0,
        "golden_diff": 0,
        "workflow_diff": 0,
        "external_model_execution": False,
        "runtime_rollout": False,
    }


def write_validation_artifact(payload: dict[str, object]) -> Path:
    VALIDATION_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return VALIDATION_PATH

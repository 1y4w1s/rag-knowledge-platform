"""Deterministic W9 P2-R1 product-boundary measurement harness.

P2-R1 ``execute_frozen_case`` bypasses production plan construction by injecting
chunks directly into ``_stream_generation_phase``. P2-R2 renames that path
``DEFENSE_IN_DEPTH_PROBE`` (see ``w9_critic_p2_r2_protocol``); product
denominator cases must use ``execute_production_path_case`` instead.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentRunOutcome, StepExecution
from app.services.rag.confidence_reply import AnswerConfidence
from app.services.rag.critic import ClaimCheck, CriticAction, CriticResult
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk


FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
CASES_PATH = FIXTURES / "w9-critic-cases.json"
CONTRACT_PATH = FIXTURES / "w9-critic-capability-contract.json"
INJECTED_PATH = FIXTURES / "w9-critic-p2-injected-reports.json"
STAGES = (
    "L0_CASE_CONTRACT_VALID",
    "L1_CRITIC_OUTPUT_VALID",
    "L2_ACTION_MAPPING_CORRECT",
    "L3_ORCHESTRATION_EXECUTION_CORRECT",
    "L4_EVIDENCE_STATE_CORRECT",
    "L5_TRAJECTORY_AUDIT_ACCOUNTING_CORRECT",
    "L6_BUDGET_SCOPE_PROVENANCE_CORRECT",
    "L7_TERMINAL_OUTCOME_CORRECT",
    "L8_SAFE_OUTCOME",
)


@dataclass(frozen=True, slots=True)
class FrozenSuite:
    cases: tuple[dict[str, object], ...]
    oracle: dict[str, dict[str, object]]
    reports: dict[str, dict[str, object]]


def load_frozen_suite() -> FrozenSuite:
    cases_payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    injected = json.loads(INJECTED_PATH.read_text(encoding="utf-8"))
    cases = tuple(cases_payload["cases"])
    oracle = {item["case_id"]: item for item in contract["oracle_cases"]}
    reports = {item["case_id"]: item for item in injected["reports"]}
    assert cases_payload["protocol"] == "w9_critic_model_inputs_v1"
    assert contract["protocol"] == "w9_critic_capability_contract_v1"
    assert injected["protocol"] == "w9_critic_p2_injected_reports_v1"
    assert len(cases) == len(oracle) == len(reports) == 12
    assert {item["case_id"] for item in cases} == set(oracle) == set(reports)
    return FrozenSuite(cases=cases, oracle=oracle, reports=reports)


def stable_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"w9-p2-r1:{value}")


def _chunk(case_id: str, evidence: dict[str, object], index: int) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=stable_uuid(str(evidence["kb_id"])),
        chunk_id=stable_uuid(f"{case_id}:chunk:{index}:{evidence['evidence_id']}"),
        document_id=stable_uuid(f"{case_id}:document:{index}"),
        doc_name=str(evidence["document"]),
        content=str(evidence["excerpt"]),
        page_number=index + 1,
        section_title=str(evidence["location"]),
        heading_path=str(evidence["location"]),
        similarity=0.9 - index * 0.01,
        kb_name=str(evidence["kb_id"]),
    )


def _critic_result(
    report: dict[str, object], case: dict[str, object], *, accepted: bool = False
) -> CriticResult:
    if accepted:
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="post-action candidate accepted",
            method=str(report["method"]),
        )
    action = CriticAction(str(report["recommended_action"]))
    claims: tuple[ClaimCheck, ...] = ()
    if action is CriticAction.RETRIEVE_MISSING_EVIDENCE:
        claims = (
            ClaimCheck(
                text=str(case["answer"]),
                citation_nums=(1,),
                ok=False,
                issue="required fact missing",
            ),
        )
    return CriticResult(
        ok=bool(report["ok"]),
        claims=claims,
        label=LABEL_UNKNOWN,
        rationale="frozen injected critic report",
        method=str(report["method"]),
        recommended_action=None if report["ok"] else action,
        metadata={"critic.issues": ["frozen injected critic report"]},
    )


async def execute_frozen_case(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    case_id = str(case["case_id"])
    allowed_kb = stable_uuid(str(case["scope"]["allowed_kb_ids"][0]))
    initial_chunks = tuple(
        _chunk(case_id, evidence, index)
        for index, evidence in enumerate(case["evidence"])
    )
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
        assert chunks == list(initial_chunks)
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
        assert hit_scores == {recovered.chunk_id: recovered.similarity}
        return [recovered]

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
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    state: dict[str, object] = {}
    events = [
        event
        async for event in _stream_generation_phase(
            MagicMock(),
            message=str(case["query"]),
            gen_plan=SimpleNamespace(
                citations=[],
                refusal=False,
                gated_chunks=initial_chunks,
                external_context=None,
            ),
            outcome=outcome,
            user_id=stable_uuid(f"{case_id}:user"),
            assistant_message_id=stable_uuid(f"{case_id}:message"),
            state=state,
            workspace=MagicMock(),
            tool_scope=MagicMock(),
            workspace_mode=True,
            default_kb_id=allowed_kb,
            thread_id=stable_uuid(f"{case_id}:thread"),
        )
    ]
    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    return {
        "case_id": case_id,
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
    }


def score_observation(
    observation: dict[str, object],
    oracle: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    outcome: AgentRunOutcome = observation["outcome"]
    expected = str(oracle["expected_action"])
    actions = list(outcome.critic_actions)
    action_observed = expected if expected == "ACCEPT" and not actions else (
        actions[0].action if actions else None
    )
    retrieval = [a for a in actions if a.action == "RETRIEVE_MISSING_EVIDENCE"]
    revisions = [a for a in actions if a.action == "REVISE_FROM_EXISTING_EVIDENCE"]
    expected_terminal = expected in {"CLARIFY", "REFUSE"}
    post_scope_ids = (
        observation["critic_calls"][-1]["kb_ids"]
        if len(observation["critic_calls"]) > 1
        else observation["critic_calls"][0]["kb_ids"]
    )
    allowed = observation["allowed_kb_id"]
    checks = {
        STAGES[0]: True,
        STAGES[1]: str(report["recommended_action"]) in {a.value for a in CriticAction},
        STAGES[2]: action_observed == expected,
        STAGES[3]: _execution_correct(expected, outcome, actions),
        STAGES[4]: _evidence_correct(expected, observation),
        STAGES[5]: len(observation["audit_calls"]) == len(actions),
        STAGES[6]: _budget_correct(expected, outcome)
        and all(kb_id == allowed for kb_id in post_scope_ids),
        STAGES[7]: (outcome.terminal_decision is not None) == expected_terminal
        and (observation["content"] == observation["refusal_content"]) == expected_terminal,
        STAGES[8]: not (expected != "ACCEPT" and observation["content"] == observation["initial_content"]),
    }
    first_failed = next((stage for stage in STAGES if not checks[stage]), None)
    classification = None
    if first_failed is not None:
        classification = (
            "UNSAFE_ACCEPT" if first_failed == STAGES[8] else "PRODUCT_CONTROL_PLANE_FAILURE"
        )
    return {
        "case_id": observation["case_id"],
        "critic_method": report["method"],
        "recommended_action": report["recommended_action"],
        "action_observed": action_observed,
        "execution_status": "EXECUTED",
        "recovery_attempts": sum(
            action.attempt_count for action in (*retrieval, *revisions)
        ),
        "retrieval_attempts": sum(a.attempt_count for a in retrieval),
        "revision_attempts": sum(a.attempt_count for a in revisions),
        "evidence_state_result": "PASS" if checks[STAGES[4]] else "FAIL",
        "trajectory_result": "PASS" if checks[STAGES[5]] else "FAIL",
        "audit_result": "PASS" if checks[STAGES[5]] else "FAIL",
        "budget_result": "PASS" if _budget_correct(expected, outcome) else "FAIL",
        "scope_provenance_result": "PASS" if checks[STAGES[6]] else "FAIL",
        "terminal_result": "PASS" if checks[STAGES[7]] else "FAIL",
        "safe_outcome": checks[STAGES[8]],
        "stage_results": checks,
        "first_failed_stage": first_failed,
        "classification": classification,
        "pass": first_failed is None,
    }


def _execution_correct(expected, outcome, actions) -> bool:
    statuses = [(a.action, a.status, a.attempt_count) for a in actions]
    if expected == "ACCEPT":
        return not statuses and outcome.critic_validation_count == 1
    if expected == "REVISE_FROM_EXISTING_EVIDENCE":
        return statuses == [(expected, "executed", 1)] and outcome.critic_revision_count == 1
    if expected == "RETRIEVE_MISSING_EVIDENCE":
        return statuses == [
            (expected, "executed", 1),
            ("REVISE_FROM_EXISTING_EVIDENCE", "executed", 1),
        ] and outcome.critic_recovery_count == outcome.critic_revision_count == 1
    terminal_status = "mapped_to_refuse" if expected == "CLARIFY" else "executed"
    return statuses == [(expected, terminal_status, 0)]


def _evidence_correct(expected, observation) -> bool:
    outcome: AgentRunOutcome = observation["outcome"]
    if expected == "RETRIEVE_MISSING_EVIDENCE":
        return [str(value) for value in outcome.evidence_state.chunk_ids] == [
            observation["recovered_chunk_id"]
        ]
    return not outcome.evidence_state.chunk_ids and not outcome.evidence_state.document_ids


def _budget_correct(expected, outcome) -> bool:
    if expected == "RETRIEVE_MISSING_EVIDENCE":
        return outcome.steps_used == 1 and len(outcome.steps) == 1 and outcome.steps[0].attempt_count == 1
    return outcome.steps_used == 0 and not outcome.steps

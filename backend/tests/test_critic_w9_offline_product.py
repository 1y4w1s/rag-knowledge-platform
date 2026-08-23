"""W9 P2 offline product-boundary evidence; no provider or model execution."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.eval.critic_capability.loader import load_bound_suite
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import AgentRunOutcome
from app.services.rag.critic import CriticAction, CriticResult
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk


FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
INJECTED_PATH = FIXTURES / "w9-critic-p2-injected-reports.json"
ARTIFACT_PATH = FIXTURES / "w9-critic-p2-offline-product.json"
FORBIDDEN_INJECTOR_KEYS = {
    "expected_action",
    "expected_status",
    "oracle",
    "pass",
    "first_failed_stage",
    "in_capability_denominator",
}


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_walk_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_walk_keys(item) for item in value))
    return set()


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="policy.md",
        content="Employees complete offboarding training before departure.",
        page_number=1,
        section_title="Offboarding",
        heading_path="Offboarding",
        similarity=0.9,
    )


def _load_injected() -> dict[str, dict[str, object]]:
    payload = json.loads(INJECTED_PATH.read_text(encoding="utf-8"))
    assert payload["protocol"] == "w9_critic_p2_injected_reports_v1"
    assert not _walk_keys(payload).intersection(FORBIDDEN_INJECTOR_KEYS)
    reports = payload["reports"]
    assert isinstance(reports, list)
    by_id = {str(item["case_id"]): item for item in reports}
    assert len(by_id) == len(reports), "injected case IDs must be unique"
    return by_id


def test_p2_injection_is_complete_and_oracle_isolation_holds() -> None:
    contract, inputs = load_bound_suite()
    injected = _load_injected()
    denominator = [case for case in contract["oracle_cases"] if case["in_capability_denominator"]]

    assert len(inputs) == len(denominator) == len(injected) == 12
    assert {case["case_id"] for case in denominator} == set(injected)
    assert Counter(case["expected_action"] for case in denominator) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }
    assert Counter(str(report["recommended_action"]) for report in injected.values()) == {
        "ACCEPT": 5,
        "REVISE_FROM_EXISTING_EVIDENCE": 3,
        "RETRIEVE_MISSING_EVIDENCE": 2,
        "CLARIFY": 1,
        "REFUSE": 1,
    }


@pytest.mark.asyncio
async def test_c11_frozen_deterministic_revision_exposes_product_boundary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C11 must retain rules_v1: changing it to llm_verify_v1 would hide the defect."""
    c11 = _load_injected()["C11-citation-format-only-defect"]
    assert c11["method"] == "rules_v1"
    assert c11["recommended_action"] == CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value

    async def _tokens(_messages):
        yield "Draft with a citation defect.[片段1]"

    async def _critic(*_args) -> CriticResult:
        return CriticResult(
            ok=False,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="CITATION_SYNTAX_INVALID",
            method=str(c11["method"]),
            recommended_action=CriticAction(str(c11["recommended_action"])),
        )

    audit = AsyncMock()
    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _tokens)
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr("app.services.agent.stream.audit_agent_recovery_action", audit)
    monkeypatch.setattr("app.services.agent.stream.degradation_requires_llm", lambda _d: True)
    monkeypatch.setattr("app.services.agent.stream.has_available_chat_provider_key", lambda: True)
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "fail_closed")
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", False)

    state: dict[str, object] = {}
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    frames = [
        frame
        async for frame in _stream_generation_phase(
            AsyncMock(),
            message="What is the retention period?",
            gen_plan=SimpleNamespace(
                citations=[], refusal=False, gated_chunks=(_chunk(),), external_context=None
            ),
            outcome=outcome,
            user_id=uuid.uuid4(),
            assistant_message_id=uuid.uuid4(),
            state=state,
        )
    ]

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    record = observed.critic_actions[-1]
    assert (record.action, record.status, record.attempt_count) == (
        CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value,
        "skipped_unavailable",
        0,
    )
    assert observed.critic_revision_count == 0
    assert state["content"] == no_context_reply_for("What is the retention period?")
    assert any("event: token" in frame for frame in frames)
    assert audit.await_args.kwargs["status"] == "skipped_unavailable"


def test_p2_artifact_preserves_partial_verdict_and_zero_rollout() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert artifact["state"] == "PARTIAL"
    assert artifact["round_start_master_sha"] == artifact["p1_merge_sha"]
    assert artifact["execution_tree_matches_round_master"] is True
    assert artifact["frozen_case_count"] == 12
    assert artifact["runnable_case_count"] == 1
    assert artifact["not_yet_run_case_count"] == 11
    assert artifact["invalid_case_count"] == artifact["non_runnable_case_count"] == 0
    assert artifact["default_behavior_changed"] is False
    assert artifact["runtime_rollout"] is False
    assert artifact["external_call_attempted"] is False
    assert artifact["model_result_obtained"] is False
    results = {item["case_id"]: item for item in artifact["case_results"]}
    assert len(results) == artifact["frozen_case_count"]
    assert set(results) == set(_load_injected())
    assert results["C11-citation-format-only-defect"]["classification"] == (
        "PRODUCT_CONTROL_PLANE_FAILURE"
    )
    assert results["C11-citation-format-only-defect"]["first_failed_stage"] == (
        "L3_ORCHESTRATION_EXECUTION_CORRECT"
    )
    assert all(
        item["execution_status"] == "NOT_EXECUTED_STOP_CONDITION"
        for case_id, item in results.items()
        if case_id != "C11-citation-format-only-defect"
    )
    metrics = artifact["metrics"]
    assert metrics["product_case_pass_rate"] == {
        "numerator": 0,
        "denominator": 1,
        "rate": 0.0,
    }
    assert all(metrics[name] == 0 for name in (
        "unsafe_accept_count",
        "hidden_recovery_count",
        "post_critic_mutation_without_revalidation_count",
    ))
    assert metrics["degenerate_policy_false_pass_count"] is None
    assert metrics["audit_accounting_rate"]["value"] is None
    assert metrics["unaccounted_recovery_count"] is None
    assert artifact["verdicts"]["DEGENERATE_POLICY_CONTROLS"] == "NOT_RUN_STOP_CONDITION"
    assert artifact["verdicts"]["READY_FOR_REAL_LOCAL_MEASUREMENT"] == "NO"

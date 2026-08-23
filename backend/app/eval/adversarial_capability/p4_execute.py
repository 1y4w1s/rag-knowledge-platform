"""Run one ADVERSARIAL P4 trial through product run_react_loop."""

from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.database import SessionLocal
from app.eval.adversarial_capability.capability_cases import CapabilityCase
from app.eval.adversarial_capability.corpus_fixtures import CORPUS_BY_ID
from app.eval.adversarial_capability.p1_evaluator import MockTrajectory, evaluate_case
from app.eval.local_agent_trajectory.injection import (
    RecordingAdapter,
    TracingPlanner,
    apply_research_flags,
    patch_planner_llm,
    restore_flags,
    restore_planner_llm,
    wrap_stop_policy,
)
from app.models.enums import AccountType, DocumentStatus
from app.models.document import Document
from app.models.user import User
from app.schemas.auth import UserPublic
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import AgentActionKind, FactStatus
from app.services.auth.password import hash_password
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.knowledge_base.crud import create_knowledge_base
from app.services.rag.thread_persistence import create_kb_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope, resolve_workspace


def _corpus_markdown(case: CapabilityCase) -> str:
    corpus = CORPUS_BY_ID[case.corpus_fixture_id]
    parts = [f"# {d['title']}\n" for d in corpus.documents]
    for chunk in corpus.chunks:
        parts.append(chunk["text"] + "\n")
    return "\n".join(parts)


async def _ensure_user() -> UUID:
    async with SessionLocal() as db:
        user = User(
            email=f"adv-p4-{uuid.uuid4().hex[:10]}@example.com",
            username=f"advp4{uuid.uuid4().hex[:8]}"[:32],
            password_hash=hash_password("AdvP4Research!a"),
            account_type=AccountType.personal,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _create_kb(user_id: UUID, case_id: str) -> UUID:
    async with SessionLocal() as db:
        row = await db.get(User, user_id)
        current = UserPublic(
            id=row.id,
            email=row.email,
            username=row.username,
            nickname=row.nickname,
            account_type=row.account_type,
        )
        workspace = await resolve_workspace(db, current, "personal")
        kb = await create_knowledge_base(
            db,
            current,
            KnowledgeBaseCreate(name=f"ADV-P4 {case_id} {uuid.uuid4().hex[:8]}"),
            workspace,
        )
        kb_id = kb.id if isinstance(kb.id, UUID) else UUID(str(kb.id))
        await db.commit()
        return kb_id


async def _ingest_corpus(*, kb_id: UUID, user_id: UUID, case: CapabilityCase, upload_dir: Path) -> None:
    text = _corpus_markdown(case)
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{doc_id}.md"
    storage_path.write_text(text, encoding="utf-8")
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=f"{case.case_id}.md",
            file_type="md",
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)


def _trajectory_from_outcome(case: CapabilityCase, outcome, captures: list) -> MockTrajectory:
    terminal = "refuse"
    if outcome.terminal_decision is not None:
        terminal = outcome.terminal_decision.action.value
    retrieval_attempted = any(
        s.decision.action == AgentActionKind.tool for s in outcome.steps
    )
    hits: set[str] = set()
    for step in outcome.steps:
        if step.execution and step.execution.data:
            data = step.execution.data
            for hit in data.get("hits") or data.get("chunks") or []:
                if isinstance(hit, dict):
                    cid = hit.get("chunk_id") or hit.get("id")
                    if cid:
                        hits.add(str(cid))
    cap = captures[-1] if captures else None
    conflicts = list(getattr(cap, "conflicts_after", []) or []) if cap else []
    facts_after = getattr(cap, "facts_after", {}) or {} if cap else {}
    evidence_state = "insufficient"
    if case.answerability_class == "ANSWERABLE":
        evidence_state = "sufficient" if any(v == "supported" for v in facts_after.values()) else "insufficient"
    elif case.answerability_class == "UNANSWERABLE_IN_CORPUS":
        evidence_state = "absent"
    elif case.answerability_class == "INSUFFICIENT_EVIDENCE":
        evidence_state = "partial" if facts_after else "partial"
    elif case.answerability_class == "CONFLICTED_EVIDENCE":
        evidence_state = "conflicted" if conflicts else "conflicted"
    citations = tuple(hits) if terminal == "finish" else ()
    return MockTrajectory(
        case_id=case.case_id,
        answerability_class=case.answerability_class,
        retrieval_attempted=retrieval_attempted,
        retrieval_hits=tuple(hits),
        evidence_state=evidence_state,
        terminal=terminal,
        citations=citations,
    )


async def run_adv_p4_trial(
    case: CapabilityCase,
    adapter: RecordingAdapter,
    *,
    user_id: UUID,
    upload_dir: Path,
    trial_index: int,
    timeout: float = 90.0,
) -> dict[str, Any]:
    saved = apply_research_flags()
    captures: list = []
    stop_wrapped = wrap_stop_policy(captures)
    from app.services.agent import matcher_runtime, stop_policy

    orig_stop = stop_policy.apply_stop_policy_decision
    stop_policy.apply_stop_policy_decision = stop_wrapped  # type: ignore[method-assign]
    patch_planner_llm(adapter)
    started = time.perf_counter()
    kb_id = await _create_kb(user_id, case.case_id)
    await _ingest_corpus(kb_id=kb_id, user_id=user_id, case=case, upload_dir=upload_dir)
    async with SessionLocal() as db:
        thread = await create_kb_thread(db, user_id=user_id, kb_id=kb_id)
        await db.commit()
        thread_id = thread.id
    workspace = WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}), default_kb_id=kb_id)
    planner = TracingPlanner(case.question, adapter=adapter, captures=captures)
    try:
        async with SessionLocal() as db:
            outcome = await run_react_loop(
                db,
                user_id=user_id,
                thread_id=thread_id,
                query=case.question,
                workspace=workspace,
                tool_scope=tool_scope,
                planner=planner,
                max_steps=5,
                timeout_seconds=timeout,
            )
            await db.commit()
    finally:
        stop_policy.apply_stop_policy_decision = orig_stop  # type: ignore[method-assign]
        restore_planner_llm()
        restore_flags(saved)
    mock = _trajectory_from_outcome(case, outcome, captures)
    evaluation = evaluate_case(case, mock)
    return {
        "case_id": case.case_id,
        "trial_index": trial_index,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "run_id": str(outcome.run_id),
        "terminal": mock.terminal,
        "retrieval_attempted": mock.retrieval_attempted,
        "passed": evaluation.passed,
        "first_failed_stage": evaluation.first_failed_stage,
        "stages": [
            {"stage": s.stage, "passed": s.passed, "detail": s.detail} for s in evaluation.stages
        ],
    }




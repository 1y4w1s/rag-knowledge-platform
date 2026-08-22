"""Timed Golden benchmark case runner (W8 P4 measurement hygiene)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.database import SessionLocal
from app.eval.golden_benchmark.timing import CaseTiming
from app.eval.local_agent_trajectory.injection import (
    RecordingAdapter,
    TracingPlanner,
    apply_research_flags,
    patch_planner_llm,
    restore_flags,
    restore_planner_llm,
    wrap_stop_policy,
)
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.user import User
from app.schemas.auth import UserPublic
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.knowledge_base.crud import create_knowledge_base
from app.services.rag.thread_persistence import create_kb_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope, resolve_workspace
from tests.golden_agent_qa_loader import AgentGoldenCase, GOLDEN_AGENT_MD
from tests.golden_qa_loader import GOLDEN_MD


@dataclass
class EntityExtractionAudit:
    """Track entity-extraction HTTP calls during benchmark ingest."""

    extract_entities_sync_calls: int = 0
    extract_entities_for_document_calls: int = 0
    http_402_retries: int = 0
    _orig_sync: Any = field(default=None, repr=False)
    _orig_for_doc: Any = field(default=None, repr=False)

    def install(self) -> None:
        import app.services.rag.entity_extractor as mod

        self._orig_sync = mod.extract_entities_sync
        self._orig_for_doc = mod.extract_entities_for_document
        audit = self

        def _tracked_sync(text: str) -> dict:
            audit.extract_entities_sync_calls += 1
            return audit._orig_sync(text)

        async def _tracked_for_doc(db, doc) -> None:  # noqa: ANN001
            audit.extract_entities_for_document_calls += 1
            return await audit._orig_for_doc(db, doc)

        mod.extract_entities_sync = _tracked_sync  # type: ignore[method-assign]
        mod.extract_entities_for_document = _tracked_for_doc  # type: ignore[method-assign]

    def restore(self) -> None:
        if self._orig_sync is None or self._orig_for_doc is None:
            return
        import app.services.rag.entity_extractor as mod

        mod.extract_entities_sync = self._orig_sync  # type: ignore[method-assign]
        mod.extract_entities_for_document = self._orig_for_doc  # type: ignore[method-assign]


def pick_fixture(case: AgentGoldenCase) -> tuple[Path, str]:
    if case.category in ("RAG", "RETRIEVAL", "MULTI_STEP"):
        return GOLDEN_AGENT_MD, "md"
    return GOLDEN_MD, "md"


async def ingest_fixture(
    *,
    kb_id: UUID,
    user_id: UUID,
    source: Path,
    file_type: str,
    upload_dir: Path,
) -> None:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=source.name,
            file_type=file_type,
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)


async def _load_user_public(user_id: UUID) -> UserPublic:
    async with SessionLocal() as db:
        from sqlalchemy import select

        row = await db.execute(select(User).where(User.id == user_id))
        user = row.scalar_one()
        return UserPublic(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            account_type=user.account_type,
        )


async def run_timed_case(
    case: AgentGoldenCase,
    adapter: RecordingAdapter,
    upload_dir: Path,
    user_id: UUID,
    *,
    run_timeout: float = 600.0,
    max_steps: int = 5,
) -> CaseTiming:
    """Run one Golden case with phase timing; agent_execution_ms excludes setup."""
    saved_flags = apply_research_flags()
    captures: list = []
    stop_wrapped = wrap_stop_policy(captures)
    from app.services.agent import matcher_runtime, stop_policy

    orig_stop = stop_policy.apply_stop_policy_decision
    orig_match = matcher_runtime.maybe_apply_evidence_match_after_tool
    stop_policy.apply_stop_policy_decision = stop_wrapped  # type: ignore[method-assign]
    matcher_runtime.maybe_apply_evidence_match_after_tool = orig_match  # type: ignore[method-assign]
    patch_planner_llm(adapter)

    case_started = time.perf_counter()
    kb_create_ms = 0.0
    fixture_select_ms = 0.0
    ingest_total_ms = 0.0
    memory_seed_ms = 0.0
    thread_create_ms = 0.0
    agent_execution_ms = 0.0
    kb_id: UUID | None = None
    task_success: bool | None = None

    try:
        t_kb = time.perf_counter()
        async with SessionLocal() as db:
            current_user = await _load_user_public(user_id)
            workspace = await resolve_workspace(db, current_user, "personal")
            kb_resp = await create_knowledge_base(
                db,
                current_user,
                KnowledgeBaseCreate(name=f"W8P4 {case.case_id}"),
                workspace,
            )
            kb_id = kb_resp.id if isinstance(kb_resp.id, UUID) else UUID(str(kb_resp.id))
        kb_create_ms = (time.perf_counter() - t_kb) * 1000.0

        t_fix = time.perf_counter()
        source, file_type = pick_fixture(case)
        fixture_select_ms = (time.perf_counter() - t_fix) * 1000.0

        t_ing = time.perf_counter()
        await ingest_fixture(
            kb_id=kb_id,
            user_id=user_id,
            source=source,
            file_type=file_type,
            upload_dir=upload_dir,
        )
        ingest_total_ms = (time.perf_counter() - t_ing) * 1000.0

        if case.category == "MEMORY" and case.pre_seed_memories:
            t_mem = time.perf_counter()
            from app.services.agent.memory import upsert_memory

            async with SessionLocal() as db:
                for mem in case.pre_seed_memories:
                    await upsert_memory(
                        db,
                        user_id,
                        memory_type=mem["memory_type"],
                        key=mem["key"],
                        value=mem["value"],
                    )
                await db.commit()
            memory_seed_ms = (time.perf_counter() - t_mem) * 1000.0

        if case.category == "AUTH":
            tool_scope = AgentToolScope(visible_kb_ids=frozenset(), default_kb_id=kb_id)
        else:
            tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}), default_kb_id=kb_id)

        t_thread = time.perf_counter()
        async with SessionLocal() as db:
            thread = await create_kb_thread(
                db, kb_id=kb_id, user_id=user_id, title=f"W8P4 {case.case_id}"
            )
            await db.commit()
            thread_id = thread.id
        thread_create_ms = (time.perf_counter() - t_thread) * 1000.0

        setup_total_ms = (
            kb_create_ms + fixture_select_ms + ingest_total_ms + memory_seed_ms + thread_create_ms
        )

        planner = TracingPlanner(case.query, adapter=adapter, captures=captures)
        t_agent = time.perf_counter()
        async with SessionLocal() as db:
            outcome = await run_react_loop(
                db,
                user_id=user_id,
                thread_id=thread_id,
                query=case.query,
                workspace=WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None),
                tool_scope=tool_scope,
                planner=planner,
                max_steps=max_steps,
                timeout_seconds=run_timeout,
            )
            await db.commit()
        agent_execution_ms = (time.perf_counter() - t_agent) * 1000.0
        task_success = outcome.terminal_decision is not None and not outcome.timed_out

        latencies = [c.latency_ms for c in captures if c.latency_ms]
        model_call_total_ms = round(sum(latencies), 1)

        case_total_wall_ms = (time.perf_counter() - case_started) * 1000.0

        return CaseTiming(
            case_id=case.case_id,
            category=case.category,
            case_total_wall_ms=round(case_total_wall_ms, 1),
            setup_total_ms=round(setup_total_ms, 1),
            kb_create_ms=round(kb_create_ms, 1),
            fixture_select_ms=round(fixture_select_ms, 1),
            ingest_total_ms=round(ingest_total_ms, 1),
            memory_seed_ms=round(memory_seed_ms, 1),
            thread_create_ms=round(thread_create_ms, 1),
            agent_execution_ms=round(agent_execution_ms, 1),
            model_call_total_ms=model_call_total_ms,
            model_call_count=len(latencies),
            model_call_latencies_ms=[round(x, 1) for x in latencies],
            entity_extraction=(
                "SKIPPED_BY_BENCHMARK_PROTOCOL"
                if settings.skip_entity_extract
                else "NOT_SKIPPED"
            ),
            entity_extraction_ms=None if settings.skip_entity_extract else None,
            task_success=task_success,
        )
    finally:
        stop_policy.apply_stop_policy_decision = orig_stop  # type: ignore[method-assign]
        matcher_runtime.maybe_apply_evidence_match_after_tool = orig_match  # type: ignore[method-assign]
        restore_flags(saved_flags)
        restore_planner_llm()

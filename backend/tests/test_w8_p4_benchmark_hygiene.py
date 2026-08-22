"""W8 P4 benchmark measurement hygiene — deterministic tests (no LM Studio)."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.eval.golden_benchmark.compatibility import (
    INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES,
    REAL_TRAJECTORY_GOLDEN_CATEGORIES,
    is_real_trajectory_category,
    is_unit_only_category,
)
from app.eval.golden_benchmark.corpus import collect_corpus_fingerprint, corpora_equivalent
from app.eval.golden_benchmark.harness import EntityExtractionAudit, ingest_fixture
from app.eval.golden_benchmark.manifest import (
    W8_P4_TIMING_VALIDATION_CASE_IDS,
    build_timing_validation_manifest,
)
from app.eval.golden_benchmark.settings import apply_benchmark_settings, restore_benchmark_settings
from app.eval.golden_benchmark.timing import (
    CaseTiming,
    aggregate_timing_stats,
    validate_timing_invariants,
)
from app.eval.local_agent_trajectory.injection import RecordingAdapter
from app.models.user import User
from app.schemas.auth import UserPublic
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.ingestion import embedder
from app.services.knowledge_base.crud import create_knowledge_base
from app.services.workspace.scope import resolve_workspace
from tests.golden_agent_qa_loader import GOLDEN_AGENT_MD, load_golden_agent_cases


def test_production_skip_entity_extract_default_unchanged() -> None:
    assert settings.skip_entity_extract is False


def test_apply_benchmark_settings_sets_skip_entity_extract() -> None:
    saved = apply_benchmark_settings()
    try:
        assert settings.skip_entity_extract is True
        assert settings.embedding_provider == "mock"
        assert settings.agent_l3_next_action_enabled is True
    finally:
        restore_benchmark_settings(saved)
    assert settings.skip_entity_extract is False


def test_timing_validation_manifest_frozen_nine_cases() -> None:
    cases = load_golden_agent_cases()
    by_id = {c.case_id: c for c in cases}
    manifest = build_timing_validation_manifest(by_id)
    assert manifest["case_count"] == 9
    assert manifest["case_ids"] == list(W8_P4_TIMING_VALIDATION_CASE_IDS)
    assert manifest["category_counts"] == {
        "ADVERSARIAL": 1,
        "AUTH": 1,
        "MEMORY": 1,
        "MULTI_STEP": 1,
        "RAG": 2,
        "RETRIEVAL": 2,
        "TOOL": 1,
    }


def test_reflection_degrade_are_unit_only_not_trajectory() -> None:
    assert INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES == frozenset({"REFLECTION", "DEGRADE"})
    assert is_unit_only_category("REFLECTION")
    assert is_unit_only_category("DEGRADE")
    assert not is_real_trajectory_category("REFLECTION")
    assert not is_real_trajectory_category("DEGRADE")
    for cat in REAL_TRAJECTORY_GOLDEN_CATEGORIES:
        assert not is_unit_only_category(cat)
        assert is_real_trajectory_category(cat)


def test_timing_fields_schema_and_invariants() -> None:
    timing = CaseTiming(
        case_id="GQ-8",
        category="RAG",
        case_total_wall_ms=12000.0,
        setup_total_ms=8000.0,
        kb_create_ms=100.0,
        fixture_select_ms=1.0,
        ingest_total_ms=7800.0,
        memory_seed_ms=0.0,
        thread_create_ms=99.0,
        agent_execution_ms=4000.0,
        model_call_total_ms=3300.0,
        model_call_count=1,
        model_call_latencies_ms=[3300.0],
    )
    payload = timing.to_dict()
    required = {
        "case_total_wall_ms",
        "setup_total_ms",
        "kb_create_ms",
        "fixture_select_ms",
        "ingest_total_ms",
        "memory_seed_ms",
        "thread_create_ms",
        "agent_execution_ms",
        "model_call_total_ms",
        "model_call_count",
        "entity_extraction",
        "entity_extraction_ms",
        "agent_non_model_overhead_ms",
    }
    assert required <= set(payload.keys())
    assert payload["entity_extraction"] == "SKIPPED_BY_BENCHMARK_PROTOCOL"
    assert payload["entity_extraction_ms"] is None
    assert payload["agent_non_model_overhead_ms"] == 700.0
    assert validate_timing_invariants(timing) == []


def test_timing_invariant_detects_setup_exceeds_total() -> None:
    timing = CaseTiming(
        case_id="GQ-8",
        category="RAG",
        case_total_wall_ms=1000.0,
        setup_total_ms=2000.0,
        kb_create_ms=2000.0,
        fixture_select_ms=0.0,
        ingest_total_ms=0.0,
        memory_seed_ms=0.0,
        thread_create_ms=0.0,
        agent_execution_ms=500.0,
        model_call_total_ms=400.0,
        model_call_count=1,
    )
    violations = validate_timing_invariants(timing)
    assert any("setup_total_ms" in v or "case_total_wall_ms" in v for v in violations)


def test_aggregate_timing_stats_structure() -> None:
    timings = [
        CaseTiming(
            case_id="a",
            category="RAG",
            case_total_wall_ms=10000.0,
            setup_total_ms=6000.0,
            kb_create_ms=100.0,
            fixture_select_ms=1.0,
            ingest_total_ms=5800.0,
            memory_seed_ms=0.0,
            thread_create_ms=99.0,
            agent_execution_ms=4000.0,
            model_call_total_ms=3000.0,
            model_call_count=1,
            model_call_latencies_ms=[3000.0],
        ),
        CaseTiming(
            case_id="b",
            category="RAG",
            case_total_wall_ms=20000.0,
            setup_total_ms=12000.0,
            kb_create_ms=200.0,
            fixture_select_ms=2.0,
            ingest_total_ms=11600.0,
            memory_seed_ms=0.0,
            thread_create_ms=198.0,
            agent_execution_ms=8000.0,
            model_call_total_ms=6000.0,
            model_call_count=2,
            model_call_latencies_ms=[3000.0, 3000.0],
        ),
    ]
    stats = aggregate_timing_stats(timings)
    assert stats["case_count"] == 2
    assert stats["case_total_wall_ms"]["p50"] == 15000.0
    assert stats["setup_total_ms"]["p50"] == 9000.0
    assert stats["agent_execution_ms"]["p50"] == 6000.0
    assert stats["entity_extraction"] == "SKIPPED_BY_BENCHMARK_PROTOCOL"


async def _mock_embed_texts(texts: list[str]) -> list[list[float]]:
    return [embedder._mock_vector(t) for t in texts]


@pytest.fixture(autouse=True)
def _mock_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedder, "embed_texts", _mock_embed_texts)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _create_kb_for_user(user_id: uuid.UUID, name: str) -> uuid.UUID:
    async with SessionLocal() as db:
        row = await db.execute(select(User).where(User.id == user_id))
        u = row.scalar_one()
        current = UserPublic(
            id=u.id,
            email=u.email,
            username=u.username,
            nickname=u.nickname,
            account_type=u.account_type,
        )
        workspace = await resolve_workspace(db, current, "personal")
        kb_resp = await create_knowledge_base(
            db,
            current,
            KnowledgeBaseCreate(name=name),
            workspace,
        )
        kb_id = kb_resp.id if isinstance(kb_resp.id, uuid.UUID) else uuid.UUID(str(kb_resp.id))
        await db.commit()
        return kb_id


@pytest.mark.asyncio
async def test_skip_entity_extract_preserves_chunk_corpus(register_and_login, upload_dir) -> None:
    """PRE (skip=False, mocked entity extract) vs POST (skip=True) chunk corpus must match."""
    _, user_payload = await register_and_login(prefix="w8p4corp")
    user_id = uuid.UUID(user_payload["id"])

    async def _noop_extract(db, doc) -> None:  # noqa: ANN001
        return None

    async def _ingest_with_skip(skip: bool) -> dict:
        saved = apply_benchmark_settings()
        settings.skip_entity_extract = skip
        try:
            kb_id = await _create_kb_for_user(user_id, f"corp-{skip}-{uuid.uuid4().hex[:6]}")
            with patch(
                "app.services.ingestion.pipeline.extract_entities_for_document",
                new=_noop_extract,
            ):
                await ingest_fixture(
                    kb_id=kb_id,
                    user_id=user_id,
                    source=GOLDEN_AGENT_MD,
                    file_type="md",
                    upload_dir=Path(upload_dir),
                )
            async with SessionLocal() as db:
                return await collect_corpus_fingerprint(db, kb_id)
        finally:
            restore_benchmark_settings(saved)

    pre = await _ingest_with_skip(skip=False)
    post = await _ingest_with_skip(skip=True)
    assert corpora_equivalent(pre, post), f"PRE={pre} POST={post}"
    assert pre["chunk_count"] > 0
    assert pre["chunk_content_hashes"] == post["chunk_content_hashes"]


@pytest.mark.asyncio
async def test_benchmark_ingest_skips_entity_extraction_calls(
    register_and_login,
    upload_dir,
) -> None:
    """With skip_entity_extract=True, extract_entities_sync must not be invoked."""
    _, user_payload = await register_and_login(prefix="w8p4net")
    user_id = uuid.UUID(user_payload["id"])
    saved = apply_benchmark_settings()
    audit = EntityExtractionAudit()
    audit.install()
    try:
        assert settings.skip_entity_extract is True
        kb_id = await _create_kb_for_user(user_id, "w8p4-net-audit")
        await ingest_fixture(
            kb_id=kb_id,
            user_id=user_id,
            source=GOLDEN_AGENT_MD,
            file_type="md",
            upload_dir=Path(upload_dir),
        )
        assert audit.extract_entities_sync_calls == 0
        assert audit.extract_entities_for_document_calls == 0
    finally:
        audit.restore()
        restore_benchmark_settings(saved)


@pytest.mark.asyncio
async def test_agent_execution_timer_excludes_setup(monkeypatch, register_and_login, upload_dir) -> None:
    """agent_execution_ms must not include KB create / ingest / thread create."""
    from app.eval.golden_benchmark.harness import ingest_fixture as orig_ingest
    from app.eval.golden_benchmark.harness import run_timed_case
    from app.services.agent.types import AgentActionKind, AgentDecision, AgentRunOutcome

    _, user_payload = await register_and_login(prefix="w8p4time")
    user_id = uuid.UUID(user_payload["id"])
    cases = load_golden_agent_cases()
    case = next(c for c in cases if c.case_id == "GQ-8")

    adapter = RecordingAdapter(AsyncMock())
    setup_delay_ms = 50.0
    agent_delay_ms = 120.0

    async def _slow_ingest(**kwargs):  # noqa: ANN003
        await asyncio.sleep(setup_delay_ms / 1000.0)
        return await orig_ingest(**kwargs)

    async def _slow_react_loop(*args, **kwargs):  # noqa: ANN003, ANN002
        await asyncio.sleep(agent_delay_ms / 1000.0)
        return AgentRunOutcome(
            run_id=uuid.uuid4(),
            steps_used=1,
            max_steps=5,
            capped=False,
            timed_out=False,
            steps=(),
            terminal_decision=AgentDecision(action=AgentActionKind.finish, reason_code="facts_covered"),
        )

    saved = apply_benchmark_settings()
    try:
        monkeypatch.setattr(
            "app.eval.golden_benchmark.harness.ingest_fixture",
            _slow_ingest,
        )
        monkeypatch.setattr(
            "app.eval.golden_benchmark.harness.run_react_loop",
            _slow_react_loop,
        )
        timing = await run_timed_case(
            case,
            adapter,
            Path(upload_dir),
            user_id,
            run_timeout=30.0,
        )
    finally:
        restore_benchmark_settings(saved)

    assert timing.ingest_total_ms >= setup_delay_ms * 0.8
    assert timing.agent_execution_ms >= agent_delay_ms * 0.8
    assert timing.setup_total_ms >= setup_delay_ms * 0.8
    assert validate_timing_invariants(timing) == []

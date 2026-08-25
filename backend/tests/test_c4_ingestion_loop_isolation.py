"""C4 regression: Celery thread-pool ingest must isolate AsyncEngine per event loop.

Failure class observed in multi-file upload:
  RuntimeError: ... got Future ... attached to a different loop

Root cause: ``--pool=threads`` + ``anyio.run()`` per task creates a new event
loop while the process-global AsyncEngine/asyncpg pool still holds connections
bound to a prior loop.

This module locks the corrected lifecycle in ``app.services.ingestion.tasks``:
serialize one loop-bound ingest at a time and ``await engine.dispose()`` when
that loop ends.
"""

from __future__ import annotations

import inspect
import threading
from typing import Any
from uuid import uuid4

import anyio
import pytest
from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.services.ingestion import tasks as tasks_mod
from app.services.ingestion.pipeline import IngestionOutcome


def test_ingest_task_exposes_loop_isolation_helpers() -> None:
    assert hasattr(tasks_mod._INGEST_LOOP_LOCK, "acquire")
    assert hasattr(tasks_mod._INGEST_LOOP_LOCK, "release")
    assert callable(tasks_mod._process_document_on_fresh_loop)


def test_process_document_on_fresh_loop_source_disposes_in_finally() -> None:
    """Structural lock: dispose must live in ``finally`` (success and failure)."""
    src = inspect.getsource(tasks_mod._process_document_on_fresh_loop)
    assert "finally:" in src
    assert "await engine.dispose()" in src
    # Pipeline call must be inside try so failures still dispose.
    try_idx = src.index("try:")
    finally_idx = src.index("finally:")
    call_idx = src.index("process_document_ingestion")
    assert try_idx < call_idx < finally_idx


def test_ingest_document_task_holds_lock_around_anyio_run() -> None:
    src = inspect.getsource(tasks_mod.ingest_document_task)
    assert "_INGEST_LOOP_LOCK" in src
    assert "anyio.run(_process_document_on_fresh_loop" in src
    lock_idx = src.index("with _INGEST_LOOP_LOCK")
    run_idx = src.index("anyio.run(_process_document_on_fresh_loop")
    assert lock_idx < run_idx


def test_shared_engine_across_sequential_anyio_runs_needs_dispose() -> None:
    """Deterministic reproduction of the failure class (no Celery, no LLM).

    First ``anyio.run`` binds pooled asyncpg connections to loop A.
    A second ``anyio.run`` (new loop B) that reuses the undisposed pool must
    fail. After ``engine.dispose()``, a third run succeeds — the invariant the
    Celery task finally-block enforces.
    """

    async def _ping() -> None:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))

    async def _dispose() -> None:
        await engine.dispose()

    anyio.run(_dispose)
    anyio.run(_ping)

    with pytest.raises(Exception) as excinfo:
        anyio.run(_ping)

    # Windows Proactor may surface AttributeError; Linux/asyncpg usually RuntimeError.
    msg = f"{type(excinfo.value).__name__}: {excinfo.value}".lower()
    assert (
        "loop" in msg
        or "future" in msg
        or "attached" in msg
        or "nonetype" in msg
        or "closed" in msg
    ), msg

    anyio.run(_dispose)
    anyio.run(_ping)
    anyio.run(_dispose)


def test_ingest_document_task_serializes_cross_thread_db_pings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Celery task entry: concurrent threads must not share loop-bound pools.

    Mirrors ``--pool=threads`` workers calling ``ingest_document_task``.
    Pipeline is stubbed to a real DB ping only (no embedding / LLM).
    """
    lock = threading.Lock()
    errors: list[str] = []
    outcomes: list[str] = []

    async def _fake_pipeline(_doc_id: Any) -> IngestionOutcome:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return IngestionOutcome.completed

    monkeypatch.setattr(
        tasks_mod,
        "process_document_ingestion",
        _fake_pipeline,
    )

    def _worker(label: str) -> None:
        try:
            result = tasks_mod.ingest_document_task.run(str(uuid4()))
            with lock:
                outcomes.append(f"{label}:{result['status']}")
        except Exception as exc:  # pragma: no cover - failure under test
            with lock:
                errors.append(f"{label}:{type(exc).__name__}:{exc}")

    threads = [
        threading.Thread(target=_worker, args=(f"t{i}",), daemon=True)
        for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
        assert not t.is_alive()

    assert errors == [], errors
    assert sorted(outcomes) == [
        "t0:completed",
        "t1:completed",
        "t2:completed",
    ]

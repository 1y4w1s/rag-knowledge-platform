"""M9-P0-1：ingestion 并发闸替换为线程安全、跨 event loop 的容量闸。"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import anyio
import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import pipeline as pipeline_mod
from app.services.ingestion.pipeline import (
    IngestionOutcome,
    _AsyncCapacityLimiter,
    process_document_ingestion,
)
from app.services.ingestion.types import ParsedBlock
from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def fresh_semaphore(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例使用独立的容量闸，避免跨用例残留计数。"""
    monkeypatch.setattr(
        pipeline_mod,
        "_INGESTION_SEMAPHORE",
        _AsyncCapacityLimiter(5),
    )


async def _wait_until(
    condition: Callable[[], bool],
    *,
    timeout: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() >= deadline:
            raise AssertionError("等待条件超时")
        await asyncio.sleep(0.02)


async def _kb_context(
    client: AsyncClient,
    register_and_login: Any,
) -> tuple[UUID, UUID]:
    headers, user = await register_and_login(prefix="m9p01")
    kb = await _create_kb(client, headers, user, name="M9-P0-1 跨 loop 容量闸")
    return UUID(kb["id"]), UUID(user["id"])


async def _seed_doc(
    kb_id: UUID,
    uploaded_by: UUID,
    tmp_path: Path,
) -> UUID:
    doc_id = uuid.uuid4()
    storage = tmp_path / f"{doc_id}.md"
    storage.write_text(
        "# 测试制度\n\n"
        "第一条款：员工每年可申请年假 10 天，需要提前两周申请，"
        "并且按照公司流程填写休假申请表，经主管审批后生效。\n",
        encoding="utf-8",
    )
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="m9-p0-1.md",
                file_type="md",
                file_size=storage.stat().st_size,
                storage_path=str(storage),
                status=DocumentStatus.queued,
                uploaded_by=uploaded_by,
            )
        )
        await db.commit()
    return doc_id


def _fake_parse(calls: dict[str, int]):
    def _parse(*_args: Any, **_kwargs: Any) -> list[ParsedBlock]:
        calls["count"] += 1
        return [
            ParsedBlock(
                content=(
                    "这是一段足够长的测试正文，用于跨 loop 场景下验证解析只执行一次，"
                    "入库管道按结构优先切分并写入文档切片。"
                ),
                section_title="测试",
                heading_path="测试",
            )
        ]

    return _parse


def test_module_semaphore_is_loop_independent_capacity_limiter() -> None:
    semaphore = pipeline_mod._INGESTION_SEMAPHORE
    assert isinstance(semaphore, _AsyncCapacityLimiter)
    assert semaphore.total_tokens == 5


async def test_cross_loop_full_slot_waits_then_acquires(
    fresh_semaphore: None,
) -> None:
    limiter = pipeline_mod._INGESTION_SEMAPHORE
    assert isinstance(limiter, _AsyncCapacityLimiter)

    holders_started = threading.Event()
    release_holders = threading.Event()
    state_lock = threading.Lock()
    outcomes: list[str] = []

    def _run_loop_a() -> None:
        async def _holder() -> None:
            async with limiter:
                with state_lock:
                    outcomes.append("a-held")
                    if outcomes.count("a-held") == 5:
                        holders_started.set()
                await asyncio.to_thread(release_holders.wait, 5)

        async def _main() -> None:
            await asyncio.gather(*(_holder() for _ in range(5)))

        try:
            anyio.run(_main)
        except Exception as exc:  # pragma: no cover - 复现失败路径
            with state_lock:
                outcomes.append(f"a-error:{type(exc).__name__}:{exc}")

    def _run_loop_b() -> None:
        async def _main() -> None:
            try:
                async with limiter:
                    with state_lock:
                        outcomes.append("b-entered")
            except Exception as exc:
                with state_lock:
                    outcomes.append(f"b-error:{type(exc).__name__}:{exc}")

        anyio.run(_main)

    thread_a = threading.Thread(target=_run_loop_a, daemon=True)
    thread_b = threading.Thread(target=_run_loop_b, daemon=True)
    thread_a.start()
    assert holders_started.wait(5), "loop A 未在 5 秒内占满 5 槽"
    thread_b.start()
    await _wait_until(lambda: len(limiter._waiters) >= 1)
    with state_lock:
        assert outcomes.count("b-entered") == 0
        assert not any(s.startswith("b-error") for s in outcomes)
    release_holders.set()
    thread_b.join(5)
    thread_a.join(5)
    with state_lock:
        assert outcomes.count("b-entered") == 1
    assert not thread_b.is_alive()
    assert not thread_a.is_alive()


async def test_capacity_limit_retained_same_loop(
    fresh_semaphore: None,
) -> None:
    limiter = pipeline_mod._INGESTION_SEMAPHORE
    assert limiter.total_tokens == 5

    entered: list[str] = []
    holders_started = threading.Event()
    release_holders = threading.Event()

    async def _holder(name: str) -> None:
        async with limiter:
            entered.append(name)
            if len(entered) == 5:
                holders_started.set()
            await asyncio.to_thread(release_holders.wait, 5)

    holders = [asyncio.create_task(_holder(f"h{i}")) for i in range(5)]
    assert await asyncio.to_thread(holders_started.wait, 5)
    sixth = asyncio.create_task(_holder("sixth"))
    await _wait_until(lambda: len(limiter._waiters) == 1)
    assert entered == ["h0", "h1", "h2", "h3", "h4"]

    release_holders.set()
    await asyncio.wait_for(sixth, 2)
    assert entered[-1] == "sixth"
    await asyncio.gather(*holders)


async def test_cancel_waiting_acquire_does_not_leak_token(
    fresh_semaphore: None,
) -> None:
    limiter = pipeline_mod._INGESTION_SEMAPHORE
    for _ in range(5):
        await limiter.acquire()

    first = asyncio.create_task(limiter.acquire())
    await _wait_until(lambda: len(limiter._waiters) == 1)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    await _wait_until(lambda: len(limiter._waiters) == 0)

    second = asyncio.create_task(limiter.acquire())
    await _wait_until(lambda: len(limiter._waiters) == 1)
    limiter.release()
    await asyncio.wait_for(second, 2)

    blocked = asyncio.create_task(limiter.acquire())
    await _wait_until(lambda: len(limiter._waiters) == 1)
    assert not blocked.done()
    limiter.release()
    await asyncio.wait_for(blocked, 2)

    for _ in range(5):
        limiter.release()


async def test_pipeline_dual_loop_completes_without_loop_error(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fresh_semaphore: None,
) -> None:
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    calls = {"count": 0}
    monkeypatch.setattr(pipeline_mod, "parse_document", _fake_parse(calls))

    limiter = pipeline_mod._INGESTION_SEMAPHORE
    holders_started = threading.Event()
    release_holders = threading.Event()
    state_lock = threading.Lock()
    holder_count = {"n": 0}

    def _run_loop_a() -> None:
        async def _holder() -> None:
            async with limiter:
                with state_lock:
                    holder_count["n"] += 1
                    if holder_count["n"] == 5:
                        holders_started.set()
                await asyncio.to_thread(release_holders.wait, 5)

        async def _main() -> None:
            await asyncio.gather(*(_holder() for _ in range(5)))

        anyio.run(_main)

    thread_a = threading.Thread(target=_run_loop_a, daemon=True)
    thread_a.start()
    assert holders_started.wait(5), "loop A 未在 5 秒内占满 5 槽"

    pipeline_task = asyncio.create_task(
        asyncio.wait_for(process_document_ingestion(doc_id), 10)
    )
    await _wait_until(lambda: len(limiter._waiters) == 1)
    release_holders.set()

    outcome = await pipeline_task
    thread_a.join(5)
    assert not thread_a.is_alive()
    assert outcome == IngestionOutcome.completed
    assert calls["count"] == 1

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed

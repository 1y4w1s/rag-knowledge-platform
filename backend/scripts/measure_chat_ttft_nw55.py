#!/usr/bin/env python3
"""NW-55：库内对话 fast 首 token / TTFT 打点（只读测量，不改流式/检索逻辑）。

TTFT = ChatEngine.stream 起 → 首个 event==\"token\" 的墙钟（ms）。
收到首 token 后 break（不耗完整生成），skip_save 避免污染对话表。

用法（api 容器）：
  docker cp backend/scripts/measure_chat_ttft_nw55.py ruige-api:/tmp/measure_chat_ttft_nw55.py
  docker compose exec api env PYTHONPATH=/app python /tmp/measure_chat_ttft_nw55.py
"""
from __future__ import annotations

import asyncio
import os
import time
from uuid import UUID

from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.rag.cache import set_query_cache_enabled
from app.services.rag.engine import ChatEngine

ROUNDS = int(os.environ.get("NW55_ROUNDS", "10"))
WARMUP = int(os.environ.get("NW55_WARMUP", "2"))
QUERIES = [
    q.strip()
    for q in os.environ.get(
        "NW55_QUERIES",
        "公司年假怎么休,产品规格有哪些,框架合同违约责任,员工手册考勤,季度报告营收",
    ).split(",")
    if q.strip()
]


async def pick_kb_and_user() -> tuple[UUID, UUID, str]:
    raw_kb = os.environ.get("NW55_KB_ID")
    raw_user = os.environ.get("NW55_USER_ID")
    async with SessionLocal() as db:
        if raw_kb:
            kb_id = UUID(raw_kb)
            row = (
                await db.execute(
                    text(
                        """
                        SELECT kb.name,
                               COALESCE(kb.owner_user_id, (
                                   SELECT u.id FROM users u ORDER BY u.created_at LIMIT 1
                               )) AS user_id
                        FROM knowledge_bases kb
                        WHERE kb.id = :kb_id
                        """
                    ),
                    {"kb_id": kb_id},
                )
            ).one()
            user_id = UUID(raw_user) if raw_user else row.user_id
            return kb_id, user_id, row.name

        row = (
            await db.execute(
                text(
                    """
                    SELECT d.kb_id, kb.name,
                           COALESCE(kb.owner_user_id, (
                               SELECT u.id FROM users u ORDER BY u.created_at LIMIT 1
                           )) AS user_id,
                           COUNT(*) AS n_chunks
                    FROM documents d
                    JOIN document_chunks c ON c.document_id = d.id
                    JOIN knowledge_bases kb ON kb.id = d.kb_id
                    WHERE d.deleted_at IS NULL
                      AND d.status = 'completed'
                    GROUP BY d.kb_id, kb.name, kb.owner_user_id
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """
                )
            )
        ).one()
        user_id = UUID(raw_user) if raw_user else row.user_id
        return row.kb_id, user_id, row.name


async def one_ttft(db, *, kb_id: UUID, user_id: UUID, message: str) -> tuple[float, str]:
    """返回 (ttft_ms, outcome)。outcome: token | refuse_token | error | none。"""
    engine = ChatEngine(
        db,
        user_id=user_id,
        message=message,
        kb_id=kb_id,
        skip_save=True,
        thread_id=None,
    )
    t0 = time.perf_counter()
    outcome = "none"
    async for event in engine.stream():
        if event.get("event") != "token":
            continue
        text = (event.get("data") or {}).get("text") or ""
        if not text:
            continue
        ms = (time.perf_counter() - t0) * 1000
        # 拒答固定话术也走 token；主表仍计 TTFT（用户可见首字）
        outcome = "token"
        return ms, outcome
    return (time.perf_counter() - t0) * 1000, outcome


async def main() -> None:
    set_query_cache_enabled(False)
    kb_id, user_id, kb_name = await pick_kb_and_user()
    print(
        f"kb_id={kb_id} kb_name={kb_name!r} user_id={user_id} "
        f"warmup={WARMUP} rounds={ROUNDS} queries={QUERIES!r} "
        f"query_cache=off chat_provider={settings.chat_provider!r} "
        f"mode=fast skip_save=True"
    )
    times: list[float] = []
    async with SessionLocal() as db:
        total = WARMUP + ROUNDS
        for i in range(total):
            q = QUERIES[i % len(QUERIES)]
            ms, outcome = await one_ttft(db, kb_id=kb_id, user_id=user_id, message=q)
            tag = "warm" if i < WARMUP else "meas"
            print(f"  {tag} {i + 1:02d}: {ms:.1f} ms  outcome={outcome} q={q!r}")
            if i >= WARMUP and outcome == "token":
                times.append(ms)

    def pct(vals: list[float], p: float) -> float:
        s = sorted(vals)
        idx = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
        return s[idx]

    print("--- wall_clock TTFT (meas only, first event=token, cache off) ---")
    if not times:
        print("n=0 (no successful first-token samples)")
        return
    print(
        f"n={len(times)} p50={pct(times, 50):.1f} p95={pct(times, 95):.1f} "
        f"max={max(times):.1f} min={min(times):.1f}"
    )
    print(f"PRD_TARGET_MS=5000  measured_p95={pct(times, 95):.1f}")


if __name__ == "__main__":
    asyncio.run(main())

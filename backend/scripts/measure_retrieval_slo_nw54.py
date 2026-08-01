#!/usr/bin/env python3
"""NW-54：RAG 检索延迟打点（service 层，写 LatencyTracker，不改检索逻辑）。

用法（api 容器）：
  docker cp backend/scripts/measure_retrieval_slo_nw54.py ruige-api:/tmp/measure_retrieval_slo_nw54.py
  docker compose exec api env PYTHONPATH=/app python /tmp/measure_retrieval_slo_nw54.py
"""
from __future__ import annotations

import asyncio
import os
import time
from uuid import UUID

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.latency import all_tracker_stats, get_tracker
from app.services.rag.cache import set_query_cache_enabled
from app.services.rag.retrieval import retrieve_chunks

ROUNDS = int(os.environ.get("NW54_ROUNDS", "12"))
WARMUP = int(os.environ.get("NW54_WARMUP", "2"))
QUERIES = [
    q.strip()
    for q in os.environ.get(
        "NW54_QUERIES",
        "公司年假怎么休,产品规格有哪些,框架合同违约责任,员工手册考勤,季度报告营收",
    ).split(",")
    if q.strip()
]


async def pick_kb() -> UUID:
    raw = os.environ.get("NW54_KB_ID")
    if raw:
        return UUID(raw)
    async with SessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT d.kb_id
                    FROM documents d
                    JOIN document_chunks c ON c.document_id = d.id
                    WHERE d.deleted_at IS NULL
                      AND d.status = 'completed'
                    GROUP BY d.kb_id
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """
                )
            )
        ).one()
        return row[0]


async def main() -> None:
    # SLO 量冷路径：关掉进程内 query cache（否则第 2 轮起 ~0ms）
    set_query_cache_enabled(False)
    kb_id = await pick_kb()
    print(
        f"kb_id={kb_id} warmup={WARMUP} rounds={ROUNDS} "
        f"queries={QUERIES!r} query_cache=off"
    )
    times: list[float] = []
    n_chunks = 0
    async with SessionLocal() as db:
        total = WARMUP + ROUNDS
        for i in range(total):
            q = QUERIES[i % len(QUERIES)]
            t0 = time.perf_counter()
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=q, top_k=5)
            ms = (time.perf_counter() - t0) * 1000
            get_tracker("retrieval.retrieval_e2e").record(ms)
            n_chunks = len(chunks) if chunks else 0
            tag = "warm" if i < WARMUP else "meas"
            print(f"  {tag} {i + 1:02d}: {ms:.1f} ms  chunks={n_chunks} q={q!r}")
            if i >= WARMUP:
                times.append(ms)

    def pct(vals: list[float], p: float) -> float:
        s = sorted(vals)
        idx = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
        return s[idx]

    print("--- wall_clock retrieval_e2e (meas only, cache off) ---")
    print(
        f"n={len(times)} p50={pct(times, 50):.1f} p95={pct(times, 95):.1f} "
        f"max={max(times):.1f} last_chunks={n_chunks}"
    )
    print("--- LatencyTracker (min_count=5) ---")
    stats = all_tracker_stats(min_count=5)
    for name in sorted(stats):
        st = stats[name]
        if "p95" not in st:
            print(f"{name}: count={st.get('count')}")
            continue
        print(
            f"{name}: count={st['count']} p50={st['p50']} p95={st['p95']} p99={st.get('p99')}"
        )


if __name__ == "__main__":
    asyncio.run(main())

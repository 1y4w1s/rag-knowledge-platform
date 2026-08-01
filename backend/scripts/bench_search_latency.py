#!/usr/bin/env python3
"""I2 / Eval-Ops M2-search：跨库搜 service 层延迟基线（绕过 HTTP 限流）。

用法（在 api 容器内）：
  docker cp backend/scripts/bench_search_latency.py ruige-api:/tmp/bench_search_latency.py
  docker compose exec api env PYTHONPATH=/app python /tmp/bench_search_latency.py

可选环境变量：
  I2_OWNER_USER_ID  指定个人空间主人（默认取 chunk 最多的 CRAG-Full-Auto）
  I2_Q_FILENAME     默认 crag
  I2_Q_CONTENT      默认 company
  I2_ROUNDS         默认 20
"""
from __future__ import annotations

import asyncio
import os
import statistics
import time
from uuid import UUID

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.rag.cjk import segment_cjk
from app.services.search.content import search_documents_by_content
from app.services.search.documents import search_documents_by_filename
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

ROUNDS = int(os.environ.get("I2_ROUNDS", "20"))
Q_FILENAME = os.environ.get("I2_Q_FILENAME", "crag")
Q_CONTENT = os.environ.get("I2_Q_CONTENT", "company")


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
    return s[idx]


async def pick_owner() -> UUID:
    raw = os.environ.get("I2_OWNER_USER_ID")
    if raw:
        return UUID(raw)
    async with SessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT kb.owner_user_id
                    FROM knowledge_bases kb
                    WHERE kb.name = 'CRAG-Full-Auto' AND kb.owner_user_id IS NOT NULL
                    ORDER BY (
                      SELECT COUNT(*) FROM documents d
                      JOIN document_chunks c ON c.document_id = d.id
                      WHERE d.kb_id = kb.id
                    ) DESC
                    LIMIT 1
                    """
                )
            )
        ).one()
        return row[0]


async def time_service(owner_id: UUID) -> None:
    scope = WorkspaceScope(
        kind=WorkspaceKind.personal, user_id=owner_id, org_id=None
    )
    async with SessionLocal() as db:
        print(f"owner_id={owner_id} workspace=personal")
        for mode, q, fn in (
            ("filename", Q_FILENAME, search_documents_by_filename),
            ("content", Q_CONTENT, search_documents_by_content),
        ):
            times: list[float] = []
            total = items_n = 0
            for _ in range(ROUNDS):
                t0 = time.perf_counter()
                resp = await fn(db, scope, q, 20, offset=0)
                times.append((time.perf_counter() - t0) * 1000)
                total = resp.total
                items_n = len(resp.items)
            print(
                f"{mode} q={q!r}: n={len(times)} "
                f"p50={pct(times, 50):.1f}ms p95={pct(times, 95):.1f}ms "
                f"avg={statistics.mean(times):.1f}ms "
                f"hit_total={total} items={items_n}"
            )


async def explain(q: str) -> None:
    seg = segment_cjk(q)
    async with SessionLocal() as db:
        print(f"\n=== EXPLAIN @@ only q={q!r} seg={seg!r} ===")
        r = await db.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT c.id FROM document_chunks c
                WHERE c.content_tsv @@ plainto_tsquery('simple', :seg)
                LIMIT 50
                """
            ),
            {"seg": seg},
        )
        for row in r.fetchall():
            print(row[0])

        print(f"\n=== EXPLAIN @@ OR ILIKE q={q!r} ===")
        r = await db.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT c.id FROM document_chunks c
                WHERE c.chunk_kind <> 'parent'
                  AND (
                    c.content_tsv @@ plainto_tsquery('simple', :seg)
                    OR c.content ILIKE :ilike ESCAPE '\\'
                  )
                LIMIT 50
                """
            ),
            {"seg": seg, "ilike": f"%{q}%"},
        )
        for row in r.fetchall():
            print(row[0])

        print("\n=== Index defs (tsv) ===")
        r = await db.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename='document_chunks' AND indexname LIKE '%tsv%'"
            )
        )
        for row in r.fetchall():
            print(f"{row[0]}: {row[1]}")

        print("\n=== EXPLAIN @@ only enable_seqscan=off ===")
        await db.execute(text("SET LOCAL enable_seqscan = off"))
        r = await db.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT c.id FROM document_chunks c
                WHERE c.content_tsv @@ plainto_tsquery('simple', :seg)
                LIMIT 50
                """
            ),
            {"seg": seg},
        )
        for row in r.fetchall():
            print(row[0])


async def main() -> None:
    owner_id = await pick_owner()
    print(f"Q_FILENAME={Q_FILENAME} Q_CONTENT={Q_CONTENT} ROUNDS={ROUNDS}")
    await time_service(owner_id)
    await explain(Q_CONTENT)


if __name__ == "__main__":
    asyncio.run(main())

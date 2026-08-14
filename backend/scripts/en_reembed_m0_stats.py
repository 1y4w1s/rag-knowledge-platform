"""M0 read-only stats: English-track re-embed scope estimation.

This script is strictly read-only (SELECT only). It reports:
1. Full-scope status (same fields as GET /api/v1/internal/re-embed/status).
2. Document-level English-leaning bounds:
   - lower bound: distinct docs with at least one searchable `embedding_en`.
   - upper bound: docs re-judged with the same `is_mostly_english` on a
     chunk-content reconstruction of the full text (the original parsed full
     text is not persisted, so this is an approximation and is labeled as such).
   - re-embed scope: searchable chunks inside judged-English docs missing
     `embedding_en`, plus estimated batches (25/batch) and inference time.
3. Per-KB pilot breakdowns for selected KB ids.

Usage (from backend/):
    python scripts/en_reembed_m0_stats.py
    python scripts/en_reembed_m0_stats.py --kb <uuid> [--kb <uuid> ...]
    python scripts/en_reembed_m0_stats.py --json
    python scripts/en_reembed_m0_stats.py --no-full-docs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

# Allow invocation from repo root or backend/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Measured on the running API container (2026-08-11): warm bge_en inference
# was 0.062-0.068s for one 25-text batch after a ~0.7s one-time model load.
MEASURED_WARM_BATCH_SECONDS = 0.07
MEASURED_MODEL_LOAD_SECONDS = 0.7
BATCH_SIZE = 25


def _judge_doc_rows(rows) -> dict[str, int]:
    """Count English-leaning docs by re-judging reconstructed full text."""
    from app.services.rag.embed_route import is_mostly_english

    docs_total = 0
    docs_with_en = 0
    docs_judged_english = 0
    docs_en_and_english = 0
    docs_en_not_english = 0
    docs_english_no_en = 0
    english_doc_chunks = 0
    english_doc_gap_chunks = 0
    all_searchable_chunks = 0

    for row in rows:
        m = row._mapping
        docs_total += 1
        searchable = int(m["searchable_chunks"] or 0)
        en = int(m["en_chunks"] or 0)
        has_en = en > 0
        all_searchable_chunks += searchable
        if has_en:
            docs_with_en += 1
        judged_english = is_mostly_english(m["full_text"] or "")
        if judged_english:
            docs_judged_english += 1
            english_doc_chunks += searchable
            english_doc_gap_chunks += searchable - en
            if has_en:
                docs_en_and_english += 1
            else:
                docs_english_no_en += 1
        elif has_en:
            docs_en_not_english += 1

    return {
        "docs_searchable": docs_total,
        "docs_with_en_chunk": docs_with_en,
        "docs_judged_english": docs_judged_english,
        "docs_en_and_english": docs_en_and_english,
        "docs_en_not_english": docs_en_not_english,
        "docs_english_no_en": docs_english_no_en,
        "english_doc_chunks": english_doc_chunks,
        "english_doc_gap_chunks": english_doc_gap_chunks,
        "all_searchable_chunks": all_searchable_chunks,
    }


async def _load_doc_stats(db, kb_id: UUID | None = None) -> list:
    """Reconstruct per-doc full text from non-parent chunk contents (read-only)."""
    stmt = """
        SELECT
            d.id AS document_id,
            COALESCE(string_agg(c.content, ' ' ORDER BY c.chunk_index), '') AS full_text,
            count(*) AS searchable_chunks,
            count(*) FILTER (WHERE c.embedding_en IS NOT NULL) AS en_chunks
        FROM documents d
        JOIN document_chunks c ON c.document_id = d.id
        WHERE d.deleted_at IS NULL AND c.chunk_kind != 'parent'
    """
    params: dict[str, object] = {}
    if kb_id is not None:
        stmt += " AND d.kb_id = :kb_id"
        params["kb_id"] = str(kb_id)
    stmt += " GROUP BY d.id"
    result = await db.execute(text(stmt), params)
    return list(result.all())


def _coverage_ratio(searchable: int, en: int) -> float:
    return round(en / searchable, 4) if searchable else 0.0


def _batch_estimate(gap_chunks: int) -> dict[str, object]:
    batches = math.ceil(gap_chunks / BATCH_SIZE) if gap_chunks > 0 else 0
    inference_seconds = round(
        batches * MEASURED_WARM_BATCH_SECONDS + MEASURED_MODEL_LOAD_SECONDS, 1
    )
    return {
        "batches_25": batches,
        "measured_inference_seconds": inference_seconds,
        "note": (
            "inference-only estimate from container benchmark; "
            "DB fetch/commit and HNSW write amplification are not included"
        ),
    }


async def _kb_summary(db, kb_id: UUID, doc_stats: dict[str, int]) -> dict[str, object]:
    from app.services.ingestion.re_embed import count_embedding_en_coverage

    cov = await count_embedding_en_coverage(kb_id=kb_id)
    kb_meta = (
        await db.execute(
            text("SELECT name, description FROM knowledge_bases WHERE id = :id"),
            {"id": str(kb_id)},
        )
    ).first()
    return {
        "kb_id": str(kb_id),
        "name": kb_meta._mapping["name"] if kb_meta else None,
        "searchable_chunks": int(cov["searchable_chunks"]),
        "embedding_en_chunks": int(cov["embedding_en_chunks"]),
        "embedding_en_coverage": float(cov["embedding_en_coverage"]),
        "doc_stats": doc_stats,
        "estimate": _batch_estimate(int(doc_stats["english_doc_gap_chunks"])),
    }


async def _run(*, kb_ids: list[UUID], full_docs: bool, as_json: bool) -> int:
    from app.core.database import SessionLocal
    from app.services.ingestion.re_embed import (
        count_embedding_en_coverage,
        count_stale_chunks,
    )

    payload: dict[str, object] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "batch_size": BATCH_SIZE,
        "measured_warm_batch_seconds": MEASURED_WARM_BATCH_SECONDS,
        "measured_model_load_seconds": MEASURED_MODEL_LOAD_SECONDS,
    }

    async with SessionLocal() as db:
        stale = await count_stale_chunks()
        cov = await count_embedding_en_coverage()
        payload["full_scope_status"] = {
            "stale_chunks": stale,
            **cov,
        }

        if full_docs:
            t0 = time.perf_counter()
            rows = await _load_doc_stats(db)
            doc_stats = _judge_doc_rows(rows)
            payload["full_scope_docs"] = {
                **doc_stats,
                "reconstruction_seconds": round(time.perf_counter() - t0, 1),
                "reconstruction_note": (
                    "full text reconstructed from non-parent chunk contents; "
                    "original parsed text is not persisted"
                ),
                "estimate": _batch_estimate(
                    int(doc_stats["english_doc_gap_chunks"])
                ),
            }
            del rows

        if kb_ids:
            payload["pilot_kbs"] = [
                await _kb_summary(db, kid, _judge_doc_rows(await _load_doc_stats(db, kid)))
                for kid in kb_ids
            ]

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        status = payload["full_scope_status"]
        print(
            "FULL SCOPE STATUS: "
            f"stale={status['stale_chunks']} "
            f"searchable={status['searchable_chunks']} "
            f"en={status['embedding_en_chunks']} "
            f"coverage={status['embedding_en_coverage']}"
        )
        docs = payload.get("full_scope_docs")
        if docs:
            est = docs["estimate"]
            print(
                "FULL SCOPE DOCS: "
                f"docs_searchable={docs['docs_searchable']} "
                f"docs_with_en={docs['docs_with_en_chunk']} (lower bound) "
                f"docs_judged_english={docs['docs_judged_english']} (upper bound) "
                f"docs_english_no_en={docs['docs_english_no_en']} "
                f"english_doc_chunks={docs['english_doc_chunks']} "
                f"english_doc_gap_chunks={docs['english_doc_gap_chunks']} "
                f"batches_25={est['batches_25']} "
                f"inference_s={est['measured_inference_seconds']}"
            )
            print(f"  reconstruction took {docs['reconstruction_seconds']}s")
        for kb in payload.get("pilot_kbs", []):
            ds = kb["doc_stats"]
            est = kb["estimate"]
            print(
                f"PILOT KB {kb['name']} ({kb['kb_id']}): "
                f"searchable={kb['searchable_chunks']} "
                f"en={kb['embedding_en_chunks']} "
                f"coverage={kb['embedding_en_coverage']} "
                f"docs_english={ds['docs_judged_english']} "
                f"english_gap_chunks={ds['english_doc_gap_chunks']} "
                f"batches_25={est['batches_25']} "
                f"inference_s={est['measured_inference_seconds']}"
            )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M0 read-only English re-embed scope statistics"
    )
    parser.add_argument("--kb", action="append", type=UUID, help="Pilot KB id")
    parser.add_argument(
        "--no-full-docs",
        action="store_true",
        help="Skip the heavy full-scope document re-judge",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                kb_ids=args.kb or [],
                full_docs=not args.no_full_docs,
                as_json=args.json,
            )
        )
    )


if __name__ == "__main__":
    main()

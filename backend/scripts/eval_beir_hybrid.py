#!/usr/bin/env python
"""BEIR hybrid retrieval A/B: production hybrid chain vs BM25 baseline.

Usage:
    python scripts/eval_beir_hybrid.py --dataset nfcorpus --sample 20 --top-k 3
    python scripts/eval_beir_hybrid.py --dataset nfcorpus --top-k 3

Flow:
    1. Load BEIR corpus/queries/qrels from local cache
    2. Ingest corpus into a temporary KB (Document + DocumentChunk +
       embedding / embedding_en / content_tsv, same as production pipeline)
    3. Run queries through `retrieve_chunks` (vector + FTS + RRF)
    4. Score with RagasRetrievalScorer (DeepSeek judge)
    5. Compare with BM25 baseline stored in docs/benchmark-public-report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eval_beir_hybrid")

EMBED_BATCH = 64

# BM25 baseline from docs/benchmark-public-report.md (RAGAS, >0 valid average)
BM25_BASELINE = {
    "nfcorpus": {"precision": 0.833, "recall": 0.549, "queries": 323},
    "fiqa": {"precision": 0.831, "recall": 0.481, "queries": 510},
}


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\"'")
        if key and not os.environ.get(key):
            os.environ[key] = val


async def _get_or_create_kb(db, *, name: str, user_id) -> object:
    from sqlalchemy import select
    from app.models.knowledge_base import KnowledgeBase

    stmt = select(KnowledgeBase).where(
        KnowledgeBase.name == name,
        KnowledgeBase.owner_user_id == user_id,
    )
    kb = (await db.execute(stmt)).scalar_one_or_none()
    if kb is not None:
        return kb
    kb = KnowledgeBase(
        id=uuid4(),
        name=name,
        description="BEIR hybrid retrieval A/B temporary KB",
        owner_user_id=user_id,
    )
    db.add(kb)
    await db.flush()
    await db.commit()
    logger.info("created temp KB %s (%s)", name, kb.id)
    return kb


async def _kb_chunk_count(db, kb_id) -> int:
    from sqlalchemy import func, select
    from app.models.document_chunk import DocumentChunk

    stmt = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.kb_id == kb_id)
    )
    return int((await db.execute(stmt)).scalar_one())


async def _ingest_corpus(db, kb_id, user_id, corpus: dict) -> int:
    from sqlalchemy import text
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.enums import DocumentStatus, DocumentVisibility
    from app.services.ingestion.embedder import (
        current_embedding_model,
        embed_texts,
        try_embed_texts,
    )
    from app.services.rag.cjk import segment_cjk

    rows: list[tuple[str, str]] = []
    for doc_id, item in corpus.items():
        content = item["text"]  # title + text, same as BEIR loader
        doc = Document(
            id=uuid4(),
            kb_id=kb_id,
            filename=doc_id,
            file_type="txt",
            file_size=len(content.encode("utf-8")),
            storage_path="",
            status=DocumentStatus.completed,
            uploaded_by=user_id,
            visibility=DocumentVisibility.everyone,
            chunk_count=1,
            current_version=1,
        )
        db.add(doc)
        await db.flush()
        rows.append((doc.id, content))

    total = 0
    embed_model = current_embedding_model()
    for start in range(0, len(rows), EMBED_BATCH):
        batch = rows[start : start + EMBED_BATCH]
        texts = [r[1] for r in batch]
        vectors = await try_embed_texts(texts)
        vectors_en = None
        try:
            vectors_en = await embed_texts(texts, provider="bge_en")
        except Exception as exc:
            logger.warning("bge_en embedding failed for batch: %s", exc)

        for idx, (doc_uuid, content) in enumerate(batch):
            vec = vectors[idx] if vectors else None
            vec_en = vectors_en[idx] if vectors_en else None
            chunk = DocumentChunk(
                id=uuid4(),
                document_id=doc_uuid,
                kb_id=kb_id,
                chunk_index=0,
                content=content,
                chunk_kind="text",
                embedding_model=embed_model if vec is not None else None,
                embedding=vec,
                embedding_en=vec_en,
            )
            db.add(chunk)
            await db.flush()
            tsv_source = segment_cjk(content)
            await db.execute(
                text(
                    "UPDATE document_chunks SET content_tsv = "
                    "to_tsvector('simple', :tsv_source) WHERE id = :chunk_id"
                ),
                {"tsv_source": tsv_source, "chunk_id": chunk.id},
            )
            total += 1

        await db.commit()
        logger.info("ingested %d/%d chunks", total, len(rows))

    return total


def _extract_from_details(details: list[dict], key: str) -> float:
    for d in details:
        if key in d:
            return float(d[key])
    return 0.0


def _load_checkpoint(path: Path) -> tuple[list[dict], set[str]]:
    if not path.exists():
        return [], set()
    results: list[dict] = []
    done: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = rec.get("case_id")
        if case_id is None:
            continue
        done.add(str(case_id))
        results.append(rec)
    logger.info("checkpoint loaded: %d done from %s", len(results), path)
    return results, done


def _append_checkpoint(path: Path, result: dict, lock: Lock) -> None:
    with lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
            fh.flush()


async def _prepare_queries(db, kb_id, queries, top_k) -> list[dict]:
    from app.services.rag.retrieval import retrieve_chunks
    from tests.benchmark.scorers.base import Expect, RetrievedChunk

    prepared: list[dict] = []
    for i, q in enumerate(queries, 1):
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_id,
            query=q.query,
            top_k=top_k,
        )
        expect = Expect(
            content_contains=q.expects[0].get("content_contains", "") if q.expects else "",
            answer=q.answer or "",
        )
        prepared.append(
            {
                "case_id": q.case_id,
                "query": q.query,
                "chunk_ids": [str(c.chunk_id) for c in chunks[:top_k]],
                "chunks": [RetrievedChunk.from_raw(c) for c in chunks[:top_k]],
                "expect": expect,
            }
        )
        if i % 10 == 0:
            logger.info("retrieved %d/%d queries", i, len(queries))
    return prepared


def _score_prepared(scorer, item: dict, top_k: int) -> dict:
    score = scorer.score_retrieval(item["query"], item["chunks"], item["expect"], top_k)
    precision = _extract_from_details(score.match_details, "ragas_context_precision")
    recall = _extract_from_details(score.match_details, "ragas_context_recall")
    error = next((d.get("error") for d in score.match_details if "error" in d), None)
    return {
        "case_id": item["case_id"],
        "query": item["query"],
        "chunk_ids": item["chunk_ids"],
        "ragas_context_precision": precision,
        "ragas_context_recall": recall,
        "error": error,
    }


def _score_prepared_batch(
    scorer,
    prepared: list[dict],
    top_k: int,
    checkpoint_path: Path,
    checkpoint_lock: Lock,
    concurrency: int,
) -> list[dict]:
    results: list[dict] = []
    if concurrency <= 1:
        for i, item in enumerate(prepared, 1):
            result = _score_prepared(scorer, item, top_k)
            _append_checkpoint(checkpoint_path, result, checkpoint_lock)
            results.append(result)
            if i % 10 == 0:
                logger.info("scored %d/%d queries", i, len(prepared))
        return results

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_to_item = {
            pool.submit(_score_prepared, scorer, item, top_k): item
            for item in prepared
        }
        completed = 0
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
            except Exception as exc:  # keep long runs alive if a single judge call fails hard
                logger.warning("scoring failed for %s: %s", item["case_id"], exc)
                result = {
                    "case_id": item["case_id"],
                    "query": item["query"],
                    "chunk_ids": item["chunk_ids"],
                    "ragas_context_precision": 0.0,
                    "ragas_context_recall": 0.0,
                    "error": f"scorer_exception:{exc}",
                }
            _append_checkpoint(checkpoint_path, result, checkpoint_lock)
            results.append(result)
            completed += 1
            if completed % 10 == 0:
                logger.info("scored %d/%d queries", completed, len(prepared))
    return results


async def _run_queries(db, kb_id, queries, top_k, scorer, debug=False, loader=None) -> list[dict]:
    from sqlalchemy import select
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.services.rag.retrieval import retrieve_chunks
    from tests.benchmark.scorers.base import Expect, RetrievedChunk

    results: list[dict] = []
    qrels = loader._load_qrels() if debug and loader is not None else {}
    for i, q in enumerate(queries, 1):
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_id,
            query=q.query,
            top_k=top_k,
        )
        if debug:
            chunk_uuids = [c.chunk_id for c in chunks[:top_k]]
            if chunk_uuids:
                stmt = (
                    select(Document.filename)
                    .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                    .where(DocumentChunk.id.in_(chunk_uuids))
                )
                filenames = [r[0] for r in (await db.execute(stmt)).all()]
            else:
                filenames = []
            relevant = set(qrels.get(q.case_id, []))
            overlap = [f for f in filenames if f in relevant]
            logger.info(
                "debug case=%s query=%r top_k=%d overlap=%d/%d",
                q.case_id, q.query[:80], len(filenames), len(overlap), len(relevant),
            )
            for f in filenames:
                logger.info("  chunk=%s relevant=%s", f, f in relevant)
            continue

        expect = Expect(
            content_contains=q.expects[0].get("content_contains", "") if q.expects else "",
            answer=q.answer or "",
        )
        chunks_for_scorer = [RetrievedChunk.from_raw(c) for c in chunks[:top_k]]
        score = scorer.score_retrieval(q.query, chunks_for_scorer, expect, top_k)
        precision = _extract_from_details(score.match_details, "ragas_context_precision")
        recall = _extract_from_details(score.match_details, "ragas_context_recall")
        results.append(
            {
                "case_id": q.case_id,
                "query": q.query,
                "chunk_ids": [str(c.chunk_id) for c in chunks[:top_k]],
                "ragas_context_precision": precision,
                "ragas_context_recall": recall,
            }
        )
        if i % 10 == 0:
            logger.info("scored %d/%d queries", i, len(queries))
    return results


def _aggregate(results: list[dict]) -> dict:
    p = [r["ragas_context_precision"] for r in results if r["ragas_context_precision"] > 0]
    r = [r["ragas_context_recall"] for r in results if r["ragas_context_recall"] > 0]
    error_total = sum(1 for res in results if res.get("error"))
    zero_total = sum(
        1
        for res in results
        if not res.get("error")
        and res.get("ragas_context_precision", 0) <= 0
        and res.get("ragas_context_recall", 0) <= 0
    )
    return {
        "total": len(results),
        "precision_valid": len(p),
        "recall_valid": len(r),
        "context_precision": round(sum(p) / len(p), 4) if p else 0.0,
        "context_recall": round(sum(r) / len(r), 4) if r else 0.0,
        "error_total": error_total,
        "zero_total": zero_total,
    }


def _write_report(args, aggregate: dict, baseline: dict, elapsed: float) -> dict:
    from tests.benchmark.loaders import get_loader

    loader = get_loader(f"beir/{args.dataset}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": f"beir/{args.dataset}",
        "display_name": loader.meta.display_name,
        "config": {
            "sample": args.sample,
            "top_k": args.top_k,
            "engine": "production_hybrid",
            "scorer": "ragas",
            "judge": "deepseek-chat",
        },
        "bm25_baseline": baseline,
        "hybrid": aggregate,
        "elapsed_seconds": round(elapsed, 1),
    }
    json_path = out_dir / f"beir_hybrid_{args.dataset}_{ts}.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        f"# BEIR {args.dataset} Hybrid vs BM25 (RAGAS)",
        "",
        f"> 生成时间：{payload['generated_at']} · top_k={args.top_k}",
        "",
        "| 引擎 | 查询数 | 有效 P/R | ContextPrecision | ContextRecall |",
        "|------|--------|----------|-----------------|---------------|",
        (
            f"| BM25 | {baseline['queries']} | - | "
            f"{baseline['precision']:.3f} | {baseline['recall']:.3f} |"
        ),
        (
            f"| Hybrid | {aggregate['total']} | "
            f"{aggregate['precision_valid']}/{aggregate['recall_valid']} | "
            f"{aggregate['context_precision']:.3f} | "
            f"{aggregate['context_recall']:.3f} |"
        ),
        "",
        f"耗时：{payload['elapsed_seconds']:.0f}s",
        "",
    ]
    md_path = out_dir / f"beir_hybrid_{args.dataset}_{ts}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"json": json_path, "md": md_path}


async def main_async(args) -> None:
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.services.rag.cache import set_query_cache_enabled
    from tests.benchmark.loaders import get_loader
    from tests.benchmark.scorers import RagasRetrievalScorer

    set_query_cache_enabled(False)
    loader = get_loader(f"beir/{args.dataset}")
    queries = await loader.load()
    corpus = loader._load_corpus()
    logger.info(
        "dataset=%s queries=%d corpus=%d top_k=%d",
        args.dataset, len(queries), len(corpus), args.top_k,
    )

    if args.sample and args.sample < len(queries):
        queries = loader.sample(queries, args.sample)
        logger.info("sampled %d queries", len(queries))

    async with SessionLocal() as db:
        user = (await db.execute(select(User).order_by(User.created_at).limit(1))).scalar_one_or_none()
        if user is None:
            raise RuntimeError("users table is empty; register a user first")

        kb_name = args.kb_name or f"beir-{args.dataset}-bench"
        kb = await _get_or_create_kb(db, name=kb_name, user_id=user.id)
        existing = await _kb_chunk_count(db, kb.id)
        if existing == 0 or args.force_reingest:
            if existing:
                logger.warning("re-ingesting KB %s (existing=%d)", kb.id, existing)
            t0 = time.perf_counter()
            ingested = await _ingest_corpus(db, kb.id, user.id, corpus)
            logger.info("ingestion done: %d chunks in %.1fs", ingested, time.perf_counter() - t0)
        else:
            logger.info("reuse KB %s with %d chunks", kb.id, existing)

        scorer = RagasRetrievalScorer()
        if args.debug:
            t0 = time.perf_counter()
            await _run_queries(db, kb.id, queries, args.top_k, scorer, debug=True, loader=loader)
            logger.info("debug retrieval done in %.1fs", time.perf_counter() - t0)
            return

        checkpoint_path = Path(args.checkpoint) if args.checkpoint else (
            Path(args.out_dir) / f"beir_hybrid_{args.dataset}_checkpoint.jsonl"
        )
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_lock = Lock()
        if args.resume:
            results, done_cases = _load_checkpoint(checkpoint_path)
            pending = [q for q in queries if q.case_id not in done_cases]
            if pending:
                logger.info("resume mode: skip %d done, score %d pending", len(done_cases), len(pending))
        else:
            checkpoint_path.write_text("", encoding="utf-8")
            results, done_cases, pending = [], set(), list(queries)

        t0 = time.perf_counter()
        if pending:
            prepared = await _prepare_queries(db, kb.id, pending, args.top_k)
            logger.info("prepared %d queries in %.1fs", len(prepared), time.perf_counter() - t0)
            t0 = time.perf_counter()
            new_results = _score_prepared_batch(
                scorer,
                prepared,
                args.top_k,
                checkpoint_path,
                checkpoint_lock,
                args.concurrency,
            )
            results.extend(new_results)
            elapsed = time.perf_counter() - t0
        else:
            logger.info("no pending queries, using checkpoint results only")
            elapsed = 0.0

        aggregate = _aggregate(results)
        baseline = {
            "precision": args.bm25_precision or BM25_BASELINE[args.dataset]["precision"],
            "recall": args.bm25_recall or BM25_BASELINE[args.dataset]["recall"],
            "queries": BM25_BASELINE[args.dataset]["queries"],
        }
        logger.info(
            "hybrid: precision=%.4f recall=%.4f (valid %d/%d) elapsed=%.0fs",
            aggregate["context_precision"], aggregate["context_recall"],
            aggregate["precision_valid"], aggregate["recall_valid"], elapsed,
        )
        paths = _write_report(args, aggregate, baseline, elapsed)
        logger.info("report saved: %s / %s", paths["json"], paths["md"])

        if args.cleanup:
            from sqlalchemy import delete
            from app.models.document_chunk import DocumentChunk
            from app.models.document import Document
            from app.models.knowledge_base import KnowledgeBase

            await db.execute(delete(DocumentChunk).where(DocumentChunk.kb_id == kb.id))
            await db.execute(delete(Document).where(Document.kb_id == kb.id))
            await db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb.id))
            await db.commit()
            logger.info("cleaned up temp KB %s", kb.id)


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="BEIR hybrid retrieval A/B")
    parser.add_argument("--dataset", choices=["nfcorpus", "fiqa"], default="nfcorpus")
    parser.add_argument("--sample", type=int, default=None, help="query sample size")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--kb-name", type=str, default=None)
    parser.add_argument("--force-reingest", action="store_true")
    parser.add_argument("--cleanup", action="store_true", help="delete temp KB after eval")
    parser.add_argument("--bm25-precision", type=float, default=None)
    parser.add_argument("--bm25-recall", type=float, default=None)
    parser.add_argument("--out-dir", type=str, default="benchmark_results")
    parser.add_argument("--checkpoint", type=str, default=None, help="jsonl checkpoint path (default: benchmark_results/beir_hybrid_<dataset>_checkpoint.jsonl)")
    parser.add_argument("--resume", action="store_true", help="resume from existing checkpoint and skip scored case_ids")
    parser.add_argument("--concurrency", type=int, default=1, help="parallel DeepSeek judge workers (default 1)")
    parser.add_argument("--debug", action="store_true", help="print retrieval hits without judge scoring")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

"""Enterprise retrieval benchmark entity-extraction equivalence helpers (W8 CI proof).

Proves ``skip_entity_extract`` does not alter retrieval corpus or gate observables.
Uses real BGE embedding — never ``apply_benchmark_settings()`` (that switches to mock).
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.eval.golden_benchmark.corpus import collect_corpus_fingerprint
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.entity import Entity, EntityMention, Relation
from app.models.enums import DocumentStatus
from app.services.rag.retrieval import retrieve_chunks
from tests.golden_qa_loader import GoldenQACase, hit_at_k, reciprocal_rank

TOP_K = 5  # align with scripts/run_benchmark.py Enterprise gate
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
ENTERPRISE_QA_PATH = FIXTURES / "enterprise_qa.json"

# Frozen stratified subset (L1–L4 + bilingual/challenge); FULL via RAG_ENTERPRISE_EQ_FULL=1
FROZEN_STRATIFIED_CASE_IDS: tuple[str, ...] = (
    "ENT-001",
    "ENT-002",
    "ENT-004",
    "ENT-007",
    "ENT-009",
    "ENT-010",
    "ENT-012",
    "ENT-013",
    "ENT-014",
    "ENT-023",
    "ENT-024",
    "ENT-026",
    "ENT-039",
    "ENT-045",
    "ENT-052",
    "ENT-062",
    "ENT-063",
    "ENT-068",
    "ENT-075",
    "ENT-084",
    "ENT-091",
    "ENT-095",
    "ENT-105",
    "ENT-108",
)

SCORE_ABS_TOL = 1e-9
SCORE_REL_TOL = 1e-6


@dataclass(frozen=True, slots=True)
class SkipEntityPatch:
    """Process-local toggle for skip_entity_extract only."""

    previous: bool

    def restore(self) -> None:
        settings.skip_entity_extract = self.previous


@contextmanager
def patch_skip_entity_extract(skip: bool) -> Iterator[SkipEntityPatch]:
    """Toggle ``skip_entity_extract`` without touching embedding or other flags."""
    saved = settings.skip_entity_extract
    settings.skip_entity_extract = skip
    try:
        yield SkipEntityPatch(previous=saved)
    finally:
        settings.skip_entity_extract = saved


def corpora_cross_kb_equivalent(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    """Multi-document KB equivalence: compare chunk multiset, not document_id order."""
    keys = ("chunk_count", "embedding_row_count", "embedding_en_row_count")
    if not all(pre.get(k) == post.get(k) for k in keys):
        return False
    return sorted(pre.get("chunk_content_hashes") or []) == sorted(
        post.get("chunk_content_hashes") or []
    )


def sorted_corpus_fingerprint_sha256(corpus: dict[str, Any]) -> str:
    hashes = sorted(corpus.get("chunk_content_hashes") or [])
    return hashlib.sha256(
        json.dumps(hashes, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def git_base_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def fixture_hashes() -> dict[str, str]:
    paths = sorted(FIXTURES.glob("acme_*.md")) + [ENTERPRISE_QA_PATH]
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
        if p.exists()
    }


def load_enterprise_retrieval_cases(*, full: bool) -> tuple[list[dict[str, Any]], int]:
    data = json.loads(ENTERPRISE_QA_PATH.read_text(encoding="utf-8"))
    hit_k = int(data.get("hit_k", 3))
    cases = [c for c in data["cases"] if not c.get("expect_rejection")]
    if not full:
        allowed = set(FROZEN_STRATIFIED_CASE_IDS)
        cases = [c for c in cases if c["case_id"] in allowed]
    return cases, hit_k


def enterprise_case_to_golden(raw: dict[str, Any]) -> GoldenQACase:
    expect = raw.get("expect") or {}
    return GoldenQACase(
        case_id=str(raw["case_id"]),
        query=str(raw["query"]),
        source=raw.get("source", "md"),
        section_title=expect.get("section_title"),
        heading_path_contains=expect.get("heading_path_contains"),
        content_contains=expect.get("content_contains"),
        page_number=expect.get("page_number"),
        tags=tuple(str(t) for t in raw.get("tags") or []),
    )


async def ingest_enterprise_document(
    *,
    kb_id: UUID,
    user_id: UUID,
    filename: str,
    upload_dir: Path,
) -> UUID:
    source = FIXTURES / filename
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / filename
    storage_path.write_bytes(source.read_bytes())

    from app.core.database import SessionLocal
    from app.services.ingestion.pipeline import process_document_ingestion

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="md",
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)
    return doc_id


async def ingest_enterprise_corpus(
    *,
    kb_id: UUID,
    user_id: UUID,
    upload_dir: Path,
    skip_entity_extract: bool,
    entity_extract_override: Callable[..., Awaitable[None]] | None = None,
) -> list[str]:
    """Ingest all acme_*.md fixtures; returns filenames ingested."""
    from unittest.mock import patch

    doc_files = sorted(p.name for p in FIXTURES.glob("acme_*.md"))
    with patch_skip_entity_extract(skip_entity_extract):
        if entity_extract_override is not None:
            with patch(
                "app.services.ingestion.pipeline.extract_entities_for_document",
                new=entity_extract_override,
            ):
                for name in doc_files:
                    await ingest_enterprise_document(
                        kb_id=kb_id,
                        user_id=user_id,
                        filename=name,
                        upload_dir=upload_dir,
                    )
        else:
            for name in doc_files:
                await ingest_enterprise_document(
                    kb_id=kb_id,
                    user_id=user_id,
                    filename=name,
                    upload_dir=upload_dir,
                )
    return doc_files


async def count_entity_rows(db: AsyncSession, kb_id: UUID) -> dict[str, int]:
    ent = await db.scalar(
        select(func.count()).select_from(Entity).where(Entity.kb_id == kb_id)
    )
    rel = await db.scalar(
        select(func.count()).select_from(Relation).where(Relation.kb_id == kb_id)
    )
    mention = await db.scalar(
        select(func.count())
        .select_from(EntityMention)
        .join(Entity, Entity.id == EntityMention.entity_id)
        .where(Entity.kb_id == kb_id)
    )
    return {
        "entities": int(ent or 0),
        "relations": int(rel or 0),
        "entity_mentions": int(mention or 0),
    }


async def deterministic_fake_extract(db: AsyncSession, doc: Document) -> None:
    """Write deterministic fake entity rows (CONTROL path, no DeepSeek)."""
    chunk_rows = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(3)
    )
    chunks = chunk_rows.scalars().all()
    if not chunks:
        doc.entity_extracted_at = datetime.now(timezone.utc)
        return

    bait_name = f"FAKE-ENTITY-{doc.filename[:20]}"
    ent = Entity(kb_id=doc.kb_id, name=bait_name, type="organization")
    db.add(ent)
    await db.flush()

    for chunk in chunks:
        db.add(EntityMention(chunk_id=chunk.id, entity_id=ent.id))

    ent2 = Entity(kb_id=doc.kb_id, name=f"{bait_name}-REL-TARGET", type="project")
    db.add(ent2)
    await db.flush()
    db.add(
        Relation(
            kb_id=doc.kb_id,
            source_id=ent.id,
            target_id=ent2.id,
            relation_type="related_to",
        )
    )
    doc.entity_extracted_at = datetime.now(timezone.utc)


async def inject_query_bait_entities(
    db: AsyncSession,
    *,
    kb_id: UUID,
    query: str,
    chunk_id: UUID,
) -> None:
    """Insert obviously query-relevant fake graph rows (isolation test)."""
    bait = Entity(kb_id=kb_id, name=query.strip()[:200], type="organization")
    db.add(bait)
    await db.flush()
    db.add(EntityMention(chunk_id=chunk_id, entity_id=bait.id))
    decoy = Entity(kb_id=kb_id, name=f"BAIT-HOP-{query[:32]}", type="project")
    db.add(decoy)
    await db.flush()
    db.add(
        Relation(
            kb_id=kb_id,
            source_id=bait.id,
            target_id=decoy.id,
            relation_type="supersedes",
        )
    )
    await db.commit()


def scores_equal(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=SCORE_REL_TOL, abs_tol=SCORE_ABS_TOL)


def chunk_content_fingerprint(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


@dataclass(slots=True)
class CaseRetrievalObserved:
    case_id: str
    query: str
    top_chunk_ids: list[str] = field(default_factory=list)
    top_content_fingerprints: list[str] = field(default_factory=list)
    top_document_names: list[str] = field(default_factory=list)
    top_scores: list[float | None] = field(default_factory=list)
    hit1: bool = False
    hit3: bool = False
    hit5: bool = False
    mrr: float = 0.0

    def fingerprint(self) -> str:
        payload = {
            "top_content_fingerprints": self.top_content_fingerprints,
            "top_document_names": self.top_document_names,
            "top_scores": self.top_scores,
            "hit1": self.hit1,
            "hit3": self.hit3,
            "hit5": self.hit5,
            "mrr": round(self.mrr, 8),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()


async def run_enterprise_retrieval_cases(
    db: AsyncSession,
    *,
    kb_id: UUID,
    cases: list[dict[str, Any]],
    hit_k: int,
    top_k: int = TOP_K,
) -> list[CaseRetrievalObserved]:
    from app.services.rag.cache import query_cache_enabled, set_query_cache_enabled

    original_cache = query_cache_enabled()
    set_query_cache_enabled(False)
    try:
        results: list[CaseRetrievalObserved] = []
        for raw in cases:
            golden = enterprise_case_to_golden(raw)
            chunks = await retrieve_chunks(
                db,
                kb_id=kb_id,
                query=raw["query"],
                top_k=top_k,
            )
            observed = CaseRetrievalObserved(
                case_id=golden.case_id,
                query=raw["query"],
                top_chunk_ids=[str(c.chunk_id) for c in chunks[:top_k]],
                top_content_fingerprints=[
                    chunk_content_fingerprint(c.content) for c in chunks[:top_k]
                ],
                top_document_names=[c.doc_name or "" for c in chunks[:top_k]],
                top_scores=[c.similarity for c in chunks[:top_k]],
                hit1=hit_at_k(chunks, golden, k=1),
                hit3=hit_at_k(chunks, golden, k=min(3, hit_k)),
                hit5=hit_at_k(chunks, golden, k=min(5, top_k)),
                mrr=reciprocal_rank(chunks, golden, k=top_k),
            )
            results.append(observed)
        return results
    finally:
        set_query_cache_enabled(original_cache)


def compare_retrieval_runs(
    baseline: list[CaseRetrievalObserved],
    other: list[CaseRetrievalObserved],
) -> dict[str, Any]:
    by_id = {r.case_id: r for r in baseline}
    top1_equal = top3_equal = top5_equal = rank_equal = 0
    mismatches: list[dict[str, Any]] = []

    for row in other:
        base = by_id.get(row.case_id)
        if base is None:
            mismatches.append({"case_id": row.case_id, "reason": "missing_in_baseline"})
            continue

        if base.top_content_fingerprints[:1] == row.top_content_fingerprints[:1]:
            top1_equal += 1
        if base.top_content_fingerprints[:3] == row.top_content_fingerprints[:3]:
            top3_equal += 1
        if base.top_content_fingerprints[:5] == row.top_content_fingerprints[:5]:
            top5_equal += 1
        if base.top_content_fingerprints == row.top_content_fingerprints:
            rank_equal += 1

        scores_ok = len(base.top_scores) == len(row.top_scores) and all(
            scores_equal(a, b) for a, b in zip(base.top_scores, row.top_scores, strict=True)
        )
        metrics_ok = (
            base.hit1 == row.hit1
            and base.hit3 == row.hit3
            and base.hit5 == row.hit5
            and math.isclose(base.mrr, row.mrr, rel_tol=SCORE_REL_TOL, abs_tol=SCORE_ABS_TOL)
        )
        if (
            base.top_content_fingerprints != row.top_content_fingerprints
            or not scores_ok
            or not metrics_ok
        ):
            mismatches.append(
                {
                    "case_id": row.case_id,
                    "baseline_top_fingerprints": base.top_content_fingerprints,
                    "other_top_fingerprints": row.top_content_fingerprints,
                    "baseline_doc_names": base.top_document_names,
                    "other_doc_names": row.top_document_names,
                    "baseline_scores": base.top_scores,
                    "other_scores": row.top_scores,
                    "baseline_hits": (base.hit1, base.hit3, base.hit5, base.mrr),
                    "other_hits": (row.hit1, row.hit3, row.hit5, row.mrr),
                }
            )

    n = len(other)
    base_hits = aggregate_hit_metrics(baseline)
    other_hits = aggregate_hit_metrics(other)
    return {
        "retrieval_case_count": n,
        "top1_equal_count": top1_equal,
        "top3_equal_count": top3_equal,
        "top5_equal_count": top5_equal,
        "rank_order_equal_count": rank_equal,
        "hit1_equal": base_hits["hit1"] == other_hits["hit1"],
        "hit3_equal": base_hits["hit3"] == other_hits["hit3"],
        "hit5_equal": base_hits["hit5"] == other_hits["hit5"],
        "mrr_equal": math.isclose(
            base_hits["mrr"],
            other_hits["mrr"],
            rel_tol=SCORE_REL_TOL,
            abs_tol=SCORE_ABS_TOL,
        ),
        "retrieval_semantics_equal": not mismatches,
        "mismatches": mismatches[:10],
        "baseline_hit_metrics": base_hits,
        "other_hit_metrics": other_hits,
    }


def aggregate_hit_metrics(rows: list[CaseRetrievalObserved]) -> dict[str, float]:
    n = max(1, len(rows))
    return {
        "hit1": sum(1 for r in rows if r.hit1) / n,
        "hit3": sum(1 for r in rows if r.hit3) / n,
        "hit5": sum(1 for r in rows if r.hit5) / n,
        "mrr": sum(r.mrr for r in rows) / n,
    }


def write_equivalence_report(payload: dict[str, Any]) -> Path:
    out_dir = (
        Path(__file__).resolve().parents[3]
        / "artifacts"
        / "benchmarks"
        / "tmp"
        / "reports"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "enterprise-entity-equivalence.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def build_report_payload(
    *,
    coverage: str,
    corpus_control: dict[str, Any],
    corpus_skip: dict[str, Any],
    corpus_fake: dict[str, Any],
    entity_rows: dict[str, dict[str, int]],
    comparisons: dict[str, Any],
    fake_injection: dict[str, Any],
    embedding_model: str,
) -> dict[str, Any]:
    return {
        "base_sha": git_base_sha(),
        "fixture_hashes": fixture_hashes(),
        "embedding_model": embedding_model,
        "embedding_provider": settings.embedding_provider,
        "graph_recall_enabled": settings.graph_recall_enabled,
        "coverage": coverage,
        "corpus_fingerprint_equal": corpora_cross_kb_equivalent(corpus_control, corpus_skip),
        "chunk_count_equal": corpus_control.get("chunk_count") == corpus_skip.get("chunk_count"),
        "embedding_count_equal": corpus_control.get("embedding_row_count")
        == corpus_skip.get("embedding_row_count"),
        "corpus_control_sorted_fingerprint": sorted_corpus_fingerprint_sha256(corpus_control),
        "corpus_skip_sorted_fingerprint": sorted_corpus_fingerprint_sha256(corpus_skip),
        "corpus_sorted_fingerprint_equal": sorted_corpus_fingerprint_sha256(corpus_control)
        == sorted_corpus_fingerprint_sha256(corpus_skip),
        "corpus_control": corpus_control,
        "corpus_skip": corpus_skip,
        "corpus_fake": corpus_fake,
        "entity_rows": entity_rows,
        "comparisons": comparisons,
        "fake_entity_injection": fake_injection,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "FROZEN_STRATIFIED_CASE_IDS",
    "TOP_K",
    "build_report_payload",
    "collect_corpus_fingerprint",
    "compare_retrieval_runs",
    "corpora_cross_kb_equivalent",
    "deterministic_fake_extract",
    "enterprise_case_to_golden",
    "ingest_enterprise_corpus",
    "inject_query_bait_entities",
    "load_enterprise_retrieval_cases",
    "patch_skip_entity_extract",
    "run_enterprise_retrieval_cases",
    "write_equivalence_report",
]

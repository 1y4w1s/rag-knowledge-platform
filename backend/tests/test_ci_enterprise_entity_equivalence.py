"""Enterprise QA retrieval vs entity extraction equivalence (CI benchmark semantics proof).

Static proof: ``graph_recall_enabled=False`` (production default) → retrieval never reads
entity/ relation tables. Dynamic proof: CONTROL (noop/fake extract) vs skip=True corpus +
top-k / Hit@K / MRR identical. Does not modify CI workflow or product defaults.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

# Real BGE before autouse mock_embedding_for_tests evaluates per test.
os.environ.setdefault("RAG_REAL_EMBEDDING", "1")

from app.core.config import settings
from app.core.database import SessionLocal
from app.eval.golden_benchmark.corpus import collect_corpus_fingerprint
from app.eval.golden_benchmark.entity_equivalence import (
    FROZEN_STRATIFIED_CASE_IDS,
    build_report_payload,
    compare_retrieval_runs,
    corpora_cross_kb_equivalent,
    count_entity_rows,
    deterministic_fake_extract,
    ingest_enterprise_corpus,
    inject_query_bait_entities,
    load_enterprise_retrieval_cases,
    patch_skip_entity_extract,
    run_enterprise_retrieval_cases,
    write_equivalence_report,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.rag import retrieval as retrieval_mod
from tests.conftest import create_test_kb as _create_kb


def test_static_retrieval_path_does_not_depend_on_entity_graph() -> None:
    """Step 1: production default keeps graph_entity_recall as no-op."""
    assert settings.graph_recall_enabled is False
    assert settings.skip_entity_extract is False

    import inspect

    from app.services.rag import retrieval

    src = inspect.getsource(retrieval.graph_entity_recall)
    assert "if not settings.graph_recall_enabled:" in src
    assert "return result" in src

    retrieve_src = inspect.getsource(retrieval.retrieve_chunks)
    assert "graph_entity_recall" in retrieve_src
    # No direct Entity / EntityMention reads outside graph_entity_recall
    for needle in ("EntityMention", "Entity.kb_id", "Relation.kb_id"):
        assert retrieve_src.count(needle) <= retrieve_src.count("graph_entity_recall")


def test_skip_entity_extract_only_toggles_pipeline_branch() -> None:
    """Step 2: skip flag must not alter embedding provider/model."""
    saved_provider = settings.embedding_provider
    saved_model = settings.embedding_model
    saved_dim = settings.embedding_dim
    with patch_skip_entity_extract(True):
        assert settings.skip_entity_extract is True
        assert settings.embedding_provider == saved_provider
        assert settings.embedding_model == saved_model
        assert settings.embedding_dim == saved_dim
    assert settings.skip_entity_extract is False


async def _noop_extract(_db, _doc) -> None:  # noqa: ANN001
    return None


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def real_bge_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve real BGE; disable query cache for deterministic retrieval."""
    monkeypatch.setattr(settings, "embedding_provider", "bge")
    monkeypatch.setattr(retrieval_mod, "query_cache_enabled", lambda: False)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_enterprise_entity_extraction_retrieval_equivalence(
    client,
    register_and_login,
    upload_dir,
    real_bge_settings,
) -> None:
    """A (noop) == B (fake entities) == C (skip=True) on corpus + retrieval observables."""
    full = os.environ.get("RAG_ENTERPRISE_EQ_FULL") == "1"
    cases, hit_k = load_enterprise_retrieval_cases(full=full)
    coverage = "FULL" if full else "SUBSET"

    headers, user = await register_and_login(prefix="ent-eq")
    user_id = uuid.UUID(user["id"])

    async def _create_named_kb(name: str) -> uuid.UUID:
        kb = await _create_kb(client, headers, user, name=name)
        return uuid.UUID(kb["id"])

    kb_no_ent = await _create_named_kb("ent-eq-no-entities")
    kb_fake = await _create_named_kb("ent-eq-fake-entities")
    kb_skip = await _create_named_kb("ent-eq-skip-extract")

    await ingest_enterprise_corpus(
        kb_id=kb_no_ent,
        user_id=user_id,
        upload_dir=Path(upload_dir),
        skip_entity_extract=False,
        entity_extract_override=_noop_extract,
    )
    await ingest_enterprise_corpus(
        kb_id=kb_fake,
        user_id=user_id,
        upload_dir=Path(upload_dir),
        skip_entity_extract=False,
        entity_extract_override=deterministic_fake_extract,
    )
    await ingest_enterprise_corpus(
        kb_id=kb_skip,
        user_id=user_id,
        upload_dir=Path(upload_dir),
        skip_entity_extract=True,
        entity_extract_override=None,
    )

    async with SessionLocal() as db:
        corpus_a = await collect_corpus_fingerprint(db, kb_no_ent)
        corpus_b = await collect_corpus_fingerprint(db, kb_fake)
        corpus_c = await collect_corpus_fingerprint(db, kb_skip)
        entity_a = await count_entity_rows(db, kb_no_ent)
        entity_b = await count_entity_rows(db, kb_fake)
        entity_c = await count_entity_rows(db, kb_skip)

    assert corpus_a["chunk_count"] > 0
    assert corpora_cross_kb_equivalent(corpus_a, corpus_c), (corpus_a, corpus_c)
    assert corpora_cross_kb_equivalent(corpus_a, corpus_b), (corpus_a, corpus_b)
    assert entity_a["entities"] == 0
    assert entity_b["entities"] > 0
    assert entity_c["entities"] == 0

    # Retrieval equivalence on ONE shared skip-ingest corpus (avoids cross-KB BGE variance).
    async with SessionLocal() as db:
        baseline = await run_enterprise_retrieval_cases(
            db, kb_id=kb_skip, cases=cases, hit_k=hit_k,
        )

        # State B: populate fake entity graph on skip corpus
        chunk_rows = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.kb_id == kb_skip)
            .order_by(DocumentChunk.chunk_index)
            .limit(6)
        )
        chunks_for_fake = list(chunk_rows.scalars().all())
        for chunk in chunks_for_fake:
            doc_row = await db.get(Document, chunk.document_id)
            if doc_row is not None:
                await deterministic_fake_extract(db, doc_row)
        await db.commit()
        entity_after_fake = await count_entity_rows(db, kb_skip)
        with_fake = await run_enterprise_retrieval_cases(
            db, kb_id=kb_skip, cases=cases, hit_k=hit_k,
        )

        # Bait injection isolation
        bait_query = cases[0]["query"]
        bait_chunk = chunks_for_fake[0]
        pre_bait = await run_enterprise_retrieval_cases(
            db, kb_id=kb_skip, cases=cases[:5], hit_k=hit_k,
        )
        await inject_query_bait_entities(
            db,
            kb_id=kb_skip,
            query=bait_query,
            chunk_id=bait_chunk.id,
        )
        entity_after_bait = await count_entity_rows(db, kb_skip)
        post_bait = await run_enterprise_retrieval_cases(
            db, kb_id=kb_skip, cases=cases[:5], hit_k=hit_k,
        )

    cmp_baseline_fake = compare_retrieval_runs(baseline, with_fake)
    cmp_baseline_bait = compare_retrieval_runs(pre_bait, post_bait)

    assert cmp_baseline_fake["retrieval_semantics_equal"], cmp_baseline_fake.get("mismatches")
    assert cmp_baseline_bait["retrieval_semantics_equal"], cmp_baseline_bait.get("mismatches")
    assert entity_after_fake["entities"] > 0
    assert entity_after_bait["entities"] > entity_after_fake["entities"]

    report = build_report_payload(
        coverage=coverage,
        corpus_control=corpus_a,
        corpus_skip=corpus_c,
        corpus_fake=corpus_b,
        entity_rows={
            "no_entities": entity_a,
            "fake_entities": entity_b,
            "skip_extract": entity_c,
            "after_bait_injection": entity_after_bait,
        },
        comparisons={
            "same_kb_baseline_vs_fake_entities": cmp_baseline_fake,
            "same_kb_pre_vs_post_bait_injection": cmp_baseline_bait,
            "frozen_case_ids": list(FROZEN_STRATIFIED_CASE_IDS),
        },
        fake_injection={
            "query": bait_query,
            "entity_rows_before_bait": entity_after_fake,
            "entity_rows_after_bait": entity_after_bait,
            "retrieval_changed": not cmp_baseline_bait["retrieval_semantics_equal"],
            "comparison": cmp_baseline_bait,
        },
        embedding_model=settings.embedding_model,
    )
    artifact_path = write_equivalence_report(report)

    assert report["corpus_fingerprint_equal"]
    assert report["chunk_count_equal"]
    assert report["embedding_count_equal"]
    assert settings.embedding_provider == "bge"
    assert cmp_baseline_bait["retrieval_semantics_equal"]
    assert artifact_path.exists()


@pytest.mark.asyncio
async def test_skip_entity_extract_setting_restored_after_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert settings.skip_entity_extract is False
    with patch_skip_entity_extract(True):
        assert settings.skip_entity_extract is True
    assert settings.skip_entity_extract is False

    saved = settings.skip_entity_extract
    monkeypatch.setattr(settings, "skip_entity_extract", True)
    assert settings.skip_entity_extract is True
    monkeypatch.setattr(settings, "skip_entity_extract", saved)
    assert settings.skip_entity_extract is False

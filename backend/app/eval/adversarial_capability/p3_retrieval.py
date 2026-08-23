"""ADVERSARIAL P3 Layer R — vector retrieval scoring against frozen P1 corpora."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.eval.adversarial_capability.capability_cases import CapabilityCase
from app.eval.adversarial_capability.corpus_fixtures import CORPUS_BY_ID, ControlledCorpus


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: str
    rank: int
    score: float


def rank_corpus_chunks(
    *,
    corpus: ControlledCorpus,
    query_vector: list[float],
    chunk_vectors: dict[str, list[float]],
    top_k: int = 5,
) -> tuple[RetrievalHit, ...]:
    scored: list[tuple[str, float]] = []
    for chunk in corpus.chunks:
        cid = chunk["chunk_id"]
        vec = chunk_vectors.get(cid)
        if vec is None:
            continue
        scored.append((cid, _cosine(query_vector, vec)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return tuple(
        RetrievalHit(chunk_id=cid, rank=i + 1, score=round(score, 6))
        for i, (cid, score) in enumerate(scored[:top_k])
    )


def _chunk_sets(case: CapabilityCase) -> dict[str, set[str]]:
    corpus = CORPUS_BY_ID[case.corpus_fixture_id]
    support = set(case.supporting_chunk_ids)
    contradict = set(case.contradicting_chunk_ids)
    partial_chunks = set()
    for fid in case.partial_fact_ids:
        for fact in corpus.fact_registry:
            if fact.fact_id == fid:
                partial_chunks.add(fact.chunk_id)
    all_ids = {c["chunk_id"] for c in corpus.chunks}
    irrelevant = all_ids - support - contradict - partial_chunks
    return {
        "support": support,
        "contradict": contradict,
        "partial": partial_chunks,
        "irrelevant": irrelevant,
    }


def required_fact_coverage(case: CapabilityCase, hits: tuple[RetrievalHit, ...]) -> dict[str, Any]:
    corpus = CORPUS_BY_ID[case.corpus_fixture_id]
    hit_ids = {h.chunk_id for h in hits}
    covered: list[str] = []
    missing: list[str] = []
    for fid in case.required_fact_ids:
        chunk_ids = {f.chunk_id for f in corpus.fact_registry if f.fact_id == fid}
        if chunk_ids & hit_ids:
            covered.append(fid)
        else:
            missing.append(fid)
    total = len(case.required_fact_ids)
    return {
        "required_fact_ids": list(case.required_fact_ids),
        "covered": covered,
        "missing": missing,
        "ratio": (len(covered) / total) if total else 1.0,
    }


def classify_retrieval_observation(case: CapabilityCase, hits: tuple[RetrievalHit, ...]) -> str:
    if not hits:
        return "ZERO_HITS"
    sets = _chunk_sets(case)
    hit_ids = {h.chunk_id for h in hits}
    if case.answerability_class == "ANSWERABLE":
        if hit_ids & sets["support"]:
            return "SUPPORT_RETRIEVED"
        return "SUPPORT_MISS"
    if case.answerability_class == "UNANSWERABLE_IN_CORPUS":
        if hit_ids & sets["support"]:
            return "UNEXPECTED_SUPPORT_HIT"
        if hit_ids:
            return "IRRELEVANT_OR_TOPIC_HITS"
        return "ZERO_HITS"
    if case.answerability_class == "INSUFFICIENT_EVIDENCE":
        if hit_ids & sets["partial"]:
            return "PARTIAL_EVIDENCE_HIT"
        return "PARTIAL_MISS"
    if case.answerability_class == "CONFLICTED_EVIDENCE":
        got = hit_ids & (sets["support"] | sets["contradict"])
        if len(got) >= 2:
            return "BOTH_SIDES_RETRIEVED"
        if len(got) == 1:
            return "SINGLE_SIDE_ONLY"
        return "CONFLICT_MISS"
    return "UNCLASSIFIED"


def score_case_retrieval(case: CapabilityCase, hits: tuple[RetrievalHit, ...]) -> dict[str, Any]:
    sets = _chunk_sets(case)
    hit_ids = {h.chunk_id for h in hits}
    return {
        "case_id": case.case_id,
        "answerability_class": case.answerability_class,
        "corpus_truth": case.answerability_class,
        "retrieved_chunk_ids": [h.chunk_id for h in hits],
        "retrieval_details": [
            {"chunk_id": h.chunk_id, "rank": h.rank, "score": h.score} for h in hits
        ],
        "support_hit": bool(hit_ids & sets["support"]),
        "contradiction_hit": bool(hit_ids & sets["contradict"]),
        "partial_hit": bool(hit_ids & sets["partial"]),
        "irrelevant_hit_count": len(hit_ids & sets["irrelevant"]),
        "required_fact_coverage": required_fact_coverage(case, hits),
        "retrieval_observation_class": classify_retrieval_observation(case, hits),
        "retrieval_contract_valid": case.corpus_fingerprint
        == CORPUS_BY_ID[case.corpus_fixture_id].corpus_fingerprint,
    }



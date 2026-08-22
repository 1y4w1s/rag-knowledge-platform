"""ADVERSARIAL Golden contract validity and retrieval measurement characterization."""

from __future__ import annotations

from pathlib import Path

from app.eval.contract_validity.golden_contracts import (
    ADVERSARIAL_FORMAL_CONTRACT,
    W8_P5_ADVERSARIAL_CASE_IDS,
    W8_P6_BGE_POSITIVE_RAG_CASE_IDS,
    W8_P6_BGE_POSITIVE_RETRIEVAL_CASE_IDS,
)
from app.eval.contract_validity.models import (
    AdversarialContractCharacterization,
    Validity,
)

# Confirmed from semantic_search.run_semantic_search + retrieve_chunks:
# always returns up to top_k hits when corpus exists; no minimum similarity cutoff.
RETRIEVAL_THRESHOLD_SEMANTICS: str = (
    "semantic_search / retrieve_chunks always return up to top_k ranked hits when "
    "the scoped KB has chunks and visibility permits access. There is no minimum "
    "similarity threshold or post-retrieval score filter that yields zero hits for "
    "low scores. Empty results occur only on scope denial or empty KB visibility. "
    "adaptive_top_k may reduce downstream LLM chunk count but does not zero agent "
    "tool hits. Scores are informational; a low top1 score still constitutes a hit."
)

MOCK_NEGATIVE_RETRIEVAL_VALIDITY: Validity = Validity.INVALID_FOR_CAPABILITY

BGE_FASTEMBED_CANDIDATE_PATHS: tuple[Path, ...] = (
    Path("models/fastembed"),
    Path("models/fastembed/fast-bge-small-zh-v1.5"),
    Path("models/fastembed/models--Qdrant--bge-small-zh-v1.5"),
)


def bge_candidate_available(repo_root: Path | None = None) -> bool:
    """CAPABILITY_VALID_RETRIEVAL_CANDIDATE — local cache present, not proven valid."""
    root = repo_root or Path(__file__).resolve().parents[3]
    return any((root / rel).exists() for rel in BGE_FASTEMBED_CANDIDATE_PATHS)


def build_adversarial_characterization(
    *,
    repo_root: Path | None = None,
    bge_proven: bool = False,
) -> AdversarialContractCharacterization:
    candidate = bge_candidate_available(repo_root)
    if bge_proven:
        conclusion = (
            "BGE retrieval distinguishes positive controls from adversarial negatives "
            "under real retrieval semantics."
        )
    elif candidate:
        conclusion = (
            "ADVERSARIAL_MEASUREMENT_REQUIRES answerability / retrieval-rejection "
            "contract beyond retrieval-only probe. Current retrieval is effectively "
            "always-top-k on single-corpus fixtures; mock embedding is unsuitable for "
            "negative semantic retrieval capability. BGE is a candidate only — not proven."
        )
    else:
        conclusion = (
            "No local BGE/fastembed cache detected. Mock embedding remains the "
            "benchmark default and is INVALID for negative retrieval measurement."
        )

    return AdversarialContractCharacterization(
        original_pass_count=1,
        original_pass_total=20,
        original_metric_validity=Validity.INVALID_FOR_CAPABILITY,
        mock_negative_retrieval_validity=MOCK_NEGATIVE_RETRIEVAL_VALIDITY,
        bge_candidate_available=candidate,
        bge_capability_valid_proven=bge_proven,
        retrieval_threshold_semantics=RETRIEVAL_THRESHOLD_SEMANTICS,
        primary_conclusion=conclusion,
        formal_contract=dict(ADVERSARIAL_FORMAL_CONTRACT),
    )


def adversarial_probe_case_ids() -> tuple[str, ...]:
    """28 query groups: 20 ADVERSARIAL + 4 RAG + 4 RETRIEVAL positive controls (fixed)."""
    return (
        W8_P5_ADVERSARIAL_CASE_IDS
        + W8_P6_BGE_POSITIVE_RAG_CASE_IDS
        + W8_P6_BGE_POSITIVE_RETRIEVAL_CASE_IDS
    )

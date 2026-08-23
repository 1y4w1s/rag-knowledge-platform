"""Controlled adversarial capability corpora — fingerprint + fact registry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def corpus_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CorpusFact:
    fact_id: str
    proposition: str
    chunk_id: str
    polarity: str = "supporting"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "proposition": self.proposition,
            "chunk_id": self.chunk_id,
            "polarity": self.polarity,
        }


@dataclass(frozen=True, slots=True)
class ControlledCorpus:
    corpus_fixture_id: str
    corpus_class: str
    documents: tuple[dict[str, str], ...]
    chunks: tuple[dict[str, str], ...]
    fact_registry: tuple[CorpusFact, ...]
    corpus_fingerprint: str
    absent_propositions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_fixture_id": self.corpus_fixture_id,
            "corpus_class": self.corpus_class,
            "documents": [dict(d) for d in self.documents],
            "chunks": [dict(c) for c in self.chunks],
            "fact_registry": [f.to_dict() for f in self.fact_registry],
            "absent_propositions": list(self.absent_propositions),
            "corpus_fingerprint": self.corpus_fingerprint,
        }


def _build_corpus(
    corpus_fixture_id: str,
    corpus_class: str,
    documents: tuple[dict[str, str], ...],
    chunks: tuple[dict[str, str], ...],
    fact_registry: tuple[CorpusFact, ...],
    absent_propositions: tuple[str, ...] = (),
) -> ControlledCorpus:
    body = {
        "corpus_fixture_id": corpus_fixture_id,
        "documents": [dict(d) for d in documents],
        "chunks": [dict(c) for c in chunks],
        "fact_registry": [f.to_dict() for f in fact_registry],
        "absent_propositions": list(absent_propositions),
    }
    return ControlledCorpus(
        corpus_fixture_id=corpus_fixture_id,
        corpus_class=corpus_class,
        documents=documents,
        chunks=chunks,
        fact_registry=fact_registry,
        absent_propositions=absent_propositions,
        corpus_fingerprint=corpus_fingerprint(body),
    )


# ANSWERABLE CONTROL — backup retention policy present.
_ANS_DOC = ({"doc_id": "adv-handbook-01", "title": "Operations Handbook"},)
_ANS_CHUNKS = (
    {
        "chunk_id": "adv-ch-001",
        "doc_id": "adv-handbook-01",
        "text": "Backup retention: production backups are retained for 30 days.",
    },
)
_ANS_FACTS = (
    CorpusFact(
        fact_id="F-ADV-RET-30",
        proposition="Production backups are retained for 30 days.",
        chunk_id="adv-ch-001",
    ),
)
CORPUS_ANSWERABLE = _build_corpus(
    "ADV-CORPUS-ANS-01",
    "ANSWERABLE_CONTROL",
    _ANS_DOC,
    _ANS_CHUNKS,
    _ANS_FACTS,
)

# UNANSWERABLE_IN_CORPUS — handbook exists but no answer for numeric literal 42.
_UNA_DOC = ({"doc_id": "adv-handbook-02", "title": "General FAQ"},)
_UNA_CHUNKS = (
    {
        "chunk_id": "adv-ch-101",
        "doc_id": "adv-handbook-02",
        "text": "This knowledge base covers internal operations policies only.",
    },
)
CORPUS_UNANSWERABLE = _build_corpus(
    "ADV-CORPUS-UNA-01",
    "UNANSWERABLE_IN_CORPUS",
    _UNA_DOC,
    _UNA_CHUNKS,
    (),
    absent_propositions=("No document defines what the number 42 means.",),
)

# PARTIAL / INSUFFICIENT — password policy without admin password value.
_PART_DOC = ({"doc_id": "adv-handbook-03", "title": "Security Policy"},)
_PART_CHUNKS = (
    {
        "chunk_id": "adv-ch-201",
        "doc_id": "adv-handbook-03",
        "text": "Passwords must be at least 12 characters and rotated every 90 days.",
    },
)
_PART_FACTS = (
    CorpusFact(
        fact_id="F-ADV-PWD-POLICY",
        proposition="Passwords must be at least 12 characters.",
        chunk_id="adv-ch-201",
    ),
)
CORPUS_PARTIAL = _build_corpus(
    "ADV-CORPUS-PART-01",
    "PARTIAL_INSUFFICIENT",
    _PART_DOC,
    _PART_CHUNKS,
    _PART_FACTS,
    absent_propositions=("The admin password value is not stored in the corpus.",),
)

# CONFLICTED — two chunks disagree on retention days.
_CON_DOC = ({"doc_id": "adv-handbook-04", "title": "Conflicting Records"},)
_CON_CHUNKS = (
    {
        "chunk_id": "adv-ch-301",
        "doc_id": "adv-handbook-04",
        "text": "Backup retention policy: retain backups for 30 days.",
    },
    {
        "chunk_id": "adv-ch-302",
        "doc_id": "adv-handbook-04",
        "text": "Legacy note: backups may be retained for 90 days per old SOP.",
    },
)
_CON_FACTS = (
    CorpusFact(
        fact_id="F-ADV-RET-30B",
        proposition="Backups retained for 30 days.",
        chunk_id="adv-ch-301",
    ),
    CorpusFact(
        fact_id="F-ADV-RET-90B",
        proposition="Backups retained for 90 days.",
        chunk_id="adv-ch-302",
        polarity="contradicting",
    ),
)
CORPUS_CONFLICTED = _build_corpus(
    "ADV-CORPUS-CON-01",
    "CONFLICTED_EVIDENCE",
    _CON_DOC,
    _CON_CHUNKS,
    _CON_FACTS,
)

ALL_CORPORA: tuple[ControlledCorpus, ...] = (
    CORPUS_ANSWERABLE,
    CORPUS_UNANSWERABLE,
    CORPUS_PARTIAL,
    CORPUS_CONFLICTED,
)

CORPUS_BY_ID: dict[str, ControlledCorpus] = {c.corpus_fixture_id: c for c in ALL_CORPORA}

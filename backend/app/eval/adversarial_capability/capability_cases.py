"""P1 capability cases + legacy migration audit sidecar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.eval.adversarial_capability.corpus_fixtures import CORPUS_BY_ID
from app.eval.adversarial_capability.freeze import LEGACY_ADV20_CASE_IDS, load_p0_contract

_LEGACY_GOLDEN = Path(__file__).resolve().parents[3] / "tests" / "golden_agent_qa.json"

MIGRATION_OUTCOMES = (
    "MIGRATED_VALID",
    "STILL_INVALID",
    "NEEDS_NEW_FIXTURE",
    "UNSATISFIABLE_CURRENT_RUNTIME",
    "OTHER",
)


@dataclass(frozen=True, slots=True)
class CapabilityCase:
    case_id: str
    answerability_class: str
    question: str
    required_fact_ids: tuple[str, ...]
    required_propositions: tuple[str, ...]
    corpus_fixture_id: str
    corpus_fingerprint: str
    fact_registry: tuple[dict[str, Any], ...]
    supporting_chunk_ids: tuple[str, ...]
    contradicting_chunk_ids: tuple[str, ...]
    partial_fact_ids: tuple[str, ...]
    expected_terminal_class: str
    citation_applicable: bool
    source_case_id: str | None
    migration_reason: str
    in_capability_denominator: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "answerability_class": self.answerability_class,
            "question": self.question,
            "required_fact_ids": list(self.required_fact_ids),
            "required_propositions": list(self.required_propositions),
            "corpus_fixture_id": self.corpus_fixture_id,
            "corpus_fingerprint": self.corpus_fingerprint,
            "fact_registry": list(self.fact_registry),
            "supporting_chunk_ids": list(self.supporting_chunk_ids),
            "contradicting_chunk_ids": list(self.contradicting_chunk_ids),
            "partial_fact_ids": list(self.partial_fact_ids),
            "expected_terminal_class": self.expected_terminal_class,
            "citation_applicable": self.citation_applicable,
            "source_case_id": self.source_case_id,
            "migration_reason": self.migration_reason,
            "in_capability_denominator": self.in_capability_denominator,
        }


def _case_from_corpus(
    case_id: str,
    *,
    question: str,
    answerability: str,
    corpus_id: str,
    required_fact_ids: tuple[str, ...] = (),
    required_propositions: tuple[str, ...] = (),
    supporting: tuple[str, ...] = (),
    contradicting: tuple[str, ...] = (),
    partial: tuple[str, ...] = (),
    terminal: str,
    citation: bool,
    source: str | None,
    reason: str,
) -> CapabilityCase:
    corpus = CORPUS_BY_ID[corpus_id]
    return CapabilityCase(
        case_id=case_id,
        answerability_class=answerability,
        question=question,
        required_fact_ids=required_fact_ids,
        required_propositions=required_propositions,
        corpus_fixture_id=corpus_id,
        corpus_fingerprint=corpus.corpus_fingerprint,
        fact_registry=tuple(f.to_dict() for f in corpus.fact_registry),
        supporting_chunk_ids=supporting,
        contradicting_chunk_ids=contradicting,
        partial_fact_ids=partial,
        expected_terminal_class=terminal,
        citation_applicable=citation,
        source_case_id=source,
        migration_reason=reason,
        in_capability_denominator=True,
    )


CAPABILITY_CASES: tuple[CapabilityCase, ...] = (
    _case_from_corpus(
        "ADV-P1-ANS-001",
        question="What is the backup retention period for production backups?",
        answerability="ANSWERABLE",
        corpus_id="ADV-CORPUS-ANS-01",
        required_fact_ids=("F-ADV-RET-30",),
        required_propositions=("Production backups are retained for 30 days.",),
        supporting=("adv-ch-001",),
        terminal="finish",
        citation=True,
        source="GQ-8",
        reason="Controlled answerable corpus with atomic fact + chunk binding.",
    ),
    _case_from_corpus(
        "ADV-P1-UNA-001",
        question="What is 42?",
        answerability="UNANSWERABLE_IN_CORPUS",
        corpus_id="ADV-CORPUS-UNA-01",
        required_propositions=("No document defines what the number 42 means.",),
        terminal="refuse",
        citation=False,
        source="GQ-104",
        reason="Negative corpus fixture; GQ-104 excluded until independent proof (P1 provides new fixture).",
    ),
    _case_from_corpus(
        "ADV-P1-PART-001",
        question="What is the admin password?",
        answerability="INSUFFICIENT_EVIDENCE",
        corpus_id="ADV-CORPUS-PART-01",
        partial=("F-ADV-PWD-POLICY",),
        supporting=("adv-ch-201",),
        terminal="refuse",
        citation=False,
        source="GQ-102",
        reason="Same-topic partial evidence; password policy present, secret value absent.",
    ),
    _case_from_corpus(
        "ADV-P1-CON-001",
        question="How many days are backups retained?",
        answerability="CONFLICTED_EVIDENCE",
        corpus_id="ADV-CORPUS-CON-01",
        required_fact_ids=("F-ADV-RET-30B", "F-ADV-RET-90B"),
        supporting=("adv-ch-301",),
        contradicting=("adv-ch-302",),
        terminal="clarify",
        citation=True,
        source=None,
        reason="Conflicting retention propositions require clarify/refuse unsupported finish.",
    ),
)

CAPABILITY_CASE_BY_ID = {c.case_id: c for c in CAPABILITY_CASES}


@dataclass(frozen=True, slots=True)
class LegacyMigrationAudit:
    case_id: str
    migration_outcome: str
    answerability_class: str
    corpus_contract_required: bool
    in_capability_denominator: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "migration_outcome": self.migration_outcome,
            "answerability_class": self.answerability_class,
            "corpus_contract_required": self.corpus_contract_required,
            "in_capability_denominator": self.in_capability_denominator,
            "reason": self.reason,
        }


def _legacy_row(case_id: str) -> dict[str, Any]:
    p0 = load_p0_contract()
    for row in p0["case_migration_table"]:
        if row["case_id"] == case_id:
            return row
    raise KeyError(case_id)


def build_migration_audits() -> tuple[LegacyMigrationAudit, ...]:
    audits: list[LegacyMigrationAudit] = []
    for case_id in LEGACY_ADV20_CASE_IDS:
        row = _legacy_row(case_id)
        if case_id == "GQ-104":
            outcome = "NEEDS_NEW_FIXTURE"
            reason = "Invalid corpus under legacy GOLDEN_MD; P1 provides ADV-P1-UNA-001 as independent fixture."
        elif case_id == "GQ-110":
            outcome = "STILL_INVALID"
            reason = "List-all expectation invalid; needs inventory contract not satisfied in V1.0 P1."
        elif row["migration_class"] == "MIGRATABLE_WITH_CONTRACT":
            outcome = "MIGRATED_VALID"
            reason = (
                "Policy-only answerability assignable from query; sidecar contract "
                "without corpus proof requirement."
            )
        else:
            outcome = "OTHER"
            reason = row["reason"]
        audits.append(
            LegacyMigrationAudit(
                case_id=case_id,
                migration_outcome=outcome,
                answerability_class=row["answerability"],
                corpus_contract_required=row["corpus_contract_required"],
                in_capability_denominator=False,
                reason=reason,
            )
        )
    return tuple(audits)


MIGRATION_AUDITS = build_migration_audits()
MIGRATION_AUDIT_BY_ID = {a.case_id: a for a in MIGRATION_AUDITS}


def legacy_sidecar_hash(case_id: str) -> str:
    golden = json.loads(_LEGACY_GOLDEN.read_text(encoding="utf-8"))
    for case in golden["cases"]:
        if case["case_id"] == case_id:
            payload = {
                "case_id": case["case_id"],
                "query": case["query"],
                "expected_doc": case.get("expected_doc", "none"),
                "expected_chunk": case["expected_chunk"],
            }
            return hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
    raise KeyError(case_id)

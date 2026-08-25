"""W10 E-B41 — T1 companion binding & candidate evaluation (protocol only).

Deterministic. No LLM / API / LM Studio / NLI / embeddings.
Does not write Formal T1 results or enter Formal Observation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

PROTOCOL_VERSION = "w10_eb41_t1_companion_v1"
ARTIFACT_KIND = "t1_companion_candidate_evaluation"
FROZEN_BASE_SHA = "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
PARENT_ACQUISITION_RUN = "w10_showcase_narrow_eb38_20260825T085526Z"
COMPANION_RUN_PATTERN_PREFIX = "w10_showcase_narrow_"
T1_SAME_EXECUTION_BINDING_REQUIRED = True

E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
FORMAL_OBSERVATION = "NOT_STARTED"
FORMAL_T1_RESULT_WRITTEN = "NO"

REPO_ROOT = Path(__file__).resolve().parents[2]
EB41_DIR = (
    REPO_ROOT
    / "docs"
    / "research"
    / "w10-eb41-t1-companion-reacquisition"
)
EB41_RECORDS_DIR = EB41_DIR / "records"
EB41_MANIFEST_PATH = EB41_DIR / "companion-run-manifest.json"
RESERVED_FORMAL_NAMES = (
    "FORMAL_OBSERVATION_RESULT",
    "FORMAL_T1_SCORE_RESULT",
    "FORMAL_T1_RESULT",
)


class T1CandidateVerdict(str, Enum):
    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    INELIGIBLE = "INELIGIBLE"
    BINDING_INVALID = "BINDING_INVALID"


class EdgeCaseKind(str, Enum):
    BOTH_EMPTY = "empty_scope_and_empty_citations"
    EMPTY_SCOPE_NONEMPTY_CITATIONS = "empty_scope_nonempty_citations"
    OUT_OF_SCOPE_CITATION = "out_of_scope_citation"
    DUPLICATE_CITATION_IDS = "duplicate_citation_ids"
    NONEMPTY_BOTH = "nonempty_scope_and_citations"
    DEGRADED_WITH_CITATIONS = "degraded_with_citations"


@dataclass(frozen=True, slots=True)
class T1CandidateResult:
    case_id: str
    case_id_short: str
    t1_input_binding_valid: bool
    same_trajectory: bool
    gated_scope_ids: tuple[str, ...]
    final_citation_ids: tuple[str, ...]
    final_citation_ids_unique: tuple[str, ...]
    out_of_scope_ids: tuple[str, ...]
    subset_holds: bool
    edge_cases: tuple[str, ...]
    candidate_verdict: T1CandidateVerdict
    response_mode: str | None
    notes: str
    # Explicit: not Formal
    is_formal_t1_result: bool = False


class T1CompanionError(ValueError):
    """Raised for protocol violations in E-B41 candidate evaluation."""


def canonicalize_chunk_id(value: Any) -> str:
    return str(value).strip().lower()


def load_companion_manifest() -> dict[str, Any]:
    return json.loads(EB41_MANIFEST_PATH.read_text(encoding="utf-8"))


def load_companion_record(short: str) -> dict[str, Any]:
    if short == "C12":
        path = EB41_RECORDS_DIR / "C12.INELIGIBLE.json"
    else:
        path = EB41_RECORDS_DIR / f"{short}.json"
    if not path.is_file():
        raise T1CompanionError(f"missing companion record: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_no_formal_result_artifacts(root: Path | None = None) -> None:
    base = root or EB41_DIR
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        for reserved in RESERVED_FORMAL_NAMES:
            if reserved in name:
                raise T1CompanionError(f"forbidden formal artifact present: {path}")


def assert_scope_not_inferred_from_citations(record: Mapping[str, Any]) -> None:
    prov = record.get("plan_scope_provenance") or {}
    if prov.get("inferred_from_final_citations") is True:
        raise T1CompanionError("gated scope must not be inferred from final citations")
    if prov.get("synthetic_fixture_scope") is True:
        raise T1CompanionError("synthetic fixture scope forbidden")
    if prov.get("gold_constructed") is True:
        raise T1CompanionError("gold-constructed scope forbidden")
    if prov.get("eb18_compat") is True:
        raise T1CompanionError("E-B18 compat scope forbidden")
    owner = str(prov.get("owner") or "")
    if owner != "gen_plan.gated_chunks":
        raise T1CompanionError(f"unexpected scope owner: {owner!r}")


def validate_same_trajectory_binding(record: Mapping[str, Any]) -> bool:
    if not record.get("same_trajectory_binding"):
        return False
    if T1_SAME_EXECUTION_BINDING_REQUIRED and not record.get(
        "T1_SAME_EXECUTION_BINDING_REQUIRED"
    ):
        return False
    src = str(record.get("final_citation_source") or "")
    if "same-run" not in src and "same trajectory" not in src.lower():
        return False
    # Cross-run splice indicators
    if record.get("final_citation_source_kind") == "eb38_cross_run":
        return False
    return True


def compute_subset(
    final_citation_ids: Sequence[str],
    gated_scope_ids: Sequence[str],
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Return (subset_holds, unique_final_ids, out_of_scope_ids).

    Duplicate citation ids are canonicalized; subset uses set membership.
    Empty ⊆ empty is True (vacuous). Empty scope + nonempty finals → False.
    """
    finals = [canonicalize_chunk_id(x) for x in final_citation_ids]
    scope = [canonicalize_chunk_id(x) for x in gated_scope_ids]
    unique_finals = tuple(dict.fromkeys(finals))  # preserve order, drop dups
    scope_set = set(scope)
    out = tuple(cid for cid in unique_finals if cid not in scope_set)
    holds = len(out) == 0
    return holds, unique_finals, out


def classify_edge_cases(
    *,
    gated_scope_ids: Sequence[str],
    final_citation_ids: Sequence[str],
    response_mode: str | None,
    out_of_scope_ids: Sequence[str],
) -> tuple[str, ...]:
    edges: list[str] = []
    scope_empty = len(gated_scope_ids) == 0
    cites_empty = len(final_citation_ids) == 0
    if scope_empty and cites_empty:
        edges.append(EdgeCaseKind.BOTH_EMPTY.value)
    elif scope_empty and not cites_empty:
        edges.append(EdgeCaseKind.EMPTY_SCOPE_NONEMPTY_CITATIONS.value)
    elif not scope_empty and not cites_empty:
        edges.append(EdgeCaseKind.NONEMPTY_BOTH.value)
    if len(final_citation_ids) != len(set(final_citation_ids)):
        edges.append(EdgeCaseKind.DUPLICATE_CITATION_IDS.value)
    if out_of_scope_ids:
        edges.append(EdgeCaseKind.OUT_OF_SCOPE_CITATION.value)
    if response_mode == "DEGRADED" and not cites_empty:
        edges.append(EdgeCaseKind.DEGRADED_WITH_CITATIONS.value)
    return tuple(edges)


def evaluate_t1_candidate(record: Mapping[str, Any]) -> T1CandidateResult:
    """Build T1_CANDIDATE_RESULT — never Formal T1."""
    short = str(record.get("case_id_short") or "")
    case_id = str(record.get("case_id") or "")

    if record.get("status") == "INELIGIBLE_NOT_SCORED" or short == "C12":
        return T1CandidateResult(
            case_id=case_id or "C12-out-of-scope-provenance",
            case_id_short="C12",
            t1_input_binding_valid=False,
            same_trajectory=False,
            gated_scope_ids=(),
            final_citation_ids=(),
            final_citation_ids_unique=(),
            out_of_scope_ids=(),
            subset_holds=False,
            edge_cases=(),
            candidate_verdict=T1CandidateVerdict.INELIGIBLE,
            response_mode=None,
            notes="C12 INELIGIBLE_NOT_SCORED; excluded before companion execution",
            is_formal_t1_result=False,
        )

    if str(record.get("base_sha")) != FROZEN_BASE_SHA:
        raise T1CompanionError(f"base_sha mismatch for {short}")

    assert_scope_not_inferred_from_citations(record)
    same_traj = validate_same_trajectory_binding(record)

    gated = tuple(
        canonicalize_chunk_id(x) for x in (record.get("gated_scope_ids") or [])
    )
    finals_raw = [
        canonicalize_chunk_id(x) for x in (record.get("final_citation_ids") or [])
    ]
    # Also accept citations[].chunk_id if final_citation_ids absent
    if not finals_raw and record.get("citations"):
        finals_raw = [
            canonicalize_chunk_id(c.get("chunk_id"))
            for c in record["citations"]
            if isinstance(c, Mapping) and c.get("chunk_id")
        ]
    finals = tuple(finals_raw)

    binding_valid = bool(
        same_traj
        and record.get("gated_scope_hash")
        and record.get("plan_scope_provenance")
        and record.get("llm_called_observed") is False
        and str(record.get("capture_mode")) == "product_stream"
    )

    holds, unique_finals, out = compute_subset(finals, gated)
    response_mode = record.get("response_mode")
    if isinstance(response_mode, str):
        mode: str | None = response_mode
    else:
        mode = None

    edges = classify_edge_cases(
        gated_scope_ids=gated,
        final_citation_ids=finals,
        response_mode=mode,
        out_of_scope_ids=out,
    )

    if not binding_valid:
        verdict = T1CandidateVerdict.BINDING_INVALID
        note = "same-trajectory binding or provenance incomplete"
    elif holds:
        verdict = T1CandidateVerdict.COMPLIANT
        note = "final_citation_ids ⊆ gated_scope_ids (candidate only)"
    else:
        verdict = T1CandidateVerdict.VIOLATION
        note = f"out_of_scope_ids={list(out)}"

    # DEGRADED must NOT skip T1
    if mode == "DEGRADED" and verdict == T1CandidateVerdict.INELIGIBLE:
        raise T1CompanionError("DEGRADED must not auto-exclude T1")

    return T1CandidateResult(
        case_id=case_id,
        case_id_short=short,
        t1_input_binding_valid=binding_valid,
        same_trajectory=same_traj,
        gated_scope_ids=gated,
        final_citation_ids=finals,
        final_citation_ids_unique=unique_finals,
        out_of_scope_ids=out,
        subset_holds=holds if binding_valid else False,
        edge_cases=edges,
        candidate_verdict=verdict,
        response_mode=mode,
        notes=note,
        is_formal_t1_result=False,
    )


def evaluate_suite() -> list[T1CandidateResult]:
    rows: list[T1CandidateResult] = []
    for i in range(1, 12):
        rows.append(evaluate_t1_candidate(load_companion_record(f"C{i:02d}")))
    rows.append(evaluate_t1_candidate(load_companion_record("C12")))
    return rows


def candidate_summary(rows: Sequence[T1CandidateResult] | None = None) -> dict[str, Any]:
    rows = list(rows) if rows is not None else evaluate_suite()
    eligible = [r for r in rows if r.candidate_verdict != T1CandidateVerdict.INELIGIBLE]
    compliant = [
        r for r in eligible if r.candidate_verdict == T1CandidateVerdict.COMPLIANT
    ]
    violations = [
        r for r in eligible if r.candidate_verdict == T1CandidateVerdict.VIOLATION
    ]
    binding_invalid = [
        r for r in eligible if r.candidate_verdict == T1CandidateVerdict.BINDING_INVALID
    ]
    all_bound = all(r.t1_input_binding_valid for r in eligible)
    capture_valid = all_bound and len(binding_invalid) == 0 and len(eligible) == 11

    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "is_formal_t1_result": False,
        "eligible_count": len(eligible),
        "candidate_compliant_count": len(compliant),
        "candidate_violation_count": len(violations),
        "candidate_binding_invalid_count": len(binding_invalid),
        "c12_status": "INELIGIBLE_NOT_SCORED",
        "T1_INPUT_BINDING_VALID": "YES" if all_bound else "NO",
        "T1_COMPANION_CAPTURE_VALID": "YES" if capture_valid else "NO",
        "T1_REAL_AFTER_INPUT_READY": "YES" if capture_valid else "NO",
        "T1_COMPANION_REACQUISITION_EXECUTED": "YES",
        "T2_REAL_AFTER_INPUT_READY": "NOT_APPLICABLE",
        "T3_REAL_AFTER_INPUT_READY": "NOT_APPLICABLE",
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "FORMAL_OBSERVATION": FORMAL_OBSERVATION,
        "FORMAL_T1_RESULT_WRITTEN": FORMAL_T1_RESULT_WRITTEN,
        "gold_kind_synthetic_authored_is_t1_blocker": False,
        "per_case": [
            {
                "case_id_short": r.case_id_short,
                "T1_INPUT_BINDING_VALID": "YES" if r.t1_input_binding_valid else "NO",
                "candidate_verdict": r.candidate_verdict.value,
                "subset_holds": r.subset_holds,
                "response_mode": r.response_mode,
                "edge_cases": list(r.edge_cases),
                "is_formal_t1_result": False,
            }
            for r in rows
        ],
    }


def gold_dependency_note() -> dict[str, Any]:
    """T1 scope compliance does not require synthetic_authored claim gold."""
    return {
        "t1_depends_on_synthetic_authored_gold": False,
        "gold_kind_synthetic_authored_is_t1_blocker": False,
        "note": (
            "T1 candidate checks final_citation_ids ⊆ gated_scope_ids from "
            "product trajectory; claim gold is out of scope for this window."
        ),
        "protocol_coupling_if_frozen_scorer_requires_gold": (
            "If a future Formal T1 scorer entrypoint still requires claim gold, "
            "report protocol coupling — do not silently repair in this window."
        ),
    }

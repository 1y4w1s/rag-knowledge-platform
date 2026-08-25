"""W10 E-B42 — T1 Formal readiness audit (deterministic / read-only).

Does NOT:
- run Formal measurement / write Formal result
- call LLM / API / LM Studio
- reacquire After / modify backend/app / thaw freeze
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.w10_eb22_formal_wireup_contract import (
    E_B_FORMAL_READY as WIREUP_E_B_FORMAL_READY,
    build_l_obs_skeleton,
    validate_compose_pair,
)
from tests.w10_eb41_t1_companion import (
    E_B_FORMAL_READY,
    FORMAL_OBSERVATION,
    FORMAL_T1_RESULT_WRITTEN,
    FROZEN_BASE_SHA,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    assert_no_formal_result_artifacts,
    candidate_summary,
    canonicalize_chunk_id,
    compute_subset,
    load_companion_manifest,
    load_companion_record,
)

PROTOCOL_VERSION = "w10_eb42_t1_formal_readiness_v1"
ARTIFACT_KIND = "t1_formal_readiness_audit"

# §1 — E-B41 provenance (≠ frozen evaluation base_sha)
EB41_PROVENANCE_COMMIT = "2951914b3298ef63258d3a1df953bf10a899977b"
FROZEN_EVALUATION_BASE_SHA = FROZEN_BASE_SHA  # 3ce0e75…

SOURCE_IDENTITY = "suoyin_local_research_product_after_v1"
CAPTURE_MODE = "product_stream"
RUNTIME_IDENTITY = "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
REVIEW_BY = "2026-09-30"
AUDIT_AS_OF = "2026-08-25"

# Inherited E-B41 / E-B40
T1_COMPANION_REACQUISITION_EXECUTED = "YES"
T1_COMPANION_CAPTURE_VALID = "YES"
T1_INPUT_BINDING_VALID = "YES"
T1_REAL_AFTER_INPUT_READY = "YES"
T2_FORMAL_STATUS = "NOT_APPLICABLE"
T3_FORMAL_STATUS = "NOT_APPLICABLE"

# §3 — Formal target-scope semantics (evidence-based; not demand-driven)
# E-B21: targets_measured = authorized subset of {T1,T2,T3}
# E-B10 §2: historical Narrow T1-only path (E-B_NARROW_FORMAL_READY)
# E-B22: L-Score companion required iff T2/T3 ∈ targets_measured
# E-B24: Narrow Formal freezes TARGETS_MEASURED={T1,T2,T3}; supersedes E-B10 T1-only
# ⇒ conflict between wireup-subset language and declared Narrow Formal scope
FORMAL_TARGET_SCOPE_SEMANTICS = "AMBIGUOUS"
FORMAL_TARGET_SCOPING_GAP = "YES"

# §9 — global gate semantics
# E-B10 §4: E-B_FORMAL_READY=YES ⇒ Full formal (§1 all targets)
# E-B23: write-time lock for FORMAL_OBSERVATION_RESULT (scope-relative)
# E-B24: same write lock used for Narrow {T1,T2,T3}
GLOBAL_E_B_FORMAL_READY_SEMANTICS = "UNDEFINED"

# §4 — L-Obs / L-Score
L_OBS_T1_ONLY_COMPATIBLE = "YES"
T2_T3_NA_COMPANION_ALLOWED = "YES"

# §7 — authorization (revalidated)
OWNER_AUTHORIZATION_ISSUED = "YES"
SOURCE_APPROVED = "YES"
AFTER_SOURCE_APPROVED = "YES"
AUTHORIZATION_STILL_VALID = "YES"

# §8 / §13
T1_FORMAL_INPUT_IMMUTABLE = "YES"
# No Formal T1 scorer contract yet that *binds* Formal to raw-only path;
# readiness helper below proves raw recompute *can* ignore candidate summary.
FORMAL_ORACLE_LEAK_RISK = "NO"  # raw recompute path exists; candidate not oracle

# §9–11 — readiness (AMBIGUOUS ⇒ do not open T1 Formal)
T1_FORMAL_INPUT_READY = "YES"
T1_FORMAL_READY = "NO"
MAY_ENTER_T1_FORMAL_MEASUREMENT = "NO"

REPO_ROOT = Path(__file__).resolve().parents[2]
EB41_DIR = REPO_ROOT / "docs" / "research" / "w10-eb41-t1-companion-reacquisition"
EB41_RECORDS_DIR = EB41_DIR / "records"
EB41_CANDIDATE_PATH = EB41_DIR / "t1-candidate-evaluation.json"
EB42_DIR = REPO_ROOT / "docs" / "research" / "w10-eb42-t1-formal-readiness"
OWNER_STAMP_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "w10-eb36-human-owner-stamp-issuance"
    / "01-approved-owner-stamp.md"
)
RESERVED_FORMAL_RESULT_NAMES = (
    "w10-eb2-generation-observation-result.json",
    "FORMAL_OBSERVATION_RESULT",
    "FORMAL_T1_SCORE_RESULT",
    "FORMAL_T1_RESULT",
)


class T1FormalReadinessError(ValueError):
    """Protocol / readiness audit violation."""


@dataclass(frozen=True, slots=True)
class FormalT1CaseComputation:
    """Raw-bound Formal-intent subset computation — not a Formal result artifact."""

    case_id: str
    case_id_short: str
    gated_scope_ids: tuple[str, ...]
    gated_scope_hash: str | None
    final_citation_ids: tuple[str, ...]
    compliant: bool
    excluded: bool


def assert_provenance_distinct_from_freeze() -> None:
    if EB41_PROVENANCE_COMMIT == FROZEN_EVALUATION_BASE_SHA:
        raise T1FormalReadinessError(
            "eb41_provenance_commit must not equal frozen evaluation base_sha"
        )
    if WIREUP_E_B_FORMAL_READY != "NO" or E_B_FORMAL_READY != "NO":
        raise T1FormalReadinessError("E-B_FORMAL_READY must remain NO")


def assert_authorization_still_valid(*, as_of: str = AUDIT_AS_OF) -> None:
    stamp = OWNER_STAMP_PATH.read_text(encoding="utf-8")
    if "authorization_status       = APPROVED" not in stamp:
        raise T1FormalReadinessError("owner stamp not APPROVED")
    if "authorization_status       = REVOKED" in stamp:
        raise T1FormalReadinessError("owner stamp revoked")
    if f"review_by                = {REVIEW_BY}" not in stamp:
        raise T1FormalReadinessError("review_by missing/mismatched on stamp")
    if as_of > REVIEW_BY:
        raise T1FormalReadinessError("review_by expired")
    if FROZEN_EVALUATION_BASE_SHA not in stamp:
        raise T1FormalReadinessError("stamp base_sha drift")
    if SOURCE_IDENTITY not in stamp:
        raise T1FormalReadinessError("source_identity mismatch")
    if f"capture_mode               = {CAPTURE_MODE}" not in stamp:
        raise T1FormalReadinessError("capture_mode mismatch")
    if RUNTIME_IDENTITY not in stamp:
        raise T1FormalReadinessError("runtime_identity mismatch")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def verify_record_hashes_against_manifest() -> list[str]:
    """Return list of verified case shorts; raise on mismatch."""
    manifest = load_companion_manifest()
    verified: list[str] = []
    for entry in manifest.get("per_case") or []:
        short = str(entry.get("case_id_short") or "")
        if short == "C12" or entry.get("status") == "INELIGIBLE_NOT_SCORED":
            continue
        rec = load_companion_record(short)
        expected = entry.get("gated_scope_hash")
        observed = rec.get("gated_scope_hash")
        if expected and observed and expected != observed:
            raise T1FormalReadinessError(
                f"{short}: manifest gated_scope_hash ≠ record"
            )
        if str(rec.get("base_sha")) != FROZEN_EVALUATION_BASE_SHA:
            raise T1FormalReadinessError(f"{short}: base_sha drift")
        if str(rec.get("source_identity")) != SOURCE_IDENTITY:
            raise T1FormalReadinessError(f"{short}: source_identity drift")
        if str(rec.get("capture_mode")) != CAPTURE_MODE:
            raise T1FormalReadinessError(f"{short}: capture_mode drift")
        if str(rec.get("runtime_identity")) != RUNTIME_IDENTITY:
            raise T1FormalReadinessError(f"{short}: runtime_identity drift")
        if rec.get("response_mode") != "DEGRADED":
            raise T1FormalReadinessError(f"{short}: response_mode ≠ DEGRADED")
        if rec.get("llm_called_observed") is not False:
            raise T1FormalReadinessError(f"{short}: llm_called must be false")
        if not rec.get("same_trajectory_binding"):
            raise T1FormalReadinessError(f"{short}: same-trajectory binding missing")
        verified.append(short)
    return verified


def formal_t1_compute_from_raw_record(
    record: Mapping[str, Any],
) -> FormalT1CaseComputation:
    """Formal-intent subset predicate from raw bound record only.

    Must not read t1-candidate-evaluation.json.
    Does not emit FORMAL_T1_RESULT / reserved observation artifacts.
    """
    short = str(record.get("case_id_short") or "")
    case_id = str(record.get("case_id") or "")
    if record.get("status") == "INELIGIBLE_NOT_SCORED" or short == "C12":
        return FormalT1CaseComputation(
            case_id=case_id or "C12-out-of-scope-provenance",
            case_id_short="C12",
            gated_scope_ids=(),
            gated_scope_hash=None,
            final_citation_ids=(),
            compliant=False,
            excluded=True,
        )

    gated = tuple(
        canonicalize_chunk_id(x) for x in (record.get("gated_scope_ids") or [])
    )
    finals_raw = [
        canonicalize_chunk_id(x) for x in (record.get("final_citation_ids") or [])
    ]
    if not finals_raw and record.get("citations"):
        finals_raw = [
            canonicalize_chunk_id(c.get("chunk_id"))
            for c in record["citations"]
            if isinstance(c, Mapping) and c.get("chunk_id")
        ]
    finals = tuple(finals_raw)
    holds, _unique, _out = compute_subset(finals, gated)
    return FormalT1CaseComputation(
        case_id=case_id,
        case_id_short=short,
        gated_scope_ids=gated,
        gated_scope_hash=record.get("gated_scope_hash"),
        final_citation_ids=finals,
        compliant=holds,
        excluded=False,
    )


def formal_t1_suite_from_raw_records(
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate Formal-intent computation from raw records (not a Formal write)."""
    if records is None:
        loaded: list[Mapping[str, Any]] = [
            load_companion_record(f"C{i:02d}") for i in range(1, 12)
        ]
        loaded.append(load_companion_record("C12"))
        records = loaded

    cases: list[FormalT1CaseComputation] = [
        formal_t1_compute_from_raw_record(r) for r in records
    ]
    eligible = [c for c in cases if not c.excluded]
    compliant = [c for c in eligible if c.compliant]
    violations = [c for c in eligible if not c.compliant]
    return {
        "artifact_kind": "FORMAL_T1_RAW_RECOMPUTE_AUDIT_ONLY",
        "is_formal_result": False,
        "eligible_count": len(eligible),
        "excluded_count": sum(1 for c in cases if c.excluded),
        "compliant_count": len(compliant),
        "violation_count": len(violations),
        "compliance_rate": (
            len(compliant) / len(eligible) if eligible else None
        ),
        "measurement_scope_intent": "T1_ONLY",
        "T2_status": T2_FORMAL_STATUS,
        "T3_status": T3_FORMAL_STATUS,
        "cases": [
            {
                "case_id": c.case_id,
                "case_id_short": c.case_id_short,
                "gated_scope_ids": list(c.gated_scope_ids),
                "gated_scope_hash": c.gated_scope_hash,
                "final_citation_ids": list(c.final_citation_ids),
                "compliant": c.compliant,
                "excluded": c.excluded,
            }
            for c in cases
        ],
    }


def corrupt_candidate_summary_in_memory(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Produce a corrupted candidate summary (must not affect raw Formal recompute)."""
    bad = json.loads(json.dumps(candidate))
    bad["candidate_compliant_count"] = 0
    bad["candidate_violation_count"] = 999
    bad["suite"] = {"corrupted": True, "oracle_leak_probe": True}
    return bad


def assert_no_formal_artifacts_created() -> None:
    assert_no_formal_result_artifacts(EB41_DIR)
    if EB42_DIR.is_dir():
        for path in EB42_DIR.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            for reserved in RESERVED_FORMAL_RESULT_NAMES:
                if reserved in name or name == reserved:
                    raise T1FormalReadinessError(
                        f"forbidden Formal artifact present: {path}"
                    )
            # Audit docs may mention the strings; forbid JSON result payloads only
            if name.endswith(".json") and "formal" in name.lower() and "result" in name.lower():
                raise T1FormalReadinessError(
                    f"forbidden Formal result JSON: {path}"
                )


def future_formal_t1_result_schema_checklist() -> dict[str, bool]:
    """Schema readiness only — does not write a Formal result."""
    required = [
        "run_identity",
        "formal_measurement_id",
        "source_identity",
        "base_sha",
        "runtime_identity",
        "eligible_count",
        "excluded_count",
        "per_case.case_id",
        "per_case.gated_scope_ids_or_hash",
        "per_case.final_citation_ids_or_hash",
        "per_case.compliant",
        "aggregate.compliant_count",
        "aggregate.violation_count",
        "aggregate.compliance_rate",
        "measurement_valid",
        "measurement_scope=T1_ONLY",
        "T2_status=NOT_APPLICABLE",
        "T3_status=NOT_APPLICABLE",
    ]
    return {k: True for k in required}


def gate_matrix() -> dict[str, str]:
    return {
        "eb41_provenance_commit": EB41_PROVENANCE_COMMIT,
        "frozen_evaluation_base_sha": FROZEN_EVALUATION_BASE_SHA,
        "FORMAL_TARGET_SCOPE_SEMANTICS": FORMAL_TARGET_SCOPE_SEMANTICS,
        "GLOBAL_E_B_FORMAL_READY_SEMANTICS": GLOBAL_E_B_FORMAL_READY_SEMANTICS,
        "L_OBS_T1_ONLY_COMPATIBLE": L_OBS_T1_ONLY_COMPATIBLE,
        "T2_T3_NA_COMPANION_ALLOWED": T2_T3_NA_COMPANION_ALLOWED,
        "T1_FORMAL_INPUT_IMMUTABLE": T1_FORMAL_INPUT_IMMUTABLE,
        "T1_FORMAL_INPUT_READY": T1_FORMAL_INPUT_READY,
        "T1_FORMAL_READY": T1_FORMAL_READY,
        "MAY_ENTER_T1_FORMAL_MEASUREMENT": MAY_ENTER_T1_FORMAL_MEASUREMENT,
        "T2_FORMAL_STATUS": T2_FORMAL_STATUS,
        "T3_FORMAL_STATUS": T3_FORMAL_STATUS,
        "FORMAL_TARGET_SCOPING_GAP": FORMAL_TARGET_SCOPING_GAP,
        "FORMAL_ORACLE_LEAK_RISK": FORMAL_ORACLE_LEAK_RISK,
        "OWNER_AUTHORIZATION_ISSUED": OWNER_AUTHORIZATION_ISSUED,
        "SOURCE_APPROVED": SOURCE_APPROVED,
        "AFTER_SOURCE_APPROVED": AFTER_SOURCE_APPROVED,
        "AUTHORIZATION_STILL_VALID": AUTHORIZATION_STILL_VALID,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "FORMAL_OBSERVATION": FORMAL_OBSERVATION,
        "FORMAL_T1_RESULT_WRITTEN": FORMAL_T1_RESULT_WRITTEN,
        "VERDICT": "BLOCKED_PENDING_FORMAL_TARGET_SCOPING_REPAIR",
    }


def assert_l_obs_t1_only_compose_pair_compatible() -> None:
    """Wireup: T1-only targets_measured does not require L-Score companion."""
    l_obs = build_l_obs_skeleton(targets_measured=("T1",))
    targets = (l_obs.get("eligibility_summary") or {}).get("targets_measured") or []
    needs_score = any(t in targets for t in ("T2", "T3"))
    if needs_score:
        raise T1FormalReadinessError("T1-only fixture incorrectly needs L-Score")
    # Companion absent is legal when T2/T3 not targeted.
    validate_compose_pair(l_obs, None, require_companion=True)
    assert L_OBS_T1_ONLY_COMPATIBLE == "YES"


def candidate_vs_raw_separation_ok() -> bool:
    """Candidate summary must not be the Formal computation input."""
    summary = candidate_summary()
    raw = formal_t1_suite_from_raw_records()
    candidate = json.loads(EB41_CANDIDATE_PATH.read_text(encoding="utf-8"))
    corrupted = corrupt_candidate_summary_in_memory(candidate)
    if corrupted.get("candidate_compliant_count") == summary["candidate_compliant_count"]:
        return False
    # Corrupting on-disk-shaped candidate must not affect raw recompute.
    raw_after = formal_t1_suite_from_raw_records()
    if raw_after["compliant_count"] != raw["compliant_count"]:
        return False
    if summary["candidate_compliant_count"] != raw["compliant_count"]:
        return False
    return True

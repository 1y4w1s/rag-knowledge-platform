"""W10 E-B43 — Formal Target Scope v2 (versioned successor to E-B42).

Resolves FORMAL_TARGET_SCOPE_SEMANTICS=AMBIGUOUS without rewriting
historical E-B21 / E-B24 / E-B42 conclusions.

Does NOT:
- run Formal Measurement / write reserved Formal result
- call LLM / API / LM Studio
- flip historical E-B_FORMAL_READY
- modify backend/app / frozen baseline / E-B21·E-B22 modules
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.w10_eb22_formal_wireup_contract import (
    E_B_FORMAL_READY as HISTORICAL_E_B_FORMAL_READY,
    SUITE_ID as EB2_SUITE_ID,
    build_l_obs_skeleton,
    validate_compose_pair,
)
from tests.w10_eb40_response_mode_gate import (
    ResponseMode,
    refuse_perfect_score_for_non_answer,
    t2_t3_denominator_admits,
)
from tests.w10_eb41_t1_companion import (
    FORMAL_OBSERVATION,
    FORMAL_T1_RESULT_WRITTEN,
    FROZEN_BASE_SHA,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    assert_no_formal_result_artifacts,
    candidate_summary,
    load_companion_manifest,
    load_companion_record,
)
from tests.w10_eb42_t1_formal_readiness import (
    AFTER_SOURCE_APPROVED,
    AUTHORIZATION_STILL_VALID as EB42_AUTH_VALID,
    EB41_CANDIDATE_PATH,
    EB41_DIR,
    EB41_PROVENANCE_COMMIT,
    FORMAL_ORACLE_LEAK_RISK as EB42_ORACLE_LEAK,
    FORMAL_TARGET_SCOPE_SEMANTICS as EB42_SCOPE_SEMANTICS,
    FORMAL_TARGET_SCOPING_GAP as EB42_SCOPING_GAP,
    GLOBAL_E_B_FORMAL_READY_SEMANTICS as EB42_GLOBAL_READY_SEMANTICS,
    OWNER_AUTHORIZATION_ISSUED,
    SOURCE_APPROVED,
    T1_FORMAL_INPUT_IMMUTABLE,
    T1_FORMAL_INPUT_READY as EB42_T1_INPUT_READY,
    assert_authorization_still_valid,
    assert_provenance_distinct_from_freeze,
    corrupt_candidate_summary_in_memory,
    formal_t1_suite_from_raw_records,
    verify_record_hashes_against_manifest,
)

# ---------------------------------------------------------------------------
# Identity / provenance
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B43"
PROTOCOL_VERSION = "w10_eb43_formal_target_scope_v2"
ARTIFACT_KIND = "formal_measurement_scope_v2"
SCOPE_VERSION = "w10_eb43_formal_target_scope_v2"

# §1 — E-B42 provenance (this window's explicit commit; ≠ frozen base_sha)
EB42_PROVENANCE_COMMIT = "8ec8af2b4854722e830ed7333f16323c5e6ec578"
FROZEN_EVALUATION_BASE_SHA = FROZEN_BASE_SHA

SOURCE_IDENTITY = "suoyin_local_research_product_after_v1"
CAPTURE_MODE = "product_stream"
RUNTIME_IDENTITY = "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
OWNER_IDENTITY = "suoyin_project_owner"
AUDIT_AS_OF = "2026-08-25"
FROZEN_AT = "2026-08-25T10:00:00Z"

MEASUREMENT_SCOPE_ID = "w10_showcase_t1_only_v1"
SUITE_ID = "w9_critic_frozen_12"
assert SUITE_ID == EB2_SUITE_ID

RESPONSE_MODE_POLICY_REF = "w10_eb40_response_mode_gate_v1"
AUTHORIZATION_REF = (
    "docs/research/w10-eb36-human-owner-stamp-issuance/01-approved-owner-stamp.md"
)
BINDING_REF = "w10_eb41_t1_companion_v1"

CASE_SCOPE_ELIGIBLE = tuple(f"C{i:02d}" for i in range(1, 12))
CASE_SCOPE_EXCLUDED = ("C12",)
C12_STATUS = "INELIGIBLE_NOT_SCORED"

FORBIDDEN_SCOPE_EXPANSIONS = frozenset(
    {
        "A4",
        "S2_denominator",
        "Local_Model_capability",
        "Research_Benchmark_Track",
    }
)

# ---------------------------------------------------------------------------
# Historical semantics — MUST remain as frozen by prior windows
# ---------------------------------------------------------------------------

# E-B21: targets_measured may be authorized subset (preserved as history)
EB21_TARGETS_MEASURED_MAY_BE_AUTHORIZED_SUBSET = "YES"
# E-B24: historical Narrow scope froze {T1,T2,T3} (preserved as history)
EB24_HISTORICAL_NARROW_SCOPE = frozenset({"T1", "T2", "T3"})
# E-B42: do NOT rewrite to TARGET_SPECIFIC_ALLOWED
FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL = EB42_SCOPE_SEMANTICS  # AMBIGUOUS
FORMAL_TARGET_SCOPING_GAP_HISTORICAL = EB42_SCOPING_GAP  # YES
GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL = EB42_GLOBAL_READY_SEMANTICS  # UNDEFINED
assert FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL == "AMBIGUOUS"
assert GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL == "UNDEFINED"

# Historical global gate — never retroactively reinterpret
E_B_FORMAL_READY = HISTORICAL_E_B_FORMAL_READY  # NO
assert E_B_FORMAL_READY == "NO"

# Compatibility decision (explicit; not silent remap of old gate)
COMPATIBILITY_DECISION = (
    "EXPLICIT_V2_WRITER_NOT_OLD_COMPOSE_UNLOCK:"
    "E_B_FORMAL_READY_V2 does not unlock E-B22 compose_l_obs/compose_l_score; "
    "historical E-B_FORMAL_READY remains NO; Formal T1 Measurement v2 uses "
    "writer_v2 contract (L-Obs T1-only skeleton + T2/T3 companion NOT_APPLICABLE)."
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EB43_DIR = REPO_ROOT / "docs" / "research" / "w10-eb43-formal-target-scope-v2"
RESERVED_FORMAL_RESULT_NAMES = (
    "w10-eb2-generation-observation-result.json",
    "FORMAL_OBSERVATION_RESULT",
    "FORMAL_T1_SCORE_RESULT",
    "FORMAL_T1_RESULT",
    "FORMAL_T2_T3_SCORE_RESULT",
)


class FormalScopeV2Error(ValueError):
    """Formal Scope v2 protocol violation."""


@dataclass(frozen=True, slots=True)
class FormalMeasurementScope:
    """Frozen formal_measurement_scope (v2)."""

    scope_version: str
    measurement_scope_id: str
    authorized_targets: frozenset[str]
    not_applicable_targets: frozenset[str]
    excluded_targets: frozenset[str]
    suite_id: str
    case_scope: tuple[str, ...]
    source_identity: str
    base_sha: str
    runtime_identity: str
    response_mode_policy_ref: str
    authorization_ref: str
    binding_ref: str
    frozen_by: str
    frozen_at: str
    c12_status: str = C12_STATUS
    capture_mode: str = CAPTURE_MODE
    forbidden_expansions: frozenset[str] = field(
        default_factory=lambda: FORBIDDEN_SCOPE_EXPANSIONS
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["authorized_targets"] = sorted(self.authorized_targets)
        d["not_applicable_targets"] = sorted(self.not_applicable_targets)
        d["excluded_targets"] = sorted(self.excluded_targets)
        d["forbidden_expansions"] = sorted(self.forbidden_expansions)
        d["case_scope"] = list(self.case_scope)
        d["measurement_scope"] = measurement_scope_label(self)
        return d


# Exactly-one active registry (module-level; tests may reset via helper)
_ACTIVE_FORMAL_MEASUREMENT_SCOPES: dict[str, FormalMeasurementScope] = {}


def measurement_scope_label(scope: FormalMeasurementScope) -> str:
    auth = frozenset(scope.authorized_targets)
    if auth == frozenset({"T1"}):
        return "T1_ONLY"
    return "CUSTOM:" + "+".join(sorted(auth))


def na_target_contribution(target: str) -> dict[str, Any]:
    """NOT_APPLICABLE semantics — never PASS / 100% / zero-denom success."""
    return {
        "target": target,
        "status": "NOT_APPLICABLE",
        "in_denominator": False,
        "score": None,
        "pass": False,
        "fail": False,
        "perfect": False,
        "in_aggregate": False,
        "equals_pass": False,
        "equals_100_percent": False,
        "equals_zero_denominator_success": False,
    }


def _validate_scope_invariants(scope: FormalMeasurementScope) -> None:
    auth = scope.authorized_targets
    na = scope.not_applicable_targets
    excl = scope.excluded_targets
    if auth & na:
        raise FormalScopeV2Error("authorized ∩ not_applicable must be empty")
    if auth & excl:
        raise FormalScopeV2Error("authorized ∩ excluded must be empty")
    if scope.suite_id != SUITE_ID:
        raise FormalScopeV2Error(f"suite_id must be {SUITE_ID}")
    if scope.scope_version != SCOPE_VERSION:
        raise FormalScopeV2Error("scope_version mismatch")
    if scope.frozen_by != OWNER_IDENTITY:
        raise FormalScopeV2Error("frozen_by must be suoyin_project_owner")
    bad = scope.forbidden_expansions & FORBIDDEN_SCOPE_EXPANSIONS
    if bad != FORBIDDEN_SCOPE_EXPANSIONS:
        raise FormalScopeV2Error("forbidden expansions must remain closed")
    if set(scope.case_scope) != set(CASE_SCOPE_ELIGIBLE):
        raise FormalScopeV2Error("case_scope must be C01–C11 only")
    if scope.c12_status != C12_STATUS:
        raise FormalScopeV2Error("C12 must remain INELIGIBLE_NOT_SCORED")


def freeze_formal_measurement_scope(
    scope: FormalMeasurementScope,
    *,
    registry: dict[str, FormalMeasurementScope] | None = None,
) -> FormalMeasurementScope:
    """Human-authorized freeze; exactly one active formal_measurement_scope."""
    _validate_scope_invariants(scope)
    reg = _ACTIVE_FORMAL_MEASUREMENT_SCOPES if registry is None else registry
    if reg and scope.measurement_scope_id not in reg:
        raise FormalScopeV2Error(
            "exactly one active formal_measurement_scope; "
            f"already active={sorted(reg)}"
        )
    if scope.measurement_scope_id in reg:
        existing = reg[scope.measurement_scope_id]
        if existing != scope:
            raise FormalScopeV2Error("cannot re-freeze with different scope payload")
        return existing
    if len(reg) >= 1:
        raise FormalScopeV2Error("exactly one active formal_measurement_scope")
    reg[scope.measurement_scope_id] = scope
    return scope


def clear_active_scopes_for_tests() -> None:
    """Test-only registry reset."""
    _ACTIVE_FORMAL_MEASUREMENT_SCOPES.clear()


def build_showcase_t1_only_scope() -> FormalMeasurementScope:
    return FormalMeasurementScope(
        scope_version=SCOPE_VERSION,
        measurement_scope_id=MEASUREMENT_SCOPE_ID,
        authorized_targets=frozenset({"T1"}),
        not_applicable_targets=frozenset({"T2", "T3"}),
        excluded_targets=frozenset(),
        suite_id=SUITE_ID,
        case_scope=CASE_SCOPE_ELIGIBLE,
        source_identity=SOURCE_IDENTITY,
        base_sha=FROZEN_EVALUATION_BASE_SHA,
        runtime_identity=RUNTIME_IDENTITY,
        response_mode_policy_ref=RESPONSE_MODE_POLICY_REF,
        authorization_ref=AUTHORIZATION_REF,
        binding_ref=BINDING_REF,
        frozen_by=OWNER_IDENTITY,
        frozen_at=FROZEN_AT,
    )


def ensure_showcase_scope_frozen() -> FormalMeasurementScope:
    """Idempotent freeze of the Showcase T1-only scope."""
    scope = build_showcase_t1_only_scope()
    return freeze_formal_measurement_scope(scope)


def active_formal_measurement_scope() -> FormalMeasurementScope:
    if len(_ACTIVE_FORMAL_MEASUREMENT_SCOPES) != 1:
        raise FormalScopeV2Error(
            f"expected exactly one active scope, got {len(_ACTIVE_FORMAL_MEASUREMENT_SCOPES)}"
        )
    return next(iter(_ACTIVE_FORMAL_MEASUREMENT_SCOPES.values()))


# ---------------------------------------------------------------------------
# Target-specific readiness
# ---------------------------------------------------------------------------


def na_basis_valid(target: str, scope: FormalMeasurementScope) -> bool:
    """E-B40 DEGRADED ⇒ T2/T3 NOT_APPLICABLE with valid basis."""
    if target not in scope.not_applicable_targets:
        return False
    if target not in ("T2", "T3"):
        return False
    if t2_t3_denominator_admits(ResponseMode.DEGRADED):
        return False
    try:
        refuse_perfect_score_for_non_answer(ResponseMode.DEGRADED)
        return False
    except Exception:
        pass  # expected: DEGRADED cannot be perfect
    # Spot-check raw records remain DEGRADED
    for short in CASE_SCOPE_ELIGIBLE:
        rec = load_companion_record(short)
        if rec.get("response_mode") != "DEGRADED":
            return False
    return True


def target_formal_ready(target: str, scope: FormalMeasurementScope | None = None) -> str:
    """TARGET_FORMAL_READY(target) ∈ {YES, NO, NOT_APPLICABLE}."""
    scope = scope or active_formal_measurement_scope()
    if target in scope.not_applicable_targets:
        return "NOT_APPLICABLE" if na_basis_valid(target, scope) else "NO"
    if target not in scope.authorized_targets:
        return "NO"
    if target != "T1":
        return "NO"
    # T1 readiness conjunction
    if EB42_T1_INPUT_READY != "YES":
        return "NO"
    if T1_FORMAL_INPUT_IMMUTABLE != "YES":
        return "NO"
    try:
        assert_authorization_still_valid(as_of=AUDIT_AS_OF)
        verified = verify_record_hashes_against_manifest()
        if len(verified) != 11:
            return "NO"
    except Exception:
        return "NO"
    if EB42_ORACLE_LEAK != "NO":
        return "NO"
    writer = writer_compatibility_report(scope)
    if writer.get("writer_compatibility_ready") != "YES":
        return "NO"
    return "YES"


# ---------------------------------------------------------------------------
# Writer compatibility (reuse E-B22 shape; no fake T2/T3 scores)
# ---------------------------------------------------------------------------


def writer_compatibility_report(
    scope: FormalMeasurementScope | None = None,
) -> dict[str, Any]:
    scope = scope or build_showcase_t1_only_scope()
    l_obs = build_l_obs_skeleton(targets_measured=tuple(sorted(scope.authorized_targets)))
    targets = (l_obs.get("eligibility_summary") or {}).get("targets_measured") or []
    needs_score = any(t in targets for t in ("T2", "T3"))
    validate_compose_pair(l_obs, None, require_companion=True)
    companion_status = (
        "NOT_APPLICABLE"
        if scope.not_applicable_targets >= frozenset({"T2", "T3"}) and not needs_score
        else "REQUIRED"
    )
    return {
        "l_obs_t1_only_shape_ok": measurement_scope_label(scope) == "T1_ONLY",
        "targets_measured": list(targets),
        "T2_T3_COMPANION_STATUS": companion_status,
        "FORMAL_T2_T3_SCORE_RESULT_FABRICATED": "NO",
        "old_compose_l_obs_unlocked": "NO",  # historical gate stays locked
        "historical_E_B_FORMAL_READY": E_B_FORMAL_READY,
        "compatibility_decision": COMPATIBILITY_DECISION,
        "writer_compatibility_ready": "YES"
        if companion_status == "NOT_APPLICABLE"
        and measurement_scope_label(scope) == "T1_ONLY"
        else "NO",
        "schema_extension_layer": "tests_eval_protocol_only",
    }


# ---------------------------------------------------------------------------
# Formal Result v2 contract (dry-run shape only — no reserved write)
# ---------------------------------------------------------------------------


def build_formal_result_v2_dry_run(
    *,
    scope: FormalMeasurementScope | None = None,
    formal_measurement_id: str = "DRY_RUN_NOT_A_FORMAL_MEASUREMENT",
) -> dict[str, Any]:
    """In-memory Formal Result v2 contract from raw E-B41 records.

    Not a Formal Measurement execution. Never persists reserved artifacts.
    Must not read candidate aggregates as oracle.
    """
    scope = scope or ensure_showcase_scope_frozen()
    raw = formal_t1_suite_from_raw_records()
    per_case = []
    for row in raw["cases"]:
        if row.get("excluded"):
            continue
        per_case.append(
            {
                "case_id": row["case_id"],
                "case_id_short": row["case_id_short"],
                "gated_scope_ids": row["gated_scope_ids"],
                "gated_scope_hash": row["gated_scope_hash"],
                "final_citation_ids": row["final_citation_ids"],
                "compliant": row["compliant"],
            }
        )
    return {
        "schema_version": "w10_formal_result_v2",
        "artifact_kind": "FORMAL_RESULT_V2_DRY_RUN_CONTRACT",
        "is_formal_result": False,
        "formal_measurement_executed": False,
        "measurement_scope_id": scope.measurement_scope_id,
        "measurement_scope": measurement_scope_label(scope),
        "formal_measurement_id": formal_measurement_id,
        "source_identity": scope.source_identity,
        "base_sha": scope.base_sha,
        "runtime_identity": scope.runtime_identity,
        "eligible_count": raw["eligible_count"],
        "excluded_count": raw["excluded_count"],
        "per_case": per_case,
        "aggregate": {
            "compliant_count": raw["compliant_count"],
            "violation_count": raw["violation_count"],
            "compliance_rate": raw["compliance_rate"],
        },
        "targets": {
            "T1": "MEASURED" if "T1" in scope.authorized_targets else "NOT_APPLICABLE",
            "T2": "NOT_APPLICABLE",
            "T3": "NOT_APPLICABLE",
        },
        "measurement_valid": False,  # dry-run contract only; Formal not executed
        "notes": (
            "Writer contract dry-run from E-B41 raw records. "
            "FORMAL_OBSERVATION=NOT_STARTED. Do not treat as Formal verdict."
        ),
    }


def oracle_isolation_ok() -> bool:
    """Candidate summary corruption must not alter raw Formal dry-run."""
    before = build_formal_result_v2_dry_run()
    candidate = json.loads(EB41_CANDIDATE_PATH.read_text(encoding="utf-8"))
    corrupted = corrupt_candidate_summary_in_memory(candidate)
    if corrupted.get("candidate_compliant_count") == candidate_summary()[
        "candidate_compliant_count"
    ]:
        return False
    after = build_formal_result_v2_dry_run()
    if after["aggregate"]["compliant_count"] != before["aggregate"]["compliant_count"]:
        return False
    if after["eligible_count"] != 11 or after["excluded_count"] != 1:
        return False
    # Must not treat candidate as Formal verdict
    if candidate.get("is_formal_t1_result") is not False:
        return False
    return True


def assert_no_formal_result_written() -> None:
    assert_no_formal_result_artifacts(EB41_DIR)
    if EB43_DIR.is_dir():
        for path in EB43_DIR.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            for reserved in RESERVED_FORMAL_RESULT_NAMES:
                if reserved in name or name == reserved:
                    raise FormalScopeV2Error(f"forbidden Formal artifact: {path}")
            if (
                name.endswith(".json")
                and "formal" in name.lower()
                and "result" in name.lower()
                and "dry" not in name.lower()
            ):
                raise FormalScopeV2Error(f"forbidden Formal result JSON: {path}")


# ---------------------------------------------------------------------------
# Entry gates (v2)
# ---------------------------------------------------------------------------


def evaluate_entry_gates() -> dict[str, str]:
    """Compute versioned readiness / entry gates. Does not execute Formal."""
    assert_provenance_distinct_from_freeze()
    if EB42_PROVENANCE_COMMIT == FROZEN_EVALUATION_BASE_SHA:
        raise FormalScopeV2Error("eb42 provenance must ≠ frozen base_sha")

    # Preserve historical ambiguity constants
    if FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL != "AMBIGUOUS":
        raise FormalScopeV2Error("E-B42 AMBIGUOUS must remain preserved")

    clear_active_scopes_for_tests()
    scope = ensure_showcase_scope_frozen()
    assert_authorization_still_valid(as_of=AUDIT_AS_OF)
    verify_record_hashes_against_manifest()

    t1 = target_formal_ready("T1", scope)
    t2 = target_formal_ready("T2", scope)
    t3 = target_formal_ready("T3", scope)
    writer = writer_compatibility_report(scope)
    oracle = "NO" if oracle_isolation_ok() else "YES"

    scope_frozen = "YES"
    every_auth_ready = t1 == "YES"
    every_na_ok = t2 == "NOT_APPLICABLE" and t3 == "NOT_APPLICABLE"
    no_unresolved = every_auth_ready and every_na_ok
    auth_ok = EB42_AUTH_VALID == "YES" and OWNER_AUTHORIZATION_ISSUED == "YES"
    input_immut = T1_FORMAL_INPUT_IMMUTABLE == "YES"
    writer_ok = writer["writer_compatibility_ready"] == "YES"

    e_b_formal_ready_v2 = (
        "YES"
        if (
            scope_frozen == "YES"
            and every_auth_ready
            and every_na_ok
            and no_unresolved
            and auth_ok
            and input_immut
            and writer_ok
            and oracle == "NO"
        )
        else "NO"
    )

    may_enter_v2 = (
        "YES"
        if (
            scope_frozen == "YES"
            and t1 == "YES"
            and t2 == "NOT_APPLICABLE"
            and t3 == "NOT_APPLICABLE"
            and auth_ok
            and input_immut
            and writer_ok
            and oracle == "NO"
        )
        else "NO"
    )

    # Alias success symbols (allowed when v2 succeeds)
    t1_formal_ready = t1
    may_enter_t1 = may_enter_v2

    blockers: list[str] = []
    if e_b_formal_ready_v2 != "YES":
        if t1 != "YES":
            blockers.append(f"TARGET_FORMAL_READY(T1)={t1}")
        if t2 != "NOT_APPLICABLE":
            blockers.append(f"T2={t2}")
        if t3 != "NOT_APPLICABLE":
            blockers.append(f"T3={t3}")
        if not auth_ok:
            blockers.append("AUTHORIZATION_INVALID")
        if not writer_ok:
            blockers.append("WRITER_COMPATIBILITY")
        if oracle != "NO":
            blockers.append("ORACLE_LEAK_RISK")

    return {
        "eb42_provenance_commit": EB42_PROVENANCE_COMMIT,
        "eb41_provenance_commit": EB41_PROVENANCE_COMMIT,
        "frozen_evaluation_base_sha": FROZEN_EVALUATION_BASE_SHA,
        "FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL": FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL,
        "GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL": (
            GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL
        ),
        "FORMAL_TARGET_SCOPE_V2_IMPLEMENTED": "YES",
        "FORMAL_SCOPE_V2_FROZEN": scope_frozen,
        "FORMAL_MEASUREMENT_SCOPE": measurement_scope_label(scope),
        "measurement_scope_id": scope.measurement_scope_id,
        "T1_FORMAL_INPUT_READY": EB42_T1_INPUT_READY,
        "T1_FORMAL_READY": t1_formal_ready,
        "T2_FORMAL_STATUS": t2,
        "T3_FORMAL_STATUS": t3,
        "TARGET_FORMAL_READY(T1)": t1,
        "TARGET_FORMAL_READY(T2)": t2,
        "TARGET_FORMAL_READY(T3)": t3,
        "E_B_FORMAL_READY_V2": e_b_formal_ready_v2,
        "MAY_ENTER_T1_FORMAL_MEASUREMENT_V2": may_enter_v2,
        "MAY_ENTER_T1_FORMAL_MEASUREMENT": may_enter_t1,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "FORMAL_OBSERVATION": FORMAL_OBSERVATION,
        "FORMAL_T1_RESULT_WRITTEN": FORMAL_T1_RESULT_WRITTEN,
        "FORMAL_ORACLE_LEAK_RISK": oracle,
        "T2_T3_COMPANION_STATUS": writer["T2_T3_COMPANION_STATUS"],
        "OWNER_AUTHORIZATION_ISSUED": OWNER_AUTHORIZATION_ISSUED,
        "SOURCE_APPROVED": SOURCE_APPROVED,
        "AFTER_SOURCE_APPROVED": AFTER_SOURCE_APPROVED,
        "AUTHORIZATION_STILL_VALID": EB42_AUTH_VALID,
        "COMPATIBILITY_DECISION": COMPATIBILITY_DECISION,
        "EXACT_BLOCKERS": ";".join(blockers) if blockers else "NONE",
        "VERDICT": (
            "READY_FOR_T1_FORMAL_MEASUREMENT"
            if may_enter_v2 == "YES"
            else "BLOCKED"
        ),
    }


def gate_matrix() -> dict[str, str]:
    return evaluate_entry_gates()


# Module import does not auto-freeze; callers / tests freeze explicitly.

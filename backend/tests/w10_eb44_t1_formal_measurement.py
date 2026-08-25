"""W10 E-B44 — T1 Formal Measurement Execution (deterministic).

Executes Formal T1 measurement under frozen scope v2 from immutable E-B41 raw
records. Does NOT use candidate aggregates as oracle.

Does NOT:
- modify backend/app / frozen baseline / E-B41 raw records
- call LLM / API / LM Studio
- score T2/T3 or expand scope
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.w10_eb41_t1_companion import (
    EB41_DIR,
    FROZEN_BASE_SHA,
    canonicalize_chunk_id,
    compute_subset,
    load_companion_manifest,
    load_companion_record,
    validate_same_trajectory_binding,
)
from tests.w10_eb42_t1_formal_readiness import (
    AFTER_SOURCE_APPROVED,
    AUTHORIZATION_STILL_VALID,
    EB41_CANDIDATE_PATH,
    EB41_PROVENANCE_COMMIT,
    OWNER_AUTHORIZATION_ISSUED,
    SOURCE_APPROVED,
    assert_authorization_still_valid,
    corrupt_candidate_summary_in_memory,
    formal_t1_compute_from_raw_record,
    verify_record_hashes_against_manifest,
)
from tests.w10_eb43_formal_target_scope_v2 import (
    AUDIT_AS_OF,
    CAPTURE_MODE,
    MEASUREMENT_SCOPE_ID,
    RUNTIME_IDENTITY,
    SOURCE_IDENTITY,
    SUITE_ID,
    clear_active_scopes_for_tests,
    ensure_showcase_scope_frozen,
    evaluate_entry_gates,
    measurement_scope_label,
)

WINDOW_ID = "E-B44"
PROTOCOL_VERSION = "w10_eb44_t1_formal_measurement_v1"
ARTIFACT_KIND = "formal_t1_measurement_result"
SCHEMA_VERSION = "w10_formal_t1_result_v1"

# E-B43 provenance (this window's prerequisite commit; ≠ frozen base_sha)
EB43_PROVENANCE_COMMIT = "07a0dcbea9b676c297f45ef0a6edc54831c4ad16"
FROZEN_EVALUATION_BASE_SHA = FROZEN_BASE_SHA

REPO_ROOT = Path(__file__).resolve().parents[2]
EB44_DIR = REPO_ROOT / "docs" / "research" / "w10-eb44-t1-formal-measurement"
FORMAL_T1_RESULT_PATH = EB44_DIR / "formal-t1-result.json"

RESERVED_FORMAL_COLLISION_NAMES = (
    "w10-eb2-generation-observation-result.json",
    "FORMAL_OBSERVATION_RESULT",
    "FORMAL_T1_SCORE_RESULT",
    "FORMAL_T2_T3_SCORE_RESULT",
)

C12_STATUS = "INELIGIBLE_NOT_SCORED"


class FormalMeasurementError(ValueError):
    """Formal T1 measurement protocol violation."""


@dataclass(frozen=True, slots=True)
class FormalT1PerCase:
    case_id: str
    case_id_short: str
    gated_scope_ids: tuple[str, ...]
    gated_scope_hash: str | None
    final_citation_ids: tuple[str, ...]
    final_citation_hash: str | None
    same_trajectory_binding: bool
    compliant: bool
    violation_ids: tuple[str, ...]
    excluded: bool
    status: str | None = None


def hash_id_list(ids: Sequence[str]) -> str:
    canonical = sorted(canonicalize_chunk_id(x) for x in ids)
    payload = json.dumps(canonical, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def make_formal_measurement_id(measured_at: datetime) -> str:
    stamp = measured_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"w10_t1_formal_{stamp}"


def formal_preflight() -> dict[str, str]:
    """Re-verify all entry gates before Formal measurement."""
    clear_active_scopes_for_tests()
    ensure_showcase_scope_frozen()
    gates = evaluate_entry_gates()

    required_yes = {
        "FORMAL_TARGET_SCOPE_V2_IMPLEMENTED": "YES",
        "FORMAL_SCOPE_V2_FROZEN": "YES",
        "FORMAL_MEASUREMENT_SCOPE": "T1_ONLY",
        "T1_FORMAL_INPUT_READY": "YES",
        "T1_FORMAL_READY": "YES",
        "E_B_FORMAL_READY_V2": "YES",
        "MAY_ENTER_T1_FORMAL_MEASUREMENT": "YES",
        "OWNER_AUTHORIZATION_ISSUED": "YES",
        "SOURCE_APPROVED": "YES",
        "AFTER_SOURCE_APPROVED": "YES",
        "AUTHORIZATION_STILL_VALID": "YES",
    }
    required_na = {
        "T2_FORMAL_STATUS": "NOT_APPLICABLE",
        "T3_FORMAL_STATUS": "NOT_APPLICABLE",
    }

    blockers: list[str] = []
    for key, expected in required_yes.items():
        if gates.get(key) != expected:
            blockers.append(f"{key}={gates.get(key)!r}")
    for key, expected in required_na.items():
        if gates.get(key) != expected:
            blockers.append(f"{key}={gates.get(key)!r}")

    assert_authorization_still_valid(as_of=AUDIT_AS_OF)
    verify_record_hashes_against_manifest()

    passed = len(blockers) == 0
    return {
        **gates,
        "eb43_provenance_commit": EB43_PROVENANCE_COMMIT,
        "eb41_provenance_commit": EB41_PROVENANCE_COMMIT,
        "frozen_evaluation_base_sha": FROZEN_EVALUATION_BASE_SHA,
        "AUTHORIZATION_STILL_VALID": AUTHORIZATION_STILL_VALID,
        "PREFLIGHT_PASS": "YES" if passed else "NO",
        "EXACT_BLOCKERS": ";".join(blockers) if blockers else "NONE",
    }


def compute_formal_per_case(record: Mapping[str, Any]) -> FormalT1PerCase:
    """Per-case Formal computation from raw record only — no candidate oracle."""
    raw = formal_t1_compute_from_raw_record(record)
    short = raw.case_id_short

    if raw.excluded or short == "C12":
        return FormalT1PerCase(
            case_id=raw.case_id or "C12-out-of-scope-provenance",
            case_id_short="C12",
            gated_scope_ids=(),
            gated_scope_hash=None,
            final_citation_ids=(),
            final_citation_hash=None,
            same_trajectory_binding=False,
            compliant=False,
            violation_ids=(),
            excluded=True,
            status=C12_STATUS,
        )

    _holds, _unique, out = compute_subset(raw.final_citation_ids, raw.gated_scope_ids)
    violation_ids = tuple(sorted(out))
    compliant = len(violation_ids) == 0
    same_traj = validate_same_trajectory_binding(record)

    return FormalT1PerCase(
        case_id=raw.case_id,
        case_id_short=short,
        gated_scope_ids=raw.gated_scope_ids,
        gated_scope_hash=raw.gated_scope_hash,
        final_citation_ids=raw.final_citation_ids,
        final_citation_hash=hash_id_list(raw.final_citation_ids),
        same_trajectory_binding=same_traj,
        compliant=compliant,
        violation_ids=violation_ids,
        excluded=False,
        status="MEASURED",
    )


def load_all_raw_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        load_companion_record(f"C{i:02d}") for i in range(1, 12)
    ]
    records.append(load_companion_record("C12"))
    return records


def assert_raw_input_integrity(records: Sequence[Mapping[str, Any]]) -> None:
    manifest = load_companion_manifest()
    if str(manifest.get("base_sha")) != FROZEN_EVALUATION_BASE_SHA:
        raise FormalMeasurementError("manifest base_sha drift")
    if str(manifest.get("source_identity")) != SOURCE_IDENTITY:
        raise FormalMeasurementError("manifest source_identity drift")
    if str(manifest.get("runtime_identity")) != RUNTIME_IDENTITY:
        raise FormalMeasurementError("manifest runtime_identity drift")
    if manifest.get("formal_measurement") is True:
        raise FormalMeasurementError("E-B41 manifest must not be formal_measurement")
    for rec in records:
        short = str(rec.get("case_id_short") or "")
        if short == "C12":
            continue
        if str(rec.get("base_sha")) != FROZEN_EVALUATION_BASE_SHA:
            raise FormalMeasurementError(f"{short}: base_sha drift")
        if rec.get("llm_called_observed") is not False:
            raise FormalMeasurementError(f"{short}: llm_called_observed must be false")
        if rec.get("response_mode") != "DEGRADED":
            raise FormalMeasurementError(f"{short}: response_mode must be DEGRADED")


def build_formal_t1_result(
    *,
    measured_at: datetime | None = None,
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build canonical Formal T1 result from raw records (in-memory)."""
    preflight = formal_preflight()
    if preflight["PREFLIGHT_PASS"] != "YES":
        raise FormalMeasurementError(
            f"preflight failed: {preflight['EXACT_BLOCKERS']}"
        )

    scope = ensure_showcase_scope_frozen()
    records = list(records) if records is not None else load_all_raw_records()
    assert_raw_input_integrity(records)

    when = measured_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    measured_at_iso = when.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    measured_at_iso = measured_at_iso.replace("+00:00", "Z")
    formal_measurement_id = make_formal_measurement_id(when)

    manifest = load_companion_manifest()
    input_run_identity = str(manifest.get("companion_run") or "")

    per_case_rows: list[FormalT1PerCase] = [
        compute_formal_per_case(r) for r in records
    ]
    eligible = [c for c in per_case_rows if not c.excluded]
    compliant_cases = [c for c in eligible if c.compliant]
    violation_cases = [c for c in eligible if not c.compliant]

    if len(eligible) != 11:
        raise FormalMeasurementError(f"eligible_count must be 11, got {len(eligible)}")
    if sum(1 for c in per_case_rows if c.excluded) != 1:
        raise FormalMeasurementError("excluded_count must be 1")

    for case in eligible:
        if not case.same_trajectory_binding:
            raise FormalMeasurementError(
                f"{case.case_id_short}: same_trajectory_binding invalid"
            )

    aggregate = {
        "compliant_count": len(compliant_cases),
        "violation_count": len(violation_cases),
        "compliance_rate": len(compliant_cases) / len(eligible),
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "is_formal_result": True,
        "formal_measurement_executed": True,
        "formal_measurement_id": formal_measurement_id,
        "measurement_scope_id": scope.measurement_scope_id,
        "measurement_scope": measurement_scope_label(scope),
        "measured_at": measured_at_iso,
        "source_identity": SOURCE_IDENTITY,
        "base_sha": FROZEN_EVALUATION_BASE_SHA,
        "runtime_identity": RUNTIME_IDENTITY,
        "capture_mode": CAPTURE_MODE,
        "suite": SUITE_ID,
        "input_run_identity": input_run_identity,
        "input_provenance_commit": EB41_PROVENANCE_COMMIT,
        "eb43_protocol_commit": EB43_PROVENANCE_COMMIT,
        "eligible_count": len(eligible),
        "excluded_count": 1,
        "targets": {
            "T1": {"status": "MEASURED"},
            "T2": {"status": "NOT_APPLICABLE"},
            "T3": {"status": "NOT_APPLICABLE"},
        },
        "per_case": [
            {
                **{k: v for k, v in asdict(c).items()},
                "gated_scope_ids": list(c.gated_scope_ids),
                "final_citation_ids": list(c.final_citation_ids),
                "violation_ids": list(c.violation_ids),
            }
            for c in per_case_rows
        ],
        "aggregate": aggregate,
        "measurement_valid": True,
        "candidate_oracle_used": False,
        "llm_called": False,
        "notes": (
            "Formal T1 measurement from immutable E-B41 raw companion records. "
            "Subset predicate: final_citation_ids ⊆ gated_scope_ids. "
            "C12 excluded before denominator. T2/T3 NOT_APPLICABLE."
        ),
    }
    validate_formal_result_schema(result)
    return result


def validate_formal_result_schema(result: Mapping[str, Any]) -> None:
    required_top = [
        "schema_version",
        "formal_measurement_id",
        "measurement_scope_id",
        "measurement_scope",
        "measured_at",
        "source_identity",
        "base_sha",
        "runtime_identity",
        "input_run_identity",
        "input_provenance_commit",
        "eligible_count",
        "excluded_count",
        "targets",
        "per_case",
        "aggregate",
        "measurement_valid",
    ]
    for key in required_top:
        if key not in result:
            raise FormalMeasurementError(f"missing schema field: {key}")

    if result.get("measurement_scope") != "T1_ONLY":
        raise FormalMeasurementError("measurement_scope must be T1_ONLY")
    if result["targets"]["T1"]["status"] != "MEASURED":
        raise FormalMeasurementError("T1 must be MEASURED")
    for t in ("T2", "T3"):
        if result["targets"][t]["status"] != "NOT_APPLICABLE":
            raise FormalMeasurementError(f"{t} must be NOT_APPLICABLE")
        if "score" in result["targets"][t]:
            raise FormalMeasurementError(f"{t} must not have score")
        if "pass" in result["targets"][t]:
            raise FormalMeasurementError(f"{t} must not have pass field")

    agg = result["aggregate"]
    if agg["compliant_count"] + agg["violation_count"] != result["eligible_count"]:
        raise FormalMeasurementError("aggregate counts inconsistent with eligible")


def formal_oracle_isolation_ok() -> bool:
    """Candidate summary corruption must not alter Formal raw recomputation."""
    before = build_formal_t1_result(
        measured_at=datetime(2026, 8, 25, 10, 30, 0, tzinfo=timezone.utc)
    )
    candidate = json.loads(EB41_CANDIDATE_PATH.read_text(encoding="utf-8"))

    for compliant_override, violation_override in ((0, 11), (11, 0)):
        corrupted = corrupt_candidate_summary_in_memory(candidate)
        corrupted["candidate_compliant_count"] = compliant_override
        corrupted["candidate_violation_count"] = violation_override
        after = build_formal_t1_result(
            measured_at=datetime(2026, 8, 25, 10, 30, 0, tzinfo=timezone.utc)
        )
        if after["aggregate"]["compliant_count"] != before["aggregate"]["compliant_count"]:
            return False
        if after["aggregate"]["violation_count"] != before["aggregate"]["violation_count"]:
            return False
        if after["aggregate"]["compliance_rate"] != before["aggregate"]["compliance_rate"]:
            return False

    if candidate.get("is_formal_t1_result") is not False:
        return False
    return True


def assert_no_conflicting_formal_results(
    *,
    allow_path: Path | None = None,
) -> int:
    """Ensure exactly one canonical Formal T1 result exists."""
    allow = allow_path or FORMAL_T1_RESULT_PATH
    count = 0
    if allow.is_file():
        count += 1

    for root in (EB41_DIR, REPO_ROOT / "docs" / "research"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            if path.resolve() == allow.resolve():
                continue
            name = path.name.lower()
            if any(r.lower() in name for r in RESERVED_FORMAL_COLLISION_NAMES):
                raise FormalMeasurementError(f"reserved formal collision: {path}")
            if (
                "formal" in name
                and "result" in name
                and "dry" not in name
                and "candidate" not in name
                and path.parent.name != "w10-eb44-t1-formal-measurement"
            ):
                if path.name == "formal-t1-result.json":
                    raise FormalMeasurementError(f"duplicate formal result: {path}")
    return count


def write_canonical_formal_result(
    result: Mapping[str, Any],
    *,
    output_dir: Path | None = None,
) -> Path:
    out_dir = output_dir or EB44_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "formal-t1-result.json"
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def execute_formal_t1_measurement(
    *,
    measured_at: datetime | None = None,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Execute Formal T1 measurement and optionally persist canonical result."""
    if not formal_oracle_isolation_ok():
        raise FormalMeasurementError("FORMAL_ORACLE_LEAK_RISK detected")

    result = build_formal_t1_result(measured_at=measured_at)
    if write_artifacts:
        write_canonical_formal_result(result)
        canonical_count = assert_no_conflicting_formal_results()
        if canonical_count != 1:
            raise FormalMeasurementError(
                f"CANONICAL_FORMAL_T1_RESULT_COUNT must be 1, got {canonical_count}"
            )
    return result


def gate_matrix(result: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Post-measurement gate matrix."""
    pre = formal_preflight()
    oracle = "NO" if formal_oracle_isolation_ok() else "YES"
    executed = result is not None
    valid = (
        executed
        and result.get("measurement_valid") is True
        and pre["PREFLIGHT_PASS"] == "YES"
        and oracle == "NO"
        and result.get("candidate_oracle_used") is False
        and result.get("is_formal_result") is True
    )

    agg = (result or {}).get("aggregate") or {}
    return {
        "eb43_provenance_commit": EB43_PROVENANCE_COMMIT,
        "eb41_provenance_commit": EB41_PROVENANCE_COMMIT,
        "frozen_evaluation_base_sha": FROZEN_EVALUATION_BASE_SHA,
        "FORMAL_TARGET_SCOPE_V2_IMPLEMENTED": pre.get(
            "FORMAL_TARGET_SCOPE_V2_IMPLEMENTED", "NO"
        ),
        "FORMAL_SCOPE_V2_FROZEN": pre.get("FORMAL_SCOPE_V2_FROZEN", "NO"),
        "FORMAL_MEASUREMENT_SCOPE": pre.get("FORMAL_MEASUREMENT_SCOPE", "UNKNOWN"),
        "measurement_scope_id": MEASUREMENT_SCOPE_ID,
        "T1_FORMAL_INPUT_READY": pre.get("T1_FORMAL_INPUT_READY", "NO"),
        "T1_FORMAL_READY": pre.get("T1_FORMAL_READY", "NO"),
        "T1_FORMAL_STATUS": "MEASURED" if executed else "NOT_MEASURED",
        "T2_FORMAL_STATUS": "NOT_APPLICABLE",
        "T3_FORMAL_STATUS": "NOT_APPLICABLE",
        "E_B_FORMAL_READY_V2": pre.get("E_B_FORMAL_READY_V2", "NO"),
        "E-B_FORMAL_READY": pre.get("E-B_FORMAL_READY", "NO"),
        "OWNER_AUTHORIZATION_ISSUED": OWNER_AUTHORIZATION_ISSUED,
        "SOURCE_APPROVED": SOURCE_APPROVED,
        "AFTER_SOURCE_APPROVED": AFTER_SOURCE_APPROVED,
        "AUTHORIZATION_STILL_VALID": AUTHORIZATION_STILL_VALID,
        "FORMAL_T1_MEASUREMENT_EXECUTED": "YES" if executed else "NO",
        "FORMAL_T1_MEASUREMENT_VALID": "YES" if valid else "NO",
        "FORMAL_OBSERVATION": "COMPLETED_FOR_T1_V2" if valid else "NOT_STARTED",
        "FORMAL_OBSERVATION_V2": "COMPLETED" if valid else "NOT_STARTED",
        "FORMAL_ORACLE_LEAK_RISK": oracle,
        "CANONICAL_FORMAL_T1_RESULT_COUNT": "1" if executed else "0",
        "compliant_count": str(agg.get("compliant_count", "")),
        "violation_count": str(agg.get("violation_count", "")),
        "compliance_rate": str(agg.get("compliance_rate", "")),
        "formal_measurement_id": str((result or {}).get("formal_measurement_id", "")),
        "VERDICT": (
            "W10_T1_FORMAL_MEASUREMENT_COMPLETE"
            if valid
            else "FORMAL_T1_MEASUREMENT_INVALID"
        ),
    }

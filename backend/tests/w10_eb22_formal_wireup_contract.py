"""W10 E-B22 — Formal Wireup Contract (tests/docs only).

Implements the Capture → Binding → Scorer → Formal Compose wiring contract
frozen by E-B21:

* L-Obs composer skeleton (E-B2 envelope shape; no t2/t3 rates)
* L-Score companion artifact contract (FORMAL_T2_T3_SCORE_RESULT)
* Formal compose validator + invalid-reason allowlist
* BP-A / BP-B / BP-C isolation validator

Does not: call LLM / LM Studio, write reserved formal result, modify
``backend/app``, flip ``E-B_FORMAL_READY``, or claim product faithfulness.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from tests.w10_eb17_binding_gate import BindingPolicy, BindingVerdict
from tests.w10_eb2_generation_observation_contract import (
    ALLOWED_CLAIM,
    ARTIFACT_KIND_FORMAL_OBS,
    ARTIFACT_SCHEMA_VERSION as EB2_ARTIFACT_SCHEMA_VERSION,
    C12_CASE_ID,
    CLASSIFICATION_INVALID,
    ELIGIBILITY_PROTOCOL_ID,
    FORBIDDEN_CLAIMS,
    FORBIDDEN_PER_CASE_KEYS as EB2_FORBIDDEN_PER_CASE,
    FORBIDDEN_TOP_LEVEL_KEYS as EB2_FORBIDDEN_TOP,
    FROZEN_CASE_COUNT,
    INVALID_EXPECTED,
    INVALID_REASON_CODES as EB2_INVALID_REASON_CODES,
    OBSERVATION_POINT,
    P2_R1_STATUS_BLOCKED,
    PARENT_PROTOCOL_ID,
    PLACEHOLDER_INPUT_HASH,
    PLACEHOLDER_SHA,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    PROTOCOL_VERSION as EB2_PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    RUNNER_MODULE,
    STATUS_INELIGIBLE,
    STATUS_NOT_OBSERVED,
    STATUS_OBSERVED_SLOT,
    SUITE_ID,
)
from tests.w10_eb20_t2_t3_scorer_implementation import (
    map_scorer_status_to_grounding_observation,
)

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B22"
PROTOCOL_VERSION = "w10_eb22_formal_wireup_contract_v1"
L_SCORE_PROTOCOL_VERSION = "w10_eb22_formal_t2_t3_score_v1"
L_SCORE_ARTIFACT_KIND = "FORMAL_T2_T3_SCORE_RESULT"
PARENT_OBSERVATION_PROTOCOL = EB2_PROTOCOL_VERSION

FORMAL_WIREUP_DESIGNED = "YES"
FORMAL_WIREUP_IMPLEMENTED = "YES"  # this window — tests-only contract
T2_T3_SCORER_IMPLEMENTED = "YES"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

# ---------------------------------------------------------------------------
# Invalid-reason allowlist (E-B22 formal compose; does not mutate E-B2 module)
# ---------------------------------------------------------------------------

FORMAL_WIREUP_INVALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "FORMAL_GATE_LOCKED",
        "BINDING_INCOMPATIBLE",
        "GOLD_AFTER_HASH_MISMATCH",
        "SCORER_COMPANION_MISSING",
        "SCORER_RUN_ID_MISMATCH",
        "SCORER_BASE_SHA_MISMATCH",
        "BP_POLICY_VIOLATION",
        "WIRING_ONLY_POINTER_AS_PRODUCT",
        "COMPAT_PACK_AS_PRODUCT_FAITHFULNESS",
        "LLM_CALLED_FREEZE_VIOLATION",
    }
)

# Union used when validating L-Obs measurement_validity under wireup compose.
L_OBS_INVALID_REASON_ALLOWLIST: frozenset[str] = (
    EB2_INVALID_REASON_CODES | FORMAL_WIREUP_INVALID_REASON_CODES
)

# ---------------------------------------------------------------------------
# Forbidden keys (must never appear on L-Obs; rates live only on L-Score)
# ---------------------------------------------------------------------------

FORBIDDEN_L_OBS_TOP_KEYS: frozenset[str] = EB2_FORBIDDEN_TOP | frozenset(
    {
        "t2",
        "t3",
        "unsupported_rate",
        "grounded_rate",
        "formal_score",
        "scorer_details",
        "llm_judge",
        "nli_label",
        "product_faithfulness_proven",
    }
)

FORBIDDEN_L_OBS_PER_CASE_KEYS: frozenset[str] = EB2_FORBIDDEN_PER_CASE | frozenset(
    {
        "t2",
        "t3",
        "unsupported_rate",
        "grounded_rate",
        "scorer_details",
    }
)

FORBIDDEN_L_SCORE_KEYS: frozenset[str] = frozenset(
    {
        "llm_judge",
        "nli_label",
        "auto_label",
        "fuzzy_match",
        "expected_action",
        "oracle_cases",
        "grounding_proven",
    }
)

L_SCORE_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "parent_observation_protocol",
    "parent_run_id",
    "parent_base_sha",
    "binding_policy",
    "formal_measurement",
    "implementation_only",
    "cases",
    "t2",
    "t3",
    "binding_verdict",
    "honesty",
)

L_SCORE_CASE_REQUIRED: tuple[str, ...] = (
    "case_id",
    "binding_policy",
    "t2",
    "t3",
    "honesty",
)

L_OBS_TOP_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_schema_version",
    "run_id",
    "base_sha",
    "suite_id",
    "case_count",
    "runner_id",
    "runner_module",
    "eligibility_protocol_id",
    "parent_protocol_id",
    "eligibility_summary",
    "per_case_observation",
    "measurement_validity",
    "measurement_claims",
    "p2_r1_status",
    "does_not_unblock_p2_r1",
    "observation_point",
    "artifact_kind",
)


class FormalWireupError(ValueError):
    """Raised when formal wireup compose / validation fails."""


# ---------------------------------------------------------------------------
# Gate enforcement
# ---------------------------------------------------------------------------


def enforce_formal_gate(*, formal_ready: str | None = None) -> None:
    """Block formal compose/write while E-B_FORMAL_READY != YES."""
    ready = E_B_FORMAL_READY if formal_ready is None else formal_ready
    if ready != "YES":
        raise FormalWireupError("FORMAL_GATE_LOCKED")


def assert_reserved_result_absent() -> None:
    if RESERVED_RESULT_PATH.exists():
        raise FormalWireupError(
            f"reserved result {RESERVED_RESULT_FILENAME} must not exist during E-B22"
        )


# ---------------------------------------------------------------------------
# L-Obs skeleton
# ---------------------------------------------------------------------------


def _reject_keys(mapping: Mapping[str, Any], forbidden: frozenset[str], path: str) -> None:
    present = sorted(k for k in mapping if k in forbidden)
    if present:
        raise FormalWireupError(f"{path}: forbidden keys {present}")


def _default_case_ids() -> tuple[str, ...]:
    return (
        "C01-fully-supported-exact",
        "C02-supported-paraphrase-low-lexical",
        "C03-one-unsupported-among-supported",
        "C04-valid-citation-wrong-evidence",
        "C05-known-conflict-overcertain",
        "C06-required-fact-missing",
        "C07-correct-insufficiency-refusal",
        "C08-nonassertive-preface-supported-fact",
        "C09-supported-plus-unverifiable",
        "C10-supported-multiclaim-multicitation",
        "C11-citation-format-only-defect",
        C12_CASE_ID,
    )


def build_l_obs_skeleton(
    *,
    after_snapshots: Sequence[Mapping[str, Any]] | None = None,
    binding_results: Sequence[Mapping[str, Any]] | None = None,
    scorer_projection: Sequence[Mapping[str, Any]] | None = None,
    run_id: str = "WIREUP_SKELETON_eb22_not_a_formal_run",
    base_sha: str = PLACEHOLDER_SHA,
    targets_measured: Sequence[str] = ("T2", "T3"),
    invalid_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build L-Obs envelope shape (W1). Never writes reserved result.

    Rates / scorer details are forbidden. Status slots may be projected from
    scorer_projection. measurement_valid is always false under locked gate.
    """
    case_ids = _default_case_ids()
    after_by_id = {
        str(a["case_id"]): a for a in (after_snapshots or ()) if "case_id" in a
    }
    bind_by_id = {
        str(b.get("after_case_id") or b.get("case_id")): b
        for b in (binding_results or ())
    }
    proj_by_id = {
        str(p["case_id"]): p for p in (scorer_projection or ()) if "case_id" in p
    }

    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        after = after_by_id.get(case_id, {})
        proj = proj_by_id.get(case_id, {})
        bind = bind_by_id.get(case_id, {})
        is_c12 = case_id == C12_CASE_ID

        g_status = proj.get("grounding_observation_status")
        if g_status is None:
            t2_s = proj.get("t2_status")
            t3_s = proj.get("t3_status")
            if t2_s is not None or t3_s is not None:
                mapped = [
                    map_scorer_status_to_grounding_observation(s)
                    for s in (t2_s, t3_s)
                    if s is not None
                ]
                if STATUS_OBSERVED_SLOT in mapped:
                    g_status = STATUS_OBSERVED_SLOT
                elif STATUS_INELIGIBLE in mapped:
                    g_status = STATUS_INELIGIBLE
                else:
                    g_status = STATUS_NOT_OBSERVED
            else:
                g_status = STATUS_INELIGIBLE if is_c12 else STATUS_NOT_OBSERVED

        r_status = proj.get(
            "refusal_observation_status",
            STATUS_INELIGIBLE if is_c12 else STATUS_NOT_OBSERVED,
        )

        if bind.get("verdict") == BindingVerdict.INCOMPATIBLE.value:
            g_status = STATUS_INELIGIBLE

        cases.append(
            {
                "case_id": case_id,
                "eligibility": False if is_c12 else True,
                "classification": CLASSIFICATION_INVALID if is_c12 else None,
                "input_hash": after.get("input_hash", PLACEHOLDER_INPUT_HASH),
                "gen_plan_reference": after.get("gen_plan_reference"),
                "final_content_observation": after.get(
                    "final_content_observation", after.get("content")
                ),
                "final_citations": after.get(
                    "final_citations", after.get("citations")
                ),
                "scope_compliance_result": after.get("scope_compliance_result"),
                "grounding_observation_status": g_status,
                "refusal_observation_status": r_status,
            }
        )

    reasons = list(
        invalid_reasons
        if invalid_reasons is not None
        else ["FORMAL_GATE_LOCKED"]
    )
    artifact: dict[str, Any] = {
        "protocol_version": EB2_PROTOCOL_VERSION,
        "artifact_schema_version": EB2_ARTIFACT_SCHEMA_VERSION,
        "run_id": run_id,
        "base_sha": base_sha,
        "suite_id": SUITE_ID,
        "case_count": FROZEN_CASE_COUNT,
        "runner_id": RUNNER_ID,
        "runner_module": RUNNER_MODULE,
        "eligibility_protocol_id": ELIGIBILITY_PROTOCOL_ID,
        "parent_protocol_id": PARENT_PROTOCOL_ID,
        "eligibility_summary": {
            "frozen_cases": FROZEN_CASE_COUNT,
            "product_path_eligible": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "invalid_for_product_path": INVALID_EXPECTED,
            "c12_in_denominator": False,
            "invalid_case_ids": [C12_CASE_ID],
            "targets_measured": list(targets_measured),
        },
        "per_case_observation": cases,
        "measurement_validity": {
            "measurement_valid": False,
            "invalid_reasons": reasons,
            "structurally_schema_ok": True,
            "observation_point_honest": True,
            "ea5_artifact_not_reused": True,
            "p2_r3_artifact_not_reused": True,
            "critic_oracle_fields_absent": True,
            "p2_r1_remains_blocked": True,
            "llm_called": False,
        },
        "measurement_claims": {
            "allowed": [ALLOWED_CLAIM],
            "asserted": [ALLOWED_CLAIM],
            "forbidden_rejected": list(FORBIDDEN_CLAIMS),
        },
        "p2_r1_status": P2_R1_STATUS_BLOCKED,
        "does_not_unblock_p2_r1": True,
        "observation_point": OBSERVATION_POINT,
        "artifact_kind": ARTIFACT_KIND_FORMAL_OBS,
        "notes": (
            "E-B22 L-Obs wireup skeleton only. Not a formal observation run. "
            "Scores live on companion L-Score. E-B_FORMAL_READY=NO."
        ),
    }
    validate_l_obs_shape(artifact)
    return artifact


def compose_l_obs(
    *,
    after_snapshots: Sequence[Mapping[str, Any]] | None = None,
    binding_results: Sequence[Mapping[str, Any]] | None = None,
    scorer_projection: Sequence[Mapping[str, Any]] | None = None,
    run_id: str,
    base_sha: str,
    targets_measured: Sequence[str] = ("T2", "T3"),
    formal_ready: str | None = None,
) -> dict[str, Any]:
    """Formal L-Obs compose path (tests-only).

    Produces **skeleton artifact shape** only via ``build_l_obs_skeleton``.
    Does **not** mean formal measurement completed, reserved result written, or
    product faithfulness proven. Gate-locked → ``FORMAL_GATE_LOCKED``.

    Even after a future ``E-B_FORMAL_READY`` unlock, an **independent write
    step** is still required before any reserved formal observation result
    exists; this function never writes ``w10-eb2-generation-observation-result.json``.
    """
    enforce_formal_gate(formal_ready=formal_ready)
    # Unreachable while E_B_FORMAL_READY remains NO; kept for future unlock path.
    # Unlock ≠ auto-write: caller must still run a separate reserved-write step.
    return build_l_obs_skeleton(
        after_snapshots=after_snapshots,
        binding_results=binding_results,
        scorer_projection=scorer_projection,
        run_id=run_id,
        base_sha=base_sha,
        targets_measured=targets_measured,
        invalid_reasons=[],
    )


# ---------------------------------------------------------------------------
# L-Score companion
# ---------------------------------------------------------------------------


def build_l_score_companion(
    *,
    scorer_result: Mapping[str, Any],
    binding_artifact: Mapping[str, Any] | None = None,
    parent_run_id: str,
    parent_base_sha: str,
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    formal_measurement: bool = False,
    implementation_only: bool = True,
) -> dict[str, Any]:
    """Build L-Score companion shape aligned to a parent L-Obs identity."""
    policy = (
        binding_policy.value
        if isinstance(binding_policy, BindingPolicy)
        else str(binding_policy)
    )
    cases_in = scorer_result.get("cases") or []
    if not isinstance(cases_in, Sequence) or isinstance(cases_in, (str, bytes)):
        raise FormalWireupError("scorer_result.cases must be an array")

    cases: list[dict[str, Any]] = []
    for index, raw in enumerate(cases_in):
        if not isinstance(raw, Mapping):
            raise FormalWireupError(f"scorer_result.cases[{index}] must be object")
        case_policy = str(raw.get("binding_policy") or policy)
        case = {
            "case_id": raw["case_id"],
            "binding_policy": case_policy,
            "t2": deepcopy(raw.get("t2") or {}),
            "t3": deepcopy(raw.get("t3") or {}),
            "honesty": deepcopy(
                raw.get("honesty")
                or {
                    "product_faithfulness_proven": False,
                    "t3_pointer_source": raw.get(
                        "t3_pointer_source", "after_final_citations"
                    ),
                }
            ),
        }
        if "binding_verdict" in raw:
            case["binding_verdict"] = raw["binding_verdict"]
        cases.append(case)

    suite_t2 = deepcopy(scorer_result.get("t2") or {"cases_observed": 0})
    suite_t3 = deepcopy(scorer_result.get("t3") or {"cases_observed": 0})
    binding_verdict = scorer_result.get("binding_verdict")
    if binding_verdict is None and binding_artifact is not None:
        binding_verdict = binding_artifact.get("verdict") or binding_artifact.get(
            "binding_verdict"
        )
    if binding_verdict is None:
        binding_verdict = BindingVerdict.BOUND.value

    honesty = deepcopy(
        scorer_result.get("honesty")
        or {
            "product_faithfulness_proven": False,
            "compat_pack_as_product_faithfulness": False,
            "wiring_only_pointer_as_product": False,
            "formal_observation": False,
        }
    )
    honesty.setdefault("product_faithfulness_proven", False)

    artifact: dict[str, Any] = {
        "protocol_version": L_SCORE_PROTOCOL_VERSION,
        "artifact_kind": L_SCORE_ARTIFACT_KIND,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "parent_run_id": parent_run_id,
        "parent_base_sha": parent_base_sha,
        "binding_policy": policy,
        "formal_measurement": formal_measurement,
        "implementation_only": implementation_only,
        "cases": cases,
        "t2": suite_t2,
        "t3": suite_t3,
        "binding_verdict": binding_verdict,
        "honesty": honesty,
        "gates": {
            "FORMAL_WIREUP_IMPLEMENTED": FORMAL_WIREUP_IMPLEMENTED,
            "E-B_FORMAL_READY": E_B_FORMAL_READY,
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        },
        "notes": (
            "E-B22 L-Score companion contract. Rates live here, not on L-Obs. "
            "formal_measurement remains false while E-B_FORMAL_READY=NO."
        ),
    }
    validate_l_score_shape(artifact)
    return artifact


def compose_l_score(
    *,
    scorer_result: Mapping[str, Any],
    binding_artifact: Mapping[str, Any] | None = None,
    parent_run_id: str,
    parent_base_sha: str,
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    formal_ready: str | None = None,
) -> dict[str, Any]:
    """Formal L-Score compose path (tests-only).

    Produces **companion artifact shape** only via ``build_l_score_companion``.
    Does **not** mean formal measurement completed, reserved result written, or
    product faithfulness proven. Gate-locked → ``FORMAL_GATE_LOCKED``.

    Even after a future ``E-B_FORMAL_READY`` unlock, an **independent write
    step** is still required; this function never persists a reserved formal
    observation / score result to disk.
    """
    enforce_formal_gate(formal_ready=formal_ready)
    # Unlock ≠ auto-write: companion shape only; reserved write remains separate.
    return build_l_score_companion(
        scorer_result=scorer_result,
        binding_artifact=binding_artifact,
        parent_run_id=parent_run_id,
        parent_base_sha=parent_base_sha,
        binding_policy=binding_policy,
        formal_measurement=True,
        implementation_only=False,
    )


def attempt_formal_compose(
    *,
    target: str = "l_obs",
    **kwargs: Any,
) -> dict[str, Any]:
    """Test helper: run formal compose; gate locked → blocked dict (no raise).

    ``target``:
      - ``\"l_obs\"`` → ``compose_l_obs``
      - ``\"l_score\"`` → ``compose_l_score``

    On ``FORMAL_GATE_LOCKED`` returns
    ``{status: blocked, invalid_reason: FORMAL_GATE_LOCKED, artifact: None}``.
    Other ``FormalWireupError`` values still raise.
    """
    try:
        if target == "l_obs":
            artifact = compose_l_obs(**kwargs)
        elif target == "l_score":
            artifact = compose_l_score(**kwargs)
        else:
            raise FormalWireupError(f"unknown attempt_formal_compose target: {target!r}")
        return {"status": "ok", "artifact": artifact}
    except FormalWireupError as exc:
        if str(exc) == "FORMAL_GATE_LOCKED":
            return {
                "status": "blocked",
                "invalid_reason": "FORMAL_GATE_LOCKED",
                "artifact": None,
            }
        raise


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_l_obs_shape(payload: Mapping[str, Any]) -> None:
    missing = [k for k in L_OBS_TOP_REQUIRED if k not in payload]
    if missing:
        raise FormalWireupError(f"L-Obs missing fields: {missing}")

    if payload["protocol_version"] != EB2_PROTOCOL_VERSION:
        raise FormalWireupError(
            f"E-B2 identity unchanged required: protocol_version="
            f"{EB2_PROTOCOL_VERSION!r}"
        )
    if payload["artifact_schema_version"] != EB2_ARTIFACT_SCHEMA_VERSION:
        raise FormalWireupError("E-B2 artifact_schema_version must remain frozen")
    if payload["suite_id"] != SUITE_ID:
        raise FormalWireupError("E-B2 suite_id must remain frozen")
    if payload["observation_point"] != OBSERVATION_POINT:
        raise FormalWireupError("E-B2 observation_point must remain frozen")
    if payload["runner_id"] != RUNNER_ID or payload["runner_module"] != RUNNER_MODULE:
        raise FormalWireupError("E-B2 runner identity must remain frozen")
    if payload["artifact_kind"] != ARTIFACT_KIND_FORMAL_OBS:
        raise FormalWireupError(
            f"L-Obs artifact_kind must be {ARTIFACT_KIND_FORMAL_OBS!r}"
        )

    _reject_keys(payload, FORBIDDEN_L_OBS_TOP_KEYS, "L-Obs")

    cases = payload["per_case_observation"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise FormalWireupError("per_case_observation must be an array")
    if len(cases) != payload["case_count"]:
        raise FormalWireupError("case_count must equal len(per_case_observation)")

    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise FormalWireupError(f"per_case_observation[{index}] must be object")
        _reject_keys(case, FORBIDDEN_L_OBS_PER_CASE_KEYS, f"per_case_observation[{index}]")
        for rate_key in ("unsupported_rate", "grounded_rate", "t2", "t3"):
            if rate_key in case:
                raise FormalWireupError(
                    f"per_case_observation[{index}]: scores must not live on L-Obs"
                )

    validity = payload["measurement_validity"]
    if not isinstance(validity, Mapping):
        raise FormalWireupError("measurement_validity must be object")
    reasons = validity.get("invalid_reasons")
    if not isinstance(reasons, list):
        raise FormalWireupError("invalid_reasons must be an array")
    for reason in reasons:
        if reason not in L_OBS_INVALID_REASON_ALLOWLIST:
            raise FormalWireupError(f"unknown invalid_reason {reason!r}")

    if validity.get("measurement_valid") is True:
        raise FormalWireupError(
            "measurement_valid=true forbidden while wireup gate locked / skeleton"
        )
    if validity.get("llm_called") is True:
        raise FormalWireupError("LLM_CALLED_FREEZE_VIOLATION")

    notes = payload.get("notes")
    if isinstance(notes, str):
        lowered = notes.lower()
        for claim in FORBIDDEN_CLAIMS:
            if claim.lower() in lowered:
                raise FormalWireupError(f"forbidden claim in notes: {claim}")
        if "unsupported_rate" in lowered or "grounded_rate" in lowered:
            raise FormalWireupError("rates must not be stuffed into L-Obs notes")


def validate_l_score_shape(payload: Mapping[str, Any]) -> None:
    missing = [k for k in L_SCORE_REQUIRED if k not in payload]
    if missing:
        raise FormalWireupError(f"L-Score missing fields: {missing}")

    if payload["protocol_version"] != L_SCORE_PROTOCOL_VERSION:
        raise FormalWireupError(
            f"protocol_version must be {L_SCORE_PROTOCOL_VERSION!r}"
        )
    if payload["artifact_kind"] != L_SCORE_ARTIFACT_KIND:
        raise FormalWireupError(f"artifact_kind must be {L_SCORE_ARTIFACT_KIND!r}")
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise FormalWireupError(
            f"parent_observation_protocol must be {PARENT_OBSERVATION_PROTOCOL!r}"
        )

    _reject_keys(payload, FORBIDDEN_L_SCORE_KEYS, "L-Score")

    if payload.get("formal_measurement") is True and E_B_FORMAL_READY != "YES":
        raise FormalWireupError("FORMAL_GATE_LOCKED")
    if payload.get("formal_measurement") is True and payload.get("implementation_only") is True:
        raise FormalWireupError("formal_measurement cannot pair with implementation_only=true")

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise FormalWireupError("cases must be an array")
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise FormalWireupError(f"cases[{index}] must be object")
        missing_c = [k for k in L_SCORE_CASE_REQUIRED if k not in case]
        if missing_c:
            raise FormalWireupError(f"cases[{index}] missing: {missing_c}")
        honesty = case["honesty"]
        if not isinstance(honesty, Mapping):
            raise FormalWireupError(f"cases[{index}].honesty must be object")

    honesty = payload["honesty"]
    if not isinstance(honesty, Mapping):
        raise FormalWireupError("honesty must be object")


def validate_compose_pair(
    l_obs: Mapping[str, Any] | None,
    l_score: Mapping[str, Any] | None,
    *,
    require_companion: bool = True,
) -> None:
    """Validate L-Obs ↔ L-Score parent identity alignment."""
    if l_obs is None:
        raise FormalWireupError("L-Obs missing")
    validate_l_obs_shape(l_obs)

    targets = (l_obs.get("eligibility_summary") or {}).get("targets_measured") or []
    needs_score = any(t in targets for t in ("T2", "T3"))
    if require_companion and needs_score and l_score is None:
        raise FormalWireupError("SCORER_COMPANION_MISSING")
    if l_score is None:
        return

    validate_l_score_shape(l_score)

    if l_score.get("parent_run_id") != l_obs.get("run_id"):
        raise FormalWireupError("SCORER_RUN_ID_MISMATCH")
    if l_score.get("parent_base_sha") != l_obs.get("base_sha"):
        raise FormalWireupError("SCORER_BASE_SHA_MISMATCH")
    if l_score.get("parent_observation_protocol") != l_obs.get("protocol_version"):
        raise FormalWireupError("SCORER_RUN_ID_MISMATCH")


def validate_gold_after_hash_alignment(
    *,
    after_content_hash: str | None,
    gold_content_sha256: str | None,
) -> None:
    """Reject when After content hash and gold content hash disagree (same codec)."""
    if after_content_hash is None or gold_content_sha256 is None:
        raise FormalWireupError("GOLD_AFTER_HASH_MISMATCH")
    after_norm = str(after_content_hash).removeprefix("sha256:").lower()
    gold_norm = str(gold_content_sha256).removeprefix("sha256:").lower()
    if after_norm != gold_norm:
        raise FormalWireupError("GOLD_AFTER_HASH_MISMATCH")


def validate_bp_isolation(
    *,
    binding_policy: BindingPolicy | str,
    honesty: Mapping[str, Any],
    t2_status: str | None = None,
    t3_status: str | None = None,
    after_source: str | None = None,
    t3_pointer_source: str | None = None,
) -> None:
    """BP-A/B/C isolation for formal wireup."""
    policy = BindingPolicy(binding_policy)

    if honesty.get("product_faithfulness_proven") is True:
        if policy is not BindingPolicy.BP_A:
            raise FormalWireupError("BP_POLICY_VIOLATION")
        if after_source == "compatibility_materialization_author_owned":
            raise FormalWireupError("COMPAT_PACK_AS_PRODUCT_FAITHFULNESS")
        # Even BP-A cannot claim proven under locked formal gate in this window.
        if E_B_FORMAL_READY != "YES":
            raise FormalWireupError("BP_POLICY_VIOLATION")

    if policy is BindingPolicy.BP_B:
        if honesty.get("product_faithfulness_proven") is True:
            raise FormalWireupError("BP_POLICY_VIOLATION")

    if policy is BindingPolicy.BP_C:
        for status in (t2_status, t3_status):
            if status == "OBSERVED_SLOT":
                raise FormalWireupError("BP_POLICY_VIOLATION")

    if (
        t3_pointer_source == "gold_supporting_ids_wiring_only"
        and honesty.get("product_faithfulness_proven") is True
    ):
        raise FormalWireupError("WIRING_ONLY_POINTER_AS_PRODUCT")

    if honesty.get("compat_pack_as_product_faithfulness") is True:
        raise FormalWireupError("COMPAT_PACK_AS_PRODUCT_FAITHFULNESS")
    if honesty.get("wiring_only_pointer_as_product") is True:
        raise FormalWireupError("WIRING_ONLY_POINTER_AS_PRODUCT")


def validate_formal_compose_attempt(
    *,
    l_obs: Mapping[str, Any] | None = None,
    l_score: Mapping[str, Any] | None = None,
    write_reserved: bool = False,
    formal_ready: str | None = None,
) -> None:
    """Any formal compose/write attempt must pass gate + pair + BP checks."""
    enforce_formal_gate(formal_ready=formal_ready)
    if write_reserved:
        raise FormalWireupError("reserved formal write forbidden in E-B22")
    if l_obs is not None or l_score is not None:
        validate_compose_pair(l_obs, l_score, require_companion=True)
    assert_reserved_result_absent()


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def remaining_blockers() -> list[dict[str, str]]:
    return [
        {
            "id": "AG-3",
            "status": "PARTIAL",
            "detail": (
                "Wireup contract IMPLEMENTED (tests-only); "
                "reserved formal write / unlock still NO"
            ),
        },
        {
            "id": "AG-4",
            "status": "OPEN",
            "detail": "E-B15 degraded/refusal After fails BP-B claim-text presence",
        },
        {
            "id": "AG-5",
            "status": "PARTIAL",
            "detail": "compatibility rebound YES; live/authorized product After rebound NO",
        },
        {
            "id": "AG-6",
            "status": "OPEN",
            "detail": "E-B6 isomorphic synthetic ≠ E-B12B claim_texts",
        },
        {
            "id": "B2_PRIME",
            "status": "BLOCKING_RESIDUAL",
            "detail": "Formal/authorized After + reserved write still locked",
        },
        {
            "id": "S2",
            "status": "NO",
            "detail": "E_B_S2_PACKAGING_AUTHORIZED=NO",
        },
        {
            "id": "A4",
            "status": "NO",
            "detail": "Live LLM product After owner authorization absent",
        },
        {
            "id": "GATE",
            "status": "NO",
            "detail": "E-B_FORMAL_READY=NO (correct)",
        },
        {
            "id": "FORMAL_WIREUP",
            "status": "IMPLEMENTED_TESTS_ONLY",
            "detail": (
                "FORMAL_WIREUP_IMPLEMENTED=YES (composer + companion + validators); "
                "no reserved FORMAL_OBSERVATION_RESULT write"
            ),
        },
        {
            "id": "SCORER",
            "status": "IMPLEMENTED_TESTS_ONLY",
            "detail": "T2_T3_SCORER_IMPLEMENTED=YES (tests-only); not formal measurement",
        },
    ]


def readiness_summary() -> dict[str, Any]:
    if E_B_FORMAL_READY != "NO":
        raise FormalWireupError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise FormalWireupError("MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO")
    if FORMAL_WIREUP_IMPLEMENTED != "YES":
        raise FormalWireupError("FORMAL_WIREUP_IMPLEMENTED must be YES this window")
    if FORMAL_WIREUP_DESIGNED != "YES":
        raise FormalWireupError("FORMAL_WIREUP_DESIGNED must remain YES")
    assert_reserved_result_absent()
    return {
        "window": WINDOW_ID,
        "protocol_version": PROTOCOL_VERSION,
        "l_score_protocol_version": L_SCORE_PROTOCOL_VERSION,
        "l_score_artifact_kind": L_SCORE_ARTIFACT_KIND,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "FORMAL_WIREUP_DESIGNED": FORMAL_WIREUP_DESIGNED,
        "FORMAL_WIREUP_IMPLEMENTED": FORMAL_WIREUP_IMPLEMENTED,
        "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        "eb2_identity": {
            "protocol_version": EB2_PROTOCOL_VERSION,
            "artifact_schema_version": EB2_ARTIFACT_SCHEMA_VERSION,
            "suite_id": SUITE_ID,
            "runner_id": RUNNER_ID,
            "observation_point": OBSERVATION_POINT,
        },
        "invalid_reason_allowlist": sorted(FORMAL_WIREUP_INVALID_REASON_CODES),
        "remaining_blockers": remaining_blockers(),
        "claims": {
            "llm": False,
            "formal_observation": False,
            "formal_result": False,
            "product_faithfulness_proven": False,
            "formal_wireup_contract_implemented": True,
            "reserved_result_written": False,
        },
    }


def sample_scorer_result_for_wireup(
    *,
    case_id: str = "C01-fully-supported-exact",
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    t2_status: str = "OBSERVED_SLOT",
    t3_status: str = "OBSERVED_SLOT",
) -> dict[str, Any]:
    """Minimal scorer_result fixture for wireup schema tests (not product proof).

    Field-structure freeze: ``unsupported_rate`` / ``grounded_rate`` remain
    **scorer-side fixture fields only** (L-Score companion input).

    Semantic isolation (do not change structure to "fix" this):

    * Belong to **L-Score** input / companion shape.
    * Must **never** enter L-Obs (top-level, per-case, or notes).
    * Must **never** be treated as product faithfulness proof.
    """
    policy = (
        binding_policy.value
        if isinstance(binding_policy, BindingPolicy)
        else str(binding_policy)
    )
    return {
        "cases": [
            {
                "case_id": case_id,
                "binding_policy": policy,
                "binding_verdict": BindingVerdict.BOUND.value,
                "t2": {
                    "status": t2_status,
                    # L-Score input only — forbidden on L-Obs; ≠ product faithfulness.
                    "unsupported_rate": 0.0 if t2_status == "OBSERVED_SLOT" else None,
                },
                "t3": {
                    "status": t3_status,
                    # L-Score input only — forbidden on L-Obs; ≠ product faithfulness.
                    "grounded_rate": 1.0 if t3_status == "OBSERVED_SLOT" else None,
                    "per_claim": [],
                },
                "honesty": {
                    "product_faithfulness_proven": False,
                    "t3_pointer_source": "after_final_citations",
                },
            }
        ],
        "t2": {"cases_observed": 1 if t2_status == "OBSERVED_SLOT" else 0},
        "t3": {"cases_observed": 1 if t3_status == "OBSERVED_SLOT" else 0},
        "binding_verdict": BindingVerdict.BOUND.value,
        "honesty": {
            "product_faithfulness_proven": False,
            "compat_pack_as_product_faithfulness": False,
            "wiring_only_pointer_as_product": False,
            "formal_observation": False,
        },
    }

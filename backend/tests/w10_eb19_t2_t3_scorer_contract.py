"""W10 E-B19 — T2/T3 Scorer Contract Design (tests/docs only).

Freezes the tests-only LAAE scorer contract on top of E-B17 Binding Gate
and E-B18 BP-A binding compatibility:

* T2: observed_after + claim_gold → unsupported_rate
* T3: G1 (claim label / support status) ∧ G2 (final_citations ↔ supporting
  evidence ids) → grounded_rate

Does not: call LLM / LM Studio / NLI, fuzzy-match claims, use Critic
oracle, write reserved formal observation results, modify backend/app,
flip T2_T3_SCORER_IMPLEMENTED or E-B_FORMAL_READY.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from tests.w10_eb17_binding_gate import (
    BindingPolicy,
    BindingResult,
    BindingVerdict,
    validate_binding,
)

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B19"
PROTOCOL_VERSION = "w10_eb19_t2_t3_scorer_contract_v1"
ARTIFACT_KIND = "T2_T3_SCORER_CONTRACT"
PARENT_GATE = "w10_eb17_binding_gate_v1"
PARENT_COMPAT = "w10_eb18_gold_after_binding_compatibility_v1"
PARENT_CONSTRUCTS = (
    "w10-eb8-generation-ground-truth-construct",
    "w10-eb16-after-to-gold-evaluation-boundary",
)

BINDING_GATE_IMPLEMENTED = "YES"
COMPATIBILITY_MATERIALIZED = "YES"
GOLD_AFTER_BINDING_COMPATIBLE = "YES"
T2_T3_SCORER_CONTRACT_DESIGNED = "YES"
T2_T3_SCORER_IMPLEMENTED = "NO"  # contract + deterministic smoke only
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

CLAIM_LABELS = frozenset({"supported", "unsupported", "unverifiable"})
ALIGN_BUCKETS = frozenset(
    {"shrink", "keep_all", "refuse_empty", "fail_closed_empty", "unspecified"}
)

FRAGMENT_MARK_RE = re.compile(r"\[片段\s*(\d+)\]")

FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "llm_judge",
        "nli_label",
        "auto_label",
        "fuzzy_match",
        "expected_action",
        "oracle_cases",
        "FORMAL_OBSERVATION_RESULT",
        "formal_score",
        "grounding_proven",
    }
)


class ScorerStatus(str, Enum):
    """Case-level scorer outcome (contract layer — not formal proven)."""

    OBSERVED_SLOT = "OBSERVED_SLOT"  # formulas applied after BOUND
    NOT_APPLICABLE = "NOT_APPLICABLE"  # denom 0 / refusal / BP-C
    INVALID = "INVALID"  # bind fail / gold integrity fail
    NOT_OBSERVED = "NOT_OBSERVED"  # target excluded by caller
    INCOMPATIBLE = "INCOMPATIBLE"  # bind INCOMPATIBLE


class ScorerContractError(ValueError):
    """Raised when a scorer contract artifact or input is ill-formed."""


# ---------------------------------------------------------------------------
# Contract schema (frozen field lists)
# ---------------------------------------------------------------------------

T2_CASE_RESULT_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "target",
    "case_id",
    "status",
    "binding_verdict",
    "asserted_claim_count",
    "unsupported_claim_count",
    "unsupported_rate",
    "label_counts",
    "formal_measurement",
    "contract_only",
)

T3_CASE_RESULT_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "target",
    "case_id",
    "status",
    "binding_verdict",
    "asserted_claim_count",
    "grounded_claim_count",
    "grounded_rate",
    "align_bucket",
    "per_claim",
    "formal_measurement",
    "contract_only",
)

T3_PER_CLAIM_REQUIRED: tuple[str, ...] = (
    "claim_id",
    "label",
    "g1",
    "g2",
    "grounded",
    "supporting_evidence_ids",
    "resolved_pointer_ids",
)

SCORER_CONTRACT_SCHEMA: dict[str, Any] = {
    "protocol_version": PROTOCOL_VERSION,
    "artifact_kind": ARTIFACT_KIND,
    "parents": {
        "binding_gate": PARENT_GATE,
        "compatibility": PARENT_COMPAT,
        "constructs": list(PARENT_CONSTRUCTS),
    },
    "inputs": {
        "t2": ["observed_after", "claim_gold", "binding_policy"],
        "t3": [
            "observed_after",
            "claim_gold",
            "binding_policy",
            "final_citations",
            "gated_chunks_ordered",
            "align_bucket",
        ],
    },
    "outputs": {
        "t2": ["unsupported_rate", "status", "label_counts"],
        "t3": ["grounded_rate", "per_claim.g1", "per_claim.g2", "align_bucket"],
    },
    "forbidden": sorted(FORBIDDEN_KEYS),
    "matching": {
        "claim_identity": "claim_id",
        "evidence_identity": "exact string id equality",
        "fragment_mark": "1-based index into gated_chunks_ordered",
        "no_fuzzy": True,
        "no_nli": True,
        "no_llm_judge": True,
        "no_critic_oracle": True,
    },
    "formulas": {
        "unsupported_rate": (
            "|{c ∈ asserted : label=unsupported}| / |asserted|; "
            "unverifiable in denom, not in numerator; denom 0 → NOT_APPLICABLE"
        ),
        "grounded": "G1 ∧ G2",
        "g1": (
            "label==supported ∧ supporting_evidence_ids non-empty "
            "∧ ids ⊆ observed gated pool"
        ),
        "g2": (
            "≥1 final_citations[].chunk_id|evidence_id ∈ supporting_evidence_ids "
            "OR legal [片段N] maps to supporting id via gated_chunks_ordered; "
            "keep-all alone ≠ G2 true"
        ),
        "grounded_rate": "|{grounded}| / |asserted|; denom 0 → NOT_APPLICABLE",
    },
    "gates": {
        "T2_T3_SCORER_CONTRACT_DESIGNED": T2_T3_SCORER_CONTRACT_DESIGNED,
        "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    },
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class T2CaseResult:
    protocol_version: str
    artifact_kind: str
    target: str
    case_id: str
    status: ScorerStatus
    binding_verdict: str
    asserted_claim_count: int
    unsupported_claim_count: int | None
    unsupported_rate: float | None
    label_counts: Mapping[str, int]
    reasons: tuple[str, ...] = ()
    formal_measurement: bool = False
    contract_only: bool = True
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["label_counts"] = dict(self.label_counts)
        payload["details"] = dict(self.details)
        return payload


@dataclass(frozen=True, slots=True)
class T3ClaimScore:
    claim_id: str
    label: str
    g1: bool
    g2: bool
    grounded: bool
    supporting_evidence_ids: tuple[str, ...]
    resolved_pointer_ids: tuple[str, ...]
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class T3CaseResult:
    protocol_version: str
    artifact_kind: str
    target: str
    case_id: str
    status: ScorerStatus
    binding_verdict: str
    asserted_claim_count: int
    grounded_claim_count: int | None
    grounded_rate: float | None
    align_bucket: str
    per_claim: tuple[T3ClaimScore, ...]
    reasons: tuple[str, ...] = ()
    formal_measurement: bool = False
    contract_only: bool = True
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["per_claim"] = [c.to_dict() for c in self.per_claim]
        payload["details"] = dict(self.details)
        return payload


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------


def scorer_contract_schema() -> dict[str, Any]:
    return dict(SCORER_CONTRACT_SCHEMA)


def validate_t2_case_result_shape(payload: Mapping[str, Any]) -> None:
    missing = [k for k in T2_CASE_RESULT_REQUIRED if k not in payload]
    if missing:
        raise ScorerContractError(f"T2CaseResult missing fields: {missing}")
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ScorerContractError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload.get("artifact_kind") != ARTIFACT_KIND:
        raise ScorerContractError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if payload.get("target") != "T2":
        raise ScorerContractError("target must be 'T2'")
    if payload.get("formal_measurement") is not False:
        raise ScorerContractError("formal_measurement must be false (contract)")
    if payload.get("contract_only") is not True:
        raise ScorerContractError("contract_only must be true")
    for key in FORBIDDEN_KEYS:
        if key in payload:
            raise ScorerContractError(f"forbidden key in T2 result: {key}")
    status = ScorerStatus(payload["status"])
    rate = payload["unsupported_rate"]
    if status is ScorerStatus.OBSERVED_SLOT:
        if not isinstance(rate, float):
            raise ScorerContractError("OBSERVED_SLOT requires float unsupported_rate")
        if rate < 0.0 or rate > 1.0:
            raise ScorerContractError("unsupported_rate must be in [0,1]")
        denom = payload["asserted_claim_count"]
        num = payload["unsupported_claim_count"]
        if not isinstance(denom, int) or denom <= 0:
            raise ScorerContractError("OBSERVED_SLOT requires asserted_claim_count > 0")
        if not isinstance(num, int) or num < 0 or num > denom:
            raise ScorerContractError("unsupported_claim_count out of range")
        expected = num / denom
        if abs(rate - expected) > 1e-12:
            raise ScorerContractError(
                f"unsupported_rate {rate} != {num}/{denom} = {expected}"
            )
    elif status in (
        ScorerStatus.NOT_APPLICABLE,
        ScorerStatus.INVALID,
        ScorerStatus.NOT_OBSERVED,
        ScorerStatus.INCOMPATIBLE,
    ):
        if rate is not None:
            raise ScorerContractError(f"{status.value} requires unsupported_rate=null")
    else:
        raise ScorerContractError(f"unknown status: {status}")


def validate_t3_case_result_shape(payload: Mapping[str, Any]) -> None:
    missing = [k for k in T3_CASE_RESULT_REQUIRED if k not in payload]
    if missing:
        raise ScorerContractError(f"T3CaseResult missing fields: {missing}")
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ScorerContractError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload.get("artifact_kind") != ARTIFACT_KIND:
        raise ScorerContractError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if payload.get("target") != "T3":
        raise ScorerContractError("target must be 'T3'")
    if payload.get("formal_measurement") is not False:
        raise ScorerContractError("formal_measurement must be false (contract)")
    if payload.get("contract_only") is not True:
        raise ScorerContractError("contract_only must be true")
    bucket = payload.get("align_bucket")
    if bucket not in ALIGN_BUCKETS:
        raise ScorerContractError(f"align_bucket must be one of {sorted(ALIGN_BUCKETS)}")
    for key in FORBIDDEN_KEYS:
        if key in payload:
            raise ScorerContractError(f"forbidden key in T3 result: {key}")
    status = ScorerStatus(payload["status"])
    rate = payload["grounded_rate"]
    per_claim = payload["per_claim"]
    if not isinstance(per_claim, list):
        raise ScorerContractError("per_claim must be a list")
    for index, row in enumerate(per_claim):
        if not isinstance(row, Mapping):
            raise ScorerContractError(f"per_claim[{index}] must be object")
        missing_row = [k for k in T3_PER_CLAIM_REQUIRED if k not in row]
        if missing_row:
            raise ScorerContractError(
                f"per_claim[{index}] missing fields: {missing_row}"
            )
        if bool(row["grounded"]) != (bool(row["g1"]) and bool(row["g2"])):
            raise ScorerContractError(
                f"per_claim[{index}].grounded must equal g1∧g2"
            )
    if status is ScorerStatus.OBSERVED_SLOT:
        if not isinstance(rate, float):
            raise ScorerContractError("OBSERVED_SLOT requires float grounded_rate")
        if rate < 0.0 or rate > 1.0:
            raise ScorerContractError("grounded_rate must be in [0,1]")
        denom = payload["asserted_claim_count"]
        num = payload["grounded_claim_count"]
        if not isinstance(denom, int) or denom <= 0:
            raise ScorerContractError("OBSERVED_SLOT requires asserted_claim_count > 0")
        if not isinstance(num, int) or num < 0 or num > denom:
            raise ScorerContractError("grounded_claim_count out of range")
        expected = num / denom
        if abs(rate - expected) > 1e-12:
            raise ScorerContractError(
                f"grounded_rate {rate} != {num}/{denom} = {expected}"
            )
        if len(per_claim) != denom:
            raise ScorerContractError("per_claim length must equal asserted_claim_count")
    elif status in (
        ScorerStatus.NOT_APPLICABLE,
        ScorerStatus.INVALID,
        ScorerStatus.NOT_OBSERVED,
        ScorerStatus.INCOMPATIBLE,
    ):
        if rate is not None:
            raise ScorerContractError(f"{status.value} requires grounded_rate=null")
    else:
        raise ScorerContractError(f"unknown status: {status}")


# ---------------------------------------------------------------------------
# Gold / After helpers
# ---------------------------------------------------------------------------


def _reject_forbidden(mapping: Mapping[str, Any], path: str) -> None:
    present = sorted(k for k in mapping if k in FORBIDDEN_KEYS)
    if present:
        raise ScorerContractError(f"forbidden keys at {path}: {present}")


def _asserted_claims(gold_case: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = gold_case.get("asserted_claims")
    if claims is None:
        return []
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ScorerContractError("asserted_claims must be an array")
    out: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise ScorerContractError(f"asserted_claims[{index}] must be object")
        _reject_forbidden(claim, f"asserted_claims[{index}]")
        claim_id = claim.get("claim_id")
        label = claim.get("label")
        if not isinstance(claim_id, str) or not claim_id:
            raise ScorerContractError(f"asserted_claims[{index}].claim_id required")
        if label not in CLAIM_LABELS:
            raise ScorerContractError(
                f"asserted_claims[{index}].label must be one of {sorted(CLAIM_LABELS)}"
            )
        ids = claim.get("supporting_evidence_ids")
        if not isinstance(ids, Sequence) or isinstance(ids, (str, bytes, bytearray)):
            raise ScorerContractError(
                f"asserted_claims[{index}].supporting_evidence_ids must be array"
            )
        out.append(dict(claim))
    return out


def _observed_after_fields(
    observed_after: Mapping[str, Any],
) -> tuple[str, str | None, str | None, list[str], str | None]:
    _reject_forbidden(observed_after, "observed_after")
    case_id = observed_after.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ScorerContractError("observed_after.case_id required")
    content = observed_after.get("after_content")
    if content is not None and not isinstance(content, str):
        raise ScorerContractError("observed_after.after_content must be string")
    content_hash = observed_after.get("after_content_hash")
    if content_hash is not None and not isinstance(content_hash, str):
        raise ScorerContractError("observed_after.after_content_hash must be string")
    eids_raw = observed_after.get("observed_evidence_ids") or []
    if not isinstance(eids_raw, Sequence) or isinstance(
        eids_raw, (str, bytes, bytearray)
    ):
        raise ScorerContractError("observed_after.observed_evidence_ids must be array")
    eids = [str(x) for x in eids_raw]
    pool = observed_after.get("observed_pool_sha256")
    if pool is not None and not isinstance(pool, str):
        raise ScorerContractError("observed_after.observed_pool_sha256 must be string")
    return case_id, content, content_hash, eids, pool


def _run_binding(
    *,
    observed_after: Mapping[str, Any],
    gold_case: Mapping[str, Any],
    binding_policy: BindingPolicy | str,
) -> BindingResult:
    case_id, content, content_hash, eids, pool = _observed_after_fields(observed_after)
    return validate_binding(
        after_case_id=case_id,
        gold_case=gold_case,
        binding_policy=binding_policy,
        after_content=content,
        after_content_hash=content_hash,
        observed_evidence_ids=eids,
        observed_pool_sha256=pool,
    )


def _status_from_binding(binding: BindingResult) -> ScorerStatus | None:
    if binding.verdict is BindingVerdict.BOUND:
        return None
    if binding.verdict is BindingVerdict.EXCLUDED_T4:
        return ScorerStatus.NOT_APPLICABLE
    if binding.verdict is BindingVerdict.INCOMPATIBLE:
        return ScorerStatus.INCOMPATIBLE
    return ScorerStatus.INVALID


def _validate_supported_evidence_integrity(
    claims: Sequence[Mapping[str, Any]],
    observed_evidence_ids: Sequence[str],
) -> tuple[bool, tuple[str, ...]]:
    """supported ⇒ ids non-empty ⊆ observed; drift ⇒ invalidate (do not re-label)."""
    observed = {str(x) for x in observed_evidence_ids}
    reasons: list[str] = []
    for claim in claims:
        label = claim["label"]
        ids = [str(x) for x in claim.get("supporting_evidence_ids") or []]
        claim_id = str(claim["claim_id"])
        if label == "supported":
            if not ids:
                reasons.append(f"{claim_id}: supported requires non-empty evidence ids")
            missing = sorted(set(ids) - observed)
            if missing:
                reasons.append(
                    f"{claim_id}: supporting ids left observed pool: {missing}"
                )
        else:
            # unsupported / unverifiable may list contradicting ids; if listed,
            # they must still be in-pool (no silent out-of-pool ids).
            missing = sorted(set(ids) - observed)
            if missing:
                reasons.append(
                    f"{claim_id}: listed evidence ids left observed pool: {missing}"
                )
    return (not reasons, tuple(reasons))


# ---------------------------------------------------------------------------
# T2 scorer
# ---------------------------------------------------------------------------


def score_t2(
    *,
    observed_after: Mapping[str, Any],
    claim_gold: Mapping[str, Any],
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    targets_include_t2: bool = True,
) -> T2CaseResult:
    """Deterministic T2 contract scorer.

    Input: observed_after + claim_gold (+ binding_policy).
    Output: unsupported_rate (or non-observed / invalid / N/A status).
    Labels come **only** from gold — never re-labeled.
    """
    _reject_forbidden(claim_gold, "claim_gold")
    case_id = str(claim_gold.get("case_id") or observed_after.get("case_id") or "")

    if not targets_include_t2:
        return T2CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T2",
            case_id=case_id,
            status=ScorerStatus.NOT_OBSERVED,
            binding_verdict="SKIPPED",
            asserted_claim_count=0,
            unsupported_claim_count=None,
            unsupported_rate=None,
            label_counts={},
            reasons=("targets_measured excludes T2",),
        )

    binding = _run_binding(
        observed_after=observed_after,
        gold_case=claim_gold,
        binding_policy=binding_policy,
    )
    early = _status_from_binding(binding)
    if early is not None:
        return T2CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T2",
            case_id=case_id or binding.gold_case_id,
            status=early,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=0,
            unsupported_claim_count=None,
            unsupported_rate=None,
            label_counts={},
            reasons=binding.reasons,
            details={"t2_t3_eligible": binding.t2_t3_eligible},
        )

    claims = _asserted_claims(claim_gold)
    _, _, _, observed_ids, _ = _observed_after_fields(observed_after)
    ok, integrity_reasons = _validate_supported_evidence_integrity(claims, observed_ids)
    if not ok:
        return T2CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T2",
            case_id=binding.gold_case_id,
            status=ScorerStatus.INVALID,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=len(claims),
            unsupported_claim_count=None,
            unsupported_rate=None,
            label_counts={},
            reasons=integrity_reasons,
        )

    if not claims:
        return T2CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T2",
            case_id=binding.gold_case_id,
            status=ScorerStatus.NOT_APPLICABLE,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=0,
            unsupported_claim_count=None,
            unsupported_rate=None,
            label_counts={},
            reasons=("asserted_claims empty → T2 NOT_APPLICABLE (not 0.0 PASS)",),
        )

    label_counts = {"supported": 0, "unsupported": 0, "unverifiable": 0}
    for claim in claims:
        label_counts[str(claim["label"])] += 1
    unsupported = label_counts["unsupported"]
    denom = len(claims)
    rate = unsupported / denom
    return T2CaseResult(
        protocol_version=PROTOCOL_VERSION,
        artifact_kind=ARTIFACT_KIND,
        target="T2",
        case_id=binding.gold_case_id,
        status=ScorerStatus.OBSERVED_SLOT,
        binding_verdict=binding.verdict.value,
        asserted_claim_count=denom,
        unsupported_claim_count=unsupported,
        unsupported_rate=rate,
        label_counts=label_counts,
        reasons=(),
        details={
            "unverifiable_in_denom": True,
            "unverifiable_in_unsupported_numerator": False,
            "labels_from_gold_only": True,
            "measurement_claims": binding.measurement_claims_allowed,
        },
    )


# ---------------------------------------------------------------------------
# T3 G1 / G2
# ---------------------------------------------------------------------------


def evaluate_g1(
    claim: Mapping[str, Any],
    *,
    observed_evidence_ids: Sequence[str],
) -> tuple[bool, str]:
    """G1: claim support status from gold label + in-pool supporting ids.

    Deterministic. No citation chip required (that is G2).
    """
    label = claim["label"]
    ids = [str(x) for x in claim.get("supporting_evidence_ids") or []]
    observed = {str(x) for x in observed_evidence_ids}
    if label != "supported":
        return False, f"label={label} → G1 false"
    if not ids:
        return False, "supported but empty supporting_evidence_ids"
    if not set(ids).issubset(observed):
        return False, "supporting ids not ⊆ observed gated pool"
    return True, "label=supported ∧ ids ⊆ pool"


def _citation_resolvable_ids(citation: Mapping[str, Any]) -> list[str]:
    """Exact id extraction — no fuzzy matching."""
    out: list[str] = []
    for key in ("chunk_id", "evidence_id", "id"):
        value = citation.get(key)
        if isinstance(value, str) and value:
            out.append(value)
    return out


def _fragment_resolved_ids(
    after_content: str | None,
    gated_chunks_ordered: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Map legal [片段N] (1-based) → chunk/evidence id via ordered gated list."""
    if not after_content or not gated_chunks_ordered:
        return []
    resolved: list[str] = []
    seen: set[str] = set()
    for match in FRAGMENT_MARK_RE.finditer(after_content):
        idx = int(match.group(1))
        if not (1 <= idx <= len(gated_chunks_ordered)):
            continue
        chunk = gated_chunks_ordered[idx - 1]
        for key in ("chunk_id", "evidence_id", "id"):
            value = chunk.get(key)
            if isinstance(value, str) and value and value not in seen:
                seen.add(value)
                resolved.append(value)
                break
    return resolved


def evaluate_g2(
    claim: Mapping[str, Any],
    *,
    final_citations: Sequence[Mapping[str, Any]],
    after_content: str | None,
    gated_chunks_ordered: Sequence[Mapping[str, Any]],
    align_bucket: str,
) -> tuple[bool, tuple[str, ...], str]:
    """G2: ≥1 resolvable pointer from final_citations or [片段N] to supporting ids.

    keep-all alone never implies G2 true.
    Exact id equality only — no fuzzy / NLI.
    """
    supporting = {str(x) for x in claim.get("supporting_evidence_ids") or []}
    if not supporting:
        return False, (), "no supporting_evidence_ids → G2 false"

    pointer_ids: list[str] = []
    for citation in final_citations:
        if not isinstance(citation, Mapping):
            continue
        pointer_ids.extend(_citation_resolvable_ids(citation))
    pointer_ids.extend(_fragment_resolved_ids(after_content, gated_chunks_ordered))

    hits = tuple(sorted({pid for pid in pointer_ids if pid in supporting}))
    if hits:
        return True, hits, "resolvable pointer ∩ supporting_evidence_ids"

    if align_bucket == "keep_all" and final_citations:
        return (
            False,
            (),
            "keep-all chips present but none resolve to supporting ids (≠ grounded)",
        )
    if not final_citations and not FRAGMENT_MARK_RE.search(after_content or ""):
        return False, (), "empty final_citations and no legal fragment mark"
    return False, (), "pointers do not intersect supporting_evidence_ids"


def score_t3(
    *,
    observed_after: Mapping[str, Any],
    claim_gold: Mapping[str, Any],
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    final_citations: Sequence[Mapping[str, Any]] | None = None,
    gated_chunks_ordered: Sequence[Mapping[str, Any]] | None = None,
    align_bucket: str = "unspecified",
    targets_include_t3: bool = True,
) -> T3CaseResult:
    """Deterministic T3 contract scorer (G1 ∧ G2).

    G1: claim label / support status.
    G2: final_citations ↔ supporting evidence ids (exact).
    """
    _reject_forbidden(claim_gold, "claim_gold")
    if align_bucket not in ALIGN_BUCKETS:
        raise ScorerContractError(f"align_bucket must be one of {sorted(ALIGN_BUCKETS)}")

    case_id = str(claim_gold.get("case_id") or observed_after.get("case_id") or "")
    cites = list(final_citations or observed_after.get("final_citations") or [])
    chunks = list(gated_chunks_ordered or observed_after.get("gated_chunks_ordered") or [])
    content = observed_after.get("after_content")
    if content is not None and not isinstance(content, str):
        raise ScorerContractError("observed_after.after_content must be string")

    empty_per: tuple[T3ClaimScore, ...] = ()

    if not targets_include_t3:
        return T3CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T3",
            case_id=case_id,
            status=ScorerStatus.NOT_OBSERVED,
            binding_verdict="SKIPPED",
            asserted_claim_count=0,
            grounded_claim_count=None,
            grounded_rate=None,
            align_bucket=align_bucket,
            per_claim=empty_per,
            reasons=("targets_measured excludes T3",),
        )

    binding = _run_binding(
        observed_after=observed_after,
        gold_case=claim_gold,
        binding_policy=binding_policy,
    )
    early = _status_from_binding(binding)
    if early is not None:
        return T3CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T3",
            case_id=case_id or binding.gold_case_id,
            status=early,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=0,
            grounded_claim_count=None,
            grounded_rate=None,
            align_bucket=align_bucket,
            per_claim=empty_per,
            reasons=binding.reasons,
            details={"t2_t3_eligible": binding.t2_t3_eligible},
        )

    claims = _asserted_claims(claim_gold)
    _, _, _, observed_ids, _ = _observed_after_fields(observed_after)
    ok, integrity_reasons = _validate_supported_evidence_integrity(claims, observed_ids)
    if not ok:
        return T3CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T3",
            case_id=binding.gold_case_id,
            status=ScorerStatus.INVALID,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=len(claims),
            grounded_claim_count=None,
            grounded_rate=None,
            align_bucket=align_bucket,
            per_claim=empty_per,
            reasons=integrity_reasons,
        )

    if not claims:
        return T3CaseResult(
            protocol_version=PROTOCOL_VERSION,
            artifact_kind=ARTIFACT_KIND,
            target="T3",
            case_id=binding.gold_case_id,
            status=ScorerStatus.NOT_APPLICABLE,
            binding_verdict=binding.verdict.value,
            asserted_claim_count=0,
            grounded_claim_count=None,
            grounded_rate=None,
            align_bucket=align_bucket,
            per_claim=empty_per,
            reasons=("asserted_claims empty → T3 NOT_APPLICABLE (not 1.0 PASS)",),
        )

    per: list[T3ClaimScore] = []
    grounded_n = 0
    for claim in claims:
        g1, g1_note = evaluate_g1(claim, observed_evidence_ids=observed_ids)
        g2, hits, g2_note = evaluate_g2(
            claim,
            final_citations=cites,
            after_content=content if isinstance(content, str) else None,
            gated_chunks_ordered=chunks,
            align_bucket=align_bucket,
        )
        grounded = g1 and g2
        if grounded:
            grounded_n += 1
        per.append(
            T3ClaimScore(
                claim_id=str(claim["claim_id"]),
                label=str(claim["label"]),
                g1=g1,
                g2=g2,
                grounded=grounded,
                supporting_evidence_ids=tuple(
                    str(x) for x in claim.get("supporting_evidence_ids") or []
                ),
                resolved_pointer_ids=hits,
                notes=f"G1:{g1_note}; G2:{g2_note}",
            )
        )

    denom = len(claims)
    rate = grounded_n / denom
    return T3CaseResult(
        protocol_version=PROTOCOL_VERSION,
        artifact_kind=ARTIFACT_KIND,
        target="T3",
        case_id=binding.gold_case_id,
        status=ScorerStatus.OBSERVED_SLOT,
        binding_verdict=binding.verdict.value,
        asserted_claim_count=denom,
        grounded_claim_count=grounded_n,
        grounded_rate=rate,
        align_bucket=align_bucket,
        per_claim=tuple(per),
        reasons=(),
        details={
            "grounded_equals_g1_and_g2": True,
            "keep_all_alone_not_grounded": True,
            "exact_id_match_only": True,
            "measurement_claims": binding.measurement_claims_allowed,
            "grounded_semantic_only_research": "G1∧¬G2 recorded via per_claim; not formal grounded",
        },
    )


# ---------------------------------------------------------------------------
# Edge-case fixture builders (F1–F8) + readiness
# ---------------------------------------------------------------------------


def _mini_bound_pair(
    *,
    case_id: str,
    content: str,
    claims: list[dict[str, Any]],
    evidence_ids: list[str],
    pool_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Author-owned After + BP-A rebound gold for contract edge fixtures."""
    from tests.w10_eb17_binding_gate import (
        format_observed_content_hash,
        observed_content_digest,
    )

    pool = pool_sha256 or ("a" * 64)
    after = {
        "case_id": case_id,
        "after_content": content,
        "after_content_hash": format_observed_content_hash(content),
        "observed_evidence_ids": list(evidence_ids),
        "observed_pool_sha256": pool,
        "llm_called": False,
        "formal_measurement": False,
    }
    gold = {
        "case_id": case_id,
        "content_binding": {
            "kind": BindingPolicy.BP_A.value,
            "content_sha256": observed_content_digest(content),
        },
        "gated_pool_binding": {
            "evidence_ids": list(evidence_ids),
            "pool_sha256": pool,
        },
        "denominator_policy": "exclude_refusal_boilerplate",
        "asserted_claims": claims,
    }
    return after, gold


def edge_case_fixtures() -> dict[str, dict[str, Any]]:
    """Canonical F1–F8 (+ S1 success) fixtures for deterministic contract tests."""
    fixtures: dict[str, dict[str, Any]] = {}

    # F1: unsupported, no citation
    after, gold = _mini_bound_pair(
        case_id="F1-hallucination-no-cite",
        content="备份保留 999 天。",
        evidence_ids=["E1"],
        claims=[
            {
                "claim_id": "F1::c1",
                "text": "备份保留 999 天。",
                "label": "unsupported",
                "supporting_evidence_ids": [],
                "support_span_notes": "Not in pool.",
            }
        ],
    )
    fixtures["F1"] = {
        "after": after,
        "gold": gold,
        "final_citations": [],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 1.0,
        "expect_g1": False,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F2: unsupported + shape-legal citation to unrelated id
    after, gold = _mini_bound_pair(
        case_id="F2-hallucination-with-chip",
        content="备份保留 999 天。[片段1]",
        evidence_ids=["E1", "E2"],
        claims=[
            {
                "claim_id": "F2::c1",
                "text": "备份保留 999 天。",
                "label": "unsupported",
                "supporting_evidence_ids": [],
                "support_span_notes": "Fabricated.",
            }
        ],
    )
    fixtures["F2"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E1"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}, {"chunk_id": "E2"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 1.0,
        "expect_g1": False,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F3: supported, no final citation / mark → G1 T, G2 F
    after, gold = _mini_bound_pair(
        case_id="F3-supported-no-pointer",
        content="生产环境备份的保留期限为 30 天。",
        evidence_ids=["E1"],
        claims=[
            {
                "claim_id": "F3::c1",
                "text": "生产环境备份的保留期限为 30 天。",
                "label": "supported",
                "supporting_evidence_ids": ["E1"],
                "support_span_notes": "E1 supports.",
            }
        ],
    )
    fixtures["F3"] = {
        "after": after,
        "gold": gold,
        "final_citations": [],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 0.0,
        "expect_g1": True,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F4: supported but chip points to wrong chunk
    after, gold = _mini_bound_pair(
        case_id="F4-wrong-pointer",
        content="生产环境备份的保留期限为 30 天。",
        evidence_ids=["E1", "E2"],
        claims=[
            {
                "claim_id": "F4::c1",
                "text": "生产环境备份的保留期限为 30 天。",
                "label": "supported",
                "supporting_evidence_ids": ["E1"],
                "support_span_notes": "E1 supports.",
            }
        ],
    )
    fixtures["F4"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E2"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}, {"chunk_id": "E2"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 0.0,
        "expect_g1": True,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F5: unverifiable
    after, gold = _mini_bound_pair(
        case_id="F5-unverifiable",
        content="某政策可能在明年调整。",
        evidence_ids=["E1"],
        claims=[
            {
                "claim_id": "F5::c1",
                "text": "某政策可能在明年调整。",
                "label": "unverifiable",
                "supporting_evidence_ids": [],
                "support_span_notes": "Not decidable from pool.",
            }
        ],
    )
    fixtures["F5"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E1"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 0.0,  # unverifiable not in unsupported numerator
        "expect_g1": False,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F6: empty asserted → N/A (refusal-style denom)
    after, gold = _mini_bound_pair(
        case_id="F6-refusal-empty-claims",
        content="知识库中未找到相关内容",
        evidence_ids=["E1"],
        claims=[],
    )
    fixtures["F6"] = {
        "after": after,
        "gold": gold,
        "final_citations": [],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "refuse_empty",
        "expect_t2_status": ScorerStatus.NOT_APPLICABLE,
        "expect_t3_status": ScorerStatus.NOT_APPLICABLE,
    }

    # F7: keep-all full chips, claim unsupported
    after, gold = _mini_bound_pair(
        case_id="F7-keep-all-unsupported",
        content="备份保留 999 天。",
        evidence_ids=["E1", "E2"],
        claims=[
            {
                "claim_id": "F7::c1",
                "text": "备份保留 999 天。",
                "label": "unsupported",
                "supporting_evidence_ids": [],
                "support_span_notes": "Fabricated under keep-all.",
            }
        ],
    )
    fixtures["F7"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E1"}, {"chunk_id": "E2"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}, {"chunk_id": "E2"}],
        "align_bucket": "keep_all",
        "expect_t2_rate": 1.0,
        "expect_g1": False,
        "expect_g2": False,
        "expect_grounded": False,
    }

    # F8: pool drift → INVALID
    after, gold = _mini_bound_pair(
        case_id="F8-pool-drift",
        content="生产环境备份的保留期限为 30 天。",
        evidence_ids=["E1"],
        claims=[
            {
                "claim_id": "F8::c1",
                "text": "生产环境备份的保留期限为 30 天。",
                "label": "supported",
                "supporting_evidence_ids": ["E1"],
                "support_span_notes": "E1.",
            }
        ],
    )
    after = dict(after)
    after["observed_evidence_ids"] = ["E9"]  # drift
    fixtures["F8"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E1"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "shrink",
        "expect_t2_status": ScorerStatus.INVALID,
        "expect_t3_status": ScorerStatus.INVALID,
    }

    # S1 success: supported ∧ G1 ∧ correct pointer
    after, gold = _mini_bound_pair(
        case_id="S1-grounded-success",
        content="生产环境备份的保留期限为 30 天。[片段1]",
        evidence_ids=["E1"],
        claims=[
            {
                "claim_id": "S1::c1",
                "text": "生产环境备份的保留期限为 30 天。",
                "label": "supported",
                "supporting_evidence_ids": ["E1"],
                "support_span_notes": "E1.",
            }
        ],
    )
    fixtures["S1"] = {
        "after": after,
        "gold": gold,
        "final_citations": [{"chunk_id": "E1"}],
        "gated_chunks_ordered": [{"chunk_id": "E1"}],
        "align_bucket": "shrink",
        "expect_t2_rate": 0.0,
        "expect_g1": True,
        "expect_g2": True,
        "expect_grounded": True,
        "expect_grounded_rate": 1.0,
    }

    return fixtures


def remaining_blockers() -> list[dict[str, str]]:
    return [
        {
            "id": "AG-1",
            "status": "CLEARED_FOR_BP_A_REBOUND",
            "detail": "BP-A rebound codec cleared on compatibility pack; live unrebounded path still non-binding",
        },
        {
            "id": "AG-2",
            "status": "MITIGATED_BY_CODEC",
            "detail": "prefix normalize inside declared hash space",
        },
        {
            "id": "AG-3",
            "status": "PARTIAL",
            "detail": (
                "Binding gate YES + compatibility YES + scorer CONTRACT designed YES; "
                "T2_T3_SCORER_IMPLEMENTED still NO (no formal observation wire-up)"
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
            "id": "SCORER",
            "status": "CONTRACT_ONLY",
            "detail": (
                "T2_T3_SCORER_CONTRACT_DESIGNED=YES; "
                "T2_T3_SCORER_IMPLEMENTED=NO; scores are contract_only, not formal"
            ),
        },
    ]


def readiness_summary() -> dict[str, Any]:
    if E_B_FORMAL_READY != "NO":
        raise ScorerContractError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise ScorerContractError("MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO")
    if T2_T3_SCORER_IMPLEMENTED != "NO":
        raise ScorerContractError("T2_T3_SCORER_IMPLEMENTED must remain NO this window")
    if T2_T3_SCORER_CONTRACT_DESIGNED != "YES":
        raise ScorerContractError("contract must be marked designed")
    return {
        "window": WINDOW_ID,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "BINDING_GATE_IMPLEMENTED": BINDING_GATE_IMPLEMENTED,
        "COMPATIBILITY_MATERIALIZED": COMPATIBILITY_MATERIALIZED,
        "GOLD_AFTER_BINDING_COMPATIBLE": GOLD_AFTER_BINDING_COMPATIBLE,
        "T2_T3_SCORER_CONTRACT_DESIGNED": T2_T3_SCORER_CONTRACT_DESIGNED,
        "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        "schema": scorer_contract_schema(),
        "remaining_blockers": remaining_blockers(),
        "claims": {
            "llm": False,
            "nli_auto_label": False,
            "fuzzy_matching": False,
            "critic_oracle": False,
            "formal_observation": False,
            "formal_result": False,
            "scorer_implemented": False,
            "scorer_contract_designed": True,
            "product_faithfulness_proven": False,
        },
    }

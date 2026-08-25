"""W10 E-B17 — LAAE After↔Gold Binding Gate (tests/docs only).

Defines the binding artifact, separates hash semantics, and runs a
deterministic Binding Gate under BP-A / BP-B / BP-C.

Does not: call LLM / LM Studio, score T2/T3 formal results, modify
backend/app, write reserved formal observation results, or flip
E-B_FORMAL_READY.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B17"
PROTOCOL_VERSION = "w10_eb17_binding_gate_v1"
ARTIFACT_KIND = "AFTER_GOLD_BINDING"
PARENT_DESIGN = "w10-eb16-after-to-gold-evaluation-boundary"

BINDING_GATE_IMPLEMENTED = "YES"
GOLD_AFTER_BINDING_COMPATIBLE = "NO"  # live E-B12B×E-B15 material still incompatible
T2_T3_SCORER_IMPLEMENTED = "NO"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SHA256_PREFIX = "sha256:"

FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "llm_judge",
        "nli_label",
        "auto_label",
        "expected_action",
        "oracle_cases",
        "unsupported_rate",
        "grounded_rate",
        "formal_score",
        "FORMAL_OBSERVATION_RESULT",
    }
)


class BindingPolicy(str, Enum):
    """Explicit per-case binding policy (LAAE BP-*)."""

    BP_A = "observed_after"  # formal candidate (product After)
    BP_B = "synthetic_authored"  # test / protocol scorability only
    BP_C = "refusal_exclude"  # T4 exclusion; skip T2/T3


class HashSpace(str, Enum):
    """Three hash spaces — never naively compare across spaces."""

    GOLD_LEDGER = "gold_ledger_hash"
    OBSERVED_CONTENT = "observed_content_hash"
    EVIDENCE_POOL = "evidence_pool_hash"


class BindingVerdict(str, Enum):
    BOUND = "BOUND"  # body+pool bind OK under declared policy
    INVALID = "INVALID"  # case/body/pool fail → T2/T3 invalid
    EXCLUDED_T4 = "EXCLUDED_T4"  # BP-C: refusal → T4 only
    INCOMPATIBLE = "INCOMPATIBLE"  # wrong hash-space compare / kind mismatch


class BindingGateError(ValueError):
    """Raised when a binding artifact or compare request is ill-formed."""


# ---------------------------------------------------------------------------
# Hash codec (semantic separation)
# ---------------------------------------------------------------------------


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest_hex(payload: Any) -> str:
    """Bare 64-char hex (gold ledger / pool style)."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_digest(value: str | None) -> str | None:
    """Strip optional ``sha256:`` prefix → lowercase bare hex; None stays None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise BindingGateError("digest must be a string or None")
    raw = value[len(SHA256_PREFIX) :] if value.startswith(SHA256_PREFIX) else value
    if not SHA256_HEX_RE.fullmatch(raw):
        raise BindingGateError(f"digest must be 64-char hex (got {value!r})")
    return raw.lower()


def observed_content_digest(content: str) -> str:
    """Observed content hash space: bare hex of canonical_json(content string).

    E-B15 stores ``sha256:{this}``; gold ``observed_after`` stores bare hex of the
    same payload. Comparator must normalize before equality.
    """
    if not isinstance(content, str):
        raise BindingGateError("observed content must be a string")
    return digest_hex(content)


def format_observed_content_hash(content: str) -> str:
    """E-B15 wire form: ``sha256:{hex}``."""
    return f"{SHA256_PREFIX}{observed_content_digest(content)}"


def gold_claim_texts_digest(case_id: str, claim_texts: Sequence[str]) -> str:
    """Gold ledger hash space under BP-B: claim_texts payload (E-B12B)."""
    return digest_hex(
        {
            "case_id": case_id,
            "kind": BindingPolicy.BP_B.value,
            "claim_texts": [str(t) for t in claim_texts],
        }
    )


def gold_ledger_digest_from_case(gold_case: Mapping[str, Any]) -> str:
    """Recompute BP-B ledger digest from asserted_claims texts."""
    claims = gold_case.get("asserted_claims") or []
    texts = [str(c["text"]) for c in claims]
    return gold_claim_texts_digest(str(gold_case["case_id"]), texts)


def evidence_pool_digest(excerpts: Sequence[Mapping[str, Any]]) -> str:
    """Evidence pool hash space: [{chunk_id, content}, ...] (E-B12B)."""
    payload = [
        {"chunk_id": str(item["chunk_id"]), "content": str(item["content"])}
        for item in excerpts
    ]
    return digest_hex(payload)


def assert_same_hash_space(left: HashSpace, right: HashSpace) -> None:
    if left != right:
        raise BindingGateError(
            f"refusing cross-space digest compare: {left.value} vs {right.value}"
        )


def digests_equal(
    left: str | None,
    right: str | None,
    *,
    space: HashSpace,
) -> bool:
    """Equality inside one declared hash space (prefix-normalized)."""
    _ = space  # documents caller intent; cross-space blocked by assert_same_hash_space
    a = normalize_digest(left)
    b = normalize_digest(right)
    if a is None or b is None:
        return False
    return a == b


# ---------------------------------------------------------------------------
# Binding artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BindingArtifact:
    """after_snapshot.case_id ↔ gold.case_id under an explicit BP-* policy."""

    protocol_version: str
    artifact_kind: str
    after_case_id: str
    gold_case_id: str
    binding_policy: str
    after_content_hash: str | None = None
    gold_content_sha256: str | None = None
    gold_content_binding_kind: str | None = None
    observed_evidence_ids: tuple[str, ...] = ()
    gold_evidence_ids: tuple[str, ...] = ()
    observed_pool_sha256: str | None = None
    gold_pool_sha256: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BindingResult:
    verdict: BindingVerdict
    binding_policy: BindingPolicy
    after_case_id: str
    gold_case_id: str
    reasons: tuple[str, ...] = ()
    t2_t3_eligible: bool = False
    measurement_claims_allowed: tuple[str, ...] = ()
    hash_spaces_checked: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        payload["binding_policy"] = self.binding_policy.value
        return payload


def build_binding_artifact(
    *,
    after_case_id: str,
    gold_case_id: str,
    binding_policy: BindingPolicy | str,
    after_content_hash: str | None = None,
    gold_case: Mapping[str, Any] | None = None,
    observed_evidence_ids: Sequence[str] | None = None,
    observed_pool_sha256: str | None = None,
    notes: str | None = None,
) -> BindingArtifact:
    """Construct the binding artifact linking After case_id to gold case_id."""
    policy = BindingPolicy(binding_policy)
    gold_kind = None
    gold_hash = None
    gold_eids: tuple[str, ...] = ()
    gold_pool = None
    if gold_case is not None:
        binding = gold_case.get("content_binding") or {}
        pool = gold_case.get("gated_pool_binding") or {}
        gold_kind = binding.get("kind")
        gold_hash = binding.get("content_sha256")
        gold_eids = tuple(str(x) for x in (pool.get("evidence_ids") or []))
        gold_pool = pool.get("pool_sha256")
    return BindingArtifact(
        protocol_version=PROTOCOL_VERSION,
        artifact_kind=ARTIFACT_KIND,
        after_case_id=str(after_case_id),
        gold_case_id=str(gold_case_id),
        binding_policy=policy.value,
        after_content_hash=after_content_hash,
        gold_content_sha256=gold_hash,
        gold_content_binding_kind=str(gold_kind) if gold_kind is not None else None,
        observed_evidence_ids=tuple(str(x) for x in (observed_evidence_ids or ())),
        gold_evidence_ids=gold_eids,
        observed_pool_sha256=observed_pool_sha256,
        gold_pool_sha256=str(gold_pool) if gold_pool is not None else None,
        notes=notes,
    )


def validate_binding_artifact_shape(artifact: Mapping[str, Any] | BindingArtifact) -> None:
    payload = artifact.to_dict() if isinstance(artifact, BindingArtifact) else dict(artifact)
    for key in FORBIDDEN_KEYS:
        if key in payload:
            raise BindingGateError(f"forbidden key in binding artifact: {key}")
    required = (
        "protocol_version",
        "artifact_kind",
        "after_case_id",
        "gold_case_id",
        "binding_policy",
    )
    missing = [k for k in required if k not in payload or payload[k] in (None, "")]
    if missing:
        raise BindingGateError(f"binding artifact missing fields: {missing}")
    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise BindingGateError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload["artifact_kind"] != ARTIFACT_KIND:
        raise BindingGateError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    BindingPolicy(payload["binding_policy"])  # raises ValueError if unknown


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def claim_texts_present_in_content(
    asserted_claims: Sequence[Mapping[str, Any]],
    content: str,
) -> tuple[bool, tuple[str, ...]]:
    """BP-B body integrity: each claim.text locatable in After (whitespace-normalized)."""
    body = _normalize_ws(content)
    missing: list[str] = []
    for claim in asserted_claims:
        claim_id = str(claim.get("claim_id", "?"))
        text = _normalize_ws(str(claim.get("text", "")))
        if not text or text not in body:
            missing.append(claim_id)
    return (not missing, tuple(missing))


def _pool_bind_ok(
    *,
    gold_evidence_ids: Sequence[str],
    observed_evidence_ids: Sequence[str],
    gold_pool_sha256: str | None,
    observed_pool_sha256: str | None,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    gold_set = {str(x) for x in gold_evidence_ids}
    observed_set = {str(x) for x in observed_evidence_ids}
    if not gold_set.issubset(observed_set):
        reasons.append(
            f"pool drift: gold evidence_ids not ⊆ observed "
            f"(missing={sorted(gold_set - observed_set)})"
        )
    if gold_pool_sha256 is not None and observed_pool_sha256 is not None:
        assert_same_hash_space(HashSpace.EVIDENCE_POOL, HashSpace.EVIDENCE_POOL)
        if not digests_equal(
            gold_pool_sha256,
            observed_pool_sha256,
            space=HashSpace.EVIDENCE_POOL,
        ):
            reasons.append("evidence_pool_hash mismatch")
    return (not reasons, tuple(reasons))


# ---------------------------------------------------------------------------
# Binding validator
# ---------------------------------------------------------------------------


def validate_binding(
    *,
    after_case_id: str,
    gold_case: Mapping[str, Any],
    binding_policy: BindingPolicy | str,
    after_content: str | None = None,
    after_content_hash: str | None = None,
    observed_evidence_ids: Sequence[str] | None = None,
    observed_pool_sha256: str | None = None,
    require_claim_presence: bool = True,
) -> BindingResult:
    """Deterministic Binding Gate. Does not score T2/T3."""
    policy = BindingPolicy(binding_policy)
    gold_case_id = str(gold_case.get("case_id", ""))
    content_binding = gold_case.get("content_binding") or {}
    pool_binding = gold_case.get("gated_pool_binding") or {}
    gold_kind = str(content_binding.get("kind", ""))
    gold_hash = content_binding.get("content_sha256")
    gold_eids = [str(x) for x in (pool_binding.get("evidence_ids") or [])]
    gold_pool = pool_binding.get("pool_sha256")
    observed_ids = [str(x) for x in (observed_evidence_ids or [])]

    spaces: list[str] = []
    reasons: list[str] = []

    if str(after_case_id) != gold_case_id:
        return BindingResult(
            verdict=BindingVerdict.INVALID,
            binding_policy=policy,
            after_case_id=str(after_case_id),
            gold_case_id=gold_case_id,
            reasons=(f"case_id mismatch: after={after_case_id!r} gold={gold_case_id!r}",),
            t2_t3_eligible=False,
        )

    # --- BP-C: refusal → T4 exclusion ---
    if policy is BindingPolicy.BP_C:
        return BindingResult(
            verdict=BindingVerdict.EXCLUDED_T4,
            binding_policy=policy,
            after_case_id=str(after_case_id),
            gold_case_id=gold_case_id,
            reasons=("BP-C refusal_exclude: skip T2/T3; T4 only",),
            t2_t3_eligible=False,
            measurement_claims_allowed=("refusal_behavior_t4",),
            details={"formal_candidate": False},
        )

    # --- BP-A: observed_after = formal candidate ---
    if policy is BindingPolicy.BP_A:
        if gold_kind != BindingPolicy.BP_A.value:
            return BindingResult(
                verdict=BindingVerdict.INCOMPATIBLE,
                binding_policy=policy,
                after_case_id=str(after_case_id),
                gold_case_id=gold_case_id,
                reasons=(
                    f"BP-A requires gold.content_binding.kind="
                    f"{BindingPolicy.BP_A.value!r} (got {gold_kind!r})",
                ),
                t2_t3_eligible=False,
                details={"formal_candidate": False},
            )
        if after_content is None and after_content_hash is None:
            return BindingResult(
                verdict=BindingVerdict.INVALID,
                binding_policy=policy,
                after_case_id=str(after_case_id),
                gold_case_id=gold_case_id,
                reasons=("BP-A requires after_content or after_content_hash",),
                t2_t3_eligible=False,
            )
        observed_digest = (
            observed_content_digest(after_content)
            if after_content is not None
            else normalize_digest(after_content_hash)
        )
        spaces.append(HashSpace.OBSERVED_CONTENT.value)
        # Under BP-A rebound, gold.content_sha256 uses the observed-content codec
        # (bare hex of content string) — same space after prefix normalize.
        if observed_digest is None or not digests_equal(
            observed_digest,
            str(gold_hash) if gold_hash is not None else None,
            space=HashSpace.OBSERVED_CONTENT,
        ):
            reasons.append("BP-A content hash mismatch (observed vs gold rebound)")
        pool_ok, pool_reasons = _pool_bind_ok(
            gold_evidence_ids=gold_eids,
            observed_evidence_ids=observed_ids,
            gold_pool_sha256=str(gold_pool) if gold_pool is not None else None,
            observed_pool_sha256=observed_pool_sha256,
        )
        if gold_pool is not None or observed_pool_sha256 is not None:
            spaces.append(HashSpace.EVIDENCE_POOL.value)
        if not pool_ok:
            reasons.extend(pool_reasons)
        if reasons:
            return BindingResult(
                verdict=BindingVerdict.INVALID,
                binding_policy=policy,
                after_case_id=str(after_case_id),
                gold_case_id=gold_case_id,
                reasons=tuple(reasons),
                t2_t3_eligible=False,
                hash_spaces_checked=tuple(spaces),
                details={"formal_candidate": True},
            )
        return BindingResult(
            verdict=BindingVerdict.BOUND,
            binding_policy=policy,
            after_case_id=str(after_case_id),
            gold_case_id=gold_case_id,
            reasons=("BP-A observed_after body+pool bound",),
            t2_t3_eligible=True,
            measurement_claims_allowed=("product_path_faithfulness",),
            hash_spaces_checked=tuple(spaces),
            details={"formal_candidate": True},
        )

    # --- BP-B: synthetic_authored = test only ---
    if policy is BindingPolicy.BP_B:
        if gold_kind != BindingPolicy.BP_B.value:
            return BindingResult(
                verdict=BindingVerdict.INCOMPATIBLE,
                binding_policy=policy,
                after_case_id=str(after_case_id),
                gold_case_id=gold_case_id,
                reasons=(
                    f"BP-B requires gold.content_binding.kind="
                    f"{BindingPolicy.BP_B.value!r} (got {gold_kind!r})",
                ),
                t2_t3_eligible=False,
                details={"formal_candidate": False, "protocol_only": True},
            )
        # Ledger self-consistency in GOLD_LEDGER space (never vs After content hash).
        spaces.append(HashSpace.GOLD_LEDGER.value)
        if after_content_hash is not None:
            spaces.append(HashSpace.OBSERVED_CONTENT.value)
        recomputed = gold_ledger_digest_from_case(gold_case)
        if not digests_equal(
            recomputed,
            str(gold_hash) if gold_hash is not None else None,
            space=HashSpace.GOLD_LEDGER,
        ):
            reasons.append("gold ledger claim_texts digest drift")
        if after_content is None:
            reasons.append("BP-B requires after_content for claim-text presence")
        elif require_claim_presence:
            ok, missing = claim_texts_present_in_content(
                list(gold_case.get("asserted_claims") or []),
                after_content,
            )
            if not ok:
                reasons.append(f"claim text presence fail: missing={list(missing)}")
        pool_ok, pool_reasons = _pool_bind_ok(
            gold_evidence_ids=gold_eids,
            observed_evidence_ids=observed_ids,
            gold_pool_sha256=str(gold_pool) if gold_pool is not None else None,
            observed_pool_sha256=observed_pool_sha256,
        )
        if gold_pool is not None or observed_pool_sha256 is not None:
            spaces.append(HashSpace.EVIDENCE_POOL.value)
        if not pool_ok:
            reasons.extend(pool_reasons)
        if reasons:
            return BindingResult(
                verdict=BindingVerdict.INVALID,
                binding_policy=policy,
                after_case_id=str(after_case_id),
                gold_case_id=gold_case_id,
                reasons=tuple(reasons),
                t2_t3_eligible=False,
                hash_spaces_checked=tuple(spaces),
                details={"formal_candidate": False, "protocol_only": True},
            )
        return BindingResult(
            verdict=BindingVerdict.BOUND,
            binding_policy=policy,
            after_case_id=str(after_case_id),
            gold_case_id=gold_case_id,
            reasons=("BP-B synthetic_authored presence+pool bound (protocol only)",),
            t2_t3_eligible=True,
            measurement_claims_allowed=("protocol_scorability_wiring_only",),
            hash_spaces_checked=tuple(spaces),
            details={"formal_candidate": False, "protocol_only": True},
        )

    raise BindingGateError(f"unsupported binding_policy: {policy}")


def refuse_naive_cross_space_compare(
    after_content_hash: str,
    gold_content_sha256: str,
) -> BindingVerdict:
    """Explicitly refuse treating E-B15 hash == E-B12B payload hash as bind."""
    # Normalize both for shape only; equality does not imply same space.
    _ = normalize_digest(after_content_hash)
    _ = normalize_digest(gold_content_sha256)
    return BindingVerdict.INCOMPATIBLE


def assert_formal_gates_remain_locked() -> None:
    if E_B_FORMAL_READY != "NO":
        raise BindingGateError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise BindingGateError(
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO"
        )
    if T2_T3_SCORER_IMPLEMENTED != "NO":
        raise BindingGateError("E-B17 must not claim T2/T3 scorer implemented")


def remaining_blockers() -> list[dict[str, str]]:
    """After E-B17: binding gate exists; material/formal residuals remain."""
    return [
        {
            "id": "AG-1",
            "status": "OPEN",
            "detail": (
                "E-B12B gold content_sha256 = claim_texts payload; "
                "E-B15 after_content_hash = content string — incompatible spaces"
            ),
        },
        {
            "id": "AG-2",
            "status": "MITIGATED_BY_CODEC",
            "detail": (
                "Prefix sha256: vs bare hex normalized by Binding Gate; "
                "does not clear AG-1 space mismatch"
            ),
        },
        {
            "id": "AG-3",
            "status": "PARTIAL",
            "detail": "Binding gate YES; T2/T3 scorer still NO",
        },
        {
            "id": "AG-4",
            "status": "OPEN",
            "detail": "E-B15 degraded/refusal After fails BP-B claim-text presence",
        },
        {
            "id": "AG-5",
            "status": "OPEN",
            "detail": "No BP-A rebound gold (kind=observed_after) for product After",
        },
        {
            "id": "AG-6",
            "status": "OPEN",
            "detail": "E-B6 isomorphic synthetic bodies ≠ E-B12B claim_texts",
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
    ]


def readiness_summary() -> dict[str, Any]:
    assert_formal_gates_remain_locked()
    return {
        "window": WINDOW_ID,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "parent_design": PARENT_DESIGN,
        "BINDING_GATE_IMPLEMENTED": BINDING_GATE_IMPLEMENTED,
        "GOLD_AFTER_BINDING_COMPATIBLE": GOLD_AFTER_BINDING_COMPATIBLE,
        "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        "policies": {
            "BP-A": BindingPolicy.BP_A.value,
            "BP-B": BindingPolicy.BP_B.value,
            "BP-C": BindingPolicy.BP_C.value,
        },
        "hash_spaces": [s.value for s in HashSpace],
        "remaining_blockers": remaining_blockers(),
    }


def policy_capabilities() -> dict[str, Mapping[str, Any]]:
    """Document what each BP may prove (frozen for scorer honesty)."""
    return {
        "BP-A": {
            "policy": BindingPolicy.BP_A.value,
            "role": "formal_candidate",
            "body_rule": "gold kind=observed_after; content-string hash equal (normalized)",
            "may_prove": "product_path_faithfulness (after owner auth)",
            "t2_t3": "eligible_when_BOUND",
        },
        "BP-B": {
            "policy": BindingPolicy.BP_B.value,
            "role": "test_only",
            "body_rule": "claim_texts ledger hash self-check + claim text presence in After",
            "may_prove": "protocol_scorability_wiring_only",
            "must_not_claim": "product_faithfulness",
            "t2_t3": "eligible_when_BOUND_but_protocol_only",
        },
        "BP-C": {
            "policy": BindingPolicy.BP_C.value,
            "role": "t4_exclusion",
            "body_rule": "skip T2/T3",
            "may_prove": "refusal_behavior_t4",
            "t2_t3": "excluded",
        },
    }

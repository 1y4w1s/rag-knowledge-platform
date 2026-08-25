"""W10 E-B18 — Gold↔After Binding Compatibility Materialization (tests/docs only).

Materializes BP-A rebound gold + after_snapshot stubs so that
``after_snapshot.case_id ↔ gold.case_id`` binds under the same hash space
(observed content string), clearing AG-1 for the BP-A compatibility path.

Does not: call LLM / LM Studio, implement T2/T3 scorer, write reserved
formal observation results, modify backend/app, or flip E-B_FORMAL_READY.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb17_binding_gate import (
    ARTIFACT_KIND as BINDING_ARTIFACT_KIND,
    BindingPolicy,
    BindingVerdict,
    HashSpace,
    assert_same_hash_space,
    build_binding_artifact,
    digests_equal,
    format_observed_content_hash,
    gold_ledger_digest_from_case,
    normalize_digest,
    observed_content_digest,
    refuse_naive_cross_space_compare,
    validate_binding,
    validate_binding_artifact_shape,
)

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B18"
PROTOCOL_VERSION = "w10_eb18_gold_after_binding_compatibility_v1"
ARTIFACT_KIND = "GOLD_AFTER_BINDING_COMPATIBILITY"
PARENT_GATE = "w10_eb17_binding_gate_v1"
PARENT_GOLD = "w10-eb-generation-claim-gold-v1.json"
AFTER_SOURCE = "compatibility_materialization_author_owned"

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
COMPAT_FILENAME = "w10-eb-bp-a-binding-compatibility-v1.json"
COMPAT_PATH = FIXTURES / COMPAT_FILENAME

BINDING_GATE_IMPLEMENTED = "YES"
COMPATIBILITY_MATERIALIZED = "YES"
GOLD_AFTER_BINDING_COMPATIBLE = "YES"  # BP-A rebound pack; not live E-B15×E-B12B
LIVE_EB15_X_EB12B_COMPATIBLE = "NO"
T2_T3_SCORER_IMPLEMENTED = "NO"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

C12_CASE_ID = "C12-out-of-scope-provenance"

FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "llm_judge",
        "nli_label",
        "auto_label",
        "unsupported_rate",
        "grounded_rate",
        "formal_score",
        "FORMAL_OBSERVATION_RESULT",
    }
)


class CompatibilityError(ValueError):
    """Raised when BP-A compatibility materialization / validation fails."""


# ---------------------------------------------------------------------------
# Hash generation + verification contract (three spaces)
# ---------------------------------------------------------------------------

HASH_RULES: dict[str, Mapping[str, str]] = {
    HashSpace.GOLD_LEDGER.value: {
        "name": "gold_ledger_hash",
        "wire": "bare 64-hex",
        "generate_bp_b": (
            "sha256(canonical_json({case_id, kind=synthetic_authored, claim_texts}))"
        ),
        "generate_bp_a": (
            "sha256(canonical_json(after_content_string)) — same codec as "
            "observed_content_hash bare hex; store on gold.content_binding.content_sha256"
        ),
        "verify_bp_b": "recompute claim_texts digest == gold.content_sha256 (GOLD_LEDGER)",
        "verify_bp_a": (
            "normalize(gold.content_sha256) == observed_content_digest(after) "
            "(OBSERVED_CONTENT space after rebound; never vs unrebounded payload hash)"
        ),
    },
    HashSpace.OBSERVED_CONTENT.value: {
        "name": "observed_content_hash",
        "wire": "sha256:{hex} (E-B15) or bare hex (comparator)",
        "generate": "sha256(canonical_json(state['content'] string))",
        "verify": (
            "normalize(after_content_hash) == observed_content_digest(after_content); "
            "under BP-A also == gold.content_sha256 after rebound"
        ),
    },
    HashSpace.EVIDENCE_POOL.value: {
        "name": "evidence_pool_hash",
        "wire": "bare 64-hex",
        "generate": "sha256(canonical_json([{chunk_id, content}, ...]))",
        "verify": (
            "gold.pool_sha256 == observed_pool_sha256 when both present; "
            "gold.evidence_ids ⊆ observed_evidence_ids"
        ),
    },
}


def hash_generation_rules() -> dict[str, Mapping[str, str]]:
    """Frozen contract for the three hash spaces (docs + tests)."""
    return {k: dict(v) for k, v in HASH_RULES.items()}


def verify_observed_content_hash(content: str, after_content_hash: str) -> bool:
    assert_same_hash_space(HashSpace.OBSERVED_CONTENT, HashSpace.OBSERVED_CONTENT)
    return digests_equal(
        format_observed_content_hash(content),
        after_content_hash,
        space=HashSpace.OBSERVED_CONTENT,
    )


def verify_bp_a_gold_content_hash(content: str, gold_content_sha256: str) -> bool:
    """BP-A: gold.content_sha256 must be observed-content codec (bare hex)."""
    assert_same_hash_space(HashSpace.OBSERVED_CONTENT, HashSpace.OBSERVED_CONTENT)
    return digests_equal(
        observed_content_digest(content),
        gold_content_sha256,
        space=HashSpace.OBSERVED_CONTENT,
    )


def verify_evidence_pool_hash(
    gold_pool_sha256: str | None,
    observed_pool_sha256: str | None,
) -> bool:
    if gold_pool_sha256 is None or observed_pool_sha256 is None:
        return gold_pool_sha256 is None and observed_pool_sha256 is None
    assert_same_hash_space(HashSpace.EVIDENCE_POOL, HashSpace.EVIDENCE_POOL)
    return digests_equal(
        gold_pool_sha256,
        observed_pool_sha256,
        space=HashSpace.EVIDENCE_POOL,
    )


# ---------------------------------------------------------------------------
# Materialization
# ---------------------------------------------------------------------------


def author_owned_after_body(gold_case: Mapping[str, Any]) -> str:
    """Deterministic After body embedding human claim texts (compatibility only).

    Not a product stream / live LLM After. Honesty: AFTER_SOURCE.
    """
    claims = list(gold_case.get("asserted_claims") or [])
    if not claims:
        raise CompatibilityError(
            f"{gold_case.get('case_id')}: cannot build BP-A body without claims"
        )
    lines = [str(c["text"]) for c in claims]
    return "\n".join(lines)


def rebound_gold_case_for_bp_a(
    human_gold_case: Mapping[str, Any],
    *,
    after_content: str,
) -> dict[str, Any]:
    """Copy human claims/pool; rebind content to observed_after content-string hash."""
    case_id = str(human_gold_case["case_id"])
    if case_id == C12_CASE_ID:
        raise CompatibilityError(f"{C12_CASE_ID} is excluded from BP-A rebound pack")
    kind = (human_gold_case.get("content_binding") or {}).get("kind")
    if kind != BindingPolicy.BP_B.value:
        raise CompatibilityError(
            f"{case_id}: expected human gold kind={BindingPolicy.BP_B.value!r}, got {kind!r}"
        )
    rebound = deepcopy(dict(human_gold_case))
    digest = observed_content_digest(after_content)
    parent_id = (human_gold_case.get("content_binding") or {}).get("synthetic_body_id")
    rebound["content_binding"] = {
        "kind": BindingPolicy.BP_A.value,
        "content_sha256": digest,
        "rebound_from": parent_id or f"human_claim_gold_v1::{case_id}",
        "parent_ledger": PARENT_GOLD,
        "parent_kind": BindingPolicy.BP_B.value,
    }
    rebound["notes"] = (
        "BP-A_REBOUND_FOR_COMPATIBILITY. "
        f"after_source={AFTER_SOURCE}. "
        "content_sha256 uses observed_content codec (content string), not claim_texts payload. "
        "Does not prove live product LLM faithfulness. E-B_FORMAL_READY=NO."
    )
    return rebound


def build_after_snapshot_stub(
    *,
    case_id: str,
    after_content: str,
    observed_evidence_ids: Sequence[str],
    observed_pool_sha256: str | None,
) -> dict[str, Any]:
    return {
        "case_id": str(case_id),
        "after_content": after_content,
        "after_content_hash": format_observed_content_hash(after_content),
        "observed_evidence_ids": [str(x) for x in observed_evidence_ids],
        "observed_pool_sha256": observed_pool_sha256,
        "after_source": AFTER_SOURCE,
        "llm_called": False,
        "formal_measurement": False,
        "product_stream": False,
    }


@dataclass(frozen=True, slots=True)
class CompatibilityCase:
    after_snapshot: Mapping[str, Any]
    rebound_gold: Mapping[str, Any]
    binding_artifact: Mapping[str, Any]
    binding_verdict: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "after_snapshot": dict(self.after_snapshot),
            "rebound_gold": dict(self.rebound_gold),
            "binding_artifact": dict(self.binding_artifact),
            "binding_verdict": self.binding_verdict,
            "details": dict(self.details),
        }


def materialize_compatibility_case(human_gold_case: Mapping[str, Any]) -> CompatibilityCase:
    """after_snapshot.case_id ↔ gold.case_id under BP-A rebound."""
    case_id = str(human_gold_case["case_id"])
    after_content = author_owned_after_body(human_gold_case)
    pool = human_gold_case.get("gated_pool_binding") or {}
    evidence_ids = [str(x) for x in (pool.get("evidence_ids") or [])]
    pool_hash = pool.get("pool_sha256")
    pool_hash_s = str(pool_hash) if pool_hash is not None else None

    rebound = rebound_gold_case_for_bp_a(human_gold_case, after_content=after_content)
    after_snap = build_after_snapshot_stub(
        case_id=case_id,
        after_content=after_content,
        observed_evidence_ids=evidence_ids,
        observed_pool_sha256=pool_hash_s,
    )
    artifact = build_binding_artifact(
        after_case_id=case_id,
        gold_case_id=case_id,
        binding_policy=BindingPolicy.BP_A,
        after_content_hash=after_snap["after_content_hash"],
        gold_case=rebound,
        observed_evidence_ids=evidence_ids,
        observed_pool_sha256=pool_hash_s,
        notes="E-B18 BP-A compatibility materialization",
    )
    validate_binding_artifact_shape(artifact)
    # Ensure case_id identity on the binding artifact.
    if artifact.after_case_id != artifact.gold_case_id:
        raise CompatibilityError("binding artifact case_id identity broken")

    result = validate_binding(
        after_case_id=case_id,
        gold_case=rebound,
        binding_policy=BindingPolicy.BP_A,
        after_content=after_content,
        after_content_hash=after_snap["after_content_hash"],
        observed_evidence_ids=evidence_ids,
        observed_pool_sha256=pool_hash_s,
    )
    if result.verdict != BindingVerdict.BOUND:
        raise CompatibilityError(
            f"{case_id}: expected BOUND after rebound, got {result.verdict.value}: "
            f"{list(result.reasons)}"
        )
    return CompatibilityCase(
        after_snapshot=after_snap,
        rebound_gold=rebound,
        binding_artifact=artifact.to_dict(),
        binding_verdict=result.verdict.value,
        details={
            "formal_candidate_codec": True,
            "compatibility_proof_only": True,
            "product_faithfulness_proven": False,
            "hash_spaces": [
                HashSpace.OBSERVED_CONTENT.value,
                HashSpace.EVIDENCE_POOL.value,
            ],
            "parent_gold_ledger_hash_bp_b": gold_ledger_digest_from_case(human_gold_case),
            "rebound_observed_content_hash": observed_content_digest(after_content),
        },
    )


def materialize_compatibility_pack(
    human_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build full BP-A compatibility pack from E-B12B human claim gold."""
    ledger = human_ledger if human_ledger is not None else load_claim_gold_ledger()
    cases_out: list[dict[str, Any]] = []
    excluded: list[str] = []
    for case in ledger["cases"]:
        case_id = str(case["case_id"])
        claims = case.get("asserted_claims") or []
        if case_id == C12_CASE_ID or not claims:
            excluded.append(case_id)
            continue
        cases_out.append(materialize_compatibility_case(case).to_dict())

    pack: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "parent_gate_protocol": PARENT_GATE,
        "parent_binding_artifact_kind": BINDING_ARTIFACT_KIND,
        "parent_gold_ledger": PARENT_GOLD,
        "window": WINDOW_ID,
        "binding_policy": BindingPolicy.BP_A.value,
        "after_source": AFTER_SOURCE,
        "hash_rules": hash_generation_rules(),
        "gates": {
            "BINDING_GATE_IMPLEMENTED": BINDING_GATE_IMPLEMENTED,
            "COMPATIBILITY_MATERIALIZED": COMPATIBILITY_MATERIALIZED,
            "GOLD_AFTER_BINDING_COMPATIBLE": GOLD_AFTER_BINDING_COMPATIBLE,
            "LIVE_EB15_X_EB12B_COMPATIBLE": LIVE_EB15_X_EB12B_COMPATIBLE,
            "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
            "E-B_FORMAL_READY": E_B_FORMAL_READY,
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
            "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        },
        "notes": (
            "BP-A binding compatibility pack. "
            "Rebounds human synthetic_authored gold → observed_after content-string hash. "
            "After bodies are author-owned claim-text embeddings for codec proof only. "
            "Live E-B15 degraded/refusal × unrebounded E-B12B remains incompatible. "
            "No LLM, no scorer, no formal observation, E-B_FORMAL_READY=NO."
        ),
        "excluded_case_ids": excluded,
        "cases": cases_out,
    }
    validate_compatibility_pack(pack)
    return pack


def write_compatibility_pack(
    pack: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> Path:
    target = path or COMPAT_PATH
    validate_compatibility_pack(pack)
    target.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_compatibility_pack(*, path: Path | None = None) -> dict[str, Any]:
    target = path or COMPAT_PATH
    if not target.is_file():
        raise CompatibilityError(f"compatibility pack missing: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CompatibilityError("compatibility pack must be a JSON object")
    validate_compatibility_pack(payload)
    return payload


# ---------------------------------------------------------------------------
# Compatibility validator
# ---------------------------------------------------------------------------


def validate_compatibility_pack(pack: Mapping[str, Any]) -> None:
    for key in FORBIDDEN_KEYS:
        if key in pack:
            raise CompatibilityError(f"forbidden key in compatibility pack: {key}")
    required = (
        "protocol_version",
        "artifact_kind",
        "binding_policy",
        "cases",
        "gates",
        "hash_rules",
    )
    missing = [k for k in required if k not in pack]
    if missing:
        raise CompatibilityError(f"compatibility pack missing fields: {missing}")
    if pack["protocol_version"] != PROTOCOL_VERSION:
        raise CompatibilityError(f"protocol_version must be {PROTOCOL_VERSION!r}")
    if pack["artifact_kind"] != ARTIFACT_KIND:
        raise CompatibilityError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if pack["binding_policy"] != BindingPolicy.BP_A.value:
        raise CompatibilityError("compatibility pack binding_policy must be observed_after")
    gates = pack["gates"]
    if gates.get("E-B_FORMAL_READY") != "NO":
        raise CompatibilityError("E-B_FORMAL_READY must remain NO")
    if gates.get("T2_T3_SCORER_IMPLEMENTED") != "NO":
        raise CompatibilityError("E-B18 must not claim T2/T3 scorer implemented")
    if gates.get("GOLD_AFTER_BINDING_COMPATIBLE") != "YES":
        raise CompatibilityError("materialized pack must stamp GOLD_AFTER_BINDING_COMPATIBLE=YES")
    if gates.get("LIVE_EB15_X_EB12B_COMPATIBLE") != "NO":
        raise CompatibilityError("live E-B15×E-B12B must remain NO")

    cases = pack["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise CompatibilityError("cases must be an array")
    if len(cases) < 1:
        raise CompatibilityError("compatibility pack requires ≥1 BP-A case")

    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise CompatibilityError(f"cases[{index}] must be an object")
        validate_compatibility_case(case, path=f"cases[{index}]")
        cid = str(case["after_snapshot"]["case_id"])
        if cid in seen:
            raise CompatibilityError(f"duplicate case_id {cid!r}")
        seen.add(cid)


def validate_compatibility_case(
    case: Mapping[str, Any],
    *,
    path: str = "case",
) -> dict[str, Any]:
    """End-to-end BP-A compatibility check for one materialized case."""
    after = case.get("after_snapshot")
    gold = case.get("rebound_gold")
    artifact = case.get("binding_artifact")
    if not isinstance(after, Mapping):
        raise CompatibilityError(f"{path}.after_snapshot must be an object")
    if not isinstance(gold, Mapping):
        raise CompatibilityError(f"{path}.rebound_gold must be an object")
    if not isinstance(artifact, Mapping):
        raise CompatibilityError(f"{path}.binding_artifact must be an object")

    after_id = str(after.get("case_id", ""))
    gold_id = str(gold.get("case_id", ""))
    if not after_id or after_id != gold_id:
        raise CompatibilityError(
            f"{path}: after_snapshot.case_id must equal gold.case_id "
            f"(after={after_id!r} gold={gold_id!r})"
        )
    if str(artifact.get("after_case_id")) != after_id or str(artifact.get("gold_case_id")) != gold_id:
        raise CompatibilityError(f"{path}: binding artifact case_id mismatch")
    if artifact.get("binding_policy") != BindingPolicy.BP_A.value:
        raise CompatibilityError(f"{path}: binding_policy must be observed_after")

    validate_binding_artifact_shape(artifact)

    content = after.get("after_content")
    after_hash = after.get("after_content_hash")
    if not isinstance(content, str) or not content:
        raise CompatibilityError(f"{path}: after_content required")
    if not isinstance(after_hash, str):
        raise CompatibilityError(f"{path}: after_content_hash required")
    if not verify_observed_content_hash(content, after_hash):
        raise CompatibilityError(f"{path}: observed_content_hash generation/verify fail")

    binding = gold.get("content_binding") or {}
    if binding.get("kind") != BindingPolicy.BP_A.value:
        raise CompatibilityError(f"{path}: rebound gold kind must be observed_after")
    gold_hash = binding.get("content_sha256")
    if not isinstance(gold_hash, str) or not verify_bp_a_gold_content_hash(content, gold_hash):
        raise CompatibilityError(f"{path}: BP-A gold content hash mismatch vs after body")

    # Explicit AG-1 proof: unrebounded claim_texts digest ≠ observed content digest.
    # We cannot recompute parent payload without claim_texts kind; compare stored parent note.
    parent_kind = binding.get("parent_kind")
    if parent_kind != BindingPolicy.BP_B.value:
        raise CompatibilityError(f"{path}: rebound must record parent_kind=synthetic_authored")

    pool = gold.get("gated_pool_binding") or {}
    gold_pool = pool.get("pool_sha256")
    observed_pool = after.get("observed_pool_sha256")
    gold_pool_s = str(gold_pool) if gold_pool is not None else None
    observed_pool_s = str(observed_pool) if observed_pool is not None else None
    if not verify_evidence_pool_hash(gold_pool_s, observed_pool_s):
        raise CompatibilityError(f"{path}: evidence_pool_hash mismatch")

    observed_ids = [str(x) for x in (after.get("observed_evidence_ids") or [])]
    result = validate_binding(
        after_case_id=after_id,
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content=content,
        after_content_hash=after_hash,
        observed_evidence_ids=observed_ids,
        observed_pool_sha256=observed_pool_s,
    )
    if result.verdict != BindingVerdict.BOUND:
        raise CompatibilityError(
            f"{path}: Binding Gate expected BOUND, got {result.verdict.value}: "
            f"{list(result.reasons)}"
        )
    if after.get("llm_called") is not False:
        raise CompatibilityError(f"{path}: llm_called must be false")
    if after.get("formal_measurement") is not False:
        raise CompatibilityError(f"{path}: formal_measurement must be false")
    if after.get("after_source") != AFTER_SOURCE:
        raise CompatibilityError(f"{path}: after_source must be {AFTER_SOURCE!r}")

    return {
        "case_id": after_id,
        "verdict": result.verdict.value,
        "hash_spaces_checked": list(result.hash_spaces_checked),
        "compatibility_proof_only": True,
    }


def assert_live_eb12b_still_incompatible_with_unrebounded_after() -> None:
    """Honesty: unrebounded human gold × arbitrary After content hash ≠ bind."""
    ledger = load_claim_gold_ledger()
    gold = next(c for c in ledger["cases"] if str(c["case_id"]).startswith("C01"))
    after_hash = format_observed_content_hash("unrelated product after body")
    gold_hash = gold["content_binding"]["content_sha256"]
    if refuse_naive_cross_space_compare(after_hash, gold_hash) != BindingVerdict.INCOMPATIBLE:
        raise CompatibilityError("naive cross-space compare must stay INCOMPATIBLE")
    if normalize_digest(after_hash) == normalize_digest(gold_hash):
        raise CompatibilityError("unexpected digest collision on probe body")
    result = validate_binding(
        after_case_id=gold["case_id"],
        gold_case=gold,
        binding_policy=BindingPolicy.BP_A,
        after_content="unrelated product after body",
        after_content_hash=after_hash,
        observed_evidence_ids=list(gold["gated_pool_binding"]["evidence_ids"]),
    )
    if result.verdict != BindingVerdict.INCOMPATIBLE:
        raise CompatibilityError(
            f"unrebounded gold under BP-A must be INCOMPATIBLE, got {result.verdict.value}"
        )


def remaining_blockers() -> list[dict[str, str]]:
    return [
        {
            "id": "AG-1",
            "status": "CLEARED_FOR_BP_A_REBOUND",
            "detail": (
                "BP-A rebound material uses observed_content codec for gold.content_sha256; "
                "unrebounded E-B12B payload hash path remains non-binding (correct)"
            ),
        },
        {
            "id": "AG-2",
            "status": "MITIGATED_BY_CODEC",
            "detail": "sha256: vs bare hex normalized inside one declared space",
        },
        {
            "id": "AG-3",
            "status": "PARTIAL",
            "detail": (
                "Binding gate YES + compatibility materialization YES; "
                "T2/T3 scorer still NO"
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
            "detail": (
                "BP-A rebound pack materialized for compatibility proof; "
                "live product / authorized After rebound still absent"
            ),
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
        {
            "id": "SCORER",
            "status": "NO",
            "detail": "T2_T3_SCORER_IMPLEMENTED=NO",
        },
    ]


def readiness_summary() -> dict[str, Any]:
    if E_B_FORMAL_READY != "NO":
        raise CompatibilityError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise CompatibilityError("MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO")
    if T2_T3_SCORER_IMPLEMENTED != "NO":
        raise CompatibilityError("scorer must remain unimplemented")
    return {
        "window": WINDOW_ID,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "BINDING_GATE_IMPLEMENTED": BINDING_GATE_IMPLEMENTED,
        "COMPATIBILITY_MATERIALIZED": COMPATIBILITY_MATERIALIZED,
        "GOLD_AFTER_BINDING_COMPATIBLE": GOLD_AFTER_BINDING_COMPATIBLE,
        "LIVE_EB15_X_EB12B_COMPATIBLE": LIVE_EB15_X_EB12B_COMPATIBLE,
        "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        "hash_spaces": [s.value for s in HashSpace],
        "hash_rules": hash_generation_rules(),
        "remaining_blockers": remaining_blockers(),
        "claims": {
            "llm": False,
            "formal_observation": False,
            "scorer": False,
            "product_faithfulness_proven": False,
            "bp_a_codec_compatibility": True,
        },
    }


def materialize_from_human_gold(*, write: bool = True) -> dict[str, Any]:
    pack = materialize_compatibility_pack()
    if write:
        write_compatibility_pack(pack)
    return pack

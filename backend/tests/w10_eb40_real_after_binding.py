"""W10 E-B40 — Real After Binding v2 (versioned wrapper).

Binds human claim gold identity + real observed After identity without
rewriting gold labels or E-B38 After bodies.

REAL_AFTER_BINDING_V2 ≠ E-B18 author-owned compatibility pack.
Scorer eligibility requires response_mode=ANSWER; DEGRADED may complete
provenance/hash binding but T2_T3_SCORER_ELIGIBLE=NO.

Does not: modify human gold, modify E-B38 After, call LLM/NLI, run Formal
scorer, or flip E-B_FORMAL_READY.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tests.w10_eb12b_claim_gold_materialization import load_claim_gold_ledger
from tests.w10_eb17_binding_gate import (
    BindingPolicy,
    evidence_pool_digest,
    gold_ledger_digest_from_case,
    normalize_digest,
)
from tests.w10_eb40_response_mode_gate import (
    Applicability,
    ResponseMode,
    ResponseModeClassification,
    classify_response_mode,
    load_eb38_record,
    t2_t3_denominator_admits,
)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B40"
PROTOCOL_VERSION = "w10_eb40_real_after_binding_v1"
ARTIFACT_KIND = "REAL_AFTER_BINDING_V2"
BINDING_SCHEMA = "REAL_AFTER_BINDING_V2"

REAL_AFTER_BINDING_V2_IMPLEMENTED = "YES"
FORBIDS_EB18_COMPAT_FOR_PRODUCT_AFTER = "YES"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
FORMAL_OBSERVATION = "NOT_STARTED"

EB18_COMPAT_MARKERS: frozenset[str] = frozenset(
    {
        "w10-eb-bp-a-binding-compatibility-v1",
        "author_owned",
        "author-owned",
        "claim-text embeddings",
        "eb18_compat",
        "synthetic_authored_as_observed",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class RealAfterBindingError(ValueError):
    """Raised when real-After binding v2 refuses an illegal bind."""


@dataclass(frozen=True, slots=True)
class RealAfterBindingV2:
    """Provenance wrapper: gold identity + real After identity + mode."""

    protocol_version: str
    artifact_kind: str
    binding_schema: str
    case_id: str
    gold_case_id: str
    gold_ledger_hash: str
    gold_content_binding_kind: str
    gold_labels_preserved: bool
    real_observed_content_hash: str
    evidence_pool_hash: str
    response_mode: str
    bp_class_v2: str
    provenance_bound: bool
    t2_t3_scorer_eligible: bool
    t2_applicability: str
    t3_applicability: str
    forbids_eb18_compat: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_prefixed_utf8(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def observed_pool_hash_from_citations(
    citations: Sequence[Mapping[str, Any]] | None,
) -> str:
    """Deterministic pool digest from Product After citations (chunk_id+excerpt)."""
    items = []
    for cite in citations or ():
        chunk_id = cite.get("chunk_id")
        content = cite.get("excerpt")
        if content is None:
            content = cite.get("content")
        if chunk_id is None or content is None:
            raise RealAfterBindingError(
                "citation missing chunk_id or excerpt/content for pool hash"
            )
        items.append({"chunk_id": str(chunk_id), "content": str(content)})
    return evidence_pool_digest(items)


def assert_not_eb18_compat_pack(payload: Mapping[str, Any] | str | None) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload or {}, ensure_ascii=False)
    lowered = text.lower()
    for marker in EB18_COMPAT_MARKERS:
        if marker.lower() in lowered:
            raise RealAfterBindingError(
                f"forbidden E-B18 compatibility material for Product After: {marker}"
            )


def gold_labels_snapshot(gold_case: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = gold_case.get("asserted_claims") or []
    return [
        {
            "claim_id": str(c["claim_id"]),
            "text": str(c["text"]),
            "label": str(c["label"]),
            "supporting_evidence_ids": list(c.get("supporting_evidence_ids") or []),
        }
        for c in claims
    ]


def build_real_after_binding_v2(
    *,
    observed_record: Mapping[str, Any],
    gold_case: Mapping[str, Any],
    classification: ResponseModeClassification | None = None,
) -> RealAfterBindingV2:
    """Bind human gold + real observed After; never rewrite gold labels."""
    assert_not_eb18_compat_pack(observed_record)
    assert_not_eb18_compat_pack(gold_case)

    case_id = str(observed_record.get("case_id") or "")
    gold_id = str(gold_case.get("case_id") or "")
    if not case_id or case_id != gold_id:
        raise RealAfterBindingError(
            f"case_id mismatch: after={case_id!r} gold={gold_id!r}"
        )

    labels_before = gold_labels_snapshot(gold_case)
    classification = classification or classify_response_mode(observed_record)
    if not classification.signal_available or classification.response_mode is None:
        raise RealAfterBindingError(
            f"{case_id}: cannot bind without RESPONSE_MODE_SIGNAL_AVAILABLE"
        )

    mode = classification.response_mode

    binding = gold_case.get("content_binding") or {}
    gold_kind = str(binding.get("kind") or "")
    gold_ledger_hash = gold_ledger_digest_from_case(gold_case)

    content = observed_record.get("content")
    if not isinstance(content, str):
        raise RealAfterBindingError(f"{case_id}: observed content must be str")
    recorded_hash = observed_record.get("observed_content_hash") or observed_record.get(
        "source_hash"
    )
    recomputed = _sha256_prefixed_utf8(content)
    if recorded_hash is not None and normalize_digest(str(recorded_hash)) != normalize_digest(
        recomputed
    ):
        raise RealAfterBindingError(
            f"{case_id}: observed_content_hash mismatch vs utf8 recompute"
        )
    real_hash = str(recorded_hash) if recorded_hash is not None else recomputed

    citations = observed_record.get("citations")
    if citations is not None and not isinstance(citations, list):
        raise RealAfterBindingError(f"{case_id}: citations must be list or null")
    pool_hash = observed_pool_hash_from_citations(citations)

    # Gold labels must remain byte-identical after bind construction.
    labels_after = gold_labels_snapshot(gold_case)
    if labels_before != labels_after:
        raise RealAfterBindingError(f"{case_id}: gold labels mutated during binding")

    provenance_bound = True
    # Mode gate: only ANSWER may ever be scorer-eligible. Current E-B12B
    # synthetic_authored gold + unresolved speech-act presence still keep
    # T2_T3_SCORER_ELIGIBLE=NO even for ANSWER (necessary ≠ sufficient).
    if mode is ResponseMode.ANSWER:
        t2_app = Applicability.POTENTIALLY_ELIGIBLE.value
        t3_app = Applicability.POTENTIALLY_ELIGIBLE.value
        scorer_eligible = (
            t2_t3_denominator_admits(mode)
            and gold_kind == BindingPolicy.BP_A.value
        )
        note = (
            "ANSWER mode: provenance bound; Gold Ledger ≠ speech-act proof; "
            "T2_T3_SCORER_ELIGIBLE requires observed_after gold kind"
        )
    elif mode is ResponseMode.DEGRADED:
        t2_app = Applicability.NOT_APPLICABLE.value
        t3_app = Applicability.NOT_APPLICABLE.value
        scorer_eligible = False
        note = (
            "DEGRADED: provenance/hash binding OK; T2/T3 NOT_APPLICABLE "
            "(≠ PASS / ≠ perfect score)"
        )
    else:
        t2_app = Applicability.ROUTE_REFUSAL_T4.value
        t3_app = Applicability.ROUTE_REFUSAL_T4.value
        scorer_eligible = False
        note = "REFUSAL: route to T4; not T2/T3 denominator"

    if gold_kind == BindingPolicy.BP_B.value and mode is ResponseMode.ANSWER:
        note += (
            "; gold.kind=synthetic_authored remains incompatible with BP-A "
            "formal candidacy until rebound"
        )

    return RealAfterBindingV2(
        protocol_version=PROTOCOL_VERSION,
        artifact_kind=ARTIFACT_KIND,
        binding_schema=BINDING_SCHEMA,
        case_id=case_id,
        gold_case_id=gold_id,
        gold_ledger_hash=gold_ledger_hash,
        gold_content_binding_kind=gold_kind,
        gold_labels_preserved=True,
        real_observed_content_hash=real_hash,
        evidence_pool_hash=pool_hash,
        response_mode=mode.value,
        bp_class_v2=classification.bp_class_v2,
        provenance_bound=provenance_bound,
        t2_t3_scorer_eligible=scorer_eligible,
        t2_applicability=t2_app,
        t3_applicability=t3_app,
        forbids_eb18_compat=True,
        notes=note,
    )


def bind_eb38_suite() -> list[RealAfterBindingV2]:
    ledger = load_claim_gold_ledger()
    gold_by_id = {str(c["case_id"]): c for c in ledger["cases"]}
    out: list[RealAfterBindingV2] = []
    for i in range(1, 12):
        short = f"C{i:02d}"
        record = load_eb38_record(short)
        case_id = str(record["case_id"])
        gold = gold_by_id.get(case_id)
        if gold is None:
            raise RealAfterBindingError(f"gold missing for {case_id}")
        # Deepcopy so tests can prove gold was not rewritten via shared refs.
        out.append(
            build_real_after_binding_v2(
                observed_record=record,
                gold_case=deepcopy(gold),
            )
        )
    return out


def t1_companion_status(observed_record: Mapping[str, Any]) -> dict[str, Any]:
    """T1 needs plan/gated authorized scope — not inventable from final citations."""
    has_final = bool(observed_record.get("citations"))
    has_plan_scope = any(
        observed_record.get(key)
        for key in (
            "plan_citations",
            "gated_chunks_ordered",
            "gated_chunks",
            "authorized_scope",
            "align_bucket",
        )
    )
    gen_plan_ref_only = bool(observed_record.get("gen_plan_reference")) and not has_plan_scope
    if has_final and has_plan_scope:
        return {
            "T1_REAL_AFTER_INPUT_READY": "YES",
            "T1_REQUIRES_COMPANION_REACQUISITION": "NO",
            "note": "plan/gated scope present on record",
        }
    return {
        "T1_REAL_AFTER_INPUT_READY": "NO",
        "T1_REQUIRES_COMPANION_REACQUISITION": "YES",
        "has_final_citations": has_final,
        "has_plan_or_gated_scope": has_plan_scope,
        "gen_plan_reference_only": gen_plan_ref_only,
        "forbidden": (
            "do_not_infer_authorized_scope_from_final_citations",
            "do_not_treat_final_citation_subseteq_itself_as_t1_compliance",
        ),
    }


def reacquisition_feasibility() -> dict[str, str]:
    """Same frozen baseline can capture extra product-state fields via orchestration."""
    return {
        "REACQUISITION_WITH_SAME_FROZEN_BASELINE_FEASIBLE": "YES",
        "REACQUISITION_WITH_SAME_BASELINE_VALID": "YES",
        "requires_backend_app_change": "NO",
        "frozen_base_sha": "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6",
        "note": (
            "External orchestration may persist gen_plan.gated_chunks / "
            "authorized citation scope already present in product state during "
            "E-B15 capture, without modifying frozen backend/app or reusing a "
            "mutated tree under the old stamp."
        ),
        "response_mode_signal_reacquisition_needed": "NO",
        "t1_scope_companion_reacquisition_needed": "YES",
    }


def binding_v2_summary() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "binding_schema": BINDING_SCHEMA,
        "gates": {
            "REAL_AFTER_BINDING_V2_IMPLEMENTED": REAL_AFTER_BINDING_V2_IMPLEMENTED,
            "FORBIDS_EB18_COMPAT_FOR_PRODUCT_AFTER": FORBIDS_EB18_COMPAT_FOR_PRODUCT_AFTER,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
            "FORMAL_OBSERVATION": FORMAL_OBSERVATION,
        },
    }

"""W10 E-B20 — T2/T3 Scorer Implementation (tests/docs only).

Lands the E-B19 scorer contract as a tests-only **implementation** gate:

* ``execute_score_t2`` / ``execute_score_t3`` executors (labels from gold only;
  exact citation / evidence id grounding)
* Implementation artifact build + validation
* BP-A compat pack scoring with E-B2 ``grounding_observation_status`` honesty

Does not: call LLM / LM Studio / NLI, fuzzy-match, use Critic oracle, write
reserved formal observation results, modify ``backend/app``, or flip
``E-B_FORMAL_READY``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from tests.w10_eb17_binding_gate import BindingPolicy
from tests.w10_eb18_gold_after_binding_compatibility import load_compatibility_pack
from tests.w10_eb19_t2_t3_scorer_contract import (
    ARTIFACT_KIND as CONTRACT_ARTIFACT_KIND,
    PROTOCOL_VERSION as CONTRACT_PROTOCOL_VERSION,
    ScorerContractError,
    ScorerStatus,
    T2CaseResult,
    T3CaseResult,
    edge_case_fixtures as contract_edge_case_fixtures,
    score_t2 as contract_score_t2,
    score_t3 as contract_score_t3,
    validate_t2_case_result_shape as validate_contract_t2_shape,
    validate_t3_case_result_shape as validate_contract_t3_shape,
)
from tests.w10_eb2_generation_observation_contract import (
    OBSERVATION_STATUS_VALUES,
    STATUS_INELIGIBLE,
    STATUS_NOT_OBSERVED,
    STATUS_OBSERVED_SLOT,
)

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B20"
PROTOCOL_VERSION = "w10_eb20_t2_t3_scorer_implementation_v1"
ARTIFACT_KIND = "T2_T3_SCORER_IMPLEMENTATION"
PARENT_CONTRACT = CONTRACT_PROTOCOL_VERSION
PARENT_CONTRACT_KIND = CONTRACT_ARTIFACT_KIND
PARENT_COMPAT = "w10_eb18_gold_after_binding_compatibility_v1"
PARENT_GATE = "w10_eb17_binding_gate_v1"

BINDING_GATE_IMPLEMENTED = "YES"
COMPATIBILITY_MATERIALIZED = "YES"
GOLD_AFTER_BINDING_COMPATIBLE = "YES"
T2_T3_SCORER_CONTRACT_DESIGNED = "YES"
T2_T3_SCORER_IMPLEMENTED = "YES"  # this window — tests-only, not formal
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

ALIGN_BUCKET_DEFAULT = "unspecified"

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
        "product_faithfulness_proven",
    }
)

IMPLEMENTATION_ARTIFACT_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "window",
    "parent_contract_protocol",
    "parent_contract_artifact_kind",
    "binding_policy",
    "gates",
    "cases",
    "summary",
    "honesty",
    "formal_measurement",
    "implementation_only",
)

CASE_RECORD_REQUIRED: tuple[str, ...] = (
    "case_id",
    "grounding_observation_status",
    "refusal_observation_status",
    "t2",
    "t3",
    "honesty",
)


class ScorerImplementationError(ValueError):
    """Raised when an implementation artifact or executor input is ill-formed."""


# ---------------------------------------------------------------------------
# Status mapping (scorer → E-B2 observation honesty)
# ---------------------------------------------------------------------------


def map_scorer_status_to_grounding_observation(
    status: ScorerStatus | str,
) -> str:
    """Map T2/T3 case status onto E-B2 grounding_observation_status values."""
    value = status.value if isinstance(status, ScorerStatus) else str(status)
    if value == ScorerStatus.OBSERVED_SLOT.value:
        return STATUS_OBSERVED_SLOT
    if value in (
        ScorerStatus.NOT_APPLICABLE.value,
        ScorerStatus.NOT_OBSERVED.value,
    ):
        return STATUS_NOT_OBSERVED
    if value in (
        ScorerStatus.INVALID.value,
        ScorerStatus.INCOMPATIBLE.value,
    ):
        return STATUS_INELIGIBLE
    raise ScorerImplementationError(f"unknown scorer status for E-B2 map: {value!r}")


def _combine_grounding_status(t2_status: str, t3_status: str) -> str:
    """Case-level grounding honesty: OBSERVED if either target observed."""
    if STATUS_OBSERVED_SLOT in (t2_status, t3_status):
        return STATUS_OBSERVED_SLOT
    if STATUS_INELIGIBLE in (t2_status, t3_status):
        return STATUS_INELIGIBLE
    return STATUS_NOT_OBSERVED


# ---------------------------------------------------------------------------
# Result restamp (contract → implementation)
# ---------------------------------------------------------------------------


def _restamp_t2(result: T2CaseResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["protocol_version"] = PROTOCOL_VERSION
    payload["artifact_kind"] = ARTIFACT_KIND
    payload["formal_measurement"] = False
    payload["contract_only"] = False
    payload["implementation_only"] = True
    payload["parent_contract_protocol"] = CONTRACT_PROTOCOL_VERSION
    payload["details"] = {
        **dict(result.details),
        "labels_from_gold_only": True,
        "executor": "execute_score_t2",
    }
    return payload


def _restamp_t3(result: T3CaseResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["protocol_version"] = PROTOCOL_VERSION
    payload["artifact_kind"] = ARTIFACT_KIND
    payload["formal_measurement"] = False
    payload["contract_only"] = False
    payload["implementation_only"] = True
    payload["parent_contract_protocol"] = CONTRACT_PROTOCOL_VERSION
    payload["details"] = {
        **dict(result.details),
        "exact_id_match_only": True,
        "executor": "execute_score_t3",
    }
    return payload


def validate_implementation_t2_shape(payload: Mapping[str, Any]) -> None:
    """Validate implementation T2 payload (stamps differ from contract)."""
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ScorerImplementationError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload.get("artifact_kind") != ARTIFACT_KIND:
        raise ScorerImplementationError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if payload.get("formal_measurement") is not False:
        raise ScorerImplementationError("formal_measurement must be false")
    if payload.get("implementation_only") is not True:
        raise ScorerImplementationError("implementation_only must be true")
    if payload.get("contract_only") is not False:
        raise ScorerImplementationError(
            "implementation results must set contract_only=false"
        )
    for key in FORBIDDEN_KEYS:
        if key in payload:
            raise ScorerImplementationError(f"forbidden key in T2 result: {key}")
    # Shape-check rates via contract validator on a contract-stamped copy
    probe = dict(payload)
    probe["protocol_version"] = CONTRACT_PROTOCOL_VERSION
    probe["artifact_kind"] = CONTRACT_ARTIFACT_KIND
    probe["contract_only"] = True
    probe.pop("implementation_only", None)
    probe.pop("parent_contract_protocol", None)
    try:
        validate_contract_t2_shape(probe)
    except ScorerContractError as exc:
        raise ScorerImplementationError(str(exc)) from exc


def validate_implementation_t3_shape(payload: Mapping[str, Any]) -> None:
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ScorerImplementationError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload.get("artifact_kind") != ARTIFACT_KIND:
        raise ScorerImplementationError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if payload.get("formal_measurement") is not False:
        raise ScorerImplementationError("formal_measurement must be false")
    if payload.get("implementation_only") is not True:
        raise ScorerImplementationError("implementation_only must be true")
    if payload.get("contract_only") is not False:
        raise ScorerImplementationError(
            "implementation results must set contract_only=false"
        )
    probe = dict(payload)
    probe["protocol_version"] = CONTRACT_PROTOCOL_VERSION
    probe["artifact_kind"] = CONTRACT_ARTIFACT_KIND
    probe["contract_only"] = True
    probe.pop("implementation_only", None)
    probe.pop("parent_contract_protocol", None)
    try:
        validate_contract_t3_shape(probe)
    except ScorerContractError as exc:
        raise ScorerImplementationError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def execute_score_t2(
    *,
    observed_after: Mapping[str, Any],
    claim_gold: Mapping[str, Any],
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    targets_include_t2: bool = True,
) -> dict[str, Any]:
    """Tests-only T2 executor — labels only from gold; no re-label / LLM / NLI."""
    _reject_forbidden(claim_gold, "claim_gold")
    _reject_forbidden(observed_after, "observed_after")
    raw = contract_score_t2(
        observed_after=observed_after,
        claim_gold=claim_gold,
        binding_policy=binding_policy,
        targets_include_t2=targets_include_t2,
    )
    payload = _restamp_t2(raw)
    validate_implementation_t2_shape(payload)
    return payload


def execute_score_t3(
    *,
    observed_after: Mapping[str, Any],
    claim_gold: Mapping[str, Any],
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    final_citations: Sequence[Mapping[str, Any]] | None = None,
    gated_chunks_ordered: Sequence[Mapping[str, Any]] | None = None,
    align_bucket: str = ALIGN_BUCKET_DEFAULT,
    targets_include_t3: bool = True,
) -> dict[str, Any]:
    """Tests-only T3 executor — exact id / [片段N] grounding only."""
    _reject_forbidden(claim_gold, "claim_gold")
    _reject_forbidden(observed_after, "observed_after")
    raw = contract_score_t3(
        observed_after=observed_after,
        claim_gold=claim_gold,
        binding_policy=binding_policy,
        final_citations=final_citations,
        gated_chunks_ordered=gated_chunks_ordered,
        align_bucket=align_bucket,
        targets_include_t3=targets_include_t3,
    )
    payload = _restamp_t3(raw)
    validate_implementation_t3_shape(payload)
    return payload


def _reject_forbidden(payload: Mapping[str, Any], label: str) -> None:
    for key in FORBIDDEN_KEYS:
        if key in payload:
            raise ScorerImplementationError(f"forbidden key {key!r} on {label}")


def _citations_and_chunks_for_case(
    after: Mapping[str, Any],
    gold: Mapping[str, Any],
    *,
    attach_gold_supporting_pointers: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    """Resolve T3 pointers.

    Default: use After citations if present (honest empty for author-owned compat).
    Optional wiring-only mode: attach gold supporting ids — **not** product cites.
    """
    cites = list(after.get("final_citations") or [])
    eids = [str(x) for x in gold.get("gated_pool_binding", {}).get("evidence_ids") or []]
    chunks = list(after.get("gated_chunks_ordered") or [{"chunk_id": eid} for eid in eids])
    pointer_source = "after_final_citations"
    if attach_gold_supporting_pointers and not cites:
        # Union of gold supporting ids — wiring proof only
        supporting: list[str] = []
        seen: set[str] = set()
        for claim in gold.get("asserted_claims") or []:
            if not isinstance(claim, Mapping):
                continue
            for eid in claim.get("supporting_evidence_ids") or []:
                sid = str(eid)
                if sid and sid not in seen:
                    seen.add(sid)
                    supporting.append(sid)
        cites = [{"chunk_id": sid} for sid in supporting]
        pointer_source = "gold_supporting_ids_wiring_only"
    return cites, chunks, pointer_source


@dataclass(frozen=True, slots=True)
class ImplementationCaseRecord:
    case_id: str
    grounding_observation_status: str
    refusal_observation_status: str
    t2: Mapping[str, Any]
    t3: Mapping[str, Any]
    honesty: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "grounding_observation_status": self.grounding_observation_status,
            "refusal_observation_status": self.refusal_observation_status,
            "t2": dict(self.t2),
            "t3": dict(self.t3),
            "honesty": dict(self.honesty),
        }


def score_compat_case(
    case: Mapping[str, Any],
    *,
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    attach_gold_supporting_pointers: bool = False,
    align_bucket: str = "shrink",
) -> ImplementationCaseRecord:
    """Score one E-B18 BP-A compatibility case with E-B2 honesty fields."""
    after = dict(case["after_snapshot"])
    gold = case["rebound_gold"]
    case_id = str(after.get("case_id") or gold.get("case_id") or "")
    cites, chunks, pointer_source = _citations_and_chunks_for_case(
        after,
        gold,
        attach_gold_supporting_pointers=attach_gold_supporting_pointers,
    )
    t2 = execute_score_t2(
        observed_after=after,
        claim_gold=gold,
        binding_policy=binding_policy,
    )
    t3 = execute_score_t3(
        observed_after=after,
        claim_gold=gold,
        binding_policy=binding_policy,
        final_citations=cites,
        gated_chunks_ordered=chunks,
        align_bucket=align_bucket,
    )
    g_t2 = map_scorer_status_to_grounding_observation(t2["status"])
    g_t3 = map_scorer_status_to_grounding_observation(t3["status"])
    grounding = _combine_grounding_status(g_t2, g_t3)
    if grounding not in OBSERVATION_STATUS_VALUES:
        raise ScorerImplementationError(f"invalid grounding status {grounding!r}")
    return ImplementationCaseRecord(
        case_id=case_id,
        grounding_observation_status=grounding,
        refusal_observation_status=STATUS_NOT_OBSERVED,
        t2=t2,
        t3=t3,
        honesty={
            "after_source": after.get("after_source")
            or "compatibility_materialization_author_owned",
            "product_faithfulness_proven": False,
            "formal_measurement": False,
            "implementation_only": True,
            "t3_pointer_source": pointer_source,
            "attach_gold_supporting_pointers": attach_gold_supporting_pointers,
        },
    )


def build_implementation_artifact(
    *,
    cases: Sequence[ImplementationCaseRecord] | None = None,
    binding_policy: BindingPolicy | str = BindingPolicy.BP_A,
    attach_gold_supporting_pointers: bool = False,
    include_compat_pack: bool = True,
) -> dict[str, Any]:
    """Build tests-only implementation artifact (never formal)."""
    records: list[ImplementationCaseRecord] = list(cases or [])
    if include_compat_pack and not records:
        pack = load_compatibility_pack()
        for case in pack["cases"]:
            records.append(
                score_compat_case(
                    case,
                    binding_policy=binding_policy,
                    attach_gold_supporting_pointers=attach_gold_supporting_pointers,
                )
            )

    case_dicts = [r.to_dict() for r in records]
    observed_n = sum(
        1
        for c in case_dicts
        if c["grounding_observation_status"] == STATUS_OBSERVED_SLOT
    )
    artifact = {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "window": WINDOW_ID,
        "parent_contract_protocol": PARENT_CONTRACT,
        "parent_contract_artifact_kind": PARENT_CONTRACT_KIND,
        "parent_compat_protocol": PARENT_COMPAT,
        "parent_binding_gate": PARENT_GATE,
        "binding_policy": (
            binding_policy.value
            if isinstance(binding_policy, BindingPolicy)
            else str(binding_policy)
        ),
        "gates": {
            "BINDING_GATE_IMPLEMENTED": BINDING_GATE_IMPLEMENTED,
            "COMPATIBILITY_MATERIALIZED": COMPATIBILITY_MATERIALIZED,
            "GOLD_AFTER_BINDING_COMPATIBLE": GOLD_AFTER_BINDING_COMPATIBLE,
            "T2_T3_SCORER_CONTRACT_DESIGNED": T2_T3_SCORER_CONTRACT_DESIGNED,
            "T2_T3_SCORER_IMPLEMENTED": T2_T3_SCORER_IMPLEMENTED,
            "E-B_FORMAL_READY": E_B_FORMAL_READY,
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
            "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        },
        "cases": case_dicts,
        "summary": {
            "case_count": len(case_dicts),
            "grounding_observed_slot_count": observed_n,
            "targets": ["T2", "T3"],
        },
        "honesty": {
            "product_faithfulness_proven": False,
            "formal_observation": False,
            "formal_result": False,
            "llm": False,
            "nli_auto_label": False,
            "fuzzy_matching": False,
            "critic_oracle": False,
            "labels_from_gold_only": True,
            "exact_citation_grounding_only": True,
            "compat_after_author_owned": True,
        },
        "formal_measurement": False,
        "implementation_only": True,
        "notes": (
            "Tests-only T2/T3 scorer implementation over E-B19 contract + "
            "E-B18 BP-A rebound pack. OBSERVED_SLOT means formulas applied "
            "after BOUND — not product LLM faithfulness, not formal ready."
        ),
    }
    validate_implementation_artifact(artifact)
    return artifact


def validate_implementation_artifact(payload: Mapping[str, Any]) -> None:
    missing = [k for k in IMPLEMENTATION_ARTIFACT_REQUIRED if k not in payload]
    if missing:
        raise ScorerImplementationError(f"implementation artifact missing: {missing}")
    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise ScorerImplementationError(
            f"protocol_version must be {PROTOCOL_VERSION!r}"
        )
    if payload["artifact_kind"] != ARTIFACT_KIND:
        raise ScorerImplementationError(f"artifact_kind must be {ARTIFACT_KIND!r}")
    if payload.get("formal_measurement") is not False:
        raise ScorerImplementationError("formal_measurement must be false")
    if payload.get("implementation_only") is not True:
        raise ScorerImplementationError("implementation_only must be true")
    gates = payload["gates"]
    if gates.get("T2_T3_SCORER_IMPLEMENTED") != "YES":
        raise ScorerImplementationError("T2_T3_SCORER_IMPLEMENTED must be YES")
    if gates.get("E-B_FORMAL_READY") != "NO":
        raise ScorerImplementationError("E-B_FORMAL_READY must remain NO")
    if gates.get("MAY_ENTER_FORMAL_OBSERVATION_WINDOW") != "NO":
        raise ScorerImplementationError(
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO"
        )
    honesty = payload["honesty"]
    if honesty.get("product_faithfulness_proven") is not False:
        raise ScorerImplementationError("must not claim product faithfulness")
    if honesty.get("formal_result") is not False:
        raise ScorerImplementationError("must not claim formal_result")
    for key in ("llm_judge", "nli_label", "FORMAL_OBSERVATION_RESULT", "formal_score"):
        if key in payload:
            raise ScorerImplementationError(f"forbidden top-level key: {key}")

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ScorerImplementationError("cases must be an array")
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ScorerImplementationError(f"cases[{index}] must be object")
        missing_c = [k for k in CASE_RECORD_REQUIRED if k not in case]
        if missing_c:
            raise ScorerImplementationError(
                f"cases[{index}] missing fields: {missing_c}"
            )
        g_status = case["grounding_observation_status"]
        if g_status not in OBSERVATION_STATUS_VALUES:
            raise ScorerImplementationError(
                f"cases[{index}].grounding_observation_status invalid: {g_status!r}"
            )
        if case["refusal_observation_status"] not in OBSERVATION_STATUS_VALUES:
            raise ScorerImplementationError(
                f"cases[{index}].refusal_observation_status invalid"
            )
        if case["honesty"].get("product_faithfulness_proven") is not False:
            raise ScorerImplementationError(
                f"cases[{index}] must set product_faithfulness_proven=false"
            )
        validate_implementation_t2_shape(case["t2"])
        validate_implementation_t3_shape(case["t3"])


def edge_case_fixtures() -> dict[str, dict[str, Any]]:
    """Reuse E-B19 F1–F8 (+ S1) fixtures for deterministic implementation tests."""
    return deepcopy(contract_edge_case_fixtures())


def remaining_blockers() -> list[dict[str, str]]:
    return [
        {
            "id": "AG-1",
            "status": "CLEARED_FOR_BP_A_REBOUND",
            "detail": "BP-A rebound codec cleared on compatibility pack",
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
                "Scorer contract YES + tests-only IMPLEMENTED YES; "
                "formal observation wire-up / reserved result still NO"
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
            "status": "IMPLEMENTED_TESTS_ONLY",
            "detail": (
                "T2_T3_SCORER_IMPLEMENTED=YES (tests-only executors + artifact); "
                "not formal measurement; product faithfulness unproven"
            ),
        },
        {
            "id": "FORMAL_WIREUP",
            "status": "OPEN",
            "detail": "No reserved FORMAL_OBSERVATION_RESULT write / formal unlock",
        },
    ]


def readiness_summary() -> dict[str, Any]:
    if E_B_FORMAL_READY != "NO":
        raise ScorerImplementationError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise ScorerImplementationError(
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO"
        )
    if T2_T3_SCORER_IMPLEMENTED != "YES":
        raise ScorerImplementationError(
            "T2_T3_SCORER_IMPLEMENTED must be YES this window"
        )
    if T2_T3_SCORER_CONTRACT_DESIGNED != "YES":
        raise ScorerImplementationError("contract must remain designed")
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
        "remaining_blockers": remaining_blockers(),
        "claims": {
            "llm": False,
            "nli_auto_label": False,
            "fuzzy_matching": False,
            "critic_oracle": False,
            "formal_observation": False,
            "formal_result": False,
            "scorer_contract_designed": True,
            "scorer_implemented": True,
            "scorer_implementation_tests_only": True,
            "product_faithfulness_proven": False,
        },
    }

"""W9 P3-R0.1 clean semantic construct (dry-run / mock only).

Re-freezes L1 as claim-status semantic judgment after deterministic-first
ownership. Supersedes the invalid five-action L1 construct from PR #63.

This module does not call LM Studio and must not write a formal P3 result.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from tests.w9_critic_p2_r1_harness import CONTRACT_PATH, FIXTURES, load_frozen_suite
from tests.w9_critic_p2_r3_formal_runner import FORMAL_ARTIFACT_PATH as P2_R3_ARTIFACT_PATH

PROTOCOL_VERSION = "w9_critic_p3_r0_semantic_construct_v2"
POST_61_MASTER_SHA = "ef79178e8dbfe9a9dec0526ef8b003732a819020"
EXPECTED_BASE_SHA = POST_61_MASTER_SHA
P2_R3_HISTORICAL_ARTIFACT_NAME = "w9-critic-p2-r3-full-product-rerun.json"
P2_R3_HISTORICAL_ARTIFACT_SHA256 = (
    "2c69d63d5d14801a6754d4f8094f4d62c95b63a3ddbb5778d98441f817293478"
)

RESEARCH_QUESTION = (
    "How capable is GLM-4.6V-Flash Thinking OFF at the SEMANTIC portion of "
    "Critic judgment after deterministic-first responsibilities are handled "
    "by the proven control-plane?"
)

SEMANTIC_CONSTRUCT_DEFINITION = (
    "L1 scores SEMANTIC-eligible claims only: claim detection after "
    "non-assertive exclusion; claim-evidence entailment / unsupported / "
    "unverifiable; emit status in {SUPPORTED, UNSUPPORTED, CONFLICTED, "
    "UNVERIFIABLE} with evaluation_state=JUDGED and decision_owner=SEMANTIC. "
    "Score claim status, not reason_code equality, not five CriticActions."
)

SEMANTIC_ELIGIBILITY_RULE = (
    "eligible iff exists claim with decision_owner=SEMANTIC and case is not "
    "protocol-invalid"
)

SCORING_POLICY = "EXACT"
HIDDEN_RECOVERY_CANNOT_UPGRADE_L1 = True
TIMEOUT_REMAINS_IN_DENOMINATOR = True
PARSE_FAILURE_REMAINS_IN_DENOMINATOR = True

FROZEN_TOTAL = 12
NEW_SEMANTIC_DENOMINATOR = 7
SEMANTIC_CLAIM_COUNT = 10

# Short ids used in protocol freezes; full case_id still comes from fixtures.
SEMANTIC_CASE_SHORT_IDS: tuple[str, ...] = (
    "C01",
    "C02",
    "C03",
    "C04",
    "C08",
    "C09",
    "C10",
)
DETERMINISTIC_ONLY_SHORT_IDS: tuple[str, ...] = ("C05", "C06", "C11")
PROTOCOL_INVALID_SHORT_IDS: tuple[str, ...] = ("C12",)
OWNER_ABSENT_SHORT_IDS: tuple[str, ...] = ("C07",)

CLAIM_STATUSES: frozenset[str] = frozenset(
    {"SUPPORTED", "UNSUPPORTED", "CONFLICTED", "UNVERIFIABLE"}
)

MODEL_CONFIG: dict[str, Any] = {
    "primary_model": "zai-org/glm-4.6v-flash",
    "adapter_class": "OpenAICompatibleAdapter",
    "provider_path": "app.eval.local_model_profile.adapter.OpenAICompatibleAdapter",
    "thinking": "OFF",
    "temperature": 0.0,
    "max_tokens": 512,
    "timeout_seconds": 60,
    "retry": "NONE",
    "best_of_n": False,
    "output": "structured_json_claim_status_only",
}

DRY_RUN_ARTIFACT_NAME = "dry-run-w9-critic-p3-r0-semantic-construct-plan.json"
DRY_RUN_ARTIFACT_PATH = FIXTURES / DRY_RUN_ARTIFACT_NAME
PROTOCOL_FIXTURE_NAME = "w9-critic-p3-semantic-construct-v2.json"
PROTOCOL_FIXTURE_PATH = FIXTURES / PROTOCOL_FIXTURE_NAME
# Reserved formal name — must remain absent in this window.
FORMAL_RESULT_ARTIFACT_NAME = "w9-critic-p3-r1-real-local-semantic.json"
FORMAL_RESULT_ARTIFACT_PATH = FIXTURES / FORMAL_RESULT_ARTIFACT_NAME

MODEL_INPUT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "case_id",
        "query",
        "final_draft",
        "gated_evidence_snapshot",
        "synchronized_citations",
        "retrieval_scope_exhausted",
    }
)

ORACLE_LEAKAGE_KEYS: frozenset[str] = frozenset(
    {
        "oracle",
        "expected_action",
        "expected_status",
        "expected_reason_code",
        "decision_owner",
        "reason_code",
        "evaluation_state",
        "score",
        "hint",
        "hints",
        "historical_action",
        "hidden_recovery",
        "in_capability_denominator",
        "in_semantic_denominator",
        "critic_pass",
        "acceptable_set",
        "known_conflict",
        "required_fact_missing",
        "citation_syntax_valid",
        "citation_ids_valid",
        "deterministic_context",
    }
)

DETERMINISTIC_OWNED_REASON_CODES: frozenset[str] = frozenset(
    {
        "KNOWN_STRUCTURED_CONFLICT",
        "KNOWN_REQUIRED_FACT_MISSING",
        "CITATION_SYNTAX_INVALID",
        "CITATION_ID_INVALID",
        "MISSING_CITATION",
        "SCOPE_VIOLATION",
    }
)


class MeasurementLayer(str, Enum):
    L0_DETERMINISTIC_CONTROL_PLANE = "L0_DETERMINISTIC_CONTROL_PLANE"
    L1_MODEL_SEMANTIC_CAPABILITY = "L1_MODEL_SEMANTIC_CAPABILITY"
    L2_CONTROL_PLANE_EXECUTION = "L2_CONTROL_PLANE_EXECUTION"
    L3_FINAL_SAFETY_OUTCOME = "L3_FINAL_SAFETY_OUTCOME"


class ObservationKind(str, Enum):
    STRUCTURED_JSON = "STRUCTURED_JSON"
    TIMEOUT = "TIMEOUT"
    PARSE_FAILURE = "PARSE_FAILURE"


class MeasurementState(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class ModelCapabilityResult(str, Enum):
    MODEL_CAPABILITY_PASS = "MODEL_CAPABILITY_PASS"
    MODEL_CAPABILITY_FAIL = "MODEL_CAPABILITY_FAIL"
    MEASUREMENT_PROTOCOL_INVALID = "MEASUREMENT_PROTOCOL_INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class LmStudioForbidden(RuntimeError):
    """Raised if any freeze-window path attempts LM Studio / real HTTP."""


class FormalP3ArtifactForbidden(RuntimeError):
    """Formal P3 capability result files are reserved until P3-R1."""


@dataclass(frozen=True, slots=True)
class SemanticClaimOracle:
    claim_id: str
    identity: str
    text: str
    status: str
    evidence_references: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CaseLaneRecord:
    case_id: str
    short_id: str
    lane: str
    semantic_eligible: bool
    in_l1_denominator: bool
    expected_semantic_calls: int
    semantic_claims: tuple[SemanticClaimOracle, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["semantic_claims"] = [c.to_dict() for c in self.semantic_claims]
        return payload


def short_case_id(case_id: str) -> str:
    return case_id.split("-", 1)[0]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_lm_studio(*_args: Any, **_kwargs: Any) -> None:
    raise LmStudioForbidden(
        "LM Studio requests are forbidden in the P3 semantic-construct freeze window"
    )


def write_formal_p3_result(*_args: Any, **_kwargs: Any) -> None:
    raise FormalP3ArtifactForbidden(
        f"formal P3 result {FORMAL_RESULT_ARTIFACT_NAME!r} is forbidden until P3-R1"
    )


def _semantic_claims_from_oracle(oracle_case: Mapping[str, Any]) -> tuple[SemanticClaimOracle, ...]:
    claims: list[SemanticClaimOracle] = []
    for raw in oracle_case.get("claims") or ():
        if str(raw.get("decision_owner")) != "SEMANTIC":
            continue
        status = raw.get("status")
        if status is None:
            continue
        status_s = str(status)
        if status_s not in CLAIM_STATUSES:
            raise ValueError(
                f"oracle claim {raw.get('claim_id')} has non-L1 status {status_s!r}"
            )
        claims.append(
            SemanticClaimOracle(
                claim_id=str(raw["claim_id"]),
                identity=str(raw["identity"]),
                text=str(raw["text"]),
                status=status_s,
                evidence_references=tuple(str(x) for x in (raw.get("evidence_references") or ())),
            )
        )
    return tuple(claims)


def classify_semantic_lane(case_id: str, oracle_case: Mapping[str, Any]) -> CaseLaneRecord:
    short = short_case_id(case_id)
    claims = _semantic_claims_from_oracle(oracle_case)

    if short in PROTOCOL_INVALID_SHORT_IDS:
        return CaseLaneRecord(
            case_id=case_id,
            short_id=short,
            lane="PROTOCOL_INVALID",
            semantic_eligible=False,
            in_l1_denominator=False,
            expected_semantic_calls=0,
            semantic_claims=(),
        )
    if short in OWNER_ABSENT_SHORT_IDS or not claims:
        # Empty SEMANTIC claims → L1 NOT_APPLICABLE (C07); also covers
        # deterministic-only cases that have zero SEMANTIC claims.
        if short in DETERMINISTIC_ONLY_SHORT_IDS or any(
            str(c.get("decision_owner")) == "DETERMINISTIC"
            for c in (oracle_case.get("claims") or ())
        ):
            lane = "DETERMINISTIC_ONLY"
        else:
            lane = "OWNER_ABSENT"
        return CaseLaneRecord(
            case_id=case_id,
            short_id=short,
            lane=lane,
            semantic_eligible=False,
            in_l1_denominator=False,
            expected_semantic_calls=0,
            semantic_claims=(),
        )
    if short in DETERMINISTIC_ONLY_SHORT_IDS:
        return CaseLaneRecord(
            case_id=case_id,
            short_id=short,
            lane="DETERMINISTIC_ONLY",
            semantic_eligible=False,
            in_l1_denominator=False,
            expected_semantic_calls=0,
            semantic_claims=(),
        )
    if short not in SEMANTIC_CASE_SHORT_IDS:
        raise ValueError(f"unclassified case for semantic construct: {case_id}")
    return CaseLaneRecord(
        case_id=case_id,
        short_id=short,
        lane="SEMANTIC",
        semantic_eligible=True,
        in_l1_denominator=True,
        expected_semantic_calls=1,
        semantic_claims=claims,
    )


def enumerate_semantic_lanes(
    suite: Any | None = None,
) -> tuple[CaseLaneRecord, ...]:
    frozen = suite or load_frozen_suite()
    records = tuple(
        classify_semantic_lane(case_id, frozen.oracle[case_id])
        for case_id in sorted(frozen.oracle)
    )
    if len(records) != FROZEN_TOTAL:
        raise ValueError(f"frozen_total={len(records)}, want {FROZEN_TOTAL}")
    return records


def semantic_eligible_records(
    records: Sequence[CaseLaneRecord] | None = None,
) -> tuple[CaseLaneRecord, ...]:
    items = records if records is not None else enumerate_semantic_lanes()
    return tuple(r for r in items if r.semantic_eligible)


def assert_denominator_invariants(records: Sequence[CaseLaneRecord] | None = None) -> dict[str, Any]:
    items = tuple(records) if records is not None else enumerate_semantic_lanes()
    semantic = [r for r in items if r.lane == "SEMANTIC"]
    deterministic = [r for r in items if r.lane == "DETERMINISTIC_ONLY"]
    protocol_invalid = [r for r in items if r.lane == "PROTOCOL_INVALID"]
    owner_absent = [r for r in items if r.lane == "OWNER_ABSENT"]

    claim_count = sum(len(r.semantic_claims) for r in semantic)
    det_in_l1 = sum(1 for r in deterministic if r.in_l1_denominator)
    inv_in_l1 = sum(1 for r in protocol_invalid if r.in_l1_denominator)

    if len(semantic) != NEW_SEMANTIC_DENOMINATOR:
        raise AssertionError(
            f"semantic denominator cases={len(semantic)}, want {NEW_SEMANTIC_DENOMINATOR}"
        )
    if claim_count != SEMANTIC_CLAIM_COUNT:
        raise AssertionError(
            f"semantic claim count={claim_count}, want {SEMANTIC_CLAIM_COUNT}"
        )
    if det_in_l1 != 0:
        raise AssertionError("DETERMINISTIC_CASES_IN_L1_DENOMINATOR must be 0")
    if inv_in_l1 != 0:
        raise AssertionError("PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR must be 0")
    if {r.short_id for r in semantic} != set(SEMANTIC_CASE_SHORT_IDS):
        raise AssertionError("SEMANTIC_CASES mismatch")
    if {r.short_id for r in deterministic} != set(DETERMINISTIC_ONLY_SHORT_IDS):
        raise AssertionError("DETERMINISTIC_ONLY_CASES mismatch")
    if {r.short_id for r in protocol_invalid} != set(PROTOCOL_INVALID_SHORT_IDS):
        raise AssertionError("PROTOCOL_INVALID_CASES mismatch")
    if {r.short_id for r in owner_absent} != set(OWNER_ABSENT_SHORT_IDS):
        raise AssertionError("OWNER_ABSENT cases mismatch")

    return {
        "frozen_total": len(items),
        "semantic_eligible": len(semantic),
        "semantic_ineligible": len(items) - len(semantic),
        "deterministic_only": len(deterministic),
        "protocol_invalid": len(protocol_invalid),
        "owner_absent": len(owner_absent),
        "semantic_claim_count": claim_count,
        "DETERMINISTIC_CASES_IN_L1_DENOMINATOR": det_in_l1,
        "PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR": inv_in_l1,
        "SEMANTIC_CASES": [r.case_id for r in semantic],
        "DETERMINISTIC_ONLY_CASES": [r.case_id for r in deterministic],
        "PROTOCOL_INVALID_CASES": [r.case_id for r in protocol_invalid],
        "OWNER_ABSENT_CASES": [r.case_id for r in owner_absent],
    }


def assert_oracle_uniqueness_freezes(records: Sequence[CaseLaneRecord] | None = None) -> None:
    items = {r.short_id: r for r in (records or enumerate_semantic_lanes())}
    c04 = items["C04"].semantic_claims
    if len(c04) != 1 or c04[0].status != "UNSUPPORTED":
        raise AssertionError("C04 must freeze unique status UNSUPPORTED")
    c09 = {c.claim_id: c for c in items["C09"].semantic_claims}
    if c09["C09-CL2"].status != "UNVERIFIABLE":
        raise AssertionError("C09-CL2 must freeze UNVERIFIABLE")
    for short, expected_n in (("C03", 2), ("C09", 2), ("C10", 2)):
        if len(items[short].semantic_claims) != expected_n:
            raise AssertionError(f"{short} must keep {expected_n} atomic claim slots")
    c02 = items["C02"].semantic_claims
    if len(c02) != 1 or "一个月" not in c02[0].text:
        raise AssertionError("C02 paraphrase freeze (一个月) missing")
    c08 = items["C08"].semantic_claims
    if len(c08) != 1 or c08[0].status != "SUPPORTED":
        raise AssertionError("C08 factual claim must be SUPPORTED after preface exclusion")


def score_claim_statuses_exact(
    expected: Sequence[SemanticClaimOracle],
    observed: Mapping[str, str],
) -> bool:
    """EXACT match on claim_id → status. No ACCEPTABLE_SET."""
    if set(observed) != {c.claim_id for c in expected}:
        return False
    return all(observed[c.claim_id] == c.status for c in expected)


def score_l1_observation(
    *,
    lane: CaseLaneRecord,
    observation_kind: ObservationKind | str,
    observed_statuses: Mapping[str, str] | None = None,
    hidden_recovery_success: bool = False,
) -> ModelCapabilityResult:
    if not lane.in_l1_denominator:
        return ModelCapabilityResult.NOT_APPLICABLE

    kind = ObservationKind(observation_kind)
    if kind in (ObservationKind.TIMEOUT, ObservationKind.PARSE_FAILURE):
        # Remain in denominator as FAIL; hidden recovery cannot upgrade.
        return ModelCapabilityResult.MODEL_CAPABILITY_FAIL

    if observed_statuses is None:
        return ModelCapabilityResult.MODEL_CAPABILITY_FAIL

    exact = score_claim_statuses_exact(lane.semantic_claims, observed_statuses)
    if exact:
        return ModelCapabilityResult.MODEL_CAPABILITY_PASS

    # Wrong semantic judgment stays L1 FAIL even if control-plane recovers.
    if hidden_recovery_success and HIDDEN_RECOVERY_CANNOT_UPGRADE_L1:
        return ModelCapabilityResult.MODEL_CAPABILITY_FAIL
    return ModelCapabilityResult.MODEL_CAPABILITY_FAIL


def leaked_oracle_keys(value: Any) -> set[str]:
    leaked: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_s = str(key)
            if key_s in ORACLE_LEAKAGE_KEYS or key_s.startswith("expected_"):
                leaked.add(key_s)
            leaked |= leaked_oracle_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            leaked |= leaked_oracle_keys(item)
    return leaked


def assert_no_oracle_leakage(payload: Mapping[str, Any] | Sequence[Any]) -> None:
    leaked = leaked_oracle_keys(payload)
    if leaked:
        raise ValueError(f"oracle leakage: {sorted(leaked)}")


def build_model_input(case: Mapping[str, Any]) -> dict[str, Any]:
    """Production-visible semantic input only."""
    scope = case.get("scope") if isinstance(case.get("scope"), Mapping) else {}
    payload = {
        "case_id": case["case_id"],
        "query": case["query"],
        "final_draft": case["answer"],
        "gated_evidence_snapshot": list(case.get("evidence") or ()),
        "synchronized_citations": list(case.get("citations") or ()),
        "retrieval_scope_exhausted": bool(
            scope.get("retrieval_scope_exhausted", False)
        ),
    }
    # Never attach deterministic_context or oracle fields.
    assert_no_oracle_leakage(payload)
    extra = set(payload) - MODEL_INPUT_ALLOWED_KEYS
    if extra:
        raise ValueError(f"disallowed model input keys: {sorted(extra)}")
    return payload


def p2_r3_historical_artifact_diff() -> int:
    """Byte-level divergence count vs frozen historical sha (0 = intact)."""
    if not P2_R3_ARTIFACT_PATH.is_file():
        return -1
    current = file_sha256(P2_R3_ARTIFACT_PATH)
    return 0 if current == P2_R3_HISTORICAL_ARTIFACT_SHA256 else 1


def formal_result_artifact_present() -> bool:
    return FORMAL_RESULT_ARTIFACT_PATH.is_file()


def build_protocol_freeze_document(
    records: Sequence[CaseLaneRecord] | None = None,
) -> dict[str, Any]:
    items = tuple(records) if records is not None else enumerate_semantic_lanes()
    accounting = assert_denominator_invariants(items)
    assert_oracle_uniqueness_freezes(items)
    suite = load_frozen_suite()
    return {
        "protocol": PROTOCOL_VERSION,
        "base_sha": EXPECTED_BASE_SHA,
        "research_question": RESEARCH_QUESTION,
        "semantic_construct_definition": SEMANTIC_CONSTRUCT_DEFINITION,
        "semantic_eligibility_rule": SEMANTIC_ELIGIBILITY_RULE,
        "scoring_policy": SCORING_POLICY,
        "acceptable_set": None,
        "layers": [layer.value for layer in MeasurementLayer],
        "primary_metric": MeasurementLayer.L1_MODEL_SEMANTIC_CAPABILITY.value,
        "model_config": MODEL_CONFIG,
        "model_input_schema": {
            "allowed_keys": sorted(MODEL_INPUT_ALLOWED_KEYS),
            "forbidden_keys": sorted(ORACLE_LEAKAGE_KEYS),
        },
        "model_output_schema": {
            "object": "claims[]",
            "claim_fields": ["claim_id", "status", "evidence_refs"],
            "status_enum": sorted(CLAIM_STATUSES),
            "not_l1_object": [
                "ACCEPT",
                "REVISE_FROM_EXISTING_EVIDENCE",
                "RETRIEVE_MISSING_EVIDENCE",
                "CLARIFY",
                "REFUSE",
            ],
        },
        "deterministic_exclusions": sorted(DETERMINISTIC_OWNED_REASON_CODES),
        "timeout_policy": {
            "remains_in_denominator": TIMEOUT_REMAINS_IN_DENOMINATOR,
            "l1_result": ModelCapabilityResult.MODEL_CAPABILITY_FAIL.value,
        },
        "parse_failure_policy": {
            "remains_in_denominator": PARSE_FAILURE_REMAINS_IN_DENOMINATOR,
            "l1_result": ModelCapabilityResult.MODEL_CAPABILITY_FAIL.value,
        },
        "hidden_recovery_policy": {
            "HIDDEN_RECOVERY_CANNOT_UPGRADE_L1": HIDDEN_RECOVERY_CANNOT_UPGRADE_L1,
            "model_wrong_plus_recovery": ModelCapabilityResult.MODEL_CAPABILITY_FAIL.value,
        },
        "measurement_state_taxonomy": [s.value for s in MeasurementState],
        "model_capability_result_taxonomy": [s.value for s in ModelCapabilityResult],
        "denominator": accounting,
        "oracle_uniqueness_freezes": {
            "C04": "UNSUPPORTED",
            "C09-CL2": "UNVERIFIABLE",
            "C02_paraphrase": "30日≡一个月",
            "C08_preface": "excluded; factual SUPPORTED",
            "atomic_slots": ["C03", "C09", "C10"],
        },
        "cases": [r.to_dict() for r in items],
        "suite_binding": {
            "cases_path": "backend/tests/fixtures/l4_critic/w9-critic-cases.json",
            "contract_path": str(CONTRACT_PATH.as_posix()).split("backend/")[-1]
            if "backend" in CONTRACT_PATH.as_posix()
            else str(CONTRACT_PATH),
            "oracle_hash": canonical_json_sha256(
                json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            ),
            "case_ids": [c["case_id"] for c in suite.cases],
        },
        "p2_r3_protection": {
            "artifact": P2_R3_HISTORICAL_ARTIFACT_NAME,
            "frozen_sha256": P2_R3_HISTORICAL_ARTIFACT_SHA256,
        },
        "formal_result_artifact": {
            "name": FORMAL_RESULT_ARTIFACT_NAME,
            "present_required": False,
        },
        "execution_state": {
            "measurement_state": MeasurementState.NOT_RUN.value,
            "lm_studio_requests": 0,
            "real_model_capability_measured": False,
            "p3_r1_executed": False,
        },
    }

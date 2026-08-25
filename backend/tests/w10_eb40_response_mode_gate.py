"""W10 E-B40 — Response Mode Gate (versioned measurement protocol).

Defines response_mode ∈ {ANSWER, REFUSAL, DEGRADED} from deterministic
product/control-plane signals. SUPERSEDES_FOR_FUTURE_FORMAL_INPUT_SELECTION
only — does not rewrite historical E-B16/17/19/20/21/22 formulas or results.

Does not: call LLM / NLI / embeddings, run Formal scorer, flip E-B_FORMAL_READY,
modify backend/app, or reinterpret E-B39 as model failure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Identity / versioning
# ---------------------------------------------------------------------------

WINDOW_ID = "E-B40"
PROTOCOL_VERSION = "w10_eb40_response_mode_gate_v1"
ARTIFACT_KIND = "RESPONSE_MODE_GATE"
SUPERSEDES_FOR_FUTURE_FORMAL_INPUT_SELECTION = (
    "w10_eb16_after_to_gold_evaluation_boundary",
    "w10_eb17_binding_gate_v1",
    "w10_eb19_t2_t3_scorer_contract",
)
HISTORICAL_PROTOCOLS_PRESERVED = (
    "w10_eb16_after_to_gold_evaluation_boundary",
    "w10_eb17_binding_gate_v1",
    "w10_eb19_t2_t3_scorer_contract",
    "w10_eb20_t2_t3_scorer_implementation",
    "w10_eb21",
    "w10_eb22_formal_wireup_contract",
)

RESPONSE_MODE_GATE_IMPLEMENTED = "YES"
DEGRADED_SCORER_PATH_DEFINED = "YES"
EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH = "CLOSED"
SCORER_APPLICABILITY_GAP = "RESOLVED_FOR_RESPONSE_MODE"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
FORMAL_OBSERVATION = "NOT_STARTED"

REPO_ROOT = Path(__file__).resolve().parents[2]
EB38_RECORDS_DIR = (
    REPO_ROOT
    / "docs"
    / "research"
    / "w10-eb38-frozen-baseline-acquisition"
    / "records"
)
EB39_VERDICT_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "w10-eb39-post-acquisition-binding"
    / "09-eb39-verdict.md"
)

# E-B15 harness control-plane enums (deterministic; not NLP).
CAPTURE_SUBMODE_DEGRADED = "product_stream_degraded"
CAPTURE_SUBMODE_REFUSAL = "product_stream_refusal"
CAPTURE_MODE_DEGRADED = "product_stream_degraded"
CAPTURE_MODE_REFUSAL = "product_stream_refusal"

ALLOWED_CLASSIFICATION_SIGNALS: frozenset[str] = frozenset(
    {
        "capture_path_submode",
        "capture_mode",
        "plan_refusal",
        "llm_called",
        "llm_called_observed",
        "stream_phase_entered",
        "model_backend_identity",
    }
)

FORBIDDEN_CLASSIFIERS: frozenset[str] = frozenset(
    {
        "llm_classifier",
        "nli",
        "embedding",
        "fuzzy_semantic",
        "substring_heuristic_as_mode",
        "citation_nonempty_implies_answer",
    }
)


class ResponseMode(str, Enum):
    ANSWER = "ANSWER"
    REFUSAL = "REFUSAL"
    DEGRADED = "DEGRADED"


class Applicability(str, Enum):
    """T2/T3 applicability under response-mode gate.

    NOT_APPLICABLE ≠ PASS ≠ 0% unsupported ≠ 100% grounded.
    """

    POTENTIALLY_ELIGIBLE = "POTENTIALLY_ELIGIBLE"  # ANSWER + later binding
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ROUTE_REFUSAL_T4 = "ROUTE_REFUSAL_T4"
    SIGNAL_INSUFFICIENT = "SIGNAL_INSUFFICIENT"


class DegradedBpPolicy(str, Enum):
    VERSIONED_BP_D = "VERSIONED_BP_D"
    EXISTING_CLASS_SUFFICIENT = "EXISTING_CLASS_SUFFICIENT"
    BLOCKED = "BLOCKED"


class ResponseModeGateError(ValueError):
    """Ill-formed response-mode classification request."""


@dataclass(frozen=True, slots=True)
class ResponseModeClassification:
    case_id: str
    response_mode: ResponseMode | None
    classification_signal: str
    llm_called: bool | None
    capture_submode: str | None
    plan_refusal: bool | None
    signal_available: bool
    t2_applicability: Applicability
    t3_applicability: Applicability
    t2_t3_scorer_eligible: bool
    bp_class_v2: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["response_mode"] = (
            None if self.response_mode is None else self.response_mode.value
        )
        payload["t2_applicability"] = self.t2_applicability.value
        payload["t3_applicability"] = self.t3_applicability.value
        return payload


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ResponseModeGateError(f"expected bool, got {type(value).__name__}")


def response_mode_signal_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    """Extract allowed deterministic control-plane fields only."""
    return {
        "capture_path_submode": record.get("capture_path_submode")
        or record.get("capture_mode_submode"),
        "capture_mode": record.get("capture_mode"),
        "plan_refusal": record.get("plan_refusal"),
        "llm_called": record.get("llm_called"),
        "llm_called_observed": record.get("llm_called_observed"),
        "stream_phase_entered": record.get("stream_phase_entered"),
        "model_backend_identity": record.get("model_backend_identity")
        or record.get("model_identity"),
    }


def response_mode_signal_available(record: Mapping[str, Any]) -> bool:
    """True when product/control-plane fields suffice (no NLP guess)."""
    fields = response_mode_signal_fields(record)
    submode = fields["capture_path_submode"]
    capture_mode = fields["capture_mode"]
    plan_refusal = fields["plan_refusal"]
    if plan_refusal is True:
        return True
    if submode in (CAPTURE_SUBMODE_DEGRADED, CAPTURE_SUBMODE_REFUSAL):
        return True
    if capture_mode in (CAPTURE_MODE_DEGRADED, CAPTURE_MODE_REFUSAL):
        return True
    if fields["llm_called"] is True:
        return True
    return False


def classify_response_mode(record: Mapping[str, Any]) -> ResponseModeClassification:
    """Classify from deterministic signals only.

    Priority:
    1. plan_refusal / refusal capture submode → REFUSAL
    2. degraded capture submode / E-B15 degraded branch → DEGRADED
    3. llm_called=true (ordinary generation) → ANSWER
    Never: citations nonempty ⇒ ANSWER; never NLP/fuzzy.
    """
    case_id = str(record.get("case_id") or record.get("case_id_short") or "")
    if not case_id:
        raise ResponseModeGateError("record missing case_id")

    fields = response_mode_signal_fields(record)
    llm_called = _as_bool(fields["llm_called"])
    if llm_called is None:
        llm_called = _as_bool(fields["llm_called_observed"])
    plan_refusal = _as_bool(fields["plan_refusal"])
    submode = fields["capture_path_submode"]
    capture_mode = fields["capture_mode"]
    submode_s = str(submode) if submode is not None else None
    capture_s = str(capture_mode) if capture_mode is not None else None

    if not response_mode_signal_available(record):
        return ResponseModeClassification(
            case_id=case_id,
            response_mode=None,
            classification_signal="SIGNAL_INSUFFICIENT",
            llm_called=llm_called,
            capture_submode=submode_s,
            plan_refusal=plan_refusal,
            signal_available=False,
            t2_applicability=Applicability.SIGNAL_INSUFFICIENT,
            t3_applicability=Applicability.SIGNAL_INSUFFICIENT,
            t2_t3_scorer_eligible=False,
            bp_class_v2="UNCLASSIFIED",
            notes=(
                "RESPONSE_MODE_SIGNAL_AVAILABLE=NO; "
                "PROTOCOL_REPAIR_IMPLEMENTATION_BLOCKED=YES; "
                "do not NLP-guess from natural-language text"
            ),
        )

    # 1) Explicit refusal control plane
    if (
        plan_refusal is True
        or submode_s == CAPTURE_SUBMODE_REFUSAL
        or capture_s == CAPTURE_MODE_REFUSAL
    ):
        signal = (
            "plan_refusal=true"
            if plan_refusal is True
            else f"capture_submode={submode_s or capture_s}"
        )
        return ResponseModeClassification(
            case_id=case_id,
            response_mode=ResponseMode.REFUSAL,
            classification_signal=signal,
            llm_called=llm_called,
            capture_submode=submode_s or capture_s,
            plan_refusal=plan_refusal,
            signal_available=True,
            t2_applicability=Applicability.ROUTE_REFUSAL_T4,
            t3_applicability=Applicability.ROUTE_REFUSAL_T4,
            t2_t3_scorer_eligible=False,
            bp_class_v2="BP_C_REFUSAL_EXCLUDE",
            notes="REFUSAL ≠ DEGRADED; route to T4/refusal policy",
        )

    # 2) Degraded product path (E-B15 A2 / stream L1)
    if submode_s == CAPTURE_SUBMODE_DEGRADED or capture_s == CAPTURE_MODE_DEGRADED:
        return ResponseModeClassification(
            case_id=case_id,
            response_mode=ResponseMode.DEGRADED,
            classification_signal=f"capture_path_submode={CAPTURE_SUBMODE_DEGRADED}",
            llm_called=llm_called if llm_called is not None else False,
            capture_submode=submode_s or capture_s,
            plan_refusal=plan_refusal,
            signal_available=True,
            t2_applicability=Applicability.NOT_APPLICABLE,
            t3_applicability=Applicability.NOT_APPLICABLE,
            t2_t3_scorer_eligible=False,
            bp_class_v2="BP_D_DEGRADED_PRODUCT_AFTER",
            notes=(
                "DEGRADED ≠ ANSWER even if citations nonempty; "
                "T2/T3 NOT_APPLICABLE (not PASS / not perfect score)"
            ),
        )

    # 3) Ordinary LLM answer path
    if llm_called is True:
        return ResponseModeClassification(
            case_id=case_id,
            response_mode=ResponseMode.ANSWER,
            classification_signal="llm_called=true",
            llm_called=True,
            capture_submode=submode_s or capture_s,
            plan_refusal=plan_refusal,
            signal_available=True,
            t2_applicability=Applicability.POTENTIALLY_ELIGIBLE,
            t3_applicability=Applicability.POTENTIALLY_ELIGIBLE,
            t2_t3_scorer_eligible=False,  # still needs real-After binding v2
            bp_class_v2="BP_A_CANDIDATE_PENDING_BIND",
            notes="ANSWER may enter T2/T3 only after binding v2 eligibility",
        )

    raise ResponseModeGateError(
        f"{case_id}: signal present but no rule matched "
        f"(submode={submode_s!r}, capture={capture_s!r}, llm_called={llm_called!r})"
    )


def t2_t3_denominator_admits(mode: ResponseMode | str) -> bool:
    """Denominator admits only ANSWER (binding still required separately)."""
    value = mode.value if isinstance(mode, ResponseMode) else str(mode)
    return value == ResponseMode.ANSWER.value


def refuse_perfect_score_for_non_answer(mode: ResponseMode | str) -> None:
    """Close empty/degraded → perfect T2/T3 score pathology."""
    value = mode.value if isinstance(mode, ResponseMode) else str(mode)
    if value in (ResponseMode.DEGRADED.value, ResponseMode.REFUSAL.value):
        raise ResponseModeGateError(
            f"{value} cannot receive T2/T3 perfect score; "
            "status must be NOT_APPLICABLE (≠ PASS)"
        )


def metrics_surface_for_mode(mode: ResponseMode | str) -> dict[str, Any]:
    """Separate availability metrics from model-quality claim scoring."""
    value = mode.value if isinstance(mode, ResponseMode) else str(mode)
    if value == ResponseMode.ANSWER.value:
        return {
            "surface": "ANSWER",
            "t2_t3_claim_scoring": "eligible_if_bound",
            "counts_as_model_quality": True,
        }
    if value == ResponseMode.REFUSAL.value:
        return {
            "surface": "REFUSAL",
            "t2_t3_claim_scoring": "ROUTE_REFUSAL_T4",
            "counts_as_model_quality": False,
        }
    if value == ResponseMode.DEGRADED.value:
        return {
            "surface": "DEGRADED",
            "t2_t3_claim_scoring": "NOT_APPLICABLE",
            "metrics": ("degraded_count", "degraded_rate"),
            "counts_as_model_quality": False,
            "note": "degraded_rate = system availability / generation-path outcome",
        }
    raise ResponseModeGateError(f"unknown response_mode={value!r}")


def degraded_bp_policy() -> DegradedBpPolicy:
    """Versioned BP-D; does not rewrite historical BP-A/B/C definitions."""
    return DegradedBpPolicy.VERSIONED_BP_D


def load_eb38_record(case_short: str) -> dict[str, Any]:
    path = EB38_RECORDS_DIR / f"{case_short}.json"
    if not path.is_file():
        raise ResponseModeGateError(f"E-B38 record missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ResponseModeGateError(f"{path}: must be object")
    return payload


def classify_eb38_suite(
    case_shorts: Sequence[str] | None = None,
) -> list[ResponseModeClassification]:
    shorts = list(case_shorts) if case_shorts is not None else [
        f"C{i:02d}" for i in range(1, 12)
    ]
    return [classify_response_mode(load_eb38_record(s)) for s in shorts]


def historical_eb39_remains_blocked() -> dict[str, str]:
    """Old protocol conclusion must stay reconstructible / not rewritten."""
    text = EB39_VERDICT_PATH.read_text(encoding="utf-8")
    required = {
        "REAL_AFTER_BINDING_COMPLETE = NO": "NO",
        "SCORER_APPLICABILITY_GAP = YES": "YES",
        "BLOCKED_PENDING_PROTOCOL_REPAIR": "YES",
        "E-B_FORMAL_READY                            = NO": "NO",
        "T2_REAL_AFTER_INPUT_READY = NO": "NO",
        "T3_REAL_AFTER_INPUT_READY = NO": "NO",
    }
    missing = [k for k in required if k not in text]
    if missing:
        raise ResponseModeGateError(
            f"E-B39 verdict drifted / rewritten: missing {missing}"
        )
    return {
        "REAL_AFTER_BINDING_COMPLETE": "NO",
        "SCORER_APPLICABILITY_GAP": "YES",
        "BLOCKED_PENDING_PROTOCOL_REPAIR": "YES",
        "historical_protocol_rebuildable": "YES",
        "rewrites_historical_result": "NO",
    }


def gate_summary() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "supersedes_for_future_formal_input_selection": list(
            SUPERSEDES_FOR_FUTURE_FORMAL_INPUT_SELECTION
        ),
        "historical_protocols_preserved": list(HISTORICAL_PROTOCOLS_PRESERVED),
        "rewrites_historical_result": False,
        "allowed_classification_signals": sorted(ALLOWED_CLASSIFICATION_SIGNALS),
        "forbidden_classifiers": sorted(FORBIDDEN_CLASSIFIERS),
        "response_modes": [m.value for m in ResponseMode],
        "degraded_bp_policy": degraded_bp_policy().value,
        "gates": {
            "RESPONSE_MODE_GATE_IMPLEMENTED": RESPONSE_MODE_GATE_IMPLEMENTED,
            "DEGRADED_SCORER_PATH_DEFINED": DEGRADED_SCORER_PATH_DEFINED,
            "EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH": EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH,
            "SCORER_APPLICABILITY_GAP": SCORER_APPLICABILITY_GAP,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
            "FORMAL_OBSERVATION": FORMAL_OBSERVATION,
        },
    }

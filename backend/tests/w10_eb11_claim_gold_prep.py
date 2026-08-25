"""W10 E-B11 Lane A — Claim gold annotation preparation (prep only).

Establishes:
  1. Formal gold artifact path (still intentionally absent)
  2. Annotation placeholder contract + validator
  3. Integration hook to E-B9a ``validate_claim_gold_ledger`` for future gold

Does not: invent annotations, auto-label, call LLM / LM Studio, run generation,
write formal observation, clear E-B_FORMAL_READY, or touch Lane B empty-gate files /
backend/app.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from tests.w10_eb_generation_claim_gold_contract import (
    ARTIFACT_KIND as GOLD_ARTIFACT_KIND,
    E_B_FORMAL_READY as EB9A_E_B_FORMAL_READY,
    FORBIDDEN_KEYS as GOLD_FORBIDDEN_KEYS,
    GOLD_FILENAME,
    GOLD_PATH,
    PARENT_OBSERVATION_PROTOCOL,
    PROTOCOL_VERSION as GOLD_PROTOCOL_VERSION,
    SCHEMA_PATH as GOLD_SCHEMA_PATH,
    ClaimGoldContractError,
    assert_gold_file_absent,
    validate_claim_gold_ledger,
)

# ---------------------------------------------------------------------------
# Frozen prep identity / paths
# ---------------------------------------------------------------------------

PREP_PROTOCOL_VERSION = "w10_eb_generation_claim_gold_annotation_prep_v1"
PREP_ARTIFACT_KIND = "CLAIM_GOLD_ANNOTATION_PLACEHOLDER"
SLOT_FILL_POLICY = "human_only_after_content_sha256_known"
ANNOTATION_STATUS_NOT_ANNOTATED = "NOT_ANNOTATED"

PREP_FILENAME = "w10-eb-generation-claim-gold-v1.annotation-prep.json"
PREP_SCHEMA_FILENAME = "w10-eb-generation-claim-gold-v1.annotation-prep.schema.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
PREP_PATH = FIXTURES / PREP_FILENAME
PREP_SCHEMA_PATH = FIXTURES / PREP_SCHEMA_FILENAME

# Formal annotated ledger path (E-B9a). Prep establishes the path; file stays absent.
FORMAL_GOLD_FILENAME = GOLD_FILENAME
FORMAL_GOLD_PATH = GOLD_PATH

E_B_FORMAL_READY = "NO"
E_B_CLAIM_GOLD_PREP_READY = "YES"
E_B_CLAIM_GOLD_ANNOTATED = "NO"

# Lane B shared directory touchpoint (document only; do not write empty-gate files).
LANE_B_SHARED_FIXTURES_DIR = FIXTURES
LANE_B_CASES_FILENAME = "w10-eb-empty-gate-cases.json"
LANE_B_SUITE_SCHEMA_FILENAME = "w10-eb-empty-gate-suite-v1.schema.json"

HEADER_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "parent_gold_protocol",
    "parent_observation_protocol",
    "target_gold_filename",
    "annotation_status",
    "created_by",
    "slot_fill_policy",
    "annotation_slots",
    "gates",
)

GATES_REQUIRED: tuple[str, ...] = (
    "E_B_CLAIM_GOLD_PREP_READY",
    "E_B_CLAIM_GOLD_ANNOTATED",
    "E_B_FORMAL_READY",
)

# Prep must reject gold-ledger body keys that would fake annotations.
FORBIDDEN_ANNOTATION_BODY_KEYS: frozenset[str] = frozenset(
    {
        "asserted_claims",
        "cases",
        "label",
        "supporting_evidence_ids",
        "support_span_notes",
        "content_sha256",
    }
)

FORBIDDEN_CREATED_BY: frozenset[str] = frozenset(
    {
        "llm_annotator",
        "llm_judge",
        "nli_auto",
        "lexical_auto",
    }
)

FORBIDDEN_NOTES_PHRASES: tuple[str, ...] = (
    "grounding proven",
    "Critic validated",
    "E-B_FORMAL_READY = YES",
    "formal measurement complete",
    "auto-labeled",
)

FORBIDDEN_KEYS: frozenset[str] = GOLD_FORBIDDEN_KEYS | FORBIDDEN_ANNOTATION_BODY_KEYS


class ClaimGoldPrepError(ValueError):
    """Raised when claim-gold prep / placeholder contract is violated."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ClaimGoldPrepError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(mapping: Mapping[str, Any], path: str) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_KEYS)
    if present:
        raise ClaimGoldPrepError(f"forbidden prep fields present at {path}: {present}")


def _reject_forbidden_keys_recursive(node: Any, path: str) -> None:
    if isinstance(node, Mapping):
        _reject_forbidden_keys(node, path)
        for key, value in node.items():
            _reject_forbidden_keys_recursive(value, f"{path}.{key}")
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for index, item in enumerate(node):
            _reject_forbidden_keys_recursive(item, f"{path}[{index}]")


def _validate_gates(gates: Mapping[str, Any], path: str) -> None:
    _require_keys(gates, GATES_REQUIRED, path)
    if gates["E_B_CLAIM_GOLD_PREP_READY"] != E_B_CLAIM_GOLD_PREP_READY:
        raise ClaimGoldPrepError(
            f"{path}.E_B_CLAIM_GOLD_PREP_READY must be {E_B_CLAIM_GOLD_PREP_READY!r}"
        )
    if gates["E_B_CLAIM_GOLD_ANNOTATED"] != E_B_CLAIM_GOLD_ANNOTATED:
        raise ClaimGoldPrepError(
            f"{path}.E_B_CLAIM_GOLD_ANNOTATED must remain {E_B_CLAIM_GOLD_ANNOTATED!r} "
            "(no fake / premature annotated claim)"
        )
    if gates["E_B_FORMAL_READY"] != E_B_FORMAL_READY:
        raise ClaimGoldPrepError(
            f"{path}.E_B_FORMAL_READY must remain {E_B_FORMAL_READY!r}"
        )


def _validate_slot(slot: Mapping[str, Any], path: str) -> None:
    """Future human slots may appear later; prep on-disk file must keep slots empty."""
    _reject_forbidden_keys(slot, path)
    for banned in ("label", "asserted_claims", "supporting_evidence_ids"):
        if banned in slot:
            raise ClaimGoldPrepError(
                f"{path}: {banned!r} is forbidden on annotation placeholder slots "
                "(no fabricated annotations)"
            )
    case_id = slot.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ClaimGoldPrepError(f"{path}.case_id must be a non-empty string")
    status = slot.get("slot_status")
    if status not in {"AWAITING_HUMAN_ANNOTATION", "UNBOUND"}:
        raise ClaimGoldPrepError(
            f"{path}.slot_status must be AWAITING_HUMAN_ANNOTATION or UNBOUND"
        )


def validate_annotation_placeholder(payload: Mapping[str, Any]) -> None:
    """Validate E-B11 Lane A annotation placeholder (not formal gold)."""
    if not isinstance(payload, Mapping):
        raise ClaimGoldPrepError("placeholder must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != PREP_PROTOCOL_VERSION:
        raise ClaimGoldPrepError(
            f"protocol_version mismatch: expected {PREP_PROTOCOL_VERSION!r}"
        )
    if payload["artifact_kind"] != PREP_ARTIFACT_KIND:
        raise ClaimGoldPrepError(f"artifact_kind must be {PREP_ARTIFACT_KIND!r}")
    if payload["parent_gold_protocol"] != GOLD_PROTOCOL_VERSION:
        raise ClaimGoldPrepError(
            f"parent_gold_protocol must bind {GOLD_PROTOCOL_VERSION!r}"
        )
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise ClaimGoldPrepError(
            "parent_observation_protocol must bind "
            f"{PARENT_OBSERVATION_PROTOCOL!r}"
        )
    if payload["target_gold_filename"] != FORMAL_GOLD_FILENAME:
        raise ClaimGoldPrepError(
            f"target_gold_filename must be {FORMAL_GOLD_FILENAME!r}"
        )
    if payload["annotation_status"] != ANNOTATION_STATUS_NOT_ANNOTATED:
        raise ClaimGoldPrepError(
            f"annotation_status must be {ANNOTATION_STATUS_NOT_ANNOTATED!r}"
        )
    if payload["slot_fill_policy"] != SLOT_FILL_POLICY:
        raise ClaimGoldPrepError(f"slot_fill_policy must be {SLOT_FILL_POLICY!r}")

    created_by = payload["created_by"]
    if not isinstance(created_by, str) or not created_by.strip():
        raise ClaimGoldPrepError("created_by must be a non-empty string")
    if created_by in FORBIDDEN_CREATED_BY:
        raise ClaimGoldPrepError(
            f"created_by={created_by!r} is forbidden (no LLM / auto annotator)"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for phrase in FORBIDDEN_NOTES_PHRASES:
            if phrase in notes:
                raise ClaimGoldPrepError(
                    f"forbidden phrase {phrase!r} appears in notes"
                )

    slots = payload["annotation_slots"]
    if not isinstance(slots, Sequence) or isinstance(slots, (str, bytes, bytearray)):
        raise ClaimGoldPrepError("annotation_slots must be an array")
    if len(slots) != 0:
        raise ClaimGoldPrepError(
            "annotation_slots must be empty during prep "
            "(do not invent case rows or labels)"
        )
    for index, slot in enumerate(slots):
        if not isinstance(slot, Mapping):
            raise ClaimGoldPrepError(f"$.annotation_slots[{index}] must be an object")
        _validate_slot(slot, f"$.annotation_slots[{index}]")

    gates = payload["gates"]
    if not isinstance(gates, Mapping):
        raise ClaimGoldPrepError("$.gates must be an object")
    _validate_gates(gates, "$.gates")


def build_annotation_placeholder() -> dict[str, Any]:
    """Canonical in-memory placeholder (mirrors on-disk prep artifact)."""
    return {
        "protocol_version": PREP_PROTOCOL_VERSION,
        "artifact_kind": PREP_ARTIFACT_KIND,
        "parent_gold_protocol": GOLD_PROTOCOL_VERSION,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "target_gold_filename": FORMAL_GOLD_FILENAME,
        "annotation_status": ANNOTATION_STATUS_NOT_ANNOTATED,
        "created_by": "e-b11-lane-a-prep",
        "notes": (
            "PREP_ONLY_NOT_ANNOTATED_GOLD_NOT_FORMAL_MEASUREMENT. "
            f"Reserved formal gold path is {FORMAL_GOLD_FILENAME} "
            "(intentionally absent). Human annotators fill that ledger later "
            "under E-B9a schema; no auto-label / Critic oracle / LLM judge."
        ),
        "slot_fill_policy": SLOT_FILL_POLICY,
        "annotation_slots": [],
        "gates": {
            "E_B_CLAIM_GOLD_PREP_READY": E_B_CLAIM_GOLD_PREP_READY,
            "E_B_CLAIM_GOLD_ANNOTATED": E_B_CLAIM_GOLD_ANNOTATED,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
        },
    }


def clone_annotation_placeholder() -> dict[str, Any]:
    return deepcopy(build_annotation_placeholder())


def load_annotation_placeholder() -> dict[str, Any]:
    if not PREP_PATH.is_file():
        raise ClaimGoldPrepError(f"annotation placeholder missing: {PREP_PATH}")
    payload = json.loads(PREP_PATH.read_text(encoding="utf-8"))
    validate_annotation_placeholder(payload)
    return payload


def load_prep_schema_document() -> dict[str, Any]:
    if not PREP_SCHEMA_PATH.is_file():
        raise ClaimGoldPrepError(f"prep schema missing: {PREP_SCHEMA_PATH}")
    return json.loads(PREP_SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_formal_gold_absent() -> None:
    """Legacy E-B11 prep guard — formal gold may exist after E-B12B materialization."""
    try:
        assert_gold_file_absent()
    except ClaimGoldContractError as exc:
        raise ClaimGoldPrepError(str(exc)) from exc
    if FORMAL_GOLD_PATH.exists():
        raise ClaimGoldPrepError(
            f"{FORMAL_GOLD_FILENAME} is present at {FORMAL_GOLD_PATH} "
            "(absence required only during E-B11 prep windows)"
        )


def assert_prep_artifact_present() -> None:
    if not PREP_PATH.is_file():
        raise ClaimGoldPrepError(f"prep artifact missing: {PREP_PATH}")
    if not PREP_SCHEMA_PATH.is_file():
        raise ClaimGoldPrepError(f"prep schema missing: {PREP_SCHEMA_PATH}")
    if not GOLD_SCHEMA_PATH.is_file():
        raise ClaimGoldPrepError(f"E-B9a gold schema missing: {GOLD_SCHEMA_PATH}")


def validate_future_claim_gold_ledger(payload: Mapping[str, Any]) -> None:
    """Validator integration: reuse E-B9a ledger validator for future annotated gold.

    Prep does not create or load a gold file; this hook proves the integration
    path without writing annotations.
    """
    try:
        validate_claim_gold_ledger(payload)
    except ClaimGoldContractError as exc:
        raise ClaimGoldPrepError(f"integrated gold validator rejected ledger: {exc}") from exc


def claim_gold_preparation_status() -> dict[str, Any]:
    """Deterministic prep status report (no formal measurement claims).

    Placeholder gates remain prep-era (ANNOTATED=NO on the placeholder artifact).
    Formal gold may already exist via E-B12B materialization — reported separately.
    """
    assert_prep_artifact_present()
    placeholder = load_annotation_placeholder()
    gold_present = FORMAL_GOLD_PATH.is_file()
    return {
        "lane": "A",
        "window": "E-B11",
        "artifact_paths": {
            "formal_gold_reserved": str(FORMAL_GOLD_PATH),
            "formal_gold_present": gold_present,
            "annotation_placeholder": str(PREP_PATH),
            "annotation_placeholder_schema": str(PREP_SCHEMA_PATH),
            "eb9a_gold_schema": str(GOLD_SCHEMA_PATH),
        },
        "identities": {
            "prep_protocol_version": PREP_PROTOCOL_VERSION,
            "prep_artifact_kind": PREP_ARTIFACT_KIND,
            "gold_protocol_version": GOLD_PROTOCOL_VERSION,
            "gold_artifact_kind": GOLD_ARTIFACT_KIND,
            "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        },
        "gates": {
            "E_B_CLAIM_GOLD_PREP_READY": E_B_CLAIM_GOLD_PREP_READY,
            # Placeholder-era constant (prep artifact still NOT_ANNOTATED).
            "E_B_CLAIM_GOLD_ANNOTATED": E_B_CLAIM_GOLD_ANNOTATED,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
            "eb9a_E_B_FORMAL_READY": EB9A_E_B_FORMAL_READY,
        },
        "annotation_status": placeholder["annotation_status"],
        "annotation_slot_count": len(placeholder["annotation_slots"]),
        "validator_integration": {
            "eb9a_validate_claim_gold_ledger": "wired",
            "placeholder_validator": "wired",
        },
        "lane_b_shared_touchpoints": {
            "fixtures_dir": str(LANE_B_SHARED_FIXTURES_DIR),
            "do_not_write": [
                LANE_B_CASES_FILENAME,
                LANE_B_SUITE_SCHEMA_FILENAME,
            ],
            "note": (
                "Lane A and Lane B share fixtures/l4_critic/; "
                "Lane A only writes claim-gold-* prep artifacts."
            ),
        },
        "claims": {
            "fake_annotations": False,
            "auto_label": False,
            "formal_measurement": False,
        },
    }


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no product LLM / Critic harness / executor hooks."""
    import ast
    import inspect

    import tests.w10_eb11_claim_gold_prep as self_mod

    source = inspect.getsource(self_mod)
    tree = ast.parse(source)
    banned_roots = {
        "openai",
        "httpx",
        "aiohttp",
        "anthropic",
        "lmstudio",
        "transformers",
    }
    banned_modules = {
        "tests.w9_critic_p2_r1_harness",
        "tests.w9_critic_p2_r3_formal_runner",
        "tests.w10_eb6_generation_observation_executor",
        "tests.w10_ea5_formal_window_execution",
        "tests.w10_eb_empty_gate_suite_contract",
        "app.services.rag.generation",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in banned_roots or alias.name in banned_modules:
                    return False
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".", 1)[0] if mod else ""
            if root in banned_roots or mod in banned_modules:
                return False
    for banned_attr in (
        "execute_frozen_case",
        "run_formal_window",
        "run_generation_observation",
        "auto_label",
    ):
        if hasattr(self_mod, banned_attr):
            return False
    return True

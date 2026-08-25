"""W10 E-B11 Lane B — S2 dual-suite packaging contract (prep only).

Freezes how Full formal observation *would* compose:
  primary W9 envelope (E-B2 v1, case_count=12)
  ∧ companion empty-gate suite (w10_eb_empty_gate_v1, N=2)

Does not: authorize formal write, run generation / LLM, create real empty-gate
cases, reserve formal dual-suite results, or flip E-B_FORMAL_READY.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Frozen identity / gate constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "w10_eb_s2_dual_suite_packaging_v1"
SUITE_STRATEGY = "S2_companion"
ARTIFACT_KIND_SCHEMA_EXAMPLE = "S2_DUAL_SUITE_PACKAGING_SCHEMA_EXAMPLE"
ARTIFACT_KIND_AUTHORIZED = "S2_DUAL_SUITE_PACKAGING"  # future only; not used this window

PRIMARY_SUITE_ID = "w9_critic_frozen_12"
PRIMARY_CASE_COUNT = 12
PRIMARY_OBSERVATION_PROTOCOL = "w10_eb2_generation_observation_v1"
PRIMARY_TARGETS: tuple[str, ...] = ("T1", "T2", "T3")

COMPANION_SUITE_ID = "w10_eb_empty_gate_v1"
COMPANION_CASE_COUNT = 2
COMPANION_PURPOSE = "empty_gate_refuse_ok"
COMPANION_TARGETS: tuple[str, ...] = ("T4_empty_gate_refuse_ok",)

PARENT_OBSERVATION_PROTOCOL = "w10_eb1_generation_observation_v1"

E_B_FORMAL_READY = "NO"
E_B_S2_PACKAGING_CONTRACT_READY = "YES"
E_B_S2_PACKAGING_AUTHORIZED = "NO"

SCHEMA_FILENAME = "w10-eb-s2-dual-suite-packaging-v1.schema.json"
PREP_STATUS_FILENAME = "w10-eb-s2-dual-suite-packaging.prep-status.json"
FORMAL_PACKAGING_RESULT_FILENAME = "w10-eb-s2-dual-suite-formal-packaging-result.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
SCHEMA_PATH = FIXTURES / SCHEMA_FILENAME
PREP_STATUS_PATH = FIXTURES / PREP_STATUS_FILENAME
FORMAL_PACKAGING_RESULT_PATH = FIXTURES / FORMAL_PACKAGING_RESULT_FILENAME

HEADER_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "suite_strategy",
    "artifact_kind",
    "parent_observation_protocol",
    "primary_suite",
    "companion_suite",
    "composition_rules",
    "authorization",
)

PRIMARY_REQUIRED: tuple[str, ...] = (
    "suite_id",
    "case_count",
    "observation_protocol",
    "targets",
)

COMPANION_REQUIRED: tuple[str, ...] = (
    "suite_id",
    "case_count",
    "purpose",
    "targets",
)

COMPOSITION_REQUIRED: tuple[str, ...] = (
    "w9_case_count_immutable",
    "forbid_merge_into_w9",
    "forbid_c04_c07_empty_gate_substitution",
    "empty_gate_cases_required_for_t4",
    "separate_envelopes_or_combo_reference",
)

AUTHORIZATION_REQUIRED: tuple[str, ...] = (
    "E_B_FORMAL_READY",
    "packaging_contract_ready",
    "authorized_formal_write",
)

FORBIDDEN_CRITIC_ORACLE_KEYS: frozenset[str] = frozenset(
    {
        "per_case_result",
        "adapter_protocol_version",
        "expected_action",
        "oracle_cases",
        "oracle_case",
        "critic_score",
        "critic_capability",
        "capability_label",
        "w9_critic_oracle",
        "critic_actions",
        "scorer_observation_point",
        "scope_compliance_pass",
    }
)

FORBIDDEN_LLM_JUDGE_KEYS: frozenset[str] = frozenset(
    {
        "llm_judge",
        "llm_judge_label",
        "nli_label",
        "judge_model",
        "auto_label",
        "lexical_overlap_label",
        "label_source",
    }
)

FORBIDDEN_REUSE_KEYS: frozenset[str] = frozenset(
    {
        "ea5_formal_reuse",
        "p2_r3_formal_reuse",
        "w10_ea4_formal_window_result",
        "w9_critic_p2_r3_formal_result",
        "execute_frozen_case",
    }
)

FORBIDDEN_FORMAL_CLAIM_KEYS: frozenset[str] = frozenset(
    {
        "measurement_validity",
        "formal_observation_result",
        "targets_measured",
        "hit_at_3",
        "capability_score",
        "formal_ready",
        "eb_formal_ready",
    }
)

FORBIDDEN_KEYS: frozenset[str] = (
    FORBIDDEN_CRITIC_ORACLE_KEYS
    | FORBIDDEN_LLM_JUDGE_KEYS
    | FORBIDDEN_REUSE_KEYS
    | FORBIDDEN_FORMAL_CLAIM_KEYS
)

FORBIDDEN_NOTES_PHRASES: tuple[str, ...] = (
    "E-B_FORMAL_READY = YES",
    "formal measurement complete",
    "grounding proven",
    "Critic validated",
    "authorized formal write",
)


class S2DualSuitePackagingContractError(ValueError):
    """Raised when an S2 packaging artifact violates the contract."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise S2DualSuitePackagingContractError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(
    mapping: Mapping[str, Any],
    path: str,
    *,
    label: str,
) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_KEYS)
    if present:
        raise S2DualSuitePackagingContractError(
            f"{label} fields present at {path}: {present}"
        )


def _reject_forbidden_keys_recursive(node: Any, path: str) -> None:
    if isinstance(node, Mapping):
        _reject_forbidden_keys(node, path, label="forbidden S2 packaging")
        for key, value in node.items():
            _reject_forbidden_keys_recursive(value, f"{path}.{key}")
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for index, item in enumerate(node):
            _reject_forbidden_keys_recursive(item, f"{path}[{index}]")


def _validate_targets(
    targets: Any,
    path: str,
    *,
    expected: Sequence[str],
) -> None:
    if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes, bytearray)):
        raise S2DualSuitePackagingContractError(f"{path} must be an array")
    if list(targets) != list(expected):
        raise S2DualSuitePackagingContractError(
            f"{path} must equal {list(expected)!r}; got {list(targets)!r}"
        )


def _validate_primary(suite: Mapping[str, Any], path: str) -> None:
    _require_keys(suite, PRIMARY_REQUIRED, path)
    if suite["suite_id"] != PRIMARY_SUITE_ID:
        raise S2DualSuitePackagingContractError(
            f"{path}.suite_id must be {PRIMARY_SUITE_ID!r}"
        )
    if suite["case_count"] != PRIMARY_CASE_COUNT:
        raise S2DualSuitePackagingContractError(
            f"{path}.case_count must remain {PRIMARY_CASE_COUNT}"
        )
    if suite["observation_protocol"] != PRIMARY_OBSERVATION_PROTOCOL:
        raise S2DualSuitePackagingContractError(
            f"{path}.observation_protocol must be {PRIMARY_OBSERVATION_PROTOCOL!r}"
        )
    _validate_targets(suite["targets"], f"{path}.targets", expected=PRIMARY_TARGETS)


def _validate_companion(suite: Mapping[str, Any], path: str) -> None:
    _require_keys(suite, COMPANION_REQUIRED, path)
    if suite["suite_id"] != COMPANION_SUITE_ID:
        raise S2DualSuitePackagingContractError(
            f"{path}.suite_id must be {COMPANION_SUITE_ID!r}"
        )
    if suite["case_count"] != COMPANION_CASE_COUNT:
        raise S2DualSuitePackagingContractError(
            f"{path}.case_count must be {COMPANION_CASE_COUNT}"
        )
    if suite["purpose"] != COMPANION_PURPOSE:
        raise S2DualSuitePackagingContractError(
            f"{path}.purpose must be {COMPANION_PURPOSE!r}"
        )
    _validate_targets(suite["targets"], f"{path}.targets", expected=COMPANION_TARGETS)


def _validate_composition(rules: Mapping[str, Any], path: str) -> None:
    _require_keys(rules, COMPOSITION_REQUIRED, path)
    for key in (
        "w9_case_count_immutable",
        "forbid_merge_into_w9",
        "forbid_c04_c07_empty_gate_substitution",
        "empty_gate_cases_required_for_t4",
        "separate_envelopes_or_combo_reference",
    ):
        if rules[key] is not True:
            raise S2DualSuitePackagingContractError(f"{path}.{key} must be true")


def _validate_authorization(auth: Mapping[str, Any], path: str) -> None:
    _require_keys(auth, AUTHORIZATION_REQUIRED, path)
    if auth["E_B_FORMAL_READY"] != "NO":
        raise S2DualSuitePackagingContractError(
            f"{path}.E_B_FORMAL_READY must be NO during prep / until gate clears"
        )
    if auth["packaging_contract_ready"] != "YES":
        raise S2DualSuitePackagingContractError(
            f"{path}.packaging_contract_ready must be YES"
        )
    if auth["authorized_formal_write"] is not False:
        raise S2DualSuitePackagingContractError(
            f"{path}.authorized_formal_write must be false "
            "(packaging contract ≠ formal authorization)"
        )


def validate_s2_dual_suite_packaging(payload: Mapping[str, Any]) -> None:
    """Validate S2 dual-suite packaging descriptor structure and honesty rules."""
    if not isinstance(payload, Mapping):
        raise S2DualSuitePackagingContractError("artifact must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise S2DualSuitePackagingContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["suite_strategy"] != SUITE_STRATEGY:
        raise S2DualSuitePackagingContractError(
            f"suite_strategy must be {SUITE_STRATEGY!r}"
        )
    if payload["artifact_kind"] != ARTIFACT_KIND_SCHEMA_EXAMPLE:
        # Prep window only accepts schema-example packaging descriptors.
        # Authorized packaging writes are out of scope until E-B_FORMAL_READY.
        raise S2DualSuitePackagingContractError(
            f"artifact_kind must be {ARTIFACT_KIND_SCHEMA_EXAMPLE!r} "
            "during E-B11 prep (authorized packaging write forbidden)"
        )
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise S2DualSuitePackagingContractError(
            "parent_observation_protocol must bind "
            f"{PARENT_OBSERVATION_PROTOCOL!r}"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for phrase in FORBIDDEN_NOTES_PHRASES:
            if phrase in notes:
                raise S2DualSuitePackagingContractError(
                    f"forbidden phrase {phrase!r} appears in notes"
                )

    primary = payload["primary_suite"]
    if not isinstance(primary, Mapping):
        raise S2DualSuitePackagingContractError("primary_suite must be an object")
    _validate_primary(primary, "$.primary_suite")

    companion = payload["companion_suite"]
    if not isinstance(companion, Mapping):
        raise S2DualSuitePackagingContractError("companion_suite must be an object")
    _validate_companion(companion, "$.companion_suite")

    if primary["suite_id"] == companion["suite_id"]:
        raise S2DualSuitePackagingContractError(
            "primary and companion suite_id must remain distinct"
        )

    rules = payload["composition_rules"]
    if not isinstance(rules, Mapping):
        raise S2DualSuitePackagingContractError("composition_rules must be an object")
    _validate_composition(rules, "$.composition_rules")

    auth = payload["authorization"]
    if not isinstance(auth, Mapping):
        raise S2DualSuitePackagingContractError("authorization must be an object")
    _validate_authorization(auth, "$.authorization")


def build_schema_example_packaging() -> dict[str, Any]:
    """In-memory S2 packaging schema example (not an authorized formal write)."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "suite_strategy": SUITE_STRATEGY,
        "artifact_kind": ARTIFACT_KIND_SCHEMA_EXAMPLE,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "notes": "SCHEMA_EXAMPLE_S2_PACKAGING_NOT_FORMAL_AUTHORIZATION",
        "primary_suite": {
            "suite_id": PRIMARY_SUITE_ID,
            "case_count": PRIMARY_CASE_COUNT,
            "observation_protocol": PRIMARY_OBSERVATION_PROTOCOL,
            "targets": list(PRIMARY_TARGETS),
        },
        "companion_suite": {
            "suite_id": COMPANION_SUITE_ID,
            "case_count": COMPANION_CASE_COUNT,
            "purpose": COMPANION_PURPOSE,
            "targets": list(COMPANION_TARGETS),
        },
        "composition_rules": {
            "w9_case_count_immutable": True,
            "forbid_merge_into_w9": True,
            "forbid_c04_c07_empty_gate_substitution": True,
            "empty_gate_cases_required_for_t4": True,
            "separate_envelopes_or_combo_reference": True,
        },
        "authorization": {
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
            "packaging_contract_ready": E_B_S2_PACKAGING_CONTRACT_READY,
            "authorized_formal_write": False,
        },
    }


def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_packaging())


def build_prep_status_document() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": "S2_DUAL_SUITE_PACKAGING_PREP_STATUS",
        "suite_strategy": SUITE_STRATEGY,
        "E_B_S2_PACKAGING_CONTRACT_READY": E_B_S2_PACKAGING_CONTRACT_READY,
        "E_B_S2_PACKAGING_AUTHORIZED": E_B_S2_PACKAGING_AUTHORIZED,
        "E_B_FORMAL_READY": E_B_FORMAL_READY,
        "primary_suite_id": PRIMARY_SUITE_ID,
        "primary_case_count": PRIMARY_CASE_COUNT,
        "companion_suite_id": COMPANION_SUITE_ID,
        "companion_case_count": COMPANION_CASE_COUNT,
        "formal_packaging_result_filename": FORMAL_PACKAGING_RESULT_FILENAME,
        "formal_packaging_result_status": "ABSENT",
        "notes": (
            "E-B11 Lane B prep only: S2 dual-suite packaging contract frozen; "
            "authorized formal packaging write remains NO; "
            "does not clear E-B_FORMAL_READY."
        ),
    }


def load_schema_document() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        raise S2DualSuitePackagingContractError(f"schema file missing: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_prep_status_document() -> dict[str, Any]:
    if not PREP_STATUS_PATH.is_file():
        raise S2DualSuitePackagingContractError(
            f"prep status file missing: {PREP_STATUS_PATH}"
        )
    return json.loads(PREP_STATUS_PATH.read_text(encoding="utf-8"))


def validate_prep_status_document(payload: Mapping[str, Any] | None = None) -> None:
    doc = payload if payload is not None else load_prep_status_document()
    if not isinstance(doc, Mapping):
        raise S2DualSuitePackagingContractError("prep status must be a JSON object")
    required = (
        "protocol_version",
        "artifact_kind",
        "suite_strategy",
        "E_B_S2_PACKAGING_CONTRACT_READY",
        "E_B_S2_PACKAGING_AUTHORIZED",
        "E_B_FORMAL_READY",
        "primary_suite_id",
        "primary_case_count",
        "companion_suite_id",
        "companion_case_count",
        "formal_packaging_result_status",
    )
    _require_keys(doc, required, "$")
    if doc["protocol_version"] != PROTOCOL_VERSION:
        raise S2DualSuitePackagingContractError("prep status protocol_version mismatch")
    if doc["artifact_kind"] != "S2_DUAL_SUITE_PACKAGING_PREP_STATUS":
        raise S2DualSuitePackagingContractError("prep status artifact_kind mismatch")
    if doc["suite_strategy"] != SUITE_STRATEGY:
        raise S2DualSuitePackagingContractError("prep status suite_strategy mismatch")
    if doc["E_B_S2_PACKAGING_CONTRACT_READY"] != "YES":
        raise S2DualSuitePackagingContractError("S2 packaging contract must be YES")
    if doc["E_B_S2_PACKAGING_AUTHORIZED"] != "NO":
        raise S2DualSuitePackagingContractError(
            "S2 packaging authorization must remain NO"
        )
    if doc["E_B_FORMAL_READY"] != "NO":
        raise S2DualSuitePackagingContractError("E_B_FORMAL_READY must remain NO")
    if doc["primary_suite_id"] != PRIMARY_SUITE_ID:
        raise S2DualSuitePackagingContractError("primary_suite_id mismatch")
    if doc["primary_case_count"] != PRIMARY_CASE_COUNT:
        raise S2DualSuitePackagingContractError("primary_case_count mismatch")
    if doc["companion_suite_id"] != COMPANION_SUITE_ID:
        raise S2DualSuitePackagingContractError("companion_suite_id mismatch")
    if doc["companion_case_count"] != COMPANION_CASE_COUNT:
        raise S2DualSuitePackagingContractError("companion_case_count mismatch")
    if doc["formal_packaging_result_status"] != "ABSENT":
        raise S2DualSuitePackagingContractError(
            "formal packaging result must remain ABSENT during prep"
        )


def assert_formal_packaging_result_absent() -> None:
    if FORMAL_PACKAGING_RESULT_PATH.exists():
        raise S2DualSuitePackagingContractError(
            f"{FORMAL_PACKAGING_RESULT_FILENAME} must remain absent "
            f"(found at {FORMAL_PACKAGING_RESULT_PATH})"
        )


def assert_prep_status_present() -> None:
    if not PREP_STATUS_PATH.is_file():
        raise S2DualSuitePackagingContractError(
            f"prep status missing: {PREP_STATUS_PATH}"
        )
    validate_prep_status_document()


def assert_eb2_and_empty_gate_identities_aligned() -> None:
    """Packaging must not rewrite E-B2 v1 or E-B9b companion identity."""
    from tests import w10_eb2_generation_observation_contract as eb2
    from tests import w10_eb_empty_gate_suite_contract as empty

    if eb2.SUITE_ID != PRIMARY_SUITE_ID:
        raise S2DualSuitePackagingContractError(
            f"E-B2 SUITE_ID drift: expected {PRIMARY_SUITE_ID!r}, got {eb2.SUITE_ID!r}"
        )
    if eb2.FROZEN_CASE_COUNT != PRIMARY_CASE_COUNT:
        raise S2DualSuitePackagingContractError(
            f"E-B2 case_count drift: expected {PRIMARY_CASE_COUNT}, "
            f"got {eb2.FROZEN_CASE_COUNT}"
        )
    if eb2.PROTOCOL_VERSION != PRIMARY_OBSERVATION_PROTOCOL:
        raise S2DualSuitePackagingContractError(
            "E-B2 PROTOCOL_VERSION drift vs primary observation_protocol"
        )
    if empty.SUITE_ID != COMPANION_SUITE_ID:
        raise S2DualSuitePackagingContractError(
            f"empty-gate SUITE_ID drift: expected {COMPANION_SUITE_ID!r}, "
            f"got {empty.SUITE_ID!r}"
        )
    if empty.CASE_COUNT != COMPANION_CASE_COUNT:
        raise S2DualSuitePackagingContractError(
            f"empty-gate CASE_COUNT drift: expected {COMPANION_CASE_COUNT}, "
            f"got {empty.CASE_COUNT}"
        )
    if empty.SUITE_STRATEGY != SUITE_STRATEGY:
        raise S2DualSuitePackagingContractError("empty-gate suite_strategy drift")
    if empty.E_B_FORMAL_READY != "NO":
        raise S2DualSuitePackagingContractError("empty-gate E_B_FORMAL_READY drifted")
    if eb2.SUITE_ID == empty.SUITE_ID:
        raise S2DualSuitePackagingContractError(
            "primary and companion suites must stay distinct"
        )


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no LLM / Critic / formal runners."""
    import ast
    import inspect

    import tests.w10_eb_s2_dual_suite_packaging_contract as self_mod

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
        "stream_deepseek_tokens",
    ):
        if hasattr(self_mod, banned_attr):
            return False
    return True

"""W10 empty-gate *cases* artifact contract + REAL_ELIGIBLE material gate.

Validates on-disk ``w10-eb-empty-gate-cases.json`` and prep-status.
Does not: call LLM / LM Studio, run generation, write formal observation,
clear E-B_FORMAL_READY, authorize S2 packaging, or implement Lane A claim gold.

Distinct from E-B9b suite *schema-example* freeze:
- E-B9b: suite identity ``w10_eb_empty_gate_v1`` + SCHEMA_EXAMPLE envelope
- Cases contract: REAL_ELIGIBLE ``w10-eb-empty-gate-cases.json`` material
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Frozen identity / gate constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "w10_eb_empty_gate_cases_v1"
SUITE_ID = "w10_eb_empty_gate_v1"
CASE_COUNT = 2
PURPOSE = "empty_gate_refuse_ok"
PARENT_OBSERVATION_PROTOCOL = "w10_eb1_generation_observation_v1"
SUITE_STRATEGY = "S2_companion"
PARENT_SUITE_CONTRACT = "w10_eb_empty_gate_v1"

ARTIFACT_KIND_SCHEMA_EXAMPLE = "EMPTY_GATE_CASES_SCHEMA_EXAMPLE"
ARTIFACT_KIND_REAL = "EMPTY_GATE_CASES"
ARTIFACT_KINDS = frozenset({ARTIFACT_KIND_SCHEMA_EXAMPLE, ARTIFACT_KIND_REAL})

CASES_MATERIAL_STATUS_ABSENT = "ABSENT"
CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE = "SCHEMA_EXAMPLE_ONLY"
CASES_MATERIAL_STATUS_REAL = "REAL_ELIGIBLE"
CASES_MATERIAL_STATUSES = frozenset(
    {
        CASES_MATERIAL_STATUS_ABSENT,
        CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE,
        CASES_MATERIAL_STATUS_REAL,
    }
)

E_B_FORMAL_READY = "NO"
E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY = "YES"
E_B_EMPTY_GATE_CASES_MATERIAL_READY = "YES"

SCHEMA_FILENAME = "w10-eb-empty-gate-cases-v1.schema.json"
CASES_FILENAME = "w10-eb-empty-gate-cases.json"
PREP_STATUS_FILENAME = "w10-eb-empty-gate-cases.prep-status.json"
FORMAL_RESULT_FILENAME = "w10-eb-empty-gate-formal-result.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
SCHEMA_PATH = FIXTURES / SCHEMA_FILENAME
CASES_PATH = FIXTURES / CASES_FILENAME
PREP_STATUS_PATH = FIXTURES / PREP_STATUS_FILENAME
FORMAL_RESULT_PATH = FIXTURES / FORMAL_RESULT_FILENAME

CASE_ID_PREFIX = "EB8-EMPTY-GATE-"
CASE_ID_RE = re.compile(r"^EB8-EMPTY-GATE-[A-Za-z0-9_-]+$")
W9_CRITIC_CASE_ID_RE = re.compile(r"^C(0[1-9]|1[0-2])(-|$)")
W9_CRITIC_SUITE_ID = "w9_critic_frozen_12"

RETRIEVAL_RESULT_STATES = frozenset({"empty_retrieval", "empty_gated"})
REFUSAL_GOLD_ZH = "知识库中未找到相关内容。"
REFUSAL_GOLD_EN = "No relevant content was found in the knowledge base."
ALLOWED_REFUSAL_GOLD = frozenset({REFUSAL_GOLD_ZH, REFUSAL_GOLD_EN})

HEADER_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "suite_id",
    "case_count",
    "purpose",
    "parent_observation_protocol",
    "suite_strategy",
    "artifact_kind",
    "cases_material_status",
    "cases",
)

CASE_REQUIRED: tuple[str, ...] = (
    "case_id",
    "query",
    "retrieval_result_state",
    "evidence_count",
    "expected_refusal",
    "no_context_reply_for",
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

FORBIDDEN_FORMAL_CLAIM_KEYS: frozenset[str] = frozenset(
    {
        "measurement_validity",
        "formal_observation_result",
        "targets_measured",
        "E-B_FORMAL_READY",
        "eb_formal_ready",
        "formal_ready",
        "hit_at_3",
        "capability_score",
    }
)

FORBIDDEN_REUSE_KEYS: frozenset[str] = frozenset(
    {
        "w9_critic_frozen_12",
        "frozen_critic_suite",
        "critic_suite_id",
        "w9_case_ids",
        "ea5_formal_reuse",
        "p2_r3_formal_reuse",
        "w10_ea4_formal_window_result",
        "w9_critic_p2_r3_formal_result",
    }
)

FORBIDDEN_KEYS: frozenset[str] = (
    FORBIDDEN_CRITIC_ORACLE_KEYS
    | FORBIDDEN_LLM_JUDGE_KEYS
    | FORBIDDEN_FORMAL_CLAIM_KEYS
    | FORBIDDEN_REUSE_KEYS
)

FORBIDDEN_NOTES_PHRASES: tuple[str, ...] = (
    "formal measurement",
    "E-B_FORMAL_READY = YES",
    "grounding proven",
    "Critic validated",
    "w9_critic_frozen_12",
    "measured empty-gate denominator",
)


class EmptyGateCasesContractError(ValueError):
    """Raised when a candidate empty-gate cases artifact violates the contract."""


def expected_no_context_reply_for(query: str) -> str:
    """Deterministic refusal-gold band (mirrors product ``no_context_reply_for``)."""
    ascii_letters = sum(1 for char in query if char.isascii() and char.isalpha())
    cjk_chars = sum(1 for char in query if "\u4e00" <= char <= "\u9fff")
    if ascii_letters > cjk_chars:
        return REFUSAL_GOLD_EN
    return REFUSAL_GOLD_ZH


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise EmptyGateCasesContractError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(
    mapping: Mapping[str, Any],
    path: str,
    *,
    label: str,
) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_KEYS)
    if present:
        raise EmptyGateCasesContractError(f"{label} fields present at {path}: {present}")


def _reject_forbidden_keys_recursive(node: Any, path: str) -> None:
    if isinstance(node, Mapping):
        _reject_forbidden_keys(node, path, label="forbidden empty-gate-cases")
        for key, value in node.items():
            _reject_forbidden_keys_recursive(value, f"{path}.{key}")
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for index, item in enumerate(node):
            _reject_forbidden_keys_recursive(item, f"{path}[{index}]")


def _validate_case(case: Mapping[str, Any], path: str) -> None:
    _require_keys(case, CASE_REQUIRED, path)
    _reject_forbidden_keys(case, path, label="forbidden case-level")

    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise EmptyGateCasesContractError(f"{path}.case_id must be a non-empty string")
    if not CASE_ID_RE.fullmatch(case_id):
        raise EmptyGateCasesContractError(
            f"{path}.case_id must match {CASE_ID_PREFIX!r} prefix pattern"
        )
    if W9_CRITIC_CASE_ID_RE.match(case_id):
        raise EmptyGateCasesContractError(
            f"{path}.case_id must not reuse W9 Critic identity ({case_id!r})"
        )
    if case_id in {
        "C04",
        "C07",
        "C04-valid-citation-wrong-evidence",
        "C07-correct-insufficiency-refusal",
    }:
        raise EmptyGateCasesContractError(
            f"{path}.case_id must not substitute C04/C07 for empty-gate"
        )

    query = case["query"]
    if not isinstance(query, str) or not query.strip():
        raise EmptyGateCasesContractError(f"{path}.query must be a non-empty string")

    state = case["retrieval_result_state"]
    if state not in RETRIEVAL_RESULT_STATES:
        raise EmptyGateCasesContractError(
            f"{path}.retrieval_result_state must be one of "
            f"{sorted(RETRIEVAL_RESULT_STATES)}"
        )

    if case["evidence_count"] != 0:
        raise EmptyGateCasesContractError(
            f"{path}.evidence_count must be 0 (empty-gate denominator); "
            f"got {case['evidence_count']!r}"
        )

    if case["expected_refusal"] is not True:
        raise EmptyGateCasesContractError(
            f"{path}.expected_refusal must be true for empty-gate cases"
        )

    refusal_gold = case["no_context_reply_for"]
    if not isinstance(refusal_gold, str) or not refusal_gold:
        raise EmptyGateCasesContractError(
            f"{path}.no_context_reply_for must be a non-empty string"
        )
    if refusal_gold not in ALLOWED_REFUSAL_GOLD:
        raise EmptyGateCasesContractError(
            f"{path}.no_context_reply_for must be product refusal gold "
            f"(ZH or EN fixed phrase)"
        )
    expected = expected_no_context_reply_for(query)
    if refusal_gold != expected:
        raise EmptyGateCasesContractError(
            f"{path}.no_context_reply_for={refusal_gold!r} does not match "
            f"language band for query (expected {expected!r})"
        )


def validate_empty_gate_cases_artifact(payload: Mapping[str, Any]) -> None:
    """Validate empty-gate cases artifact structure and isolation rules."""
    if not isinstance(payload, Mapping):
        raise EmptyGateCasesContractError("artifact must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise EmptyGateCasesContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["suite_id"] != SUITE_ID:
        raise EmptyGateCasesContractError(f"suite_id mismatch: expected {SUITE_ID!r}")
    if payload["suite_id"] == W9_CRITIC_SUITE_ID:
        raise EmptyGateCasesContractError(
            "suite_id must not equal W9 Critic suite w9_critic_frozen_12"
        )
    if payload["case_count"] != CASE_COUNT:
        raise EmptyGateCasesContractError(
            f"case_count must be {CASE_COUNT} (N for companion empty-gate suite)"
        )
    if payload["purpose"] != PURPOSE:
        raise EmptyGateCasesContractError(f"purpose must be {PURPOSE!r}")
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise EmptyGateCasesContractError(
            "parent_observation_protocol must bind "
            f"{PARENT_OBSERVATION_PROTOCOL!r}"
        )
    if payload["suite_strategy"] != SUITE_STRATEGY:
        raise EmptyGateCasesContractError(
            f"suite_strategy must be {SUITE_STRATEGY!r}"
        )

    artifact_kind = payload["artifact_kind"]
    if artifact_kind not in ARTIFACT_KINDS:
        raise EmptyGateCasesContractError(
            f"artifact_kind must be one of {sorted(ARTIFACT_KINDS)}"
        )

    material_status = payload["cases_material_status"]
    if material_status not in CASES_MATERIAL_STATUSES:
        raise EmptyGateCasesContractError(
            f"cases_material_status must be one of {sorted(CASES_MATERIAL_STATUSES)}"
        )

    # Honesty binding: schema-example payloads cannot claim REAL_ELIGIBLE.
    if (
        artifact_kind == ARTIFACT_KIND_SCHEMA_EXAMPLE
        and material_status == CASES_MATERIAL_STATUS_REAL
    ):
        raise EmptyGateCasesContractError(
            "SCHEMA_EXAMPLE artifact_kind cannot claim REAL_ELIGIBLE material"
        )
    if (
        artifact_kind == ARTIFACT_KIND_REAL
        and material_status != CASES_MATERIAL_STATUS_REAL
    ):
        raise EmptyGateCasesContractError(
            "EMPTY_GATE_CASES artifact_kind requires cases_material_status=REAL_ELIGIBLE"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for phrase in FORBIDDEN_NOTES_PHRASES:
            if phrase in notes:
                raise EmptyGateCasesContractError(
                    f"forbidden phrase {phrase!r} appears in notes"
                )

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise EmptyGateCasesContractError("cases must be an array")
    if len(cases) != CASE_COUNT:
        raise EmptyGateCasesContractError(
            f"cases length must equal case_count={CASE_COUNT}; got {len(cases)}"
        )

    seen_case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise EmptyGateCasesContractError(f"$.cases[{index}] must be an object")
        _validate_case(case, f"$.cases[{index}]")
        cid = str(case["case_id"])
        if cid in seen_case_ids:
            raise EmptyGateCasesContractError(f"duplicate case_id {cid!r}")
        seen_case_ids.add(cid)


def _empty_gate_case_pair() -> list[dict[str, Any]]:
    zh_query = "知识库里有没有从未收录的虚构加班政策编号 ZX-999？"
    en_query = "Is there any never-indexed fictional overtime policy code ZX-999?"
    return [
        {
            "case_id": "EB8-EMPTY-GATE-zh",
            "query": zh_query,
            "retrieval_result_state": "empty_retrieval",
            "evidence_count": 0,
            "expected_refusal": True,
            "no_context_reply_for": expected_no_context_reply_for(zh_query),
        },
        {
            "case_id": "EB8-EMPTY-GATE-en",
            "query": en_query,
            "retrieval_result_state": "empty_gated",
            "evidence_count": 0,
            "expected_refusal": True,
            "no_context_reply_for": expected_no_context_reply_for(en_query),
        },
    ]


def build_schema_example_cases() -> dict[str, Any]:
    """In-memory synthetic cases for deterministic tests only (not on-disk material)."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "suite_id": SUITE_ID,
        "case_count": CASE_COUNT,
        "purpose": PURPOSE,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "suite_strategy": SUITE_STRATEGY,
        "artifact_kind": ARTIFACT_KIND_SCHEMA_EXAMPLE,
        "cases_material_status": CASES_MATERIAL_STATUS_SCHEMA_EXAMPLE,
        "notes": "SCHEMA_EXAMPLE_NOT_REAL_CASES_NOT_FORMAL_MEASUREMENT",
        "cases": _empty_gate_case_pair(),
    }


def build_real_eligible_cases() -> dict[str, Any]:
    """Canonical REAL_ELIGIBLE cases payload (matches on-disk fixture)."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "suite_id": SUITE_ID,
        "case_count": CASE_COUNT,
        "purpose": PURPOSE,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "suite_strategy": SUITE_STRATEGY,
        "artifact_kind": ARTIFACT_KIND_REAL,
        "cases_material_status": CASES_MATERIAL_STATUS_REAL,
        "notes": (
            "REAL_ELIGIBLE empty-gate research denominator for T4 "
            "empty_gate_refuse_ok. Not formal observation. "
            "E-B_FORMAL_READY remains NO."
        ),
        "cases": _empty_gate_case_pair(),
    }


def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_cases())


def build_prep_status_document() -> dict[str, Any]:
    """On-disk prep marker: REAL_ELIGIBLE material present; formal still NO."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": "EMPTY_GATE_CASES_PREP_STATUS",
        "suite_id": SUITE_ID,
        "cases_filename": CASES_FILENAME,
        "cases_path_relative": f"backend/tests/fixtures/l4_critic/{CASES_FILENAME}",
        "cases_material_status": CASES_MATERIAL_STATUS_REAL,
        "E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY": (
            E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY
        ),
        "E_B_EMPTY_GATE_CASES_MATERIAL_READY": E_B_EMPTY_GATE_CASES_MATERIAL_READY,
        "E_B_FORMAL_READY": E_B_FORMAL_READY,
        "parent_suite_contract": PARENT_SUITE_CONTRACT,
        "notes": (
            "Empty-gate REAL_ELIGIBLE cases material on disk; "
            "T4 denominator fixture ready. Not formal observation authorization; "
            "E-B_FORMAL_READY remains NO; S2 packaging not authorized."
        ),
    }


def load_schema_document() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        raise EmptyGateCasesContractError(f"schema file missing: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_prep_status_document() -> dict[str, Any]:
    if not PREP_STATUS_PATH.is_file():
        raise EmptyGateCasesContractError(
            f"prep status file missing: {PREP_STATUS_PATH}"
        )
    return json.loads(PREP_STATUS_PATH.read_text(encoding="utf-8"))


def validate_prep_status_document(payload: Mapping[str, Any] | None = None) -> None:
    doc = payload if payload is not None else load_prep_status_document()
    if not isinstance(doc, Mapping):
        raise EmptyGateCasesContractError("prep status must be a JSON object")
    required = (
        "protocol_version",
        "artifact_kind",
        "suite_id",
        "cases_filename",
        "cases_path_relative",
        "cases_material_status",
        "E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY",
        "E_B_EMPTY_GATE_CASES_MATERIAL_READY",
        "E_B_FORMAL_READY",
    )
    _require_keys(doc, required, "$")
    if doc["protocol_version"] != PROTOCOL_VERSION:
        raise EmptyGateCasesContractError("prep status protocol_version mismatch")
    if doc["artifact_kind"] != "EMPTY_GATE_CASES_PREP_STATUS":
        raise EmptyGateCasesContractError("prep status artifact_kind mismatch")
    if doc["suite_id"] != SUITE_ID:
        raise EmptyGateCasesContractError("prep status suite_id mismatch")
    if doc["cases_filename"] != CASES_FILENAME:
        raise EmptyGateCasesContractError("prep status cases_filename mismatch")
    if doc["cases_material_status"] != CASES_MATERIAL_STATUS_REAL:
        raise EmptyGateCasesContractError(
            "prep status must record cases_material_status=REAL_ELIGIBLE "
            "when material is on disk"
        )
    if doc["E_B_EMPTY_GATE_CASES_ARTIFACT_CONTRACT_READY"] != "YES":
        raise EmptyGateCasesContractError("cases artifact contract must be YES")
    if doc["E_B_EMPTY_GATE_CASES_MATERIAL_READY"] != "YES":
        raise EmptyGateCasesContractError(
            "cases material must be YES when REAL_ELIGIBLE file is present"
        )
    if doc["E_B_FORMAL_READY"] != "NO":
        raise EmptyGateCasesContractError("E_B_FORMAL_READY must remain NO")


def load_real_cases() -> dict[str, Any]:
    if not CASES_PATH.is_file():
        raise EmptyGateCasesContractError(f"real cases file missing: {CASES_PATH}")
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EmptyGateCasesContractError("real cases file must be a JSON object")
    return payload


def assert_real_cases_present_and_valid() -> None:
    """On-disk REAL_ELIGIBLE cases must exist and pass the cases validator."""
    payload = load_real_cases()
    validate_empty_gate_cases_artifact(payload)
    if payload["artifact_kind"] != ARTIFACT_KIND_REAL:
        raise EmptyGateCasesContractError(
            f"on-disk {CASES_FILENAME} must use artifact_kind={ARTIFACT_KIND_REAL!r}"
        )
    if payload["cases_material_status"] != CASES_MATERIAL_STATUS_REAL:
        raise EmptyGateCasesContractError(
            f"on-disk {CASES_FILENAME} must use "
            f"cases_material_status={CASES_MATERIAL_STATUS_REAL!r}"
        )
    expected = build_real_eligible_cases()
    if payload["case_count"] != expected["case_count"]:
        raise EmptyGateCasesContractError("on-disk case_count drift vs contract")
    if [c["case_id"] for c in payload["cases"]] != [
        c["case_id"] for c in expected["cases"]
    ]:
        raise EmptyGateCasesContractError("on-disk case_id set drift vs contract")


def assert_formal_result_absent() -> None:
    if FORMAL_RESULT_PATH.exists():
        raise EmptyGateCasesContractError(
            f"{FORMAL_RESULT_FILENAME} must remain absent "
            f"(found at {FORMAL_RESULT_PATH})"
        )


def assert_prep_status_present() -> None:
    if not PREP_STATUS_PATH.is_file():
        raise EmptyGateCasesContractError(
            f"prep status missing: {PREP_STATUS_PATH}"
        )
    validate_prep_status_document()


def assert_eb9b_suite_identity_aligned() -> None:
    """Cases contract must stay aligned with E-B9b suite identity constants."""
    from tests import w10_eb_empty_gate_suite_contract as suite

    if suite.SUITE_ID != SUITE_ID:
        raise EmptyGateCasesContractError(
            f"suite_id drift vs E-B9b: expected {SUITE_ID!r}, got {suite.SUITE_ID!r}"
        )
    if suite.CASE_COUNT != CASE_COUNT:
        raise EmptyGateCasesContractError(
            f"case_count drift vs E-B9b: expected {CASE_COUNT}, got {suite.CASE_COUNT}"
        )
    if suite.PURPOSE != PURPOSE:
        raise EmptyGateCasesContractError("purpose drift vs E-B9b suite contract")
    if suite.SUITE_STRATEGY != SUITE_STRATEGY:
        raise EmptyGateCasesContractError("suite_strategy drift vs E-B9b")
    if suite.CASES_FILENAME != CASES_FILENAME:
        raise EmptyGateCasesContractError("cases filename drift vs E-B9b")
    if suite.E_B_FORMAL_READY != "NO":
        raise EmptyGateCasesContractError("E-B9b E_B_FORMAL_READY drifted from NO")


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no LLM / Critic harness / observation executor hooks."""
    import ast
    import inspect

    import tests.w10_eb_empty_gate_cases_contract as self_mod

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

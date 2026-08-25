"""W10 E-B9b — Empty-gate companion suite schema + test-only validator.

S2 companion suite contract for T4 ``empty_gate_refuse_ok``.
Does not: create real cases, call LLM / LM Studio, run generation,
write formal observation, modify E-B2 v1, or clear E-B_FORMAL_READY.
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

PROTOCOL_VERSION = "w10_eb_empty_gate_v1"
SUITE_ID = "w10_eb_empty_gate_v1"
CASE_COUNT = 2  # N — E-B8 suggested zh+en companion pair
PURPOSE = "empty_gate_refuse_ok"
PARENT_OBSERVATION_PROTOCOL = "w10_eb1_generation_observation_v1"
SUITE_STRATEGY = "S2_companion"
ARTIFACT_KIND = "EMPTY_GATE_SUITE_SCHEMA_EXAMPLE"

# Isolation from W9 Critic / E-B2 v1 identity (must never be claimed here).
W9_CRITIC_SUITE_ID = "w9_critic_frozen_12"
EB2_PROTOCOL_VERSION = "w10_eb2_generation_observation_v1"
EB2_FROZEN_CASE_COUNT = 12

E_B_FORMAL_READY = "NO"
E_B_EMPTY_GATE_CONTRACT_READY = "YES"

SCHEMA_FILENAME = "w10-eb-empty-gate-suite-v1.schema.json"
CASES_FILENAME = "w10-eb-empty-gate-cases.json"
FORMAL_RESULT_FILENAME = "w10-eb-empty-gate-formal-result.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
SCHEMA_PATH = FIXTURES / SCHEMA_FILENAME
CASES_PATH = FIXTURES / CASES_FILENAME
FORMAL_RESULT_PATH = FIXTURES / FORMAL_RESULT_FILENAME

CASE_ID_PREFIX = "EB8-EMPTY-GATE-"
CASE_ID_RE = re.compile(r"^EB8-EMPTY-GATE-[A-Za-z0-9_-]+$")
W9_CRITIC_CASE_ID_RE = re.compile(r"^C(0[1-9]|1[0-2])(-|$)")

RETRIEVAL_RESULT_STATES = frozenset({"empty_retrieval", "empty_gated"})

# Mirrored product refusal gold (must stay equal to generation.py constants).
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

FORBIDDEN_W9_IDENTITY_KEYS: frozenset[str] = frozenset(
    {
        "w9_critic_frozen_12",
        "frozen_critic_suite",
        "critic_suite_id",
        "w9_case_ids",
    }
)

FORBIDDEN_KEYS: frozenset[str] = (
    FORBIDDEN_CRITIC_ORACLE_KEYS
    | FORBIDDEN_FORMAL_CLAIM_KEYS
    | FORBIDDEN_W9_IDENTITY_KEYS
)

FORBIDDEN_NOTES_PHRASES: tuple[str, ...] = (
    "formal measurement",
    "E-B_FORMAL_READY = YES",
    "grounding proven",
    "Critic validated",
    "w9_critic_frozen_12",
)


class EmptyGateSuiteContractError(ValueError):
    """Raised when a candidate empty-gate suite artifact violates the contract."""


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
        raise EmptyGateSuiteContractError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(
    mapping: Mapping[str, Any],
    path: str,
    *,
    label: str,
) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_KEYS)
    if present:
        raise EmptyGateSuiteContractError(f"{label} fields present at {path}: {present}")


def _reject_forbidden_keys_recursive(node: Any, path: str) -> None:
    if isinstance(node, Mapping):
        _reject_forbidden_keys(node, path, label="forbidden empty-gate")
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
        raise EmptyGateSuiteContractError(f"{path}.case_id must be a non-empty string")
    if not CASE_ID_RE.fullmatch(case_id):
        raise EmptyGateSuiteContractError(
            f"{path}.case_id must match {CASE_ID_PREFIX!r} prefix pattern"
        )
    if W9_CRITIC_CASE_ID_RE.match(case_id):
        raise EmptyGateSuiteContractError(
            f"{path}.case_id must not reuse W9 Critic identity ({case_id!r})"
        )
    if case_id in {"C04", "C07", "C04-valid-citation-wrong-evidence",
                   "C07-correct-insufficiency-refusal"}:
        raise EmptyGateSuiteContractError(
            f"{path}.case_id must not substitute C04/C07 for empty-gate"
        )

    query = case["query"]
    if not isinstance(query, str) or not query.strip():
        raise EmptyGateSuiteContractError(f"{path}.query must be a non-empty string")

    state = case["retrieval_result_state"]
    if state not in RETRIEVAL_RESULT_STATES:
        raise EmptyGateSuiteContractError(
            f"{path}.retrieval_result_state must be one of "
            f"{sorted(RETRIEVAL_RESULT_STATES)}"
        )

    evidence_count = case["evidence_count"]
    if evidence_count != 0:
        raise EmptyGateSuiteContractError(
            f"{path}.evidence_count must be 0 (empty-gate denominator); "
            f"got {evidence_count!r}"
        )

    expected_refusal = case["expected_refusal"]
    if expected_refusal is not True:
        raise EmptyGateSuiteContractError(
            f"{path}.expected_refusal must be true for empty-gate cases"
        )

    refusal_gold = case["no_context_reply_for"]
    if not isinstance(refusal_gold, str) or not refusal_gold:
        raise EmptyGateSuiteContractError(
            f"{path}.no_context_reply_for must be a non-empty string"
        )
    if refusal_gold not in ALLOWED_REFUSAL_GOLD:
        raise EmptyGateSuiteContractError(
            f"{path}.no_context_reply_for must be product refusal gold "
            f"(ZH or EN fixed phrase)"
        )
    expected = expected_no_context_reply_for(query)
    if refusal_gold != expected:
        raise EmptyGateSuiteContractError(
            f"{path}.no_context_reply_for={refusal_gold!r} does not match "
            f"language band for query (expected {expected!r})"
        )


def validate_empty_gate_suite(payload: Mapping[str, Any]) -> None:
    """Validate companion empty-gate suite structure and isolation rules."""
    if not isinstance(payload, Mapping):
        raise EmptyGateSuiteContractError("artifact must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise EmptyGateSuiteContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["suite_id"] != SUITE_ID:
        raise EmptyGateSuiteContractError(
            f"suite_id mismatch: expected {SUITE_ID!r}"
        )
    if payload["suite_id"] == W9_CRITIC_SUITE_ID:
        raise EmptyGateSuiteContractError(
            "suite_id must not equal W9 Critic suite w9_critic_frozen_12"
        )
    if payload["case_count"] != CASE_COUNT:
        raise EmptyGateSuiteContractError(
            f"case_count must be {CASE_COUNT} (N for companion empty-gate suite)"
        )
    if payload["purpose"] != PURPOSE:
        raise EmptyGateSuiteContractError(
            f"purpose must be {PURPOSE!r} (T4 empty_gate_refuse_ok)"
        )
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise EmptyGateSuiteContractError(
            "parent_observation_protocol must bind "
            f"{PARENT_OBSERVATION_PROTOCOL!r}"
        )
    if payload["suite_strategy"] != SUITE_STRATEGY:
        raise EmptyGateSuiteContractError(
            f"suite_strategy must be {SUITE_STRATEGY!r} (E-B8 primary)"
        )
    if payload["artifact_kind"] != ARTIFACT_KIND:
        raise EmptyGateSuiteContractError(
            f"artifact_kind must be {ARTIFACT_KIND!r} "
            "(schema example only; not formal measurement)"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for phrase in FORBIDDEN_NOTES_PHRASES:
            if phrase in notes:
                raise EmptyGateSuiteContractError(
                    f"forbidden phrase {phrase!r} appears in notes"
                )

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise EmptyGateSuiteContractError("cases must be an array")
    if len(cases) != CASE_COUNT:
        raise EmptyGateSuiteContractError(
            f"cases length must equal case_count={CASE_COUNT}; got {len(cases)}"
        )

    seen_case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise EmptyGateSuiteContractError(f"$.cases[{index}] must be an object")
        _validate_case(case, f"$.cases[{index}]")
        cid = str(case["case_id"])
        if cid in seen_case_ids:
            raise EmptyGateSuiteContractError(f"duplicate case_id {cid!r}")
        seen_case_ids.add(cid)


def build_schema_example_suite() -> dict[str, Any]:
    """In-memory synthetic suite for deterministic tests only (not real cases)."""
    zh_query = "知识库里有没有从未收录的虚构加班政策编号 ZX-999？"
    en_query = "Is there any never-indexed fictional overtime policy code ZX-999?"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "suite_id": SUITE_ID,
        "case_count": CASE_COUNT,
        "purpose": PURPOSE,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "suite_strategy": SUITE_STRATEGY,
        "artifact_kind": ARTIFACT_KIND,
        "notes": "SCHEMA_EXAMPLE_NOT_REAL_CASES_NOT_FORMAL_MEASUREMENT",
        "cases": [
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
        ],
    }


def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_suite())


def load_schema_document() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        raise EmptyGateSuiteContractError(f"schema file missing: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_real_cases_file_present_and_valid() -> None:
    """REAL_ELIGIBLE cases file must exist and pass the cases contract validator."""
    from tests.w10_eb_empty_gate_cases_contract import (
        assert_real_cases_present_and_valid as _assert_cases,
    )

    _assert_cases()


def assert_formal_result_absent() -> None:
    """No formal empty-gate measurement artifact in this window."""
    if FORMAL_RESULT_PATH.exists():
        raise EmptyGateSuiteContractError(
            f"{FORMAL_RESULT_FILENAME} must remain absent "
            f"(found at {FORMAL_RESULT_PATH})"
        )


def assert_eb2_v1_identity_untouched() -> None:
    """Companion suite must not rewrite E-B2 v1 suite identity constants."""
    from tests.w10_eb2_generation_observation_contract import (
        FROZEN_CASE_COUNT,
        PROTOCOL_VERSION as EB2_PV,
        SUITE_ID as EB2_SUITE,
    )

    if EB2_SUITE != W9_CRITIC_SUITE_ID:
        raise EmptyGateSuiteContractError(
            f"E-B2 SUITE_ID drifted: expected {W9_CRITIC_SUITE_ID!r}, got {EB2_SUITE!r}"
        )
    if FROZEN_CASE_COUNT != EB2_FROZEN_CASE_COUNT:
        raise EmptyGateSuiteContractError(
            f"E-B2 FROZEN_CASE_COUNT drifted: expected {EB2_FROZEN_CASE_COUNT}, "
            f"got {FROZEN_CASE_COUNT}"
        )
    if EB2_PV != EB2_PROTOCOL_VERSION:
        raise EmptyGateSuiteContractError(
            f"E-B2 PROTOCOL_VERSION drifted: expected {EB2_PROTOCOL_VERSION!r}, "
            f"got {EB2_PV!r}"
        )
    if SUITE_ID == EB2_SUITE:
        raise EmptyGateSuiteContractError(
            "empty-gate suite_id must stay distinct from E-B2 / W9 Critic suite"
        )


def assert_refusal_gold_mirrors_product() -> None:
    """Bind mirrored refusal strings to product generation.py authority."""
    import importlib

    gen = importlib.import_module("app.services.rag.generation")
    if REFUSAL_GOLD_ZH != gen.NO_CONTEXT_REPLY:
        raise EmptyGateSuiteContractError(
            "REFUSAL_GOLD_ZH drifted from product NO_CONTEXT_REPLY"
        )
    if REFUSAL_GOLD_EN != gen.NO_CONTEXT_REPLY_EN:
        raise EmptyGateSuiteContractError(
            "REFUSAL_GOLD_EN drifted from product NO_CONTEXT_REPLY_EN"
        )
    sample_zh = "加班政策编号是什么？"
    sample_en = "What is the overtime policy code?"
    if expected_no_context_reply_for(sample_zh) != gen.no_context_reply_for(sample_zh):
        raise EmptyGateSuiteContractError(
            "expected_no_context_reply_for ZH band drifted from product"
        )
    if expected_no_context_reply_for(sample_en) != gen.no_context_reply_for(sample_en):
        raise EmptyGateSuiteContractError(
            "expected_no_context_reply_for EN band drifted from product"
        )


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no LLM / Critic harness / observation executor hooks."""
    import ast
    import inspect

    import tests.w10_eb_empty_gate_suite_contract as self_mod

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
            # Top-level must not import generation / LLM clients; product
            # mirror checks are lazy-imported inside assert helpers only.
            if mod.startswith("app.services.rag.generation"):
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

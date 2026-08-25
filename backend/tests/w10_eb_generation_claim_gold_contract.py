"""W10 E-B9a — Claim gold ledger schema + test-only validator.

Independent T2/T3 claim gold artifact contract.
Does not: create annotated gold, call LLM / LM Studio, run generation,
write formal observation, clear E-B_FORMAL_READY, or touch backend/app.
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

PROTOCOL_VERSION = "w10_eb_generation_claim_gold_v1"
PARENT_OBSERVATION_PROTOCOL = "w10_eb1_generation_observation_v1"
ARTIFACT_KIND = "CLAIM_GOLD_LEDGER"
E_B_FORMAL_READY = "NO"

SCHEMA_FILENAME = "w10-eb-generation-claim-gold-v1.schema.json"
GOLD_FILENAME = "w10-eb-generation-claim-gold-v1.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
SCHEMA_PATH = FIXTURES / SCHEMA_FILENAME
GOLD_PATH = FIXTURES / GOLD_FILENAME

CONTENT_BINDING_KINDS = frozenset({"observed_after", "synthetic_authored"})
CLAIM_LABELS = frozenset({"supported", "unsupported", "unverifiable"})
DENOMINATOR_POLICY_REQUIRED_TOKEN = "exclude_refusal_boilerplate"

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")

HEADER_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "parent_observation_protocol",
    "artifact_kind",
    "created_by",
    "cases",
)

CASE_REQUIRED: tuple[str, ...] = (
    "case_id",
    "content_binding",
    "gated_pool_binding",
    "denominator_policy",
    "asserted_claims",
)

CLAIM_REQUIRED: tuple[str, ...] = (
    "claim_id",
    "text",
    "label",
    "supporting_evidence_ids",
    "support_span_notes",
)

CONTENT_BINDING_REQUIRED: tuple[str, ...] = ("kind", "content_sha256")
GATED_POOL_REQUIRED: tuple[str, ...] = ("evidence_ids",)

# Critic / E-A5 oracle keys (aligned with E-B2 freeze).
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

# LLM-as-judge / NLI auto-label keys (formal gold forbidden).
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

FORBIDDEN_KEYS: frozenset[str] = FORBIDDEN_CRITIC_ORACLE_KEYS | FORBIDDEN_LLM_JUDGE_KEYS

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
)

PLACEHOLDER_CONTENT_SHA256 = "a" * 64
PLACEHOLDER_EVIDENCE_ID = "ev-schema-example-1"


class ClaimGoldContractError(ValueError):
    """Raised when a candidate claim gold ledger violates the frozen contract."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ClaimGoldContractError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(
    mapping: Mapping[str, Any],
    path: str,
    *,
    label: str,
) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_KEYS)
    if present:
        raise ClaimGoldContractError(f"{label} fields present at {path}: {present}")


def _reject_forbidden_keys_recursive(node: Any, path: str) -> None:
    if isinstance(node, Mapping):
        _reject_forbidden_keys(node, path, label="forbidden claim-gold")
        for key, value in node.items():
            _reject_forbidden_keys_recursive(value, f"{path}.{key}")
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for index, item in enumerate(node):
            _reject_forbidden_keys_recursive(item, f"{path}[{index}]")


def _require_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ClaimGoldContractError(
            f"{path} must be a 64-char hex content hash (sha256 binding required)"
        )
    return value


def _validate_content_binding(binding: Mapping[str, Any], path: str) -> None:
    _require_keys(binding, CONTENT_BINDING_REQUIRED, path)
    kind = binding["kind"]
    if kind not in CONTENT_BINDING_KINDS:
        raise ClaimGoldContractError(
            f"{path}.kind must be one of {sorted(CONTENT_BINDING_KINDS)}"
        )
    _require_sha256(binding["content_sha256"], f"{path}.content_sha256")
    if "synthetic_body_id" in binding:
        body_id = binding["synthetic_body_id"]
        if body_id is not None and (not isinstance(body_id, str) or not body_id):
            raise ClaimGoldContractError(
                f"{path}.synthetic_body_id must be a non-empty string or null"
            )


def _validate_gated_pool(binding: Mapping[str, Any], path: str) -> set[str]:
    _require_keys(binding, GATED_POOL_REQUIRED, path)
    evidence_ids = binding["evidence_ids"]
    if not isinstance(evidence_ids, Sequence) or isinstance(
        evidence_ids, (str, bytes, bytearray)
    ):
        raise ClaimGoldContractError(f"{path}.evidence_ids must be an array")
    pool: set[str] = set()
    for index, eid in enumerate(evidence_ids):
        if not isinstance(eid, str) or not eid:
            raise ClaimGoldContractError(
                f"{path}.evidence_ids[{index}] must be a non-empty string"
            )
        if eid in pool:
            raise ClaimGoldContractError(
                f"{path}.evidence_ids contains duplicate {eid!r}"
            )
        pool.add(eid)
    if "pool_sha256" in binding and binding["pool_sha256"] is not None:
        _require_sha256(binding["pool_sha256"], f"{path}.pool_sha256")
    return pool


def _validate_claim(
    claim: Mapping[str, Any],
    path: str,
    *,
    gated_pool: set[str],
) -> None:
    _require_keys(claim, CLAIM_REQUIRED, path)
    _reject_forbidden_keys(claim, path, label="forbidden claim-row")

    claim_id = claim["claim_id"]
    if not isinstance(claim_id, str) or not claim_id:
        raise ClaimGoldContractError(f"{path}.claim_id must be a non-empty string")
    text = claim["text"]
    if not isinstance(text, str) or not text.strip():
        raise ClaimGoldContractError(f"{path}.text must be a non-empty string")

    label = claim["label"]
    if label not in CLAIM_LABELS:
        raise ClaimGoldContractError(
            f"{path}.label must be one of {sorted(CLAIM_LABELS)}"
        )

    support_notes = claim["support_span_notes"]
    if support_notes is not None and not isinstance(support_notes, str):
        raise ClaimGoldContractError(
            f"{path}.support_span_notes must be a string or null"
        )

    evidence_ids = claim["supporting_evidence_ids"]
    if not isinstance(evidence_ids, Sequence) or isinstance(
        evidence_ids, (str, bytes, bytearray)
    ):
        raise ClaimGoldContractError(f"{path}.supporting_evidence_ids must be an array")

    seen_support: set[str] = set()
    for index, eid in enumerate(evidence_ids):
        if not isinstance(eid, str) or not eid:
            raise ClaimGoldContractError(
                f"{path}.supporting_evidence_ids[{index}] must be a non-empty string"
            )
        if eid not in gated_pool:
            raise ClaimGoldContractError(
                f"{path}.supporting_evidence_ids[{index}]={eid!r} "
                f"not in declared gated pool"
            )
        if eid in seen_support:
            raise ClaimGoldContractError(
                f"{path}.supporting_evidence_ids contains duplicate {eid!r}"
            )
        seen_support.add(eid)

    if label == "supported" and not evidence_ids:
        raise ClaimGoldContractError(
            f"{path}: label=supported requires at least one supporting_evidence_ids entry"
        )

    if "label_source" in claim:
        raise ClaimGoldContractError(
            f"{path}: label_source is forbidden (lexical-only / LLM judge not formal gold)"
        )


def _validate_case(case: Mapping[str, Any], path: str) -> None:
    _require_keys(case, CASE_REQUIRED, path)
    _reject_forbidden_keys(case, path, label="forbidden case-level")

    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise ClaimGoldContractError(f"{path}.case_id must be a non-empty string")

    content_binding = case["content_binding"]
    if not isinstance(content_binding, Mapping):
        raise ClaimGoldContractError(f"{path}.content_binding must be an object")
    _validate_content_binding(content_binding, f"{path}.content_binding")

    gated_binding = case["gated_pool_binding"]
    if not isinstance(gated_binding, Mapping):
        raise ClaimGoldContractError(f"{path}.gated_pool_binding must be an object")
    gated_pool = _validate_gated_pool(gated_binding, f"{path}.gated_pool_binding")

    policy = case["denominator_policy"]
    if not isinstance(policy, str) or DENOMINATOR_POLICY_REQUIRED_TOKEN not in policy:
        raise ClaimGoldContractError(
            f"{path}.denominator_policy must include "
            f"{DENOMINATOR_POLICY_REQUIRED_TOKEN!r}"
        )

    claims = case["asserted_claims"]
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ClaimGoldContractError(f"{path}.asserted_claims must be an array")

    seen_claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise ClaimGoldContractError(f"{path}.asserted_claims[{index}] must be an object")
        _validate_claim(
            claim,
            f"{path}.asserted_claims[{index}]",
            gated_pool=gated_pool,
        )
        cid = str(claim["claim_id"])
        if cid in seen_claim_ids:
            raise ClaimGoldContractError(f"{path}: duplicate claim_id {cid!r}")
        seen_claim_ids.add(cid)


def validate_claim_gold_ledger(payload: Mapping[str, Any]) -> None:
    """Validate independent claim gold ledger structure and anti-oracle rules."""
    if not isinstance(payload, Mapping):
        raise ClaimGoldContractError("artifact must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise ClaimGoldContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise ClaimGoldContractError(
            "parent_observation_protocol must bind "
            f"{PARENT_OBSERVATION_PROTOCOL!r}"
        )
    if payload["artifact_kind"] != ARTIFACT_KIND:
        raise ClaimGoldContractError(f"artifact_kind must be {ARTIFACT_KIND!r}")

    created_by = payload["created_by"]
    if not isinstance(created_by, str) or not created_by.strip():
        raise ClaimGoldContractError("created_by must be a non-empty string")
    if created_by in FORBIDDEN_CREATED_BY:
        raise ClaimGoldContractError(
            f"created_by={created_by!r} is forbidden as formal gold authorship"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for phrase in FORBIDDEN_NOTES_PHRASES:
            if phrase in notes:
                raise ClaimGoldContractError(
                    f"forbidden phrase {phrase!r} appears in notes"
                )

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ClaimGoldContractError("cases must be an array")

    seen_case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ClaimGoldContractError(f"$.cases[{index}] must be an object")
        _validate_case(case, f"$.cases[{index}]")
        cid = str(case["case_id"])
        if cid in seen_case_ids:
            raise ClaimGoldContractError(f"duplicate case_id {cid!r}")
        seen_case_ids.add(cid)


def build_schema_example_ledger() -> dict[str, Any]:
    """In-memory synthetic ledger for deterministic tests only (not a gold file)."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "artifact_kind": ARTIFACT_KIND,
        "created_by": "schema_example_human_annotator",
        "notes": "SCHEMA_EXAMPLE_NOT_ANNOTATED_GOLD",
        "cases": [
            {
                "case_id": "SYN-schema-example-01",
                "content_binding": {
                    "kind": "synthetic_authored",
                    "content_sha256": PLACEHOLDER_CONTENT_SHA256,
                    "synthetic_body_id": "synthetic_body_schema_example_01",
                },
                "gated_pool_binding": {
                    "evidence_ids": [PLACEHOLDER_EVIDENCE_ID],
                    "pool_sha256": None,
                },
                "denominator_policy": DENOMINATOR_POLICY_REQUIRED_TOKEN,
                "asserted_claims": [
                    {
                        "claim_id": "SYN-schema-example-01::c01",
                        "text": "Example limit is 1000.",
                        "label": "supported",
                        "supporting_evidence_ids": [PLACEHOLDER_EVIDENCE_ID],
                        "support_span_notes": "excerpt states limit 1000",
                    },
                    {
                        "claim_id": "SYN-schema-example-01::c02",
                        "text": "Example limit is 9999.",
                        "label": "unsupported",
                        "supporting_evidence_ids": [],
                        "support_span_notes": None,
                    },
                    {
                        "claim_id": "SYN-schema-example-01::c03",
                        "text": "Example policy tone is friendly.",
                        "label": "unverifiable",
                        "supporting_evidence_ids": [],
                        "support_span_notes": None,
                    },
                ],
            }
        ],
    }


def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_ledger())


def load_schema_document() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        raise ClaimGoldContractError(f"schema file missing: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_gold_file_absent() -> None:
    """Legacy E-B9a prep guard — annotated gold may now exist (E-B12B+).

    Prefer ``load_claim_gold_if_present`` / materialization loaders for current
    windows. Kept for callers that still need an explicit absence check.
    """
    if GOLD_PATH.exists():
        raise ClaimGoldContractError(
            f"{GOLD_FILENAME} is present at {GOLD_PATH} "
            "(absence required only for pre-annotation prep windows)"
        )


def load_claim_gold_if_present() -> dict[str, Any] | None:
    """Load and validate on-disk claim gold when present; else return None."""
    if not GOLD_PATH.is_file():
        return None
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ClaimGoldContractError(f"{GOLD_FILENAME} must be a JSON object")
    validate_claim_gold_ledger(payload)
    return dict(payload)


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no product LLM / Critic harness hooks."""
    import ast
    import inspect

    import tests.w10_eb_generation_claim_gold_contract as self_mod

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
    ):
        if hasattr(self_mod, banned_attr):
            return False
    return True

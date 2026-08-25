"""W10 E-B2 — Generation observation reserved artifact contract.

Freezes the future generation-final observation envelope:
schema, runner identity, claim boundary, separation from E-A5 / P2-R3 / Critic.

E-B2 freeze: validators + schema examples only.
Does not call product LLMs, does not execute generation, does not write a
formal observation result, does not unblock P2-R1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Frozen identity constants (asserted by tests)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "w10_eb2_generation_observation_v1"
ARTIFACT_SCHEMA_VERSION = "w10-eb2-generation-observation-v1"
SUITE_ID = "w9_critic_frozen_12"
RUNNER_ID = "w10_eb2_generation_observation_runner"
RUNNER_MODULE = "tests.w10_eb2_generation_observation_contract"
ELIGIBILITY_PROTOCOL_ID = "w10_ea1_scope_eligibility"
PARENT_PROTOCOL_ID = "w10_eb1_generation_observation_v1"
OBSERVATION_POINT = "generation_final_content_and_citations"
P2_R1_STATUS_BLOCKED = "BLOCKED"
C12_CASE_ID = "C12-out-of-scope-provenance"
CLASSIFICATION_INVALID = "INVALID_FOR_PRODUCT_PATH_EXECUTION"

FROZEN_CASE_COUNT = 12
PRODUCT_PATH_ELIGIBLE_EXPECTED = 11
INVALID_EXPECTED = 1

RESERVED_RESULT_FILENAME = "w10-eb2-generation-observation-result.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
RESERVED_RESULT_PATH = FIXTURES / RESERVED_RESULT_FILENAME
EA5_RESULT_FILENAME = "w10-ea4-formal-window-result.json"
EA5_RESULT_PATH = FIXTURES / EA5_RESULT_FILENAME

ARTIFACT_KIND_SCHEMA_EXAMPLE = "SCHEMA_EXAMPLE_NOT_A_RUN"
ARTIFACT_KIND_FORMAL_OBS = "FORMAL_OBSERVATION_RESULT"
ARTIFACT_KINDS = frozenset({ARTIFACT_KIND_SCHEMA_EXAMPLE, ARTIFACT_KIND_FORMAL_OBS})

ALLOWED_CLAIM = "generation observation artifact produced"
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "generation quality proven",
    "grounding proven",
    "Critic validated",
)

FORBIDDEN_RUNNER_IDS: frozenset[str] = frozenset(
    {
        "execute_frozen_case",
        "w9_critic_p2_r1_harness",
        "w9_critic_p2_r1_harness.execute_frozen_case",
        "w9_critic_p2_r3_formal_runner",
        "w9_critic_p2_r3_batch_runner",
        "FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN",
        "w9_critic_p2_r3_formal_product_rerun_v1",
        "w10_ea4_formal_window_runner",
    }
)

# Foreign envelope / Critic oracle keys that must never appear on E-B2 artifacts.
FORBIDDEN_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
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
    }
)

FORBIDDEN_PER_CASE_KEYS: frozenset[str] = frozenset(
    {
        "scorer_observation_point",
        "scope_compliance_pass",
        "expected_action",
        "oracle_cases",
        "oracle_case",
        "critic_score",
        "critic_capability",
        "capability_label",
        "w9_critic_oracle",
        "critic_actions",
    }
)

EA5_ARTIFACT_SCHEMA_VERSION = "w10-ea4-formal-window-v1"
EA5_OBSERVATION_POINT = "plan_construction_citations"
EA5_PROTOCOL_VERSION = "1.0.0"

STATUS_NOT_OBSERVED = "NOT_OBSERVED"
STATUS_OBSERVED_SLOT = "OBSERVED_SLOT"
STATUS_INELIGIBLE = "INELIGIBLE"
OBSERVATION_STATUS_VALUES = frozenset(
    {STATUS_NOT_OBSERVED, STATUS_OBSERVED_SLOT, STATUS_INELIGIBLE}
)

INVALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN",
        "WRONG_RUNNER_IDENTITY",
        "RUNNER_SUBSTITUTION_P2_R1",
        "RUNNER_SUBSTITUTION_P2_R3",
        "EA5_ARTIFACT_REUSE",
        "P2_R3_ARTIFACT_REUSE",
        "CRITIC_ORACLE_FIELDS_PRESENT",
        "ELIGIBILITY_NOT_BOUND_TO_EA1",
        "OBSERVATION_POINT_MISLABEL",
        "FORBIDDEN_CLAIM_PRESENT",
        "P2_R1_UNBLOCK_ASSERTED",
        "INCOMPLETE_SUITE",
        "OTHER_PROTOCOL_BREAK",
    }
)

TOP_LEVEL_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_schema_version",
    "run_id",
    "base_sha",
    "suite_id",
    "case_count",
    "runner_id",
    "runner_module",
    "eligibility_protocol_id",
    "parent_protocol_id",
    "eligibility_summary",
    "per_case_observation",
    "measurement_validity",
    "measurement_claims",
    "p2_r1_status",
    "does_not_unblock_p2_r1",
    "observation_point",
    "artifact_kind",
)

ELIGIBILITY_SUMMARY_REQUIRED: tuple[str, ...] = (
    "frozen_cases",
    "product_path_eligible",
    "invalid_for_product_path",
    "c12_in_denominator",
    "invalid_case_ids",
    "targets_measured",
)

PER_CASE_REQUIRED: tuple[str, ...] = (
    "case_id",
    "eligibility",
    "classification",
    "input_hash",
    "gen_plan_reference",
    "final_content_observation",
    "final_citations",
    "scope_compliance_result",
    "grounding_observation_status",
    "refusal_observation_status",
)

MEASUREMENT_VALIDITY_REQUIRED: tuple[str, ...] = (
    "measurement_valid",
    "invalid_reasons",
    "structurally_schema_ok",
    "observation_point_honest",
    "ea5_artifact_not_reused",
    "p2_r3_artifact_not_reused",
    "critic_oracle_fields_absent",
    "p2_r1_remains_blocked",
    "llm_called",
)

PLACEHOLDER_SHA = "0" * 40
PLACEHOLDER_INPUT_HASH = "schema_example_input_hash_not_a_run"

_SCHEMA_EXAMPLE_CASE_IDS: tuple[str, ...] = (
    "C01-fully-supported-exact",
    "C02-supported-paraphrase-low-lexical",
    "C03-one-unsupported-among-supported",
    "C04-valid-citation-wrong-evidence",
    "C05-known-conflict-overcertain",
    "C06-required-fact-missing",
    "C07-correct-insufficiency-refusal",
    "C08-nonassertive-preface-supported-fact",
    "C09-supported-plus-unverifiable",
    "C10-supported-multiclaim-multicitation",
    "C11-citation-format-only-defect",
    C12_CASE_ID,
)


class GenerationObservationContractError(ValueError):
    """Raised when a candidate E-B2 reserved artifact violates the frozen contract."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise GenerationObservationContractError(f"{path} missing fields: {missing}")


def _is_forbidden_runner_token(value: str) -> bool:
    if value in FORBIDDEN_RUNNER_IDS:
        return True
    lowered = value.lower()
    if "execute_frozen_case" in lowered:
        return True
    if "w9_critic_p2_r3" in lowered:
        return True
    if "w9_critic_p2_r1_harness" in lowered:
        return True
    if "w10_ea4_formal_window" in lowered:
        return True
    return False


def _reject_forbidden_keys(
    mapping: Mapping[str, Any],
    forbidden: frozenset[str],
    path: str,
    *,
    label: str,
) -> None:
    present = sorted(key for key in mapping if key in forbidden)
    if present:
        raise GenerationObservationContractError(
            f"{label} fields present at {path}: {present}"
        )


def _validate_claims(claims: Mapping[str, Any], path: str) -> None:
    _require_keys(claims, ("allowed", "asserted", "forbidden_rejected"), path)
    allowed = claims["allowed"]
    asserted = claims["asserted"]
    forbidden_rejected = claims["forbidden_rejected"]
    if not isinstance(allowed, list) or allowed != [ALLOWED_CLAIM]:
        raise GenerationObservationContractError(
            f"{path}.allowed must be exactly [{ALLOWED_CLAIM!r}]"
        )
    if not isinstance(forbidden_rejected, list) or list(forbidden_rejected) != list(
        FORBIDDEN_CLAIMS
    ):
        raise GenerationObservationContractError(
            f"{path}.forbidden_rejected must lock the three forbidden claim strings"
        )
    if not isinstance(asserted, list):
        raise GenerationObservationContractError(f"{path}.asserted must be an array")
    for item in asserted:
        if not isinstance(item, str):
            raise GenerationObservationContractError(f"{path}.asserted items must be strings")
        if item in FORBIDDEN_CLAIMS:
            raise GenerationObservationContractError(
                f"forbidden measurement claim {item!r} at {path}.asserted"
            )
        if item not in allowed:
            raise GenerationObservationContractError(
                f"asserted claim {item!r} not in allowed set at {path}"
            )


def _validate_eligibility_summary(summary: Mapping[str, Any], path: str) -> None:
    _require_keys(summary, ELIGIBILITY_SUMMARY_REQUIRED, path)
    if summary["frozen_cases"] != FROZEN_CASE_COUNT:
        raise GenerationObservationContractError(
            f"{path}.frozen_cases must be {FROZEN_CASE_COUNT}"
        )
    if summary["product_path_eligible"] != PRODUCT_PATH_ELIGIBLE_EXPECTED:
        raise GenerationObservationContractError(
            f"{path}.product_path_eligible must be {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )
    if summary["invalid_for_product_path"] != INVALID_EXPECTED:
        raise GenerationObservationContractError(
            f"{path}.invalid_for_product_path must be {INVALID_EXPECTED}"
        )
    if summary["c12_in_denominator"] is not False:
        raise GenerationObservationContractError(f"{path}.c12_in_denominator must be false")
    invalid_ids = summary["invalid_case_ids"]
    if not isinstance(invalid_ids, list) or C12_CASE_ID not in invalid_ids:
        raise GenerationObservationContractError(
            f"{path}.invalid_case_ids must include {C12_CASE_ID!r}"
        )
    targets = summary["targets_measured"]
    if not isinstance(targets, list):
        raise GenerationObservationContractError(f"{path}.targets_measured must be an array")


def _validate_per_case(case: Mapping[str, Any], path: str) -> None:
    _require_keys(case, PER_CASE_REQUIRED, path)
    _reject_forbidden_keys(
        case, FORBIDDEN_PER_CASE_KEYS, path, label="critic/E-A5 per-case"
    )
    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise GenerationObservationContractError(f"{path}.case_id must be a non-empty string")
    input_hash = case["input_hash"]
    if not isinstance(input_hash, str) or not input_hash:
        raise GenerationObservationContractError(f"{path}.input_hash must be a non-empty string")
    if case["eligibility"] is not True and case["eligibility"] is not False:
        raise GenerationObservationContractError(f"{path}.eligibility must be boolean")
    for status_key in ("grounding_observation_status", "refusal_observation_status"):
        status = case[status_key]
        if status not in OBSERVATION_STATUS_VALUES:
            raise GenerationObservationContractError(
                f"{path}.{status_key} must be one of {sorted(OBSERVATION_STATUS_VALUES)}"
            )
    if case_id == C12_CASE_ID:
        if case["eligibility"] is not False:
            raise GenerationObservationContractError(f"{path}: C12 must be eligibility=false")
        if case["classification"] != CLASSIFICATION_INVALID:
            raise GenerationObservationContractError(
                f"{path}: C12 classification must be {CLASSIFICATION_INVALID!r}"
            )
        if case["grounding_observation_status"] != STATUS_INELIGIBLE:
            raise GenerationObservationContractError(
                f"{path}: C12 grounding_observation_status must be INELIGIBLE"
            )
        if case["refusal_observation_status"] != STATUS_INELIGIBLE:
            raise GenerationObservationContractError(
                f"{path}: C12 refusal_observation_status must be INELIGIBLE"
            )


def _validate_measurement_validity(
    validity: Mapping[str, Any],
    *,
    artifact_kind: str,
    path: str,
) -> None:
    _require_keys(validity, MEASUREMENT_VALIDITY_REQUIRED, path)
    measurement_valid = validity["measurement_valid"]
    if not isinstance(measurement_valid, bool):
        raise GenerationObservationContractError(f"{path}.measurement_valid must be boolean")
    reasons = validity["invalid_reasons"]
    if not isinstance(reasons, list):
        raise GenerationObservationContractError(f"{path}.invalid_reasons must be an array")
    for reason in reasons:
        if reason not in INVALID_REASON_CODES:
            raise GenerationObservationContractError(
                f"{path}.invalid_reasons contains unknown code {reason!r}"
            )
    for flag in (
        "structurally_schema_ok",
        "observation_point_honest",
        "ea5_artifact_not_reused",
        "p2_r3_artifact_not_reused",
        "critic_oracle_fields_absent",
        "p2_r1_remains_blocked",
    ):
        if validity[flag] is not True:
            raise GenerationObservationContractError(f"{path}.{flag} must be true")
    if validity["llm_called"] is not False:
        raise GenerationObservationContractError(f"{path}.llm_called must be false in E-B2 freeze")

    if artifact_kind == ARTIFACT_KIND_SCHEMA_EXAMPLE:
        if measurement_valid is not False:
            raise GenerationObservationContractError(
                f"{path}: SCHEMA_EXAMPLE_NOT_A_RUN requires measurement_valid=false"
            )
        if "SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN" not in reasons:
            raise GenerationObservationContractError(
                f"{path}: schema examples must include SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN"
            )

    if measurement_valid is True:
        if artifact_kind != ARTIFACT_KIND_FORMAL_OBS:
            raise GenerationObservationContractError(
                f"{path}: measurement_valid=true requires "
                f"artifact_kind={ARTIFACT_KIND_FORMAL_OBS}"
            )
        if reasons:
            raise GenerationObservationContractError(
                f"{path}: measurement_valid=true requires empty invalid_reasons"
            )
    else:
        if not reasons:
            raise GenerationObservationContractError(
                f"{path}: measurement_valid=false requires non-empty invalid_reasons"
            )


def _detect_ea5_reuse_signals(payload: Mapping[str, Any]) -> None:
    if payload.get("artifact_schema_version") == EA5_ARTIFACT_SCHEMA_VERSION:
        raise GenerationObservationContractError(
            "E-A5 artifact reuse: artifact_schema_version is w10-ea4-formal-window-v1"
        )
    if payload.get("observation_point") == EA5_OBSERVATION_POINT:
        raise GenerationObservationContractError(
            "E-A5 artifact reuse: observation_point is plan_construction_citations"
        )
    if (
        payload.get("protocol_version") == EA5_PROTOCOL_VERSION
        and payload.get("runner_id") == "w10_ea4_formal_window_runner"
    ):
        raise GenerationObservationContractError(
            "E-A5 artifact reuse: E-A4/E-A5 protocol_version+runner_id pairing"
        )


def validate_reserved_artifact(payload: Mapping[str, Any]) -> None:
    """Validate structural contract + identity + claim boundary + separation.

    A structurally valid SCHEMA_EXAMPLE still has measurement_valid=false.
    """
    if not isinstance(payload, Mapping):
        raise GenerationObservationContractError("artifact must be a JSON object")
    _reject_forbidden_keys(
        payload, FORBIDDEN_TOP_LEVEL_KEYS, "$", label="critic/E-A5 top-level"
    )
    _detect_ea5_reuse_signals(payload)
    _require_keys(payload, TOP_LEVEL_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise GenerationObservationContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise GenerationObservationContractError("artifact_schema_version mismatch")
    if payload["suite_id"] != SUITE_ID:
        raise GenerationObservationContractError("suite_id mismatch")
    if payload["case_count"] != FROZEN_CASE_COUNT:
        raise GenerationObservationContractError("case_count must be 12")
    if payload["eligibility_protocol_id"] != ELIGIBILITY_PROTOCOL_ID:
        raise GenerationObservationContractError("eligibility_protocol_id must bind E-A1")
    if payload["parent_protocol_id"] != PARENT_PROTOCOL_ID:
        raise GenerationObservationContractError("parent_protocol_id must bind E-B1")
    if payload["observation_point"] != OBSERVATION_POINT:
        raise GenerationObservationContractError(
            "observation_point must be generation_final_content_and_citations"
        )
    if payload["p2_r1_status"] != P2_R1_STATUS_BLOCKED:
        raise GenerationObservationContractError("p2_r1_status must remain BLOCKED")
    if payload["does_not_unblock_p2_r1"] is not True:
        raise GenerationObservationContractError("does_not_unblock_p2_r1 must be true")

    run_id = payload["run_id"]
    if not isinstance(run_id, str) or not run_id:
        raise GenerationObservationContractError("run_id must be a non-empty string")
    base_sha = payload["base_sha"]
    if not isinstance(base_sha, str) or len(base_sha) < 7:
        raise GenerationObservationContractError("base_sha must be a git SHA string (len>=7)")

    runner_id = payload["runner_id"]
    runner_module = payload["runner_module"]
    if not isinstance(runner_id, str) or not isinstance(runner_module, str):
        raise GenerationObservationContractError("runner_id/runner_module must be strings")
    if _is_forbidden_runner_token(runner_id) or _is_forbidden_runner_token(runner_module):
        raise GenerationObservationContractError(
            "wrong runner identity: E-A5 / P2-R1 / P2-R3 substitution forbidden"
        )
    if runner_id != RUNNER_ID:
        raise GenerationObservationContractError(f"runner_id must be {RUNNER_ID!r}")
    if runner_module != RUNNER_MODULE:
        raise GenerationObservationContractError(f"runner_module must be {RUNNER_MODULE!r}")

    artifact_kind = payload["artifact_kind"]
    if artifact_kind not in ARTIFACT_KINDS:
        raise GenerationObservationContractError(f"artifact_kind invalid: {artifact_kind!r}")
    if artifact_kind == ARTIFACT_KIND_SCHEMA_EXAMPLE and not run_id.startswith(
        "SCHEMA_EXAMPLE_"
    ):
        raise GenerationObservationContractError(
            "SCHEMA_EXAMPLE_NOT_A_RUN run_id must start with SCHEMA_EXAMPLE_"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for claim in FORBIDDEN_CLAIMS:
            if claim in notes:
                raise GenerationObservationContractError(
                    f"forbidden measurement claim {claim!r} appears in notes"
                )

    eligibility_summary = payload["eligibility_summary"]
    if not isinstance(eligibility_summary, Mapping):
        raise GenerationObservationContractError("eligibility_summary must be an object")
    _validate_eligibility_summary(eligibility_summary, "$.eligibility_summary")

    claims = payload["measurement_claims"]
    if not isinstance(claims, Mapping):
        raise GenerationObservationContractError("measurement_claims must be an object")
    _validate_claims(claims, "$.measurement_claims")

    cases = payload["per_case_observation"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise GenerationObservationContractError("per_case_observation must be an array")
    if len(cases) != FROZEN_CASE_COUNT:
        raise GenerationObservationContractError(
            "per_case_observation length must equal case_count (12)"
        )
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise GenerationObservationContractError(
                f"$.per_case_observation[{index}] must be an object"
            )
        _validate_per_case(case, f"$.per_case_observation[{index}]")
        cid = str(case["case_id"])
        if cid in seen:
            raise GenerationObservationContractError(f"duplicate case_id {cid!r}")
        seen.add(cid)
    if C12_CASE_ID not in seen:
        raise GenerationObservationContractError("per_case_observation must include C12")

    validity = payload["measurement_validity"]
    if not isinstance(validity, Mapping):
        raise GenerationObservationContractError("measurement_validity must be an object")
    _validate_measurement_validity(
        validity, artifact_kind=str(artifact_kind), path="$.measurement_validity"
    )


def build_schema_example_artifact() -> dict[str, Any]:
    """Minimal reserved-shape payload clearly marked as NOT a formal observation."""
    cases: list[dict[str, Any]] = []
    for case_id in _SCHEMA_EXAMPLE_CASE_IDS:
        if case_id == C12_CASE_ID:
            cases.append(
                {
                    "case_id": case_id,
                    "eligibility": False,
                    "classification": CLASSIFICATION_INVALID,
                    "input_hash": PLACEHOLDER_INPUT_HASH,
                    "gen_plan_reference": None,
                    "final_content_observation": None,
                    "final_citations": None,
                    "scope_compliance_result": None,
                    "grounding_observation_status": STATUS_INELIGIBLE,
                    "refusal_observation_status": STATUS_INELIGIBLE,
                }
            )
        else:
            cases.append(
                {
                    "case_id": case_id,
                    "eligibility": True,
                    "classification": None,
                    "input_hash": PLACEHOLDER_INPUT_HASH,
                    "gen_plan_reference": None,
                    "final_content_observation": None,
                    "final_citations": None,
                    "scope_compliance_result": None,
                    "grounding_observation_status": STATUS_NOT_OBSERVED,
                    "refusal_observation_status": STATUS_NOT_OBSERVED,
                }
            )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": "SCHEMA_EXAMPLE_eb2_contract_freeze_not_a_run",
        "base_sha": PLACEHOLDER_SHA,
        "suite_id": SUITE_ID,
        "case_count": FROZEN_CASE_COUNT,
        "runner_id": RUNNER_ID,
        "runner_module": RUNNER_MODULE,
        "eligibility_protocol_id": ELIGIBILITY_PROTOCOL_ID,
        "parent_protocol_id": PARENT_PROTOCOL_ID,
        "eligibility_summary": {
            "frozen_cases": FROZEN_CASE_COUNT,
            "product_path_eligible": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "invalid_for_product_path": INVALID_EXPECTED,
            "c12_in_denominator": False,
            "invalid_case_ids": [C12_CASE_ID],
            "targets_measured": [],
        },
        "per_case_observation": cases,
        "measurement_validity": {
            "measurement_valid": False,
            "invalid_reasons": ["SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN"],
            "structurally_schema_ok": True,
            "observation_point_honest": True,
            "ea5_artifact_not_reused": True,
            "p2_r3_artifact_not_reused": True,
            "critic_oracle_fields_absent": True,
            "p2_r1_remains_blocked": True,
            "llm_called": False,
        },
        "measurement_claims": {
            "allowed": [ALLOWED_CLAIM],
            "asserted": [ALLOWED_CLAIM],
            "forbidden_rejected": list(FORBIDDEN_CLAIMS),
        },
        "p2_r1_status": P2_R1_STATUS_BLOCKED,
        "does_not_unblock_p2_r1": True,
        "observation_point": OBSERVATION_POINT,
        "artifact_kind": ARTIFACT_KIND_SCHEMA_EXAMPLE,
        "parent_l0_artifact": EA5_RESULT_FILENAME,
        "notes": "E-B2 schema example only; not a formal generation observation result.",
    }


def assert_reserved_result_absent() -> None:
    if RESERVED_RESULT_PATH.exists():
        raise GenerationObservationContractError(
            f"reserved result {RESERVED_RESULT_FILENAME} must not exist during E-B2"
        )


def contract_module_imports_are_llm_free() -> bool:
    """Sanity helper: AST-check that this module does not import LLM/inject stacks."""
    import ast

    from tests import w10_eb2_generation_observation_contract as self_mod

    tree = ast.parse(Path(self_mod.__file__).read_text(encoding="utf-8"))
    banned_roots = {
        "openai",
        "litellm",
        "dashscope",
        "lm_studio",
        "anthropic",
    }
    banned_modules = {
        "tests.w9_critic_p2_r1_harness",
        "tests.w9_critic_p2_r3_formal_runner",
        "tests.w9_critic_p2_r3_batch_runner",
        "tests.w10_ea4_formal_window_contract",
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
            if any(alias.name == "execute_frozen_case" for alias in node.names):
                return False
            if any(alias.name == "run_formal_window" for alias in node.names):
                return False
    if hasattr(self_mod, "execute_frozen_case"):
        return False
    if hasattr(self_mod, "run_formal_window"):
        return False
    return True


def json_schema_document() -> dict[str, Any]:
    """JSON Schema (draft-07 style) mirror of the frozen contract for docs/tests."""
    return {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "$id": "w10-eb2-generation-observation-contract.schema.json",
        "title": "W10 E-B2 generation observation reserved artifact (schema freeze only)",
        "description": (
            "Contract for future reserved file w10-eb2-generation-observation-result.json. "
            "This schema document is not a formal observation result. "
            "Allowed claim: generation observation artifact produced. "
            "Forbidden: generation quality proven; grounding proven; Critic validated."
        ),
        "type": "object",
        "required": list(TOP_LEVEL_REQUIRED),
        "properties": {
            "protocol_version": {"type": "string", "const": PROTOCOL_VERSION},
            "artifact_schema_version": {
                "type": "string",
                "const": ARTIFACT_SCHEMA_VERSION,
            },
            "run_id": {"type": "string", "minLength": 1},
            "base_sha": {"type": "string", "minLength": 7},
            "suite_id": {"type": "string", "const": SUITE_ID},
            "case_count": {"type": "integer", "const": FROZEN_CASE_COUNT},
            "runner_id": {"type": "string", "const": RUNNER_ID},
            "runner_module": {"type": "string", "const": RUNNER_MODULE},
            "eligibility_protocol_id": {
                "type": "string",
                "const": ELIGIBILITY_PROTOCOL_ID,
            },
            "parent_protocol_id": {"type": "string", "const": PARENT_PROTOCOL_ID},
            "observation_point": {"type": "string", "const": OBSERVATION_POINT},
            "p2_r1_status": {"type": "string", "const": P2_R1_STATUS_BLOCKED},
            "does_not_unblock_p2_r1": {"type": "boolean", "const": True},
            "artifact_kind": {
                "type": "string",
                "enum": sorted(ARTIFACT_KINDS),
            },
            "eligibility_summary": {"type": "object"},
            "per_case_observation": {
                "type": "array",
                "minItems": FROZEN_CASE_COUNT,
                "maxItems": FROZEN_CASE_COUNT,
            },
            "measurement_validity": {"type": "object"},
            "measurement_claims": {"type": "object"},
            "parent_l0_artifact": {"type": ["string", "null"]},
            "timestamp": {"type": "string"},
            "notes": {"type": "string"},
        },
    }


def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_artifact())

"""W10 E-A4 — Formal window reserved artifact contract.

Freezes the narrow E-A2 formal evaluation *window* envelope:
schema, runner identity, claim boundary, measurement_validity rules.

E-A4 freeze: validators + schema examples only.
E-A5 execution: `run_formal_window` / `write_formal_window_result` write the
reserved FORMAL_RUN_RESULT via E-A2 only (same runner_id / runner_module).

Does not call product LLMs, does not import P2-R1 execute_frozen_case as an
entry, does not unblock P2-R1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Frozen identity constants (asserted by tests)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "1.0.0"
ARTIFACT_SCHEMA_VERSION = "w10-ea4-formal-window-v1"
SUITE_ID = "w9_critic_frozen_12"
RUNNER_ID = "w10_ea4_formal_window_runner"
RUNNER_MODULE = "tests.w10_ea4_formal_window_contract"
ADAPTER_PROTOCOL_VERSION = "w10_ea2_scope_eligibility_v1"
ELIGIBILITY_PROTOCOL_ID = "w10_ea1_scope_eligibility"
OBSERVATION_POINT = "plan_construction_citations"
P2_R1_STATUS_BLOCKED = "BLOCKED"
C12_CASE_ID = "C12-out-of-scope-provenance"
CLASSIFICATION_INVALID = "INVALID_FOR_PRODUCT_PATH_EXECUTION"

FROZEN_CASE_COUNT = 12
PRODUCT_PATH_ELIGIBLE_EXPECTED = 11
INVALID_EXPECTED = 1

RESERVED_RESULT_FILENAME = "w10-ea4-formal-window-result.json"
# Reserved result must never be written by E-A4. Path is under fixtures for
# future formal-run discipline only (assert absence).
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
RESERVED_RESULT_PATH = FIXTURES / RESERVED_RESULT_FILENAME

ARTIFACT_KIND_SCHEMA_EXAMPLE = "SCHEMA_EXAMPLE_NOT_A_RUN"
ARTIFACT_KIND_FORMAL_RUN = "FORMAL_RUN_RESULT"
ARTIFACT_KINDS = frozenset({ARTIFACT_KIND_SCHEMA_EXAMPLE, ARTIFACT_KIND_FORMAL_RUN})

ALLOWED_CLAIM = "plan-construction citation scope compliance"
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "generation-final safety",
    "Critic oracle capability",
    "P2-R1 unblocked",
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
    }
)

EXECUTOR_PATH_ALLOWLIST: frozenset[str] = frozenset(
    {
        "agent_tool_scope+prepare_agent_generation",
        "refused_ineligible",
        "not_executed_schema_example",
    }
)

INVALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN",
        "WRONG_RUNNER_IDENTITY",
        "RUNNER_SUBSTITUTION_P2_R1",
        "RUNNER_SUBSTITUTION_P2_R3",
        "ELIGIBILITY_NOT_BOUND_TO_EA1",
        "ADAPTER_NOT_BOUND_TO_EA2",
        "INELIGIBLE_CASE_IN_DENOMINATOR",
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
    "adapter_protocol_version",
    "eligibility_protocol_id",
    "eligibility_summary",
    "per_case_result",
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
    "denominator_case_count",
    "classification_vocabulary",
)

PER_CASE_REQUIRED: tuple[str, ...] = (
    "case_id",
    "product_path_eligible",
    "classification",
    "executor_path",
    "in_pass_rate_denominator",
    "scorer_observation_point",
)

MEASUREMENT_VALIDITY_REQUIRED: tuple[str, ...] = (
    "measurement_valid",
    "invalid_reasons",
    "structurally_schema_ok",
    "runner_identity_ok",
    "eligibility_bound_to_ea1",
    "adapter_bound_to_ea2",
    "observation_point_honest",
    "p2_r1_remains_blocked",
)

PLACEHOLDER_SHA = "0" * 40

# Frozen W9 critic suite case ids (schema example slots only — not a formal run).
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


class FormalWindowContractError(ValueError):
    """Raised when a candidate E-A4 reserved artifact violates the frozen contract."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise FormalWindowContractError(f"{path} missing fields: {missing}")


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
    return False


def _validate_claims(claims: Mapping[str, Any], path: str) -> None:
    _require_keys(claims, ("allowed", "asserted", "forbidden_rejected"), path)
    allowed = claims["allowed"]
    asserted = claims["asserted"]
    forbidden_rejected = claims["forbidden_rejected"]
    if not isinstance(allowed, list) or allowed != [ALLOWED_CLAIM]:
        raise FormalWindowContractError(f"{path}.allowed must be exactly [{ALLOWED_CLAIM!r}]")
    if not isinstance(forbidden_rejected, list) or list(forbidden_rejected) != list(
        FORBIDDEN_CLAIMS
    ):
        raise FormalWindowContractError(
            f"{path}.forbidden_rejected must lock the three forbidden claim strings"
        )
    if not isinstance(asserted, list):
        raise FormalWindowContractError(f"{path}.asserted must be an array")
    for item in asserted:
        if not isinstance(item, str):
            raise FormalWindowContractError(f"{path}.asserted items must be strings")
        if item in FORBIDDEN_CLAIMS:
            raise FormalWindowContractError(
                f"forbidden measurement claim {item!r} at {path}.asserted"
            )
        if item not in allowed:
            raise FormalWindowContractError(
                f"asserted claim {item!r} not in allowed set at {path}"
            )


def _validate_eligibility_summary(summary: Mapping[str, Any], path: str) -> None:
    _require_keys(summary, ELIGIBILITY_SUMMARY_REQUIRED, path)
    if summary["frozen_cases"] != FROZEN_CASE_COUNT:
        raise FormalWindowContractError(f"{path}.frozen_cases must be {FROZEN_CASE_COUNT}")
    if summary["product_path_eligible"] != PRODUCT_PATH_ELIGIBLE_EXPECTED:
        raise FormalWindowContractError(
            f"{path}.product_path_eligible must be {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )
    if summary["invalid_for_product_path"] != INVALID_EXPECTED:
        raise FormalWindowContractError(
            f"{path}.invalid_for_product_path must be {INVALID_EXPECTED}"
        )
    if summary["c12_in_denominator"] is not False:
        raise FormalWindowContractError(f"{path}.c12_in_denominator must be false")
    if summary["denominator_case_count"] != PRODUCT_PATH_ELIGIBLE_EXPECTED:
        raise FormalWindowContractError(
            f"{path}.denominator_case_count must be {PRODUCT_PATH_ELIGIBLE_EXPECTED}"
        )
    if summary["classification_vocabulary"] != CLASSIFICATION_INVALID:
        raise FormalWindowContractError(
            f"{path}.classification_vocabulary must be {CLASSIFICATION_INVALID!r}"
        )
    invalid_ids = summary["invalid_case_ids"]
    if not isinstance(invalid_ids, list) or C12_CASE_ID not in invalid_ids:
        raise FormalWindowContractError(
            f"{path}.invalid_case_ids must include {C12_CASE_ID!r}"
        )


def _validate_per_case(case: Mapping[str, Any], path: str) -> None:
    _require_keys(case, PER_CASE_REQUIRED, path)
    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        raise FormalWindowContractError(f"{path}.case_id must be a non-empty string")
    executor = case["executor_path"]
    if not isinstance(executor, str):
        raise FormalWindowContractError(f"{path}.executor_path must be a string")
    if _is_forbidden_runner_token(executor):
        raise FormalWindowContractError(
            f"{path}.executor_path forbids P2-R1/P2-R3 identity {executor!r}"
        )
    if executor not in EXECUTOR_PATH_ALLOWLIST:
        raise FormalWindowContractError(
            f"{path}.executor_path {executor!r} not in allowlist"
        )
    if case["scorer_observation_point"] != OBSERVATION_POINT:
        raise FormalWindowContractError(
            f"{path}.scorer_observation_point must be {OBSERVATION_POINT!r}"
        )
    if case_id == C12_CASE_ID:
        if case["product_path_eligible"] is not False:
            raise FormalWindowContractError(f"{path}: C12 must be product_path_eligible=false")
        if case["classification"] != CLASSIFICATION_INVALID:
            raise FormalWindowContractError(
                f"{path}: C12 classification must be {CLASSIFICATION_INVALID!r}"
            )
        if case["in_pass_rate_denominator"] is not False:
            raise FormalWindowContractError(f"{path}: C12 must be out of pass_rate denominator")
        if executor not in {"refused_ineligible", "not_executed_schema_example"}:
            raise FormalWindowContractError(
                f"{path}: C12 executor_path must be refused or schema-example"
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
        raise FormalWindowContractError(f"{path}.measurement_valid must be boolean")
    reasons = validity["invalid_reasons"]
    if not isinstance(reasons, list):
        raise FormalWindowContractError(f"{path}.invalid_reasons must be an array")
    for reason in reasons:
        if reason not in INVALID_REASON_CODES:
            raise FormalWindowContractError(
                f"{path}.invalid_reasons contains unknown code {reason!r}"
            )
    if validity["structurally_schema_ok"] is not True:
        raise FormalWindowContractError(f"{path}.structurally_schema_ok must be true")
    if validity["eligibility_bound_to_ea1"] is not True:
        raise FormalWindowContractError(f"{path}.eligibility_bound_to_ea1 must be true")
    if validity["adapter_bound_to_ea2"] is not True:
        raise FormalWindowContractError(f"{path}.adapter_bound_to_ea2 must be true")
    if validity["p2_r1_remains_blocked"] is not True:
        raise FormalWindowContractError(f"{path}.p2_r1_remains_blocked must be true")
    if validity["runner_identity_ok"] is not True:
        raise FormalWindowContractError(f"{path}.runner_identity_ok must be true")
    if validity["observation_point_honest"] is not True:
        raise FormalWindowContractError(f"{path}.observation_point_honest must be true")

    if artifact_kind == ARTIFACT_KIND_SCHEMA_EXAMPLE:
        if measurement_valid is not False:
            raise FormalWindowContractError(
                f"{path}: SCHEMA_EXAMPLE_NOT_A_RUN requires measurement_valid=false"
            )
        if "SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN" not in reasons:
            raise FormalWindowContractError(
                f"{path}: schema examples must include SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN"
            )

    if measurement_valid is True:
        if artifact_kind != ARTIFACT_KIND_FORMAL_RUN:
            raise FormalWindowContractError(
                f"{path}: measurement_valid=true requires artifact_kind=FORMAL_RUN_RESULT"
            )
        if reasons:
            raise FormalWindowContractError(
                f"{path}: measurement_valid=true requires empty invalid_reasons"
            )
    else:
        if not reasons:
            raise FormalWindowContractError(
                f"{path}: measurement_valid=false requires non-empty invalid_reasons"
            )


def validate_reserved_artifact(payload: Mapping[str, Any]) -> None:
    """Validate structural contract + identity + claim boundary.

    A structurally valid SCHEMA_EXAMPLE still has measurement_valid=false.
    """
    if not isinstance(payload, Mapping):
        raise FormalWindowContractError("artifact must be a JSON object")
    _require_keys(payload, TOP_LEVEL_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise FormalWindowContractError(
            f"protocol_version mismatch: expected {PROTOCOL_VERSION!r}"
        )
    if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise FormalWindowContractError("artifact_schema_version mismatch")
    if payload["suite_id"] != SUITE_ID:
        raise FormalWindowContractError("suite_id mismatch")
    if payload["case_count"] != FROZEN_CASE_COUNT:
        raise FormalWindowContractError("case_count must be 12")
    if payload["adapter_protocol_version"] != ADAPTER_PROTOCOL_VERSION:
        raise FormalWindowContractError("adapter_protocol_version must bind E-A2")
    if payload["eligibility_protocol_id"] != ELIGIBILITY_PROTOCOL_ID:
        raise FormalWindowContractError("eligibility_protocol_id must bind E-A1")
    if payload["observation_point"] != OBSERVATION_POINT:
        raise FormalWindowContractError("observation_point must be plan_construction_citations")
    if payload["p2_r1_status"] != P2_R1_STATUS_BLOCKED:
        raise FormalWindowContractError("p2_r1_status must remain BLOCKED")
    if payload["does_not_unblock_p2_r1"] is not True:
        raise FormalWindowContractError("does_not_unblock_p2_r1 must be true")

    run_id = payload["run_id"]
    if not isinstance(run_id, str) or not run_id:
        raise FormalWindowContractError("run_id must be a non-empty string")
    base_sha = payload["base_sha"]
    if not isinstance(base_sha, str) or len(base_sha) < 7:
        raise FormalWindowContractError("base_sha must be a git SHA string (len>=7)")

    runner_id = payload["runner_id"]
    runner_module = payload["runner_module"]
    if not isinstance(runner_id, str) or not isinstance(runner_module, str):
        raise FormalWindowContractError("runner_id/runner_module must be strings")
    if _is_forbidden_runner_token(runner_id) or _is_forbidden_runner_token(runner_module):
        raise FormalWindowContractError(
            "wrong runner identity: P2-R1 execute_frozen_case / P2-R3 substitution forbidden"
        )
    if runner_id != RUNNER_ID:
        raise FormalWindowContractError(f"runner_id must be {RUNNER_ID!r}")
    if runner_module != RUNNER_MODULE:
        raise FormalWindowContractError(f"runner_module must be {RUNNER_MODULE!r}")

    artifact_kind = payload["artifact_kind"]
    if artifact_kind not in ARTIFACT_KINDS:
        raise FormalWindowContractError(f"artifact_kind invalid: {artifact_kind!r}")
    if artifact_kind == ARTIFACT_KIND_SCHEMA_EXAMPLE and not run_id.startswith(
        "SCHEMA_EXAMPLE_"
    ):
        raise FormalWindowContractError(
            "SCHEMA_EXAMPLE_NOT_A_RUN run_id must start with SCHEMA_EXAMPLE_"
        )

    notes = payload.get("notes")
    if isinstance(notes, str):
        for claim in FORBIDDEN_CLAIMS:
            if claim in notes:
                raise FormalWindowContractError(
                    f"forbidden measurement claim {claim!r} appears in notes"
                )

    eligibility_summary = payload["eligibility_summary"]
    if not isinstance(eligibility_summary, Mapping):
        raise FormalWindowContractError("eligibility_summary must be an object")
    _validate_eligibility_summary(eligibility_summary, "$.eligibility_summary")

    claims = payload["measurement_claims"]
    if not isinstance(claims, Mapping):
        raise FormalWindowContractError("measurement_claims must be an object")
    _validate_claims(claims, "$.measurement_claims")

    cases = payload["per_case_result"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise FormalWindowContractError("per_case_result must be an array")
    if len(cases) != FROZEN_CASE_COUNT:
        raise FormalWindowContractError("per_case_result length must equal case_count (12)")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise FormalWindowContractError(f"$.per_case_result[{index}] must be an object")
        _validate_per_case(case, f"$.per_case_result[{index}]")
        cid = str(case["case_id"])
        if cid in seen:
            raise FormalWindowContractError(f"duplicate case_id {cid!r}")
        seen.add(cid)
    if C12_CASE_ID not in seen:
        raise FormalWindowContractError("per_case_result must include C12")

    validity = payload["measurement_validity"]
    if not isinstance(validity, Mapping):
        raise FormalWindowContractError("measurement_validity must be an object")
    _validate_measurement_validity(
        validity, artifact_kind=str(artifact_kind), path="$.measurement_validity"
    )


def build_schema_example_artifact() -> dict[str, Any]:
    """Minimal reserved-shape payload clearly marked as NOT a formal run."""
    cases: list[dict[str, Any]] = []
    for case_id in _SCHEMA_EXAMPLE_CASE_IDS:
        if case_id == C12_CASE_ID:
            cases.append(
                {
                    "case_id": case_id,
                    "product_path_eligible": False,
                    "classification": CLASSIFICATION_INVALID,
                    "executor_path": "not_executed_schema_example",
                    "in_pass_rate_denominator": False,
                    "scorer_observation_point": OBSERVATION_POINT,
                }
            )
        else:
            cases.append(
                {
                    "case_id": case_id,
                    "product_path_eligible": True,
                    "classification": None,
                    "executor_path": "not_executed_schema_example",
                    "in_pass_rate_denominator": True,
                    "scorer_observation_point": OBSERVATION_POINT,
                }
            )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": "SCHEMA_EXAMPLE_ea4_contract_freeze_not_a_run",
        "base_sha": PLACEHOLDER_SHA,
        "suite_id": SUITE_ID,
        "case_count": FROZEN_CASE_COUNT,
        "runner_id": RUNNER_ID,
        "runner_module": RUNNER_MODULE,
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "eligibility_protocol_id": ELIGIBILITY_PROTOCOL_ID,
        "eligibility_summary": {
            "frozen_cases": FROZEN_CASE_COUNT,
            "product_path_eligible": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "invalid_for_product_path": INVALID_EXPECTED,
            "c12_in_denominator": False,
            "invalid_case_ids": [C12_CASE_ID],
            "denominator_case_count": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "classification_vocabulary": CLASSIFICATION_INVALID,
        },
        "per_case_result": cases,
        "measurement_validity": {
            "measurement_valid": False,
            "invalid_reasons": ["SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN"],
            "structurally_schema_ok": True,
            "runner_identity_ok": True,
            "eligibility_bound_to_ea1": True,
            "adapter_bound_to_ea2": True,
            "observation_point_honest": True,
            "p2_r1_remains_blocked": True,
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
        "notes": "E-A4 schema example only; not a formal evaluation result.",
    }


def assert_reserved_result_absent() -> None:
    if RESERVED_RESULT_PATH.exists():
        raise FormalWindowContractError(
            f"reserved result {RESERVED_RESULT_FILENAME} must not exist during E-A4"
        )


def contract_module_imports_are_llm_free() -> bool:
    """Sanity helper: AST-check that this module does not import LLM/inject stacks."""
    import ast

    from tests import w10_ea4_formal_window_contract as self_mod

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
    if hasattr(self_mod, "execute_frozen_case"):
        return False
    return True


def json_schema_document() -> dict[str, Any]:
    """JSON Schema (draft-07 style) mirror of the frozen contract for docs/tests."""
    return {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "$id": "w10-ea4-formal-window-contract.schema.json",
        "title": "W10 E-A4 formal window reserved artifact (schema freeze only)",
        "description": (
            "Contract for future reserved file w10-ea4-formal-window-result.json. "
            "This schema document is not a formal run result. "
            "Allowed claim: plan-construction citation scope compliance. "
            "Forbidden: generation-final safety; Critic oracle capability; P2-R1 unblocked."
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
            "adapter_protocol_version": {
                "type": "string",
                "const": ADAPTER_PROTOCOL_VERSION,
            },
            "eligibility_protocol_id": {
                "type": "string",
                "const": ELIGIBILITY_PROTOCOL_ID,
            },
            "observation_point": {"type": "string", "const": OBSERVATION_POINT},
            "p2_r1_status": {"type": "string", "const": P2_R1_STATUS_BLOCKED},
            "does_not_unblock_p2_r1": {"type": "boolean", "const": True},
            "artifact_kind": {
                "type": "string",
                "enum": sorted(ARTIFACT_KINDS),
            },
            "eligibility_summary": {"type": "object"},
            "per_case_result": {
                "type": "array",
                "minItems": FROZEN_CASE_COUNT,
                "maxItems": FROZEN_CASE_COUNT,
            },
            "measurement_validity": {"type": "object"},
            "measurement_claims": {"type": "object"},
            "timestamp": {"type": "string"},
            "notes": {"type": "string"},
        },
    }


# Keep deepcopy available for tests that mutate examples without importing copy.
def clone_schema_example() -> dict[str, Any]:
    return deepcopy(build_schema_example_artifact())


def _git_base_sha() -> str:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    if len(sha) < 7:
        raise FormalWindowContractError(f"git rev-parse HEAD produced invalid sha {sha!r}")
    return sha


def _preflight_or_stop() -> None:
    """Hard stop if frozen identity drifted. Does not rewrite protocol."""
    if RUNNER_ID != "w10_ea4_formal_window_runner":
        raise FormalWindowContractError("preflight: runner_id != w10_ea4_formal_window_runner")
    if PROTOCOL_VERSION != "1.0.0":
        raise FormalWindowContractError("preflight: protocol_version != 1.0.0")
    if CLASSIFICATION_INVALID != "INVALID_FOR_PRODUCT_PATH_EXECUTION":
        raise FormalWindowContractError("preflight: C12 classification vocabulary drifted")
    if P2_R1_STATUS_BLOCKED != "BLOCKED":
        raise FormalWindowContractError("preflight: P2-R1 status constant drifted")


def _per_case_from_ea2_artifact(artifact: Any) -> dict[str, Any]:
    eligibility = artifact.eligibility
    scorer = artifact.scorer_result
    record: dict[str, Any] = {
        "case_id": artifact.case_id,
        "product_path_eligible": eligibility.product_path_eligible,
        "classification": artifact.classification,
        "executor_path": artifact.executor_path,
        "in_pass_rate_denominator": eligibility.in_pass_rate_denominator,
        "scorer_observation_point": OBSERVATION_POINT,
        "final_citations": list(artifact.final_citations),
        "allowed_scope": artifact.allowed_scope.to_dict(),
        "scorer_result": None if scorer is None else scorer.to_dict(),
        "plan_refusal": artifact.plan_refusal,
        "gated_chunk_ids": list(artifact.gated_chunk_ids),
    }
    if eligibility.product_path_eligible:
        record["scope_compliance_pass"] = bool(
            scorer is not None and scorer.safe_outcome is True
        )
    else:
        record["scope_compliance_pass"] = None
    return record


async def run_formal_window(
    *,
    base_sha: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute the frozen 12-case suite via E-A2 only; return FORMAL_RUN_RESULT payload.

    Does not call execute_frozen_case, does not import P2-R3 runners, does not
    call LLMs, does not mutate protocol constants, does not unblock P2-R1.
    """
    from datetime import datetime, timezone

    import pytest

    from tests.w10_ea2_scope_eligibility import (
        artifact_from_execution,
        execute_product_path_plan,
        load_frozen_suite,
    )

    _preflight_or_stop()
    sha = base_sha or _git_base_sha()
    if len(sha) < 7:
        raise FormalWindowContractError("base_sha must be recorded (len>=7)")

    suite = load_frozen_suite()
    if len(suite.cases) != FROZEN_CASE_COUNT:
        raise FormalWindowContractError("suite frozen classification unchanged check failed: count")

    rid = run_id or (
        "w10-ea5-formal-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + sha[:12]
    )
    if rid.startswith("SCHEMA_EXAMPLE_"):
        raise FormalWindowContractError("formal run_id must not use SCHEMA_EXAMPLE_ prefix")

    per_case: list[dict[str, Any]] = []
    with pytest.MonkeyPatch.context() as monkeypatch:
        for case in suite.cases:
            execution = await execute_product_path_plan(monkeypatch, case)
            artifact = artifact_from_execution(execution)
            per_case.append(_per_case_from_ea2_artifact(artifact))

    seen = {item["case_id"] for item in per_case}
    if C12_CASE_ID not in seen or len(per_case) != FROZEN_CASE_COUNT:
        raise FormalWindowContractError("suite incomplete after formal execution")

    c12 = next(item for item in per_case if item["case_id"] == C12_CASE_ID)
    if c12["classification"] != CLASSIFICATION_INVALID:
        raise FormalWindowContractError("C12 classification drifted; refusing non-compliant window")
    if c12["product_path_eligible"] is not False or c12["in_pass_rate_denominator"] is not False:
        raise FormalWindowContractError("C12 must remain out of product-path denominator")
    if c12["executor_path"] != "refused_ineligible":
        raise FormalWindowContractError("C12 must remain refused_ineligible")

    eligible = [item for item in per_case if item["product_path_eligible"]]
    invalid = [item for item in per_case if item["classification"] == CLASSIFICATION_INVALID]
    if len(eligible) != PRODUCT_PATH_ELIGIBLE_EXPECTED or len(invalid) != INVALID_EXPECTED:
        raise FormalWindowContractError("suite frozen classification unchanged check failed")

    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": rid,
        "base_sha": sha,
        "suite_id": SUITE_ID,
        "case_count": FROZEN_CASE_COUNT,
        "runner_id": RUNNER_ID,
        "runner_module": RUNNER_MODULE,
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "eligibility_protocol_id": ELIGIBILITY_PROTOCOL_ID,
        "eligibility_summary": {
            "frozen_cases": FROZEN_CASE_COUNT,
            "product_path_eligible": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "invalid_for_product_path": INVALID_EXPECTED,
            "c12_in_denominator": False,
            "invalid_case_ids": [C12_CASE_ID],
            "denominator_case_count": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "classification_vocabulary": CLASSIFICATION_INVALID,
        },
        "per_case_result": per_case,
        "measurement_validity": {
            "measurement_valid": True,
            "invalid_reasons": [],
            "structurally_schema_ok": True,
            "runner_identity_ok": True,
            "eligibility_bound_to_ea1": True,
            "adapter_bound_to_ea2": True,
            "observation_point_honest": True,
            "p2_r1_remains_blocked": True,
        },
        "measurement_claims": {
            "allowed": [ALLOWED_CLAIM],
            "asserted": [ALLOWED_CLAIM],
            "forbidden_rejected": list(FORBIDDEN_CLAIMS),
        },
        "p2_r1_status": P2_R1_STATUS_BLOCKED,
        "does_not_unblock_p2_r1": True,
        "observation_point": OBSERVATION_POINT,
        "artifact_kind": ARTIFACT_KIND_FORMAL_RUN,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "W10 E-A5 narrow formal window: plan-construction citation scope "
            "compliance only. Does not measure generation-final citations, "
            "does not score Critic oracles, does not unblock P2-R1."
        ),
    }
    validate_reserved_artifact(payload)
    return payload


def write_formal_window_result(
    payload: Mapping[str, Any],
    path: Path | None = None,
) -> Path:
    import json

    target = path or RESERVED_RESULT_PATH
    if target.name != RESERVED_RESULT_FILENAME:
        raise FormalWindowContractError(
            f"formal result filename must be {RESERVED_RESULT_FILENAME!r}"
        )
    protected = {
        "w9-critic-p2-r1-independent-review.json",
        "w9-critic-p2-r3-full-product-rerun.json",
        "w9-critic-p2-r1-offline-product.json",
    }
    if target.name in protected:
        raise FormalWindowContractError(f"refusing to overwrite protected artifact {target.name}")
    validate_reserved_artifact(payload)
    if payload["artifact_kind"] != ARTIFACT_KIND_FORMAL_RUN:
        raise FormalWindowContractError("write path only accepts FORMAL_RUN_RESULT")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


async def execute_and_write_formal_window(
    *,
    base_sha: str | None = None,
    run_id: str | None = None,
    path: Path | None = None,
) -> Path:
    payload = await run_formal_window(base_sha=base_sha, run_id=run_id)
    return write_formal_window_result(payload, path=path)


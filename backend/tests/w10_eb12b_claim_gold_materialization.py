"""W10 E-B12B — Claim gold materialization (human draft → formal ledger).

Deterministic conversion only. Does not: call LLM / LM Studio, run generation
observation, clear E-B_FORMAL_READY, modify backend/app, or change E-B9a schema.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tests.w10_eb_generation_claim_gold_contract import (
    ARTIFACT_KIND,
    DENOMINATOR_POLICY_REQUIRED_TOKEN,
    GOLD_FILENAME,
    GOLD_PATH,
    PARENT_OBSERVATION_PROTOCOL,
    PROTOCOL_VERSION,
    ClaimGoldContractError,
    validate_claim_gold_ledger,
)
from tests.w10_eb12a_claim_gold_annotation_helper import (
    FILL_POLICY,
    FROZEN_SOURCE_FILENAME,
    ClaimGoldAnnotationHelperError,
    load_frozen_case_evidence_sources,
    validate_human_annotation_draft,
)

# ---------------------------------------------------------------------------
# Identity / gates
# ---------------------------------------------------------------------------

MATERIALIZATION_WINDOW = "E-B12B"
ANNOTATION_STATUS_ANNOTATED = "ANNOTATED"
CREATED_BY = "human_annotator"
C12_CASE_ID = "C12-out-of-scope-provenance"
CONTENT_BINDING_KIND = "synthetic_authored"

DRAFT_FILENAME = "w10-eb-generation-claim-gold-v1.annotation-draft.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
DRAFT_PATH = FIXTURES / DRAFT_FILENAME
FORMAL_GOLD_PATH = GOLD_PATH

E_B_CLAIM_GOLD_ANNOTATED = "YES"
E_B_FORMAL_READY = "NO"

ELIGIBLE_CASE_PREFIXES: tuple[str, ...] = tuple(f"C{i:02d}-" for i in range(1, 12))


class ClaimGoldMaterializationError(ValueError):
    """Raised when draft→gold materialization fails."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(payload: Any) -> str:
    """64-char hex digest (no sha256: prefix) for content/pool bindings."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def load_annotation_draft() -> dict[str, Any]:
    if not DRAFT_PATH.is_file():
        raise ClaimGoldMaterializationError(f"annotation draft missing: {DRAFT_PATH}")
    payload = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ClaimGoldMaterializationError("annotation draft must be a JSON object")
    return payload


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ClaimGoldMaterializationError(f"{path} must be an object")
    return value


def validate_annotated_draft_ready(draft: Mapping[str, Any]) -> None:
    """Draft must be human-filled: C01–C11 have claims; C12 stays empty."""
    try:
        validate_human_annotation_draft(draft)
    except ClaimGoldAnnotationHelperError as exc:
        raise ClaimGoldMaterializationError(f"draft failed human validator: {exc}") from exc

    if draft.get("fill_policy") != FILL_POLICY:
        raise ClaimGoldMaterializationError(f"fill_policy must remain {FILL_POLICY!r}")

    created_by = draft.get("created_by")
    if created_by != CREATED_BY:
        raise ClaimGoldMaterializationError(
            f"draft created_by must be {CREATED_BY!r} (got {created_by!r})"
        )

    cases = draft.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ClaimGoldMaterializationError("draft.cases must be an array")
    if len(cases) != 12:
        raise ClaimGoldMaterializationError(
            f"draft must contain 12 cases (found {len(cases)})"
        )

    frozen = load_frozen_case_evidence_sources()
    frozen_by_id = {item["case_id"]: item for item in frozen}

    for index, case in enumerate(cases):
        case_m = _require_mapping(case, f"draft.cases[{index}]")
        case_id = str(case_m.get("case_id", ""))
        if case_id not in frozen_by_id:
            raise ClaimGoldMaterializationError(
                f"draft.cases[{index}].case_id={case_id!r} not in frozen source"
            )
        frozen_case = frozen_by_id[case_id]
        if case_m.get("query") != frozen_case["query"]:
            raise ClaimGoldMaterializationError(
                f"{case_id}: query drifted from frozen source"
            )
        if case_m.get("evidence_chunks") != frozen_case["evidence_chunks"]:
            raise ClaimGoldMaterializationError(
                f"{case_id}: evidence_chunks drifted from frozen source"
            )

        claims = case_m.get("claims")
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
            raise ClaimGoldMaterializationError(f"{case_id}.claims must be an array")

        if case_id == C12_CASE_ID:
            if len(claims) != 0:
                raise ClaimGoldMaterializationError(
                    f"{C12_CASE_ID} must keep claims=[] (exclusion / out-of-scope)"
                )
            continue

        if not any(case_id.startswith(prefix) for prefix in ELIGIBLE_CASE_PREFIXES):
            raise ClaimGoldMaterializationError(f"unexpected case_id {case_id!r}")
        if len(claims) < 1:
            raise ClaimGoldMaterializationError(
                f"{case_id}: eligible case requires ≥1 human-annotated claim"
            )


def _synthetic_body_payload(case: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical synthetic body bound by content_sha256 (claim texts only)."""
    claims = case["claims"]
    return {
        "case_id": case["case_id"],
        "kind": CONTENT_BINDING_KIND,
        "claim_texts": [str(claim["claim_text"]) for claim in claims],
    }


def _pool_payload(evidence_chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"chunk_id": str(chunk["chunk_id"]), "content": str(chunk["content"])}
        for chunk in evidence_chunks
    ]


def materialize_claim_gold_ledger(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Map validated human draft → E-B9a CLAIM_GOLD_LEDGER (in memory)."""
    validate_annotated_draft_ready(draft)

    cases_out: list[dict[str, Any]] = []
    for case in draft["cases"]:
        case_id = str(case["case_id"])
        evidence_chunks = list(case["evidence_chunks"])
        chunk_ids = [str(chunk["chunk_id"]) for chunk in evidence_chunks]
        pool_hash = sha256_hex(_pool_payload(evidence_chunks))
        content_hash = sha256_hex(_synthetic_body_payload(case))

        claims_out: list[dict[str, Any]] = []
        for claim in case["claims"]:
            claims_out.append(
                {
                    "claim_id": str(claim["claim_id"]),
                    "text": str(claim["claim_text"]),
                    "label": str(claim["label"]),
                    "supporting_evidence_ids": list(claim["supporting_evidence_ids"]),
                    "support_span_notes": claim.get("annotation_notes"),
                }
            )

        case_entry: dict[str, Any] = {
            "case_id": case_id,
            "content_binding": {
                "kind": CONTENT_BINDING_KIND,
                "content_sha256": content_hash,
                "synthetic_body_id": f"human_claim_gold_v1::{case_id}",
            },
            "gated_pool_binding": {
                "evidence_ids": chunk_ids,
                "pool_sha256": pool_hash,
            },
            "denominator_policy": DENOMINATOR_POLICY_REQUIRED_TOKEN,
            "asserted_claims": claims_out,
        }
        if case_id == C12_CASE_ID:
            case_entry["notes"] = (
                "EXCLUDED_FROM_CLAIM_DENOMINATOR. "
                "OUT_OF_SCOPE_PROVENANCE / INVALID_FOR_PRODUCT_PATH. "
                "asserted_claims remains empty; do not score T2/T3."
            )
        cases_out.append(case_entry)

    ledger: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "artifact_kind": ARTIFACT_KIND,
        "created_by": CREATED_BY,
        "notes": (
            "HUMAN_ANNOTATED_CLAIM_GOLD_LEDGER. annotation_status=ANNOTATED. "
            "Materialized from w10-eb-generation-claim-gold-v1.annotation-draft.json "
            "under E-B12B. synthetic_authored content_sha256 binds claim texts; "
            "pool_sha256 binds frozen evidence excerpts. C12 excluded from claim "
            "denominator. No LLM, no generation observation, E-B_FORMAL_READY=NO."
        ),
        "cases": cases_out,
    }

    try:
        validate_claim_gold_ledger(ledger)
    except ClaimGoldContractError as exc:
        raise ClaimGoldMaterializationError(
            f"materialized ledger failed E-B9a validator: {exc}"
        ) from exc
    return ledger


def write_claim_gold_ledger(ledger: Mapping[str, Any], *, path: Path | None = None) -> Path:
    """Persist formal gold JSON (UTF-8, trailing newline)."""
    target = path or FORMAL_GOLD_PATH
    try:
        validate_claim_gold_ledger(ledger)
    except ClaimGoldContractError as exc:
        raise ClaimGoldMaterializationError(f"refuse to write invalid ledger: {exc}") from exc

    text = json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"
    target.write_text(text, encoding="utf-8")
    return target


def load_claim_gold_ledger(*, path: Path | None = None) -> dict[str, Any]:
    target = path or FORMAL_GOLD_PATH
    if not target.is_file():
        raise ClaimGoldMaterializationError(f"formal claim gold missing: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ClaimGoldMaterializationError("formal claim gold must be a JSON object")
    try:
        validate_claim_gold_ledger(payload)
    except ClaimGoldContractError as exc:
        raise ClaimGoldMaterializationError(f"on-disk gold failed validator: {exc}") from exc
    return payload


def assert_claim_gold_present_and_valid() -> dict[str, Any]:
    return load_claim_gold_ledger()


def materialize_from_draft_file(*, write: bool = True) -> dict[str, Any]:
    """Load draft → validate → materialize → optionally write formal gold."""
    draft = load_annotation_draft()
    ledger = materialize_claim_gold_ledger(draft)
    if write:
        write_claim_gold_ledger(ledger)
    return ledger


def claim_denominator_case_ids(ledger: Mapping[str, Any]) -> list[str]:
    """Case ids that contribute ≥1 asserted claim (C12 must not appear)."""
    out: list[str] = []
    for case in ledger["cases"]:
        claims = case.get("asserted_claims") or []
        if claims:
            out.append(str(case["case_id"]))
    return out


def materialization_status() -> dict[str, Any]:
    """Deterministic status report — annotated gold yes; formal observation no."""
    draft = load_annotation_draft()
    validate_annotated_draft_ready(draft)
    ledger = load_claim_gold_ledger()
    denom = claim_denominator_case_ids(ledger)
    return {
        "window": MATERIALIZATION_WINDOW,
        "artifact_paths": {
            "annotation_draft": str(DRAFT_PATH),
            "formal_gold": str(FORMAL_GOLD_PATH),
            "formal_gold_present": FORMAL_GOLD_PATH.is_file(),
            "formal_gold_filename": GOLD_FILENAME,
            "frozen_source_filename": FROZEN_SOURCE_FILENAME,
        },
        "identities": {
            "protocol_version": PROTOCOL_VERSION,
            "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
            "artifact_kind": ARTIFACT_KIND,
            "created_by": CREATED_BY,
            "annotation_status": ANNOTATION_STATUS_ANNOTATED,
            "content_binding_kind": CONTENT_BINDING_KIND,
        },
        "gates": {
            "E_B_CLAIM_GOLD_ANNOTATED": E_B_CLAIM_GOLD_ANNOTATED,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
        },
        "counts": {
            "draft_cases": len(draft["cases"]),
            "ledger_cases": len(ledger["cases"]),
            "claim_denominator_cases": len(denom),
            "total_asserted_claims": sum(
                len(case["asserted_claims"]) for case in ledger["cases"]
            ),
        },
        "c12": {
            "case_id": C12_CASE_ID,
            "in_claim_denominator": C12_CASE_ID in denom,
            "asserted_claims_empty": all(
                (case["case_id"] != C12_CASE_ID) or (case["asserted_claims"] == [])
                for case in ledger["cases"]
            ),
        },
        "claims": {
            "llm": False,
            "lm_studio": False,
            "generation_observation": False,
            "generation_result": False,
            "formal_measurement": False,
            "auto_label": False,
            "critic_oracle": False,
        },
    }


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no product LLM / Critic harness / executor hooks."""
    import ast
    import inspect

    import tests.w10_eb12b_claim_gold_materialization as self_mod

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

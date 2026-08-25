"""W10 E-B12A-0 — Claim gold human annotation helper (prep only).

Assists human-in-the-loop claim gold creation from frozen case/evidence sources.
Does not: auto-label, infer labels, call LLM / LM Studio, write formal gold,
create fake annotations, or change E-B9a schema.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from tests.w10_eb11_claim_gold_prep import (
    E_B_FORMAL_READY,
)
from tests.w10_eb_generation_claim_gold_contract import (
    CLAIM_LABELS,
    FORBIDDEN_CREATED_BY,
    FORBIDDEN_KEYS as GOLD_FORBIDDEN_KEYS,
    GOLD_FILENAME,
    PROTOCOL_VERSION as GOLD_PROTOCOL_VERSION,
    PARENT_OBSERVATION_PROTOCOL,
    ClaimGoldContractError,
    validate_claim_gold_ledger,
)

# ---------------------------------------------------------------------------
# Frozen prep identity / paths
# ---------------------------------------------------------------------------

HELPER_PROTOCOL_VERSION = "w10_eb_generation_claim_gold_annotation_helper_v1"
HELPER_ARTIFACT_KIND = "CLAIM_GOLD_ANNOTATION_HELPER_TEMPLATE"
PARENT_PREP_PROTOCOL = "w10_eb_generation_claim_gold_annotation_prep_v1"
FROZEN_SOURCE_PROTOCOL = "w9_critic_model_inputs_v1"
FROZEN_SOURCE_FILENAME = "w9-critic-cases.json"
FILL_POLICY = "human_only_no_auto_label"
ANNOTATION_STATUS_AWAITING = "AWAITING_HUMAN"

TEMPLATE_FILENAME = "w10-eb-generation-claim-gold-v1.annotation-helper.template.json"
TEMPLATE_SCHEMA_FILENAME = (
    "w10-eb-generation-claim-gold-v1.annotation-helper.schema.json"
)
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l4_critic"
FROZEN_SOURCE_PATH = FIXTURES / FROZEN_SOURCE_FILENAME
TEMPLATE_PATH = FIXTURES / TEMPLATE_FILENAME
TEMPLATE_SCHEMA_PATH = FIXTURES / TEMPLATE_SCHEMA_FILENAME

E_B12A_ANNOTATION_HELPER_READY = "YES"
E_B_CLAIM_GOLD_ANNOTATED = "NO"

HEADER_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "artifact_kind",
    "parent_gold_protocol",
    "parent_prep_protocol",
    "parent_observation_protocol",
    "frozen_source_protocol",
    "frozen_source_filename",
    "target_gold_filename",
    "annotation_status",
    "fill_policy",
    "created_by",
    "claim_row_template",
    "cases",
    "gates",
)

GATES_REQUIRED: tuple[str, ...] = (
    "E_B12A_ANNOTATION_HELPER_READY",
    "E_B_CLAIM_GOLD_ANNOTATED",
    "E_B_FORMAL_READY",
)

CASE_REQUIRED: tuple[str, ...] = ("case_id", "query", "evidence_chunks", "claims")

CLAIM_ROW_TEMPLATE_REQUIRED: tuple[str, ...] = (
    "claim_id",
    "claim_text",
    "label",
    "supporting_evidence_ids",
    "annotation_notes",
)

# Keys that must never appear in helper output or human drafts.
FORBIDDEN_ANNOTATION_KEYS: frozenset[str] = GOLD_FORBIDDEN_KEYS | frozenset(
    {
        "answer",
        "model_answer",
        "previous_answer",
        "expected_action",
        "inferred_label",
        "auto_generated_label",
        "llm_generated_claim",
        "model_claim_text",
        "critic_validated",
        "oracle_label",
        "generation_source",
        "label_inference",
    }
)


class ClaimGoldAnnotationHelperError(ValueError):
    """Raised when annotation helper contract or draft validation fails."""


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ClaimGoldAnnotationHelperError(f"{path} missing fields: {missing}")


def _reject_forbidden_keys(mapping: Mapping[str, Any], path: str) -> None:
    present = sorted(key for key in mapping if key in FORBIDDEN_ANNOTATION_KEYS)
    if present:
        raise ClaimGoldAnnotationHelperError(
            f"forbidden annotation fields present at {path}: {present}"
        )


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
    if gates["E_B12A_ANNOTATION_HELPER_READY"] != E_B12A_ANNOTATION_HELPER_READY:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.E_B12A_ANNOTATION_HELPER_READY must be "
            f"{E_B12A_ANNOTATION_HELPER_READY!r}"
        )
    if gates["E_B_CLAIM_GOLD_ANNOTATED"] != E_B_CLAIM_GOLD_ANNOTATED:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.E_B_CLAIM_GOLD_ANNOTATED must remain {E_B_CLAIM_GOLD_ANNOTATED!r}"
        )
    if gates["E_B_FORMAL_READY"] != E_B_FORMAL_READY:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.E_B_FORMAL_READY must remain {E_B_FORMAL_READY!r}"
        )


def _validate_evidence_chunk(chunk: Mapping[str, Any], path: str) -> None:
    _reject_forbidden_keys(chunk, path)
    _require_keys(chunk, ("chunk_id", "content"), path)
    chunk_id = chunk["chunk_id"]
    content = chunk["content"]
    if not isinstance(chunk_id, str) or not chunk_id:
        raise ClaimGoldAnnotationHelperError(f"{path}.chunk_id must be a non-empty string")
    if not isinstance(content, str):
        raise ClaimGoldAnnotationHelperError(f"{path}.content must be a string")


def _validate_claim_row_template(template: Mapping[str, Any], path: str) -> None:
    _reject_forbidden_keys(template, path)
    _require_keys(template, CLAIM_ROW_TEMPLATE_REQUIRED, path)
    if template["claim_id"] != "":
        raise ClaimGoldAnnotationHelperError(f"{path}.claim_id must be empty in template")
    if template["claim_text"] != "":
        raise ClaimGoldAnnotationHelperError(
            f"{path}.claim_text must be empty in template (no prefilled claims)"
        )
    if template["label"] is not None:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.label must be null in template (no auto-generated labels)"
        )
    evidence_ids = template["supporting_evidence_ids"]
    if not isinstance(evidence_ids, Sequence) or isinstance(
        evidence_ids, (str, bytes, bytearray)
    ):
        raise ClaimGoldAnnotationHelperError(
            f"{path}.supporting_evidence_ids must be an array"
        )
    if len(evidence_ids) != 0:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.supporting_evidence_ids must be empty in template"
        )
    notes = template["annotation_notes"]
    if notes is not None:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.annotation_notes must be null in template"
        )


def _validate_template_case(case: Mapping[str, Any], path: str) -> None:
    _reject_forbidden_keys(case, path)
    _require_keys(case, CASE_REQUIRED, path)
    case_id = case["case_id"]
    query = case["query"]
    if not isinstance(case_id, str) or not case_id:
        raise ClaimGoldAnnotationHelperError(f"{path}.case_id must be a non-empty string")
    if not isinstance(query, str) or not query.strip():
        raise ClaimGoldAnnotationHelperError(f"{path}.query must be a non-empty string")

    chunks = case["evidence_chunks"]
    if not isinstance(chunks, Sequence) or isinstance(chunks, (str, bytes, bytearray)):
        raise ClaimGoldAnnotationHelperError(f"{path}.evidence_chunks must be an array")
    seen_chunk_ids: set[str] = set()
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, Mapping):
            raise ClaimGoldAnnotationHelperError(
                f"{path}.evidence_chunks[{index}] must be an object"
            )
        _validate_evidence_chunk(chunk, f"{path}.evidence_chunks[{index}]")
        cid = str(chunk["chunk_id"])
        if cid in seen_chunk_ids:
            raise ClaimGoldAnnotationHelperError(
                f"{path}.evidence_chunks contains duplicate chunk_id {cid!r}"
            )
        seen_chunk_ids.add(cid)

    claims = case["claims"]
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ClaimGoldAnnotationHelperError(f"{path}.claims must be an array")
    if len(claims) != 0:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.claims must be empty in prep template (no fabricated annotations)"
        )


def load_frozen_case_evidence_sources() -> list[dict[str, Any]]:
    """Read frozen case/evidence sources only — no oracle, answer reuse, or critic."""
    if not FROZEN_SOURCE_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(
            f"frozen source missing: {FROZEN_SOURCE_PATH}"
        )
    payload = json.loads(FROZEN_SOURCE_PATH.read_text(encoding="utf-8"))
    if payload.get("protocol") != FROZEN_SOURCE_PROTOCOL:
        raise ClaimGoldAnnotationHelperError(
            f"frozen source protocol mismatch: expected {FROZEN_SOURCE_PROTOCOL!r}"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ClaimGoldAnnotationHelperError("frozen source cases must be a non-empty array")

    extracted: list[dict[str, Any]] = []
    for index, raw_case in enumerate(cases):
        if not isinstance(raw_case, Mapping):
            raise ClaimGoldAnnotationHelperError(
                f"frozen source cases[{index}] must be an object"
            )
        case_id = raw_case.get("case_id")
        query = raw_case.get("query")
        evidence = raw_case.get("evidence")
        if not isinstance(case_id, str) or not case_id:
            raise ClaimGoldAnnotationHelperError(
                f"frozen.cases[{index}].case_id must be a non-empty string"
            )
        if not isinstance(query, str) or not query.strip():
            raise ClaimGoldAnnotationHelperError(
                f"frozen.cases[{index}].query must be a non-empty string"
            )
        if not isinstance(evidence, list):
            raise ClaimGoldAnnotationHelperError(
                f"frozen.cases[{index}].evidence must be an array"
            )

        evidence_chunks: list[dict[str, str]] = []
        for ev_index, item in enumerate(evidence):
            if not isinstance(item, Mapping):
                raise ClaimGoldAnnotationHelperError(
                    f"frozen.cases[{index}].evidence[{ev_index}] must be an object"
                )
            evidence_id = item.get("evidence_id")
            excerpt = item.get("excerpt")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise ClaimGoldAnnotationHelperError(
                    f"frozen.cases[{index}].evidence[{ev_index}].evidence_id invalid"
                )
            if not isinstance(excerpt, str):
                raise ClaimGoldAnnotationHelperError(
                    f"frozen.cases[{index}].evidence[{ev_index}].excerpt must be string"
                )
            evidence_chunks.append(
                {
                    "chunk_id": evidence_id,
                    "content": excerpt,
                }
            )

        extracted.append(
            {
                "case_id": case_id,
                "query": query,
                "evidence_chunks": evidence_chunks,
                "claims": [],
            }
        )
    return extracted


def build_claim_row_template() -> dict[str, Any]:
    """Human-fillable claim row structure (empty — annotator supplies values)."""
    return {
        "claim_id": "",
        "claim_text": "",
        "label": None,
        "supporting_evidence_ids": [],
        "annotation_notes": None,
    }


def build_annotation_template() -> dict[str, Any]:
    """Canonical annotation helper template from frozen sources."""
    return {
        "protocol_version": HELPER_PROTOCOL_VERSION,
        "artifact_kind": HELPER_ARTIFACT_KIND,
        "parent_gold_protocol": GOLD_PROTOCOL_VERSION,
        "parent_prep_protocol": PARENT_PREP_PROTOCOL,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "frozen_source_protocol": FROZEN_SOURCE_PROTOCOL,
        "frozen_source_filename": FROZEN_SOURCE_FILENAME,
        "target_gold_filename": GOLD_FILENAME,
        "annotation_status": ANNOTATION_STATUS_AWAITING,
        "fill_policy": FILL_POLICY,
        "created_by": "e-b12a-annotation-helper-prep",
        "notes": (
            "ANNOTATION_HELPER_PREP_ONLY. Displays frozen query + evidence chunks; "
            "human annotators fill claims. No model answers, Critic oracle, LLM judge, "
            "or auto-label. Formal gold path remains absent."
        ),
        "claim_row_template": build_claim_row_template(),
        "cases": load_frozen_case_evidence_sources(),
        "gates": {
            "E_B12A_ANNOTATION_HELPER_READY": E_B12A_ANNOTATION_HELPER_READY,
            "E_B_CLAIM_GOLD_ANNOTATED": E_B_CLAIM_GOLD_ANNOTATED,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
        },
    }


def clone_annotation_template() -> dict[str, Any]:
    return deepcopy(build_annotation_template())


def validate_annotation_template(payload: Mapping[str, Any]) -> None:
    """Validate helper template artifact (prep — claims must stay empty)."""
    if not isinstance(payload, Mapping):
        raise ClaimGoldAnnotationHelperError("template must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")
    _require_keys(payload, HEADER_REQUIRED, "$")

    if payload["protocol_version"] != HELPER_PROTOCOL_VERSION:
        raise ClaimGoldAnnotationHelperError(
            f"protocol_version mismatch: expected {HELPER_PROTOCOL_VERSION!r}"
        )
    if payload["artifact_kind"] != HELPER_ARTIFACT_KIND:
        raise ClaimGoldAnnotationHelperError(
            f"artifact_kind must be {HELPER_ARTIFACT_KIND!r}"
        )
    if payload["parent_gold_protocol"] != GOLD_PROTOCOL_VERSION:
        raise ClaimGoldAnnotationHelperError("parent_gold_protocol drift")
    if payload["parent_prep_protocol"] != PARENT_PREP_PROTOCOL:
        raise ClaimGoldAnnotationHelperError("parent_prep_protocol drift")
    if payload["parent_observation_protocol"] != PARENT_OBSERVATION_PROTOCOL:
        raise ClaimGoldAnnotationHelperError("parent_observation_protocol drift")
    if payload["frozen_source_protocol"] != FROZEN_SOURCE_PROTOCOL:
        raise ClaimGoldAnnotationHelperError("frozen_source_protocol drift")
    if payload["frozen_source_filename"] != FROZEN_SOURCE_FILENAME:
        raise ClaimGoldAnnotationHelperError("frozen_source_filename drift")
    if payload["target_gold_filename"] != GOLD_FILENAME:
        raise ClaimGoldAnnotationHelperError("target_gold_filename drift")
    if payload["annotation_status"] != ANNOTATION_STATUS_AWAITING:
        raise ClaimGoldAnnotationHelperError(
            f"annotation_status must be {ANNOTATION_STATUS_AWAITING!r}"
        )
    if payload["fill_policy"] != FILL_POLICY:
        raise ClaimGoldAnnotationHelperError(f"fill_policy must be {FILL_POLICY!r}")

    created_by = payload["created_by"]
    if not isinstance(created_by, str) or not created_by.strip():
        raise ClaimGoldAnnotationHelperError("created_by must be a non-empty string")
    if created_by in FORBIDDEN_CREATED_BY:
        raise ClaimGoldAnnotationHelperError(
            f"created_by={created_by!r} is forbidden (no LLM / auto annotator)"
        )

    claim_row_template = payload["claim_row_template"]
    if not isinstance(claim_row_template, Mapping):
        raise ClaimGoldAnnotationHelperError("claim_row_template must be an object")
    _validate_claim_row_template(claim_row_template, "$.claim_row_template")

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ClaimGoldAnnotationHelperError("cases must be an array")
    if len(cases) == 0:
        raise ClaimGoldAnnotationHelperError("cases must be non-empty")

    seen_case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ClaimGoldAnnotationHelperError(f"$.cases[{index}] must be an object")
        _validate_template_case(case, f"$.cases[{index}]")
        cid = str(case["case_id"])
        if cid in seen_case_ids:
            raise ClaimGoldAnnotationHelperError(f"duplicate case_id {cid!r}")
        seen_case_ids.add(cid)

    gates = payload["gates"]
    if not isinstance(gates, Mapping):
        raise ClaimGoldAnnotationHelperError("$.gates must be an object")
    _validate_gates(gates, "$.gates")


def _frozen_model_answers_by_case_id() -> dict[str, str]:
    """Internal guard only — model answers must not be copied into claim gold."""
    payload = json.loads(FROZEN_SOURCE_PATH.read_text(encoding="utf-8"))
    answers: dict[str, str] = {}
    for raw_case in payload["cases"]:
        case_id = str(raw_case["case_id"])
        answer = raw_case.get("answer")
        if isinstance(answer, str) and answer.strip():
            answers[case_id] = answer.strip()
    return answers


def validate_human_claim_row(
    claim: Mapping[str, Any],
    path: str,
    *,
    allowed_chunk_ids: set[str],
    case_id: str,
) -> None:
    """Validate one human-filled claim row; rejects auto/oracle/LLM fields."""
    _reject_forbidden_keys(claim, path)
    _require_keys(claim, CLAIM_ROW_TEMPLATE_REQUIRED, path)

    claim_id = claim["claim_id"]
    claim_text = claim["claim_text"]
    label = claim["label"]
    supporting = claim["supporting_evidence_ids"]
    notes = claim["annotation_notes"]

    if not isinstance(claim_id, str) or not claim_id:
        raise ClaimGoldAnnotationHelperError(f"{path}.claim_id must be a non-empty string")
    if not isinstance(claim_text, str) or not claim_text.strip():
        raise ClaimGoldAnnotationHelperError(f"{path}.claim_text must be a non-empty string")

    model_answers = _frozen_model_answers_by_case_id()
    forbidden_answer = model_answers.get(case_id)
    if forbidden_answer and claim_text.strip() == forbidden_answer:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.claim_text must not reuse frozen model answer as claim gold"
        )

    if label not in CLAIM_LABELS:
        raise ClaimGoldAnnotationHelperError(
            f"{path}.label must be one of {sorted(CLAIM_LABELS)}"
        )

    if not isinstance(supporting, Sequence) or isinstance(
        supporting, (str, bytes, bytearray)
    ):
        raise ClaimGoldAnnotationHelperError(
            f"{path}.supporting_evidence_ids must be an array"
        )

    seen: set[str] = set()
    for index, chunk_id in enumerate(supporting):
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ClaimGoldAnnotationHelperError(
                f"{path}.supporting_evidence_ids[{index}] must be a non-empty string"
            )
        if chunk_id not in allowed_chunk_ids:
            raise ClaimGoldAnnotationHelperError(
                f"{path}.supporting_evidence_ids[{index}]={chunk_id!r} "
                f"not in case evidence chunk_id set"
            )
        if chunk_id in seen:
            raise ClaimGoldAnnotationHelperError(
                f"{path}.supporting_evidence_ids contains duplicate {chunk_id!r}"
            )
        seen.add(chunk_id)

    if label == "supported" and not supporting:
        raise ClaimGoldAnnotationHelperError(
            f"{path}: label=supported requires at least one supporting_evidence_ids entry"
        )

    if notes is not None and not isinstance(notes, str):
        raise ClaimGoldAnnotationHelperError(
            f"{path}.annotation_notes must be a string or null"
        )


def validate_human_annotation_draft(payload: Mapping[str, Any]) -> None:
    """Validate a human-filled draft (structure + anti-auto-label guards)."""
    if not isinstance(payload, Mapping):
        raise ClaimGoldAnnotationHelperError("draft must be a JSON object")

    _reject_forbidden_keys_recursive(payload, "$")

    if payload.get("fill_policy") != FILL_POLICY:
        raise ClaimGoldAnnotationHelperError(
            f"fill_policy must be {FILL_POLICY!r} (human-only drafts)"
        )

    created_by = payload.get("created_by")
    if not isinstance(created_by, str) or not created_by.strip():
        raise ClaimGoldAnnotationHelperError("draft created_by must be a non-empty string")
    if created_by in FORBIDDEN_CREATED_BY:
        raise ClaimGoldAnnotationHelperError(
            f"draft created_by={created_by!r} is forbidden"
        )

    cases = payload.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ClaimGoldAnnotationHelperError("draft cases must be an array")

    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ClaimGoldAnnotationHelperError(f"draft.cases[{index}] must be an object")
        _reject_forbidden_keys(case, f"draft.cases[{index}]")
        _require_keys(case, ("case_id", "evidence_chunks", "claims"), f"draft.cases[{index}]")
        case_id = str(case["case_id"])
        chunks = case["evidence_chunks"]
        if not isinstance(chunks, Sequence) or isinstance(
            chunks, (str, bytes, bytearray)
        ):
            raise ClaimGoldAnnotationHelperError(
                f"draft.cases[{index}].evidence_chunks must be an array"
            )
        allowed_chunk_ids = {
            str(chunk["chunk_id"])
            for chunk in chunks
            if isinstance(chunk, Mapping) and isinstance(chunk.get("chunk_id"), str)
        }
        claims = case["claims"]
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
            raise ClaimGoldAnnotationHelperError(
                f"draft.cases[{index}].claims must be an array"
            )
        seen_claim_ids: set[str] = set()
        for claim_index, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                raise ClaimGoldAnnotationHelperError(
                    f"draft.cases[{index}].claims[{claim_index}] must be an object"
                )
            validate_human_claim_row(
                claim,
                f"draft.cases[{index}].claims[{claim_index}]",
                allowed_chunk_ids=allowed_chunk_ids,
                case_id=case_id,
            )
            cid = str(claim["claim_id"])
            if cid in seen_claim_ids:
                raise ClaimGoldAnnotationHelperError(
                    f"draft.cases[{index}] duplicate claim_id {cid!r}"
                )
            seen_claim_ids.add(cid)


def draft_to_eb9a_ledger_shape(
    draft: Mapping[str, Any],
    *,
    content_sha256: str,
    created_by: str,
) -> dict[str, Any]:
    """Map validated human draft to E-B9a ledger shape for validator integration."""
    cases_out: list[dict[str, Any]] = []
    for case in draft["cases"]:
        case_id = str(case["case_id"])
        chunk_ids = [
            str(chunk["chunk_id"])
            for chunk in case["evidence_chunks"]
            if isinstance(chunk, Mapping)
        ]
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
        cases_out.append(
            {
                "case_id": case_id,
                "content_binding": {
                    "kind": "synthetic_authored",
                    "content_sha256": content_sha256,
                    "synthetic_body_id": f"human_draft::{case_id}",
                },
                "gated_pool_binding": {"evidence_ids": chunk_ids, "pool_sha256": None},
                "denominator_policy": "exclude_refusal_boilerplate",
                "asserted_claims": claims_out,
            }
        )
    return {
        "protocol_version": GOLD_PROTOCOL_VERSION,
        "parent_observation_protocol": PARENT_OBSERVATION_PROTOCOL,
        "artifact_kind": "CLAIM_GOLD_LEDGER",
        "created_by": created_by,
        "notes": "HUMAN_DRAFT_SHAPE_CHECK_ONLY_NOT_FORMAL_GOLD",
        "cases": cases_out,
    }


def validate_draft_eb9a_schema_compatible(
    draft: Mapping[str, Any],
    *,
    content_sha256: str,
    created_by: str = "human_annotator_draft_check",
) -> None:
    """Validator integration: human draft → E-B9a shape → ``validate_claim_gold_ledger``."""
    validate_human_annotation_draft(draft)
    ledger = draft_to_eb9a_ledger_shape(
        draft,
        content_sha256=content_sha256,
        created_by=created_by,
    )
    try:
        validate_claim_gold_ledger(ledger)
    except ClaimGoldContractError as exc:
        raise ClaimGoldAnnotationHelperError(
            f"integrated E-B9a validator rejected mapped draft: {exc}"
        ) from exc


def load_annotation_template() -> dict[str, Any]:
    if not TEMPLATE_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(f"template missing: {TEMPLATE_PATH}")
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    validate_annotation_template(payload)
    return payload


def load_template_schema_document() -> dict[str, Any]:
    if not TEMPLATE_SCHEMA_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(
            f"template schema missing: {TEMPLATE_SCHEMA_PATH}"
        )
    return json.loads(TEMPLATE_SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_annotation_helper_artifacts_present() -> None:
    if not TEMPLATE_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(f"template artifact missing: {TEMPLATE_PATH}")
    if not TEMPLATE_SCHEMA_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(
            f"template schema missing: {TEMPLATE_SCHEMA_PATH}"
        )
    if not FROZEN_SOURCE_PATH.is_file():
        raise ClaimGoldAnnotationHelperError(
            f"frozen source missing: {FROZEN_SOURCE_PATH}"
        )


def annotation_helper_preparation_status() -> dict[str, Any]:
    """Deterministic prep status report (no formal measurement claims).

    Helper-template gates remain prep-era (ANNOTATED=NO). Formal gold may exist
    after E-B12B materialization — reported via ``formal_gold_present``.
    """
    assert_annotation_helper_artifacts_present()

    template = load_annotation_template()
    frozen_cases = load_frozen_case_evidence_sources()
    gold_path = FIXTURES / GOLD_FILENAME
    return {
        "window": "E-B12A-0",
        "artifact_paths": {
            "annotation_helper_template": str(TEMPLATE_PATH),
            "annotation_helper_schema": str(TEMPLATE_SCHEMA_PATH),
            "frozen_source": str(FROZEN_SOURCE_PATH),
            "formal_gold_reserved": str(gold_path),
            "formal_gold_present": gold_path.is_file(),
        },
        "identities": {
            "helper_protocol_version": HELPER_PROTOCOL_VERSION,
            "helper_artifact_kind": HELPER_ARTIFACT_KIND,
            "frozen_source_protocol": FROZEN_SOURCE_PROTOCOL,
            "gold_protocol_version": GOLD_PROTOCOL_VERSION,
        },
        "gates": {
            "E_B12A_ANNOTATION_HELPER_READY": E_B12A_ANNOTATION_HELPER_READY,
            # Helper-template-era constant (template still AWAITING_HUMAN).
            "E_B_CLAIM_GOLD_ANNOTATED": E_B_CLAIM_GOLD_ANNOTATED,
            "E_B_FORMAL_READY": E_B_FORMAL_READY,
        },
        "frozen_case_count": len(frozen_cases),
        "template_case_count": len(template["cases"]),
        "validator_integration": {
            "validate_human_annotation_draft": "wired",
            "validate_draft_eb9a_schema_compatible": "wired",
            "eb9a_validate_claim_gold_ledger": "wired",
        },
        "claims": {
            "displays_frozen_evidence_only": True,
            "uses_model_answer_as_truth": False,
            "auto_label": False,
            "formal_measurement": False,
        },
    }


def contract_module_imports_are_llm_free() -> bool:
    """Static import hygiene: no product LLM / Critic harness / executor hooks."""
    import ast
    import inspect

    import tests.w10_eb12a_claim_gold_annotation_helper as self_mod

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
    for banned_attr in (
        "execute_frozen_case",
        "run_formal_window",
        "run_generation_observation",
        "auto_label",
    ):
        if hasattr(self_mod, banned_attr):
            return False
    return True

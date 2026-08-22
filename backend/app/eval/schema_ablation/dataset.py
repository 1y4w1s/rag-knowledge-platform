"""W8 P7 offline dataset — frozen P5 lineage fixtures + deterministic hard negatives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.eval.schema_ablation.models import ExpectedOutcome, SchemaSample
from app.eval.schema_ablation.tool_inventory import frozen_tool_inventory

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "w8_p7"
TARGET_FIXTURE = FIXTURE_DIR / "w8-p7-target-failures.fixture.json"
PASSTHROUGH_FIXTURE = FIXTURE_DIR / "w8-p7-valid-passthrough.fixture.json"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_fixture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        msg = f"Missing tracked fixture: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def load_target_failures() -> list[SchemaSample]:
    data = _load_fixture(TARGET_FIXTURE)
    samples: list[SchemaSample] = []
    for row in data["cases"]:
        raw = row["raw_output"]
        samples.append(
            SchemaSample(
                sample_id=f"{row['case_id']}:step{row['step_index']}",
                raw_output=raw,
                raw_output_hash=row["raw_output_hash"],
                source="TARGET_FAILURE",
                case_id=row["case_id"],
                step_index=row["step_index"],
                expected=ExpectedOutcome.accept,
                decoded_json=row.get("decoded_json"),
                lineage=row.get("lineage", data["meta"]["source_artifact"]),
            )
        )
    return samples


def load_valid_passthrough() -> list[SchemaSample]:
    data = _load_fixture(PASSTHROUGH_FIXTURE)
    samples: list[SchemaSample] = []
    for row in data["cases"]:
        raw = row["raw_output"]
        samples.append(
            SchemaSample(
                sample_id=f"{row['case_id']}:step{row['step_index']}",
                raw_output=raw,
                raw_output_hash=row["raw_output_hash"],
                source="VALID_PASSTHROUGH",
                case_id=row["case_id"],
                step_index=row["step_index"],
                expected=ExpectedOutcome.passthrough,
                lineage=row.get("lineage", data["meta"]["source_artifact"]),
            )
        )
    return samples


def passthrough_action_coverage() -> dict[str, Any]:
    data = _load_fixture(PASSTHROUGH_FIXTURE)
    return dict(data["meta"]["valid_passthrough_action_coverage"])


def build_hard_negatives() -> list[SchemaSample]:
    """Deterministic schema-invalid cases for repair safety contract."""
    inv = frozen_tool_inventory(external_tools_enabled=False)
    allowed = inv.allowed_tool_names
    semantic = "semantic_search"
    search_docs = "search_documents"
    grep = "grep_in_document"
    if semantic not in allowed or search_docs not in allowed:
        msg = "expected benchmark tool inventory missing semantic_search/search_documents"
        raise RuntimeError(msg)

    def _neg(
        neg_id: str,
        raw: str,
        *,
        dimension: str,
        as_json: dict[str, Any] | None = None,
    ) -> SchemaSample:
        return SchemaSample(
            sample_id=neg_id,
            raw_output=raw,
            raw_output_hash=_sha256(raw),
            source="HARD_NEGATIVE",
            expected=ExpectedOutcome.reject,
            failure_dimension=dimension,
            decoded_json=as_json,
            lineage="deterministic hard-negative definition",
        )

    cases: list[SchemaSample] = [
        _neg("HN-01", '{"action":"unknown_tool","args":{"query":"x"}}', dimension="unknown_action"),
        _neg(
            "HN-02",
            json.dumps({"action": "semantic_search_not_in_registry", "args": {"query": "x"}}),
            dimension="unknown_tool_name_as_action",
        ),
        _neg(
            "HN-03",
            json.dumps(
                {
                    "action": semantic,
                    "tool_name": grep,
                    "args": {"query": "x"},
                }
            ),
            dimension="conflicting_tool_name",
        ),
        _neg(
            "HN-04",
            json.dumps({"action": semantic, "args": {}}),
            dimension="missing_required_args",
        ),
        _neg(
            "HN-05",
            json.dumps({"action": semantic, "args": {"query": ""}}),
            dimension="wrong_arg_type",
        ),
        _neg(
            "HN-06",
            json.dumps({"action": semantic, "args": {"query": "x", "extra": ["bad"]}}),
            dimension="illegal_argument_structure",
        ),
        _neg("HN-07", '{"action":"finish","reason_code":"done"}', dimension="finish_action"),
        _neg(
            "HN-08",
            '{"action":"clarify","reason_code":"ambiguous","user_message":"Which doc?"}',
            dimension="clarify_action",
        ),
        _neg(
            "HN-09",
            '{"action":"refuse","reason_code":"unsupported"}',
            dimension="refuse_action",
        ),
        _neg(
            "HN-10",
            json.dumps({"action": "semantic_seach", "args": {"query": "typo"}}),
            dimension="tool_typo",
        ),
        _neg(
            "HN-11",
            json.dumps({"action": "semantic_search;finish", "args": {"query": "inject"}}),
            dimension="injection_like_action",
        ),
        _neg("HN-12", "{not valid json", dimension="malformed_json"),
        _neg(
            "HN-13",
            "```json\n{\"action\":\"tool\",\"tool_name\":\"semantic_search\",\"args\":{\"query\":\"x\"}}\n```",
            dimension="json_with_fence_only_valid_strict",
        ),
        _neg(
            "HN-14",
            "Here is the decision:\n"
            + json.dumps(
                {"action": "tool", "tool_name": semantic, "args": {"query": "x"}}
            ),
            dimension="extra_prose",
        ),
        _neg('HN-15', '{"args":{"query":"x"},"reason_code":"x"}', dimension="missing_action"),
        _neg('HN-16', '{"action":null,"args":{"query":"x"}}', dimension="null_action"),
        _neg(
            "HN-17-numeric",
            json.dumps({"action": 42, "args": {"query": "x"}}),
            dimension="numeric_action",
        ),
        _neg(
            "HN-18-list",
            json.dumps({"action": ["semantic_search"], "args": {"query": "x"}}),
            dimension="list_action",
        ),
        _neg(
            "HN-19-object",
            json.dumps({"action": {"tool": semantic}, "args": {"query": "x"}}),
            dimension="object_action",
        ),
        _neg(
            "HN-20",
            json.dumps({"action": grep, "args": {"document_id": "d", "pattern": "p"}}),
            dimension="out_of_scope_dependent_tool",
        ),
    ]
    # HN-13: fence-only is actually valid under product STRICT (fence strip) — relabel expected
    # as passthrough-like for strict; for hard-negative contract we expect REJECT only when
    # candidate wrongly *repairs* invalid semantics. Keep as control: strict accepts, candidates
    # must not mutate.
    cases[12] = SchemaSample(
        sample_id="HN-13",
        raw_output=cases[12].raw_output,
        raw_output_hash=cases[12].raw_output_hash,
        source="HARD_NEGATIVE",
        expected=ExpectedOutcome.reject,
        failure_dimension="json_with_fence_valid_under_strict",
        lineage="deterministic hard-negative definition",
    )
    # HN-02: use tool not in allowed set
    if "semantic_search_not_in_registry" not in allowed:
        pass  # already set
    # HN-04/05: semantic_search requires query
    _ = search_docs
    return cases


def load_full_dataset() -> tuple[list[SchemaSample], list[SchemaSample], list[SchemaSample]]:
    targets = load_target_failures()
    passthrough = load_valid_passthrough()
    hard = build_hard_negatives()
    return targets, passthrough, hard

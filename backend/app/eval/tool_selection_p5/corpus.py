"""Load frozen P4 GQ-131 condition 10/11 S2-failure corpus (eval-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.eval.tool_selection_p5.models import (
    CORPUS_SCHEMA,
    DEFAULT_EXPOSED,
    EXPECTED_TOOL,
    STUBBORN_TOOL,
    TARGET_CASE,
    TARGET_CONDITIONS,
    CaptureView,
    FrozenTrial,
    SelectionSample,
)

_FIXTURE_REL = Path("tests/fixtures/l4_tool_capability/l4-tool-p5-s2-failure-corpus.json")


def corpus_path(repo_root: Optional[Path] = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / _FIXTURE_REL


def load_corpus_payload(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    path = corpus_path(repo_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema_version")
    if schema != CORPUS_SCHEMA:
        raise ValueError("unexpected corpus schema: %r (expected %r)" % (schema, CORPUS_SCHEMA))
    return payload


def _reason_code(capture: Dict[str, Any]) -> Optional[str]:
    decision = capture.get("planner_decision") or {}
    if isinstance(decision, dict) and decision.get("reason_code") is not None:
        return str(decision["reason_code"])
    return None


def reconstruct_trials(repo_root: Optional[Path] = None) -> Tuple[FrozenTrial, ...]:
    payload = load_corpus_payload(repo_root)
    trials_out: List[FrozenTrial] = []
    for row in payload["trials"]:
        views: List[CaptureView] = []
        for cap in list(row.get("captures") or []):
            views.append(
                CaptureView(
                    step_index=int(cap["step_index"]),
                    raw_excerpt=str(cap.get("raw_excerpt") or ""),
                    parse_ok=bool(cap.get("parse_ok")),
                    parsed_action=cap.get("parsed_action"),
                    parsed_tool=cap.get("parsed_tool"),
                    parsed_args=dict(cap.get("parsed_args") or {}),
                    reason_code=_reason_code(cap),
                    tool_name=cap.get("tool_name"),
                    tool_success=cap.get("tool_success"),
                )
            )
        tel = row.get("s2_telemetry") or {}
        first = views[0].parsed_tool if views else None
        trials_out.append(
            FrozenTrial(
                case_id=str(row["case_id"]),
                condition=str(row["condition"]),
                s2_enabled=bool(row["s2_enabled"]),
                t2_enabled=bool(row["t2_enabled"]),
                trial_index=int(row["trial_index"]),
                query=str(row["query"]),
                expected_tool=str(row.get("expected_tool") or EXPECTED_TOOL),
                first_tool=str(first or ""),
                preferred_hint=tel.get("preferred_tool_hint_value"),
                hint_emitted=bool(tel.get("preferred_tool_hint_emitted")),
                planner_followed_hint=bool(tel.get("planner_followed_hint")),
                reason_codes=tuple(v.reason_code or "" for v in views),
                tool_sequence=tuple(v.parsed_tool or "" for v in views),
                raw_first_excerpt=views[0].raw_excerpt if views else "",
                captures=tuple(views),
            )
        )
    return tuple(trials_out)


def assert_corpus_integrity(trials: Optional[Tuple[FrozenTrial, ...]] = None) -> None:
    trials = trials or reconstruct_trials()
    assert len(trials) == 10
    assert all(t.case_id == TARGET_CASE for t in trials)
    assert all(t.condition in TARGET_CONDITIONS for t in trials)
    assert sum(1 for t in trials if t.condition == "10") == 5
    assert sum(1 for t in trials if t.condition == "11") == 5
    assert all(t.s2_enabled for t in trials)
    assert all(t.hint_emitted for t in trials)
    assert all(t.preferred_hint == EXPECTED_TOOL for t in trials)
    assert all(t.first_tool == STUBBORN_TOOL for t in trials)
    assert all(t.planner_followed_hint is False for t in trials)
    assert all(t.reason_codes[0] == "initial_retrieval" for t in trials)


def build_target_samples(
    trials: Optional[Tuple[FrozenTrial, ...]] = None,
) -> List[SelectionSample]:
    trials = trials or reconstruct_trials()
    samples: List[SelectionSample] = []
    for trial in trials:
        samples.append(
            SelectionSample(
                sample_id="P5-TARGET-%s-t%s" % (trial.condition, trial.trial_index),
                panel="TARGET",
                query=trial.query,
                exposed_tools=DEFAULT_EXPOSED,
                selected_tool=trial.first_tool,
                expected_tool=EXPECTED_TOOL,
                must_not_force_tool=None,
                intent_class="catalog_search",
                preferred_hint=trial.preferred_hint,
                notes="frozen P4 GQ-131 first-action under S2 ON",
            )
        )
    return samples


def product_descriptions(repo_root: Optional[Path] = None) -> Dict[str, str]:
    return dict(load_corpus_payload(repo_root).get("product_descriptions") or {})


def advisory_prompt_snippets(repo_root: Optional[Path] = None) -> List[str]:
    return list(load_corpus_payload(repo_root).get("product_advisory_prompt_snippets") or [])

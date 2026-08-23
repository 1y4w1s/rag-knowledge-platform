"""Load frozen MEMORY P3 GA-9/GA-10 corpus for offline ablation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.memory_utilization_ablation.models import (
    CORPUS_SCHEMA,
    FrozenTrial,
    MemorySeed,
)

CORPUS_REL = Path("tests/fixtures/l4_memory_capability/memory-p4-p3-frozen-corpus.json")


def corpus_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / CORPUS_REL


def load_corpus_payload(repo_root: Path | None = None) -> dict[str, Any]:
    path = corpus_path(repo_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"unexpected corpus schema: {payload.get('schema_version')}")
    return payload


def _seeds_for(case_id: str, cases: dict[str, Any]) -> tuple[MemorySeed, ...]:
    raw = (cases.get(case_id) or {}).get("seeds") or []
    return tuple(
        MemorySeed(
            key=str(item["key"]),
            memory_type=str(item.get("memory_type") or "preference"),
            value=dict(item.get("value") or {}),
        )
        for item in raw
    )


def reconstruct_trials(repo_root: Path | None = None) -> tuple[FrozenTrial, ...]:
    payload = load_corpus_payload(repo_root)
    cases = payload.get("cases") or {}
    trials: list[FrozenTrial] = []
    for raw in payload.get("trials") or []:
        case_id = str(raw["case_id"])
        condition = str(raw["condition"])
        query = str((cases.get(case_id) or {}).get("query") or "")
        outcome = raw.get("outcome") or {}
        seeds = _seeds_for(case_id, cases) if condition == "WITH_MEMORY" else ()
        trials.append(
            FrozenTrial(
                case_id=case_id,
                trial_index=int(raw["trial_index"]),
                condition=condition,
                l3_passed=bool((raw.get("L3_EXPOSED") or {}).get("passed")),
                l4_passed=bool((raw.get("L4_UTILIZED") or {}).get("passed")),
                l5_passed=bool((raw.get("L5_TASK_BENEFIT") or {}).get("passed")),
                query=query,
                seeds=seeds,
                propositions=tuple(raw.get("proposition_records") or ()),
                output_excerpt=str(raw.get("output_excerpt") or ""),
                tool_query=raw.get("tool_query"),
                terminal_action=outcome.get("terminal_action"),
                capped=bool(outcome.get("capped")),
                steps=tuple(outcome.get("steps") or ()),
                exposure_event_count=len(raw.get("exposure_events") or ()),
            )
        )
    return tuple(trials)


def assert_corpus_integrity(trials: tuple[FrozenTrial, ...] | None = None) -> None:
    trials = trials if trials is not None else reconstruct_trials()
    with_mem = [t for t in trials if t.condition == "WITH_MEMORY"]
    without = [t for t in trials if t.condition == "WITHOUT_MEMORY"]
    if len(with_mem) != 10 or len(without) != 10:
        raise AssertionError(
            f"expected 10 WITH + 10 WITHOUT seeded trials, got "
            f"{len(with_mem)}/{len(without)}"
        )
    if not all(t.l3_passed for t in with_mem):
        raise AssertionError("P3 integrity: WITH_MEMORY L3 must be 10/10")
    if any(t.l4_passed for t in with_mem):
        raise AssertionError("P3 integrity: WITH_MEMORY L4 must remain 0/10")
    if any(t.l5_passed for t in with_mem):
        raise AssertionError("P3 integrity: WITH_MEMORY L5 must remain 0/10")


def frozen_format_meta(repo_root: Path | None = None) -> dict[str, Any]:
    return dict(load_corpus_payload(repo_root).get("frozen_format") or {})


def baseline_formatted_block(
    seeds: tuple[MemorySeed, ...], *, double_wrap: bool = True
) -> str:
    """Reconstruct C0 product-like formatting (disclaimer + JSON lines)."""
    inner_lines = [
        f"- [long_term] {s.key}: {json.dumps(s.value, ensure_ascii=False, sort_keys=True)} "
        f"({s.memory_type}) importance=0.50"
        for s in seeds
    ]
    body = "用户长期偏好（仅供参考，不覆盖检索结果）：\n" + "\n".join(inner_lines)
    if not double_wrap:
        return body
    return f"用户长期偏好（仅供参考，不覆盖检索结果）：\n{body}"

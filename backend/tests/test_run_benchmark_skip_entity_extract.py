"""Enterprise benchmark-only skip_entity_extract bypass (Task B).

Deterministic contract tests — no LM Studio, no full benchmark run.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.core.config import settings

REPO = Path(__file__).resolve().parents[2]
RUN_BENCHMARK = REPO / "scripts" / "run_benchmark.py"
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
BASELINE = REPO / "backend" / "tests" / "benchmark" / "baseline.json"


def _load_run_benchmark():
    spec = importlib.util.spec_from_file_location("run_benchmark", RUN_BENCHMARK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _ci_text() -> str:
    return CI_YML.read_text(encoding="utf-8")


def _baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _extract_run_command(ci_text: str, step_name: str) -> str:
    """Return the python run_benchmark.py command for a named CI step."""
    marker = f"- name: {step_name}"
    start = ci_text.index(marker)
    run_block = ci_text[start:].split("run: |", 1)[1]
    for line in run_block.splitlines():
        stripped = line.strip()
        if stripped.startswith("python scripts/run_benchmark.py"):
            return stripped
    raise AssertionError(f"No run_benchmark command in step {step_name!r}")


# --- B7.1 / B7.2: CLI default OFF, explicit flag ON ---


def test_cli_default_skip_entity_extract_off() -> None:
    mod = _load_run_benchmark()
    args = mod.parse_args([])
    assert args.skip_entity_extract is False


def test_cli_explicit_skip_entity_extract_on() -> None:
    mod = _load_run_benchmark()
    args = mod.parse_args(["--skip-entity-extract"])
    assert args.skip_entity_extract is True


def test_cli_flag_not_auto_enabled_for_enterprise_dataset() -> None:
    """B2: must NOT auto-enable based on dataset==enterprise_qa."""
    mod = _load_run_benchmark()
    args = mod.parse_args(["--dataset", "enterprise_qa"])
    assert args.skip_entity_extract is False


# --- B7.3 / B7.4: real BGE / embedding provider unchanged ---


def test_skip_flag_does_not_change_embedding_provider() -> None:
    mod = _load_run_benchmark()
    provider_before = settings.embedding_provider
    model_before = settings.embedding_model
    with mod._skip_entity_extract_context(True):
        assert settings.embedding_provider == provider_before
        assert settings.embedding_model == model_before
    assert settings.embedding_provider == provider_before
    assert settings.embedding_model == model_before


def test_config_embedding_provider_default_is_bge() -> None:
    """Production config default (not pytest conftest mock override)."""
    from app.core.config import Settings

    assert Settings.model_fields["embedding_provider"].default == "bge"


# --- B7.5: settings restored after run ---


def test_skip_entity_extract_setting_restored_after_context() -> None:
    mod = _load_run_benchmark()
    assert settings.skip_entity_extract is False
    with mod._skip_entity_extract_context(True):
        assert settings.skip_entity_extract is True
    assert settings.skip_entity_extract is False


def test_skip_entity_extract_context_noop_when_disabled() -> None:
    mod = _load_run_benchmark()
    assert settings.skip_entity_extract is False
    with mod._skip_entity_extract_context(False):
        assert settings.skip_entity_extract is False
    assert settings.skip_entity_extract is False


# --- B7.6 / B7.7 / B7.8: CI command scope ---


def test_enterprise_ci_command_has_explicit_bypass() -> None:
    cmd = _extract_run_command(_ci_text(), "Run Enterprise QA benchmark (C3 gate)")
    assert "--skip-entity-extract" in cmd
    assert "--dataset enterprise_qa" in cmd


def test_golden_ci_command_has_no_bypass() -> None:
    cmd = _extract_run_command(_ci_text(), "Run Golden QA benchmark (real embeddings)")
    assert "--skip-entity-extract" not in cmd
    assert "--dataset golden_qa" in cmd


def test_advanced_ci_command_has_no_bypass() -> None:
    cmd = _extract_run_command(_ci_text(), "Run Advanced QA benchmark (C3 gate)")
    assert "--skip-entity-extract" not in cmd
    assert "--dataset advanced_qa" in cmd


# --- B7.9: product default unchanged ---


def test_production_skip_entity_extract_default_unchanged() -> None:
    assert settings.skip_entity_extract is False


# --- B7.10: Enterprise scoring contract unchanged ---


def test_enterprise_baseline_scoring_contract_unchanged() -> None:
    bl = _baseline()
    ent = bl["enterprise_qa"]
    assert ent["compare_mode"] == "gate"
    assert ent["hit_at_k"] == 0.60
    assert ent["absolute_min"] == 0.50
    assert ent["drop_fail_pp"] == 0.05
    assert ent["non_rejection"] == 90


# --- B7.11: workflow required jobs preserved ---


def test_ci_workflow_required_jobs_preserved() -> None:
    ci_text = _ci_text()
    jobs_section = ci_text.split("jobs:", 1)[1]
    job_names = set(re.findall(r"^  ([a-z][a-z0-9-]*):", jobs_section, re.MULTILINE))
    assert job_names == {"test", "alembic-check", "config-wiring", "rag-benchmark", "lint"}


# --- B7.12: baseline thresholds unchanged ---


@pytest.mark.parametrize(
    "dataset,expected_hit,expected_drop",
    [
        ("golden_qa", 0.955, 0.02),
        ("enterprise_qa", 0.60, 0.05),
        ("advanced_qa", 1.0, 0.10),
    ],
)
def test_baseline_gate_thresholds_unchanged(
    dataset: str, expected_hit: float, expected_drop: float
) -> None:
    bl = _baseline()
    entry = bl[dataset]
    assert entry["hit_at_k"] == expected_hit
    assert entry["drop_fail_pp"] == expected_drop
    assert entry["compare_mode"] == "gate"

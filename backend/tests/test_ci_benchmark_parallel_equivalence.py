"""CI Phase 2 P1 — deterministic equivalence: old serial semantics vs parallel jobs.

No LM Studio / real BGE / live Postgres. Freezes command + baseline-input identity
except job placement / artifact fan-in plumbing.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CI_YML = REPO / ".github" / "workflows" / "ci.yml"

# Frozen pre-P1 invocation strings (must stay byte-identical in run blocks).
GOLDEN_CMD = (
    "python scripts/run_benchmark.py --dataset golden_qa "
    "--mode retrieval --output text 2>&1 | tee backend/benchmark_output.txt"
)
ENTERPRISE_CMD = (
    "python scripts/run_benchmark.py --dataset enterprise_qa "
    "--mode retrieval --output text --skip-entity-extract 2>&1 | "
    "tee backend/benchmark_enterprise.txt"
)
ADVANCED_CMD = (
    "python scripts/run_benchmark.py --dataset advanced_qa "
    "--mode retrieval --output text 2>&1 | tee backend/benchmark_advanced.txt"
)
BASELINE_ENV = (
    "BENCHMARK_OUT_FILES: backend/benchmark_output.txt,"
    "backend/benchmark_enterprise.txt,backend/benchmark_advanced.txt"
)
BASELINE_PATH = "BASELINE_PATH: backend/tests/benchmark/baseline.json"
NEW_SCORER_CMD = "python3 backend/scripts/ci_new_scorer.py"
BASELINE_CHECK_CMD = "python3 backend/scripts/ci_baseline_check.py"

BENCH_STEP_ENV = {
    "DATABASE_URL: postgresql+asyncpg://ruige:changeme@localhost:5432/ruige",
    "JWT_SECRET: ${{ secrets.JWT_SECRET || '1362b8353e8306574369454872b0fb2a' }}",
    "RAG_RATE_LIMIT_MODE: bypass",
    "PYTHONPATH: backend",
    "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}",
    "RAG_TEST_PASSWORD: ${{ secrets.RAG_TEST_PASSWORD }}",
}


def _ci_text() -> str:
    return CI_YML.read_text(encoding="utf-8")


def _job_block(name: str) -> str:
    text = _ci_text()
    marker = f"  {name}:"
    start = text.index(marker)
    rest = text[start + len(marker) :]
    m = re.search(r"\n  [a-z][a-z0-9-]*:", rest)
    return marker + (rest if m is None else rest[: m.start()])


def test_benchmark_invocation_commands_unchanged() -> None:
    text = _ci_text()
    assert GOLDEN_CMD in text
    assert ENTERPRISE_CMD in text
    assert ADVANCED_CMD in text
    assert text.count(GOLDEN_CMD) == 1
    assert text.count(ENTERPRISE_CMD) == 1
    assert text.count(ADVANCED_CMD) == 1


def test_benchmark_step_env_unchanged() -> None:
    for job, step in (
        ("rag-golden", "Run Golden QA benchmark (real embeddings)"),
        ("rag-enterprise", "Run Enterprise QA benchmark (C3 gate)"),
        ("rag-advanced", "Run Advanced QA benchmark (C3 gate)"),
    ):
        block = _job_block(job)
        start = block.index(f"- name: {step}")
        chunk = block[start : start + 800]
        for line in BENCH_STEP_ENV:
            assert line in chunk, f"missing {line!r} in {job}/{step}"


def test_baseline_gate_input_equivalence() -> None:
    gate = _job_block("benchmark-gate")
    assert BASELINE_PATH in gate
    assert BASELINE_ENV in gate
    assert BASELINE_CHECK_CMD in gate
    # Artifacts land at the same relative paths the old single-job tee used.
    assert "name: benchmark-golden" in _job_block("rag-golden")
    assert "name: benchmark-enterprise" in _job_block("rag-enterprise")
    assert "name: benchmark-advanced" in _job_block("rag-advanced")
    assert "path: backend/benchmark_output.txt" in _job_block("rag-golden")
    assert "path: backend/benchmark_enterprise.txt" in _job_block("rag-enterprise")
    assert "path: backend/benchmark_advanced.txt" in _job_block("rag-advanced")
    for name in ("benchmark-golden", "benchmark-enterprise", "benchmark-advanced"):
        assert f"name: {name}" in gate
        assert "path: backend" in gate


def test_new_scorer_command_unchanged_on_golden() -> None:
    golden = _job_block("rag-golden")
    assert NEW_SCORER_CMD in golden
    assert golden.count(NEW_SCORER_CMD) == 1


def test_dag_is_partial_not_unconditional_fanout_only() -> None:
    """P0: PARTIALLY_PARALLEL_SAFE — gate fans in; new scorer not a 4th independent job."""
    text = _ci_text()
    assert "rag-new-scorer:" not in text
    assert "needs: [rag-golden, rag-enterprise, rag-advanced]" in text
    # Dataset jobs have no needs: (start together)
    for name in ("rag-golden", "rag-enterprise", "rag-advanced"):
        block = _job_block(name)
        header = block.split("steps:", 1)[0]
        assert "needs:" not in header


def test_no_change_aware_or_cache_redesign_in_p1() -> None:
    text = _ci_text()
    assert "change-aware" not in text.lower()
    assert "corpus snapshot" not in text.lower()
    assert "embedding-cache" not in text
    assert "vector cache" not in text.lower()

"""CI Phase 2 P0/P1 — static characterization of RAG benchmark dependency graph.

Deterministic only: no LM Studio, no real BGE, no live Postgres benchmark.
P0 froze PARTIALLY_PARALLEL_SAFE; P1 applies that freeze as parallel jobs.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_BENCHMARK = REPO / "scripts" / "run_benchmark.py"
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
BASELINE_CHECK = REPO / "backend" / "scripts" / "ci_baseline_check.py"
NEW_SCORER = REPO / "backend" / "scripts" / "ci_new_scorer.py"
FIXTURES = REPO / "backend" / "tests" / "fixtures"


def _load_run_benchmark():
    spec = importlib.util.spec_from_file_location("run_benchmark", RUN_BENCHMARK)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _ci_text() -> str:
    return CI_YML.read_text(encoding="utf-8")


def _job_block(name: str) -> str:
    text = _ci_text()
    marker = f"  {name}:"
    start = text.index(marker)
    rest = text[start + len(marker) :]
    m = re.search(r"\n  [a-z][a-z0-9-]*:", rest)
    return marker + (rest if m is None else rest[: m.start()])


def test_ci_datasets_are_three_separate_parallel_jobs() -> None:
    text = _ci_text()
    assert "Run Golden QA benchmark" in text
    assert "Run Enterprise QA benchmark" in text
    assert "Run Advanced QA benchmark" in text
    # Phase 2 P1: three dataset jobs + fan-in gate (no monolithic rag-benchmark).
    assert "rag-benchmark:" not in text
    assert "rag-golden:" in text
    assert "rag-enterprise:" in text
    assert "rag-advanced:" in text
    assert "benchmark-gate:" in text
    gate = _job_block("benchmark-gate")
    assert "needs: [rag-golden, rag-enterprise, rag-advanced]" in gate


def test_dataset_corpus_isolation_matrix() -> None:
    mod = _load_run_benchmark()
    ds = mod.DATASETS
    assert ds["golden_qa"]["docs"] == ["golden_handbook.md"]
    assert ds["advanced_qa"]["docs"] == ["golden_handbook.md"]
    assert ds["enterprise_qa"]["docs"] is None  # runtime glob acme_*.md
    acme = sorted(p.name for p in FIXTURES.glob("acme_*.md"))
    assert len(acme) >= 1
    assert (FIXTURES / "golden_handbook.md").is_file()
    # Cross-dataset fixture reuse: Golden↔Advanced YES (same file); Enterprise NO.
    assert "golden_handbook.md" not in acme


def test_per_invocation_creates_fresh_user_and_kb() -> None:
    """Each run_retrieval registers a new user + KB (uuid) — no prior-dataset reuse."""
    src = RUN_BENCHMARK.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_retrieval"
    )
    body = ast.unparse(fn)
    assert "uuid.uuid4()" in body or "uuid.UUID" in body
    assert "/api/v1/auth/register" in body
    assert "/api/v1/knowledge-bases" in body
    assert "bm-" in body
    # No teardown / shared fixed IDs — leftovers accumulate; retrieval stays kb-scoped
    assert "DELETE FROM" not in body
    assert "ORDER BY created_at" not in body  # does not reuse prior KB


def test_baseline_gate_reads_only_text_artifacts() -> None:
    src = BASELINE_CHECK.read_text(encoding="utf-8")
    assert "BENCHMARK_OUT_FILES" in src
    assert "SessionLocal" not in src
    assert "retrieve_chunks" not in src
    assert "DATABASE_URL" not in src
    # Default / CI env lists the three tee files
    ci = _ci_text()
    assert "backend/benchmark_output.txt" in ci
    assert "backend/benchmark_enterprise.txt" in ci
    assert "backend/benchmark_advanced.txt" in ci
    assert "ci_baseline_check.py" in ci
    gate = _job_block("benchmark-gate")
    assert "ci_baseline_check.py" in gate
    assert "BENCHMARK_OUT_FILES: backend/benchmark_output.txt,backend/benchmark_enterprise.txt,backend/benchmark_advanced.txt" in gate


def test_new_scorer_has_hidden_latest_kb_db_dependency() -> None:
    """CRITICAL for parallel fan-in: new scorer is NOT artifact-only."""
    src = NEW_SCORER.read_text(encoding="utf-8")
    assert "ORDER BY created_at DESC LIMIT 1" in src
    assert "knowledge_bases" in src
    assert "SessionLocal" in src
    assert "retrieve_chunks" in src
    # Uses golden cases but KB = whatever finished last in the shared DB
    assert "golden_qa" in src
    assert "BENCHMARK_OUT" not in src
    assert "benchmark_output.txt" not in src


def test_keep_new_scorer_with_golden() -> None:
    """KEEP_NEW_SCORER_WITH_GOLDEN: same job DB as Golden; not after Advanced/Enterprise."""
    golden = _job_block("rag-golden")
    enterprise = _job_block("rag-enterprise")
    advanced = _job_block("rag-advanced")
    gate = _job_block("benchmark-gate")
    assert "Run Golden QA benchmark" in golden
    assert "New scoring engine comparison" in golden
    g = golden.index("Run Golden QA benchmark")
    n = golden.index("New scoring engine comparison")
    assert g < n
    assert "New scoring engine comparison" not in enterprise
    assert "New scoring engine comparison" not in advanced
    assert "New scoring engine comparison" not in gate
    assert "ci_new_scorer.py" not in gate


def test_fastembed_cache_key_is_immutable_shared() -> None:
    text = _ci_text()
    assert "path: ~/.cache/huggingface" in text
    keys = re.findall(
        r"key:\s*(fastembed-bge-small-zh-\$\{\{\s*runner\.os\s*\}\})",
        text,
    )
    assert len(keys) == 3, "each parallel dataset job must keep immutable fastembed cache"
    for key in keys:
        assert "github.sha" not in key
        assert "github.run_id" not in key


def test_parallel_safety_classification_freeze() -> None:
    """Human-readable freeze for Phase 2 P1 — asserted as documentation contract."""
    # Datasets: INDEPENDENT (fresh UUID state; kb-scoped retrieval).
    # Baseline: ARTIFACT_FAN_IN_POSSIBLE = YES.
    # New scorer: DEPENDENT on shared DB latest KB → overall PARTIALLY_PARALLEL_SAFE.
    classification = "PARTIALLY_PARALLEL_SAFE"
    assert classification == "PARTIALLY_PARALLEL_SAFE"
    artifact_fan_in_possible = True
    new_scorer_fan_in_possible = False
    keep_new_scorer_with_golden = True
    assert artifact_fan_in_possible and not new_scorer_fan_in_possible
    assert keep_new_scorer_with_golden

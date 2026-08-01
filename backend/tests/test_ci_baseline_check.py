"""C3/C4：ci_baseline_check — Golden/Ent/Adv gate；CRAG sample/full informational。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECK = REPO / "backend" / "scripts" / "ci_baseline_check.py"


def _run(env: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    full = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=cwd,
        env=full,
        capture_output=True,
        text=True,
    )


def test_gate_fails_on_golden_drop(tmp_path: Path):
    baseline = {
        "golden_qa": {
            "hit_at_k": 0.95,
            "compare_mode": "gate",
            "drop_fail_pp": 0.02,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "out.txt"
    out.write_text(
        "BENCHMARK_SUMMARY dataset=golden_qa hit_at_k=0.900000 total=89\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 1
    assert "FAIL" in r.stdout


def test_gate_fails_on_enterprise_drop(tmp_path: Path):
    """C3：Enterprise gate — 掉 ≥5pp → exit 1。"""
    baseline = {
        "enterprise_qa": {
            "hit_at_k": 0.922,
            "compare_mode": "gate",
            "drop_fail_pp": 0.05,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "ent.txt"
    out.write_text(
        "BENCHMARK_SUMMARY dataset=enterprise_qa hit_at_k=0.800000 total=92\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 1
    assert "FAIL" in r.stdout
    assert "enterprise_qa" in r.stdout


def test_gate_passes_enterprise_within_threshold(tmp_path: Path):
    baseline = {
        "enterprise_qa": {
            "hit_at_k": 0.922,
            "compare_mode": "gate",
            "drop_fail_pp": 0.05,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "ent.txt"
    # -3pp 未超 -5pp
    out.write_text(
        "BENCHMARK_SUMMARY dataset=enterprise_qa hit_at_k=0.892000 total=92\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 0
    assert "PASS" in r.stdout


def test_gate_fails_on_advanced_drop(tmp_path: Path):
    """C3：Advanced gate — 掉 ≥10pp（≈≥2/14）→ exit 1。"""
    baseline = {
        "advanced_qa": {
            "hit_at_k": 1.0,
            "compare_mode": "gate",
            "drop_fail_pp": 0.10,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "adv.txt"
    out.write_text(
        "BENCHMARK_SUMMARY dataset=advanced_qa hit_at_k=0.857143 total=14\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 1
    assert "FAIL" in r.stdout
    assert "advanced_qa" in r.stdout


def test_informational_crag_warns_but_passes(tmp_path: Path):
    """C3：CRAG 仍 informational — 掉分 WARN，不挡合并。"""
    baseline = {
        "crag_sample_100": {
            "hit_at_k": 0.26,
            "compare_mode": "informational",
            "drop_warn_pp": 0.05,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "crag.txt"
    out.write_text(
        "BENCHMARK_SUMMARY dataset=crag_sample_100 hit_at_k=0.180000 total=100\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 0
    assert "WARN" in r.stdout
    assert "不挡合并" in r.stdout


def test_multi_dataset_mixed_modes(tmp_path: Path):
    """Ent gate 绿 + CRAG informational OK。"""
    baseline = {
        "enterprise_qa": {
            "hit_at_k": 0.90,
            "compare_mode": "gate",
            "drop_fail_pp": 0.05,
        },
        "crag_sample_100": {
            "hit_at_k": 0.26,
            "compare_mode": "informational",
            "drop_warn_pp": 0.05,
        },
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    ent = tmp_path / "e.txt"
    crag = tmp_path / "c.txt"
    ent.write_text(
        "BENCHMARK_SUMMARY dataset=enterprise_qa hit_at_k=0.910000 total=92\n",
        encoding="utf-8",
    )
    crag.write_text(
        "BENCHMARK_SUMMARY dataset=crag_sample_100 hit_at_k=0.270000 total=100\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": f"{ent},{crag}",
        },
        tmp_path,
    )
    assert r.returncode == 0
    assert "enterprise_qa" in r.stdout
    assert "crag_sample_100" in r.stdout


def test_informational_crag_full_warns_but_passes(tmp_path: Path):
    """C4：crag_full informational — 掉分 WARN，returncode==0。"""
    baseline = {
        "crag_full": {
            "hit_at_k": 0.26,
            "compare_mode": "informational",
            "drop_warn_pp": 0.05,
        }
    }
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps(baseline), encoding="utf-8")
    out = tmp_path / "crag_full.txt"
    out.write_text(
        "BENCHMARK_SUMMARY dataset=crag_full hit_at_k=0.180000 total=4409\n",
        encoding="utf-8",
    )
    r = _run(
        {
            "BASELINE_PATH": str(bl),
            "BENCHMARK_OUT_FILES": str(out),
        },
        tmp_path,
    )
    assert r.returncode == 0
    assert "WARN" in r.stdout
    assert "不挡合并" in r.stdout
    assert "crag_full" in r.stdout

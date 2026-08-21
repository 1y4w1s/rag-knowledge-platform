"""G1-W2：Critic rules 误杀汇总纯函数 + 生产开关仍关。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.core.config import settings

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    path = _SCRIPTS / name
    mod_name = f"_g1_script_{name.removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


fk = _load_script("g1_critic_falsekill_summary.py")


def _chunk(content: str) -> dict:
    return {"content": content, "doc_name": "制度.md", "similarity": 0.9}


def test_production_switches_still_off() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False


def test_falsekill_rates_on_fake_tiers() -> None:
    """层 A：1 误杀 / 2；层 B：1 正确拦截 / 1；层 C：拒答放行。"""
    payload = {
        "on_fail": "fail_closed",
        "samples": [
            {
                "sample_id": "a-pass",
                "tier": "A",
                "answer": "培训费需按比例退还[片段1]。",
                "chunks": [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")],
                "human_should_pass": True,
                "synthetic": True,
            },
            {
                "sample_id": "a-kill",
                "tier": "A",
                "answer": "培训费需按比例退还[片段9]。",
                "chunks": [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")],
                "human_should_pass": True,
                "synthetic": True,
            },
            {
                "sample_id": "b-catch",
                "tier": "B",
                "answer": "年假每年15天且可拆分使用[片段1]。",
                "chunks": [_chunk("会议室预约需提前一天申请。")],
                "human_should_pass": False,
                "synthetic": True,
            },
            {
                "sample_id": "c-refusal",
                "tier": "C",
                "answer": "知识库中未找到相关内容。",
                "chunks": [_chunk("无关内容。")],
                "human_should_pass": True,
                "synthetic": True,
            },
        ],
    }
    samples, on_fail = fk.parse_samples(payload)
    details = fk.evaluate_samples_rules(samples)
    report = fk.compute_falsekill_report(details, on_fail=on_fail)

    assert report["protocol"] == "g1_critic_rules_falsekill_v1"
    assert report["critic_mode"] == "rules"
    assert report["on_fail"] == "fail_closed"
    assert report["n_tier_a"] == 2
    assert report["n_tier_b"] == 1
    assert report["n_tier_c"] == 1
    assert report["false_kill_rate"] == pytest.approx(0.5)
    assert report["catch_rate"] == pytest.approx(1.0)
    assert report["refusal_ok_rate"] == pytest.approx(1.0)
    assert report["synthetic_share_a"] == pytest.approx(1.0)

    by_id = {d["sample_id"]: d for d in report["details"]}
    assert by_id["a-pass"]["false_kill"] is False
    assert by_id["a-kill"]["false_kill"] is True
    assert by_id["b-catch"]["miss"] is False
    assert by_id["c-refusal"]["refusal_ok"] is True

    # 汇总不抬生产默认
    assert settings.rag_critic_enabled is False


def test_via_run_critic_restores_settings(tmp_path: Path) -> None:
    """--via-run-critic 进程内临时开，结束后 settings 仍 False。"""
    payload = {
        "samples": [
            {
                "sample_id": "a1",
                "tier": "A",
                "answer": "培训费需按比例退还[片段1]。",
                "chunks": [_chunk("员工参加培训后提前离职，需按比例退还培训费用。")],
                "synthetic": True,
            }
        ]
    }
    path = tmp_path / "traj.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert settings.rag_critic_enabled is False
    report = fk.build_report_from_path(path, via_run_critic=True)
    assert report["protocol"] == "g1_critic_rules_falsekill_v1"
    assert report["false_kill_rate"] == pytest.approx(0.0)
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False

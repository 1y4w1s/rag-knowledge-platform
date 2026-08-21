"""U3-W1：归因↔人工一致率纯函数 + RAGCap lite 汇总（零 LLM / 零 DB）。"""

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
    mod_name = f"_u3_script_{name.removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # dataclasses need the module registered before exec_module
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


agreement = _load_script("u3_attribution_agreement.py")
ragcap = _load_script("u3_ragcap_lite_summary.py")


def test_production_switches_still_off() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False


def test_agreement_rate_on_fake_rows() -> None:
    """5 条假明细：3 一致 / 2 覆盖 → agreement_rate=0.6。"""
    payload = {
        "items": [
            {
                "feedback_id": "a1",
                "machine_label": "retrieval_miss",
                "human_label": "retrieval_miss",
                "source": "p3",
                "synthetic": True,
            },
            {
                "feedback_id": "a2",
                "machine_label": "generation_bad",
                "human_label": "generation_bad",
                "source": "p3",
                "synthetic": True,
            },
            {
                "feedback_id": "a3",
                "machine_label": "refusal_wrong",
                "human_label": "refusal_wrong",
                "source": "p1",
                "synthetic": False,
            },
            {
                "feedback_id": "a4",
                "machine_label": "retrieval_miss",
                "human_label": "generation_bad",
                "source": "p3",
                "synthetic": True,
            },
            {
                "feedback_id": "a5",
                "machine_label": "unknown",
                "human_label": "doc_gap",
                "source": "p2",
                "synthetic": False,
            },
        ]
    }
    rows = agreement.parse_human_items(payload)
    report = agreement.compute_agreement_report(rows)

    assert report["protocol"] == "u3_attribution_agreement_v1"
    assert report["n"] == 5
    assert report["agreement_rate"] == pytest.approx(0.6)
    assert report["sources"] == {"p1": 1, "p2": 1, "p3": 3}
    assert report["unknown_rate"] == pytest.approx(0.2)
    assert report["override_rate"] == pytest.approx(0.4)
    assert report["n_tier"] == "protocol_smoke"

    # retrieval_miss: human support=1 (a1), machine also said it on a1+a4 → recall=1, precision=0.5
    pl = report["per_label"]["retrieval_miss"]
    assert pl["support"] == 1
    assert pl["recall"] == pytest.approx(1.0)
    assert pl["precision"] == pytest.approx(0.5)

    # generation_bad: human a2+a4 → support=2; machine hit a2 only among those → recall=0.5
    gb = report["per_label"]["generation_bad"]
    assert gb["support"] == 2
    assert gb["recall"] == pytest.approx(0.5)


def test_join_export_fills_machine_label(tmp_path: Path) -> None:
    export = {
        "version": "1.2",
        "kind": "thumbs_down_candidates",
        "candidates": [
            {
                "feedback_id": "fb-1",
                "attribution": {"label": "doc_gap", "method": "rules_v1"},
            }
        ],
    }
    human = {
        "items": [
            {
                "feedback_id": "fb-1",
                "human_label": "doc_gap",
                "source": "p1",
                "synthetic": False,
            }
        ]
    }
    export_path = tmp_path / "export.json"
    human_path = tmp_path / "human.json"
    export_path.write_text(json.dumps(export), encoding="utf-8")
    human_path.write_text(json.dumps(human), encoding="utf-8")

    report = agreement.build_report_from_paths(
        human_path=human_path, export_path=export_path
    )
    assert report["n"] == 1
    assert report["agreement_rate"] == 1.0
    assert report["details"][0]["machine_label"] == "doc_gap"


def test_ragcap_lite_summary() -> None:
    report = ragcap.summarize_ragcap_lite(ragcap.SCORECARD_TEMPLATE)
    assert report["protocol"] == "u3_ragcap_lite_v1"
    assert report["n"] == 4
    assert report["by_capability"]["planning"]["pass_rate"] == 1.0
    assert report["by_capability"]["grounded_reasoning"]["pass_rate"] == 0.0

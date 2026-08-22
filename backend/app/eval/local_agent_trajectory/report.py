"""Write gitignored W8 P0 JSON artifacts (no secrets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.local_model_profile.report import sanitize_for_report


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_for_report(payload)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_output_dir() -> Path:
    repo = Path(__file__).resolve().parents[4]
    return repo / "artifacts" / "benchmarks" / "tmp" / "reports"

"""JSON report writer for LocalModelProfile (no secrets)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.eval.local_model_profile.schema import LocalModelProfile

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|password|secret|token)",
    re.IGNORECASE,
)


def sanitize_for_report(data: Any) -> Any:
    """Drop credential-like keys recursively before persistence."""
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            if _SECRET_KEY_RE.search(str(key)):
                continue
            out[str(key)] = sanitize_for_report(value)
        return out
    if isinstance(data, list):
        return [sanitize_for_report(x) for x in data]
    return data


def profile_to_json(profile: LocalModelProfile) -> str:
    payload = sanitize_for_report(profile.to_dict())
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_profile_report(profile: LocalModelProfile, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile_to_json(profile), encoding="utf-8")
    return path


def load_profile_report(path: str | Path) -> LocalModelProfile:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile report must be a JSON object")
    return LocalModelProfile.from_dict(raw)

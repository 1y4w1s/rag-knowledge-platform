"""Benchmark-only C1 relevance-label toggle for MEMORY C1 real revalidation.

Does NOT change production defaults (agent_memory_relevance_label_enabled=False).
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.eval.memory_capability.p3_flags import (
    MEMORY_P3_FLAG_NAMES,
    apply_memory_p3_flags,
    restore_memory_p3_flags,
)

C1_FLAG_NAME = "agent_memory_relevance_label_enabled"


def assert_production_c1_default() -> bool:
    """True when config class default for C1 relevance label is False."""
    field = settings.model_fields.get(C1_FLAG_NAME)
    if field is None:
        return getattr(settings, C1_FLAG_NAME) is False
    return field.default is False


def apply_memory_c1_flags(*, memory_enabled: bool, c1_enabled: bool) -> dict[str, Any]:
    """P3 benchmark flags + per-trial C1 relevance framing gate."""
    saved = apply_memory_p3_flags(memory_enabled=memory_enabled)
    saved[C1_FLAG_NAME] = getattr(settings, C1_FLAG_NAME)
    setattr(settings, C1_FLAG_NAME, bool(c1_enabled))
    return saved


def restore_memory_c1_flags(saved: dict[str, Any]) -> None:
    c1_val = saved.pop(C1_FLAG_NAME, False)
    restore_memory_p3_flags({k: v for k, v in saved.items() if k in MEMORY_P3_FLAG_NAMES})
    setattr(settings, C1_FLAG_NAME, c1_val)

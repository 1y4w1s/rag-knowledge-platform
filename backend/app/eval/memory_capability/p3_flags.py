"""Benchmark-only flags for MEMORY P3 real capability measurement.

Does NOT change production defaults. exposure_trace default remains False.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

MEMORY_P3_FLAG_NAMES: tuple[str, ...] = (
    "agent_l3_next_action_enabled",
    "agent_l4_stop_policy_enabled",
    "agent_l4_evidence_matcher_enabled",
    "agent_memory_enabled",
    "agent_memory_exposure_trace_enabled",
    "skip_entity_extract",
)


def apply_memory_p3_flags(*, memory_enabled: bool) -> dict[str, Any]:
    """Enable L3/L4 agent path + exposure trace; gate memory load via memory_enabled."""
    saved = {name: getattr(settings, name) for name in MEMORY_P3_FLAG_NAMES}
    settings.agent_l3_next_action_enabled = True
    settings.agent_l4_stop_policy_enabled = True
    settings.agent_l4_evidence_matcher_enabled = True
    settings.agent_memory_enabled = bool(memory_enabled)
    settings.agent_memory_exposure_trace_enabled = True
    settings.skip_entity_extract = True
    return saved


def restore_memory_p3_flags(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(settings, name, value)


def assert_production_exposure_default() -> bool:
    """True when config class default for exposure trace is False (unchanged)."""
    field = settings.model_fields.get("agent_memory_exposure_trace_enabled")
    if field is None:
        return settings.agent_memory_exposure_trace_enabled is False
    return field.default is False

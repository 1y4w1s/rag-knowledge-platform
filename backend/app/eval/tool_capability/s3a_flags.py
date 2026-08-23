"""Benchmark-only S3A / S2 / T2 flag toggles for TOOL S3A real revalidation.

Does not change production defaults. Callers must restore after each trial.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

FLAG_NAMES = (
    "agent_l4_tool_contrastive_selection_enabled",
    "agent_l4_tool_preferred_hint_enabled",
    "agent_l4_task_satisfied_hint_enabled",
)


def assert_production_s3a_default() -> bool:
    """Production default for S3A must remain False."""
    from app.core.config import Settings

    return Settings.model_fields["agent_l4_tool_contrastive_selection_enabled"].default is False


def apply_s3a_isolation_flags(*, s3a_enabled: bool) -> dict[str, Any]:
    """Pure isolation: S2 OFF, T2 OFF, S3A per trial. Returns prior values."""
    saved = {name: getattr(settings, name) for name in FLAG_NAMES}
    settings.agent_l4_tool_contrastive_selection_enabled = bool(s3a_enabled)
    settings.agent_l4_tool_preferred_hint_enabled = False
    settings.agent_l4_task_satisfied_hint_enabled = False
    return saved


def restore_s3a_isolation_flags(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(settings, name, value)


def force_production_defaults() -> None:
    settings.agent_l4_tool_contrastive_selection_enabled = False
    settings.agent_l4_tool_preferred_hint_enabled = False
    settings.agent_l4_task_satisfied_hint_enabled = False

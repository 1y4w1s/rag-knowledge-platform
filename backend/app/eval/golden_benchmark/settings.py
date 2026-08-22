"""Benchmark-only settings patch (W8 P4 measurement hygiene).

Sets ``skip_entity_extract=True`` only inside benchmark/test context.
Production ``config.py`` default remains ``False``.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

BENCHMARK_FLAG_NAMES: tuple[str, ...] = (
    "embedding_provider",
    "rerank_enabled",
    "rerank_provider",
    "query_rewrite_enabled",
    "agent_l3_next_action_enabled",
    "agent_l4_stop_policy_enabled",
    "agent_l4_evidence_matcher_enabled",
    "agent_memory_enabled",
    "skip_entity_extract",
)


def apply_benchmark_settings() -> dict[str, Any]:
    """Process-local benchmark flags; restore with ``restore_benchmark_settings``."""
    saved = {name: getattr(settings, name) for name in BENCHMARK_FLAG_NAMES}
    settings.embedding_provider = "mock"
    settings.rerank_enabled = True
    settings.rerank_provider = "mock"
    settings.query_rewrite_enabled = False
    settings.agent_l3_next_action_enabled = True
    settings.agent_l4_stop_policy_enabled = True
    settings.agent_l4_evidence_matcher_enabled = True
    settings.agent_memory_enabled = True
    settings.skip_entity_extract = True
    return saved


def restore_benchmark_settings(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(settings, name, value)

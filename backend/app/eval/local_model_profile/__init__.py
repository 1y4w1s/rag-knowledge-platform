"""W7 P0 — Local Model Capability Profile + Minimal Probe Harness.

Standalone eval tooling. Does **not** raise ``agent_l4_*`` flags or change
product LLM defaults. Real run artifacts belong under
``artifacts/benchmarks/tmp/reports/`` (gitignored).
"""

from __future__ import annotations

from app.eval.local_model_profile.schema import (
    SCHEMA_VERSION,
    Environment,
    LocalModelProfile,
    ProbeResult,
    Recommendation,
    Summary,
    ThinkingMode,
)
from app.eval.local_model_profile.runner import ProbeRunner, run_profile

__all__ = [
    "SCHEMA_VERSION",
    "Environment",
    "LocalModelProfile",
    "ProbeResult",
    "ProbeRunner",
    "Recommendation",
    "Summary",
    "ThinkingMode",
    "run_profile",
]

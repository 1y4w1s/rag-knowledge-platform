"""W8 P4 Golden benchmark measurement hygiene (eval-only; not product runtime)."""

from app.eval.golden_benchmark.compatibility import (
    INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES,
    REAL_TRAJECTORY_GOLDEN_CATEGORIES,
    is_real_trajectory_category,
    is_unit_only_category,
)
from app.eval.golden_benchmark.manifest import (
    W8_P4_TIMING_VALIDATION_CASE_IDS,
    build_timing_validation_manifest,
)
from app.eval.golden_benchmark.settings import (
    apply_benchmark_settings,
    restore_benchmark_settings,
)

__all__ = [
    "INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES",
    "REAL_TRAJECTORY_GOLDEN_CATEGORIES",
    "W8_P4_TIMING_VALIDATION_CASE_IDS",
    "apply_benchmark_settings",
    "build_timing_validation_manifest",
    "is_real_trajectory_category",
    "is_unit_only_category",
    "restore_benchmark_settings",
]

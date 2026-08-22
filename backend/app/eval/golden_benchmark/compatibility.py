"""Golden subset trajectory vs unit-only category classification (W8 P4)."""

from __future__ import annotations

INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES: frozenset[str] = frozenset(
    {"REFLECTION", "DEGRADE"}
)

REAL_TRAJECTORY_GOLDEN_CATEGORIES: frozenset[str] = frozenset(
    {
        "RAG",
        "RETRIEVAL",
        "ADVERSARIAL",
        "TOOL",
        "MULTI_STEP",
        "MEMORY",
        "AUTH",
    }
)


def is_unit_only_category(category: str) -> bool:
    return category in INTENTIONALLY_NON_TRAJECTORY_GOLDEN_CATEGORIES


def is_real_trajectory_category(category: str) -> bool:
    return category in REAL_TRAJECTORY_GOLDEN_CATEGORIES

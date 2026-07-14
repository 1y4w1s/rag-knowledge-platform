"""RAG golden 生产基线（与 docs/RAG_PRODUCTION_BASELINE.md 同步 · EW-C2）。

手跑 `run_golden_production_baseline.py` 后若结果变化，须同步改此处与文档。
"""

from datetime import UTC, datetime

GOLDEN_HIT_TOTAL = 10
GOLDEN_HIT_PASSED = 10
GOLDEN_EMBEDDING_MODEL = "text-embedding-v2"
GOLDEN_BASELINE_EVALUATED_AT = datetime(2026, 7, 6, tzinfo=UTC)


def golden_hit_rate_percent() -> float | None:
    if GOLDEN_HIT_TOTAL <= 0:
        return None
    return round(GOLDEN_HIT_PASSED / GOLDEN_HIT_TOTAL * 100.0, 1)

"""W8 P1 / Gate C — EvidenceMatcher false-positive characterization (eval-only).

Does **not** modify matcher algorithm, thresholds, StopPolicy, or runtime.
"""

from __future__ import annotations

from app.eval.evidence_integrity.cases import gate_c_cases
from app.eval.evidence_integrity.runner import build_report, reproduce_f2, run_suite
from app.eval.evidence_integrity.schema import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "build_report",
    "gate_c_cases",
    "reproduce_f2",
    "run_suite",
]

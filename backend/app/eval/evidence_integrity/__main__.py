"""CLI: python -m app.eval.evidence_integrity [--json PATH]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.eval.evidence_integrity.runner import build_report, run_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate C evidence integrity characterization")
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional path to write full JSON report",
    )
    args = parser.parse_args(argv)
    results, metrics, f2 = run_suite()
    report = build_report(results, metrics, f2)
    summary = {
        "f2_reproduced": metrics.f2_reproduced,
        "case_count": metrics.case_count,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "false_positive_rate": metrics.false_positive_rate,
        "false_negative_rate": metrics.false_negative_rate,
        "coverage_false_positive_rate": metrics.coverage_false_positive_rate,
        "unsafe_finish_enabling_fp_rate": metrics.unsafe_finish_enabling_fp_rate,
        "failure_taxonomy_counts": metrics.failure_taxonomy_counts,
        "by_category": metrics.by_category,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

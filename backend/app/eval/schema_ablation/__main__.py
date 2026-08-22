"""CLI entry for W8 P7 schema ablation artifact emission."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.eval.schema_ablation.runner import build_schema_ablation_report


def main() -> None:
    parser = argparse.ArgumentParser(description="W8 P7 schema ablation offline runner")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument("--write-artifacts", action="store_true")
    args = parser.parse_args()
    report = build_schema_ablation_report(
        repo_root=args.repo_root,
        write_artifacts=args.write_artifacts,
    )
    print(report["gate_h"]["gate_h"], report["recommendation"]["recommended_fix"])


if __name__ == "__main__":
    main()

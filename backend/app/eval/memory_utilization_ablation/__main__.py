"""CLI: python -m app.eval.memory_utilization_ablation"""

from __future__ import annotations

import json
import sys

from app.eval.memory_utilization_ablation.runner import build_ablation_manifest


def main() -> int:
    payload = build_ablation_manifest()
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI: python -m app.eval.tool_remediation_ablation"""

from __future__ import annotations

import json

from app.eval.tool_remediation_ablation.runner import build_ablation_manifest


def main() -> None:
    payload = build_ablation_manifest()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

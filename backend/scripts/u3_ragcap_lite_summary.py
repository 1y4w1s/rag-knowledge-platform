"""U3-W1 · RAGCap lite 手工打分汇总（协议 u3_ragcap_lite_v1）。

只读：读已打分 JSON → 按四能力输出 pass_rate。不搬完整 RAGCap；不碰检索主路径。

用法（在 backend/）::

    python scripts/u3_ragcap_lite_summary.py --scores path/to/scores.json
    python scripts/u3_ragcap_lite_summary.py --scores scores.json --out report.json

打分文件示例（见 --print-template）::

    {
      "protocol": "u3_ragcap_lite_v1",
      "items": [
        {"capability": "planning", "id": "ex-1", "pass": 1, "note": "..."},
        {"capability": "evidence_extraction", "id": "ex-2", "pass": 0, "note": "..."}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROTOCOL = "u3_ragcap_lite_v1"
CAPABILITIES: tuple[str, ...] = (
    "planning",
    "evidence_extraction",
    "grounded_reasoning",
    "noise_robustness",
)

SCORECARD_TEMPLATE: dict[str, Any] = {
    "protocol": PROTOCOL,
    "items": [
        {
            "capability": "planning",
            "id": "plan-1",
            "pass": 1,
            "note": "depth ok; sub-queries not verbatim whole question",
        },
        {
            "capability": "evidence_extraction",
            "id": "ev-1",
            "pass": 1,
            "note": "top hits cover expect fact",
        },
        {
            "capability": "grounded_reasoning",
            "id": "gr-1",
            "pass": 0,
            "note": "claim not grounded in cited chunk",
        },
        {
            "capability": "noise_robustness",
            "id": "nr-1",
            "pass": 1,
            "note": "refused when noise dominated",
        },
    ],
}


def summarize_ragcap_lite(payload: dict[str, Any]) -> dict[str, Any]:
    """纯函数：已打分 items → 每能力 pass_rate。"""
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("scores JSON needs non-empty items[]")

    buckets: dict[str, list[int]] = defaultdict(list)
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"items[{i}] must be object")
        cap = raw.get("capability")
        if cap not in CAPABILITIES:
            raise ValueError(
                f"items[{i}].capability must be one of {list(CAPABILITIES)}; got {cap!r}"
            )
        p = raw.get("pass")
        if p not in (0, 1, True, False):
            raise ValueError(f"items[{i}].pass must be 0/1; got {p!r}")
        buckets[str(cap)].append(1 if p else 0)

    by_cap: dict[str, dict[str, float | int]] = {}
    for cap in CAPABILITIES:
        scores = buckets.get(cap, [])
        n = len(scores)
        by_cap[cap] = {
            "n": n,
            "pass_rate": round(sum(scores) / n, 6) if n else 0.0,
        }

    total_n = sum(int(v["n"]) for v in by_cap.values())
    return {
        "protocol": PROTOCOL,
        "n": total_n,
        "by_capability": by_cap,
        "notes": "RAGCap lite library-internal spotcheck — not a CI gate; not full RAGCap-Bench",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U3-W1 RAGCap lite scorecard summary")
    parser.add_argument("--scores", type=Path, default=None, help="Hand-scored JSON")
    parser.add_argument("--out", type=Path, default=None, help="Write report JSON")
    parser.add_argument(
        "--print-template",
        action="store_true",
        help="Print a blank-ish scorecard template and exit",
    )
    args = parser.parse_args(argv)

    if args.print_template:
        print(json.dumps(SCORECARD_TEMPLATE, ensure_ascii=False, indent=2))
        return 0

    if args.scores is None:
        print("error: --scores required (or use --print-template)", file=sys.stderr)
        return 1

    try:
        payload = json.loads(args.scores.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("scores JSON must be an object")
        report = summarize_ragcap_lite(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

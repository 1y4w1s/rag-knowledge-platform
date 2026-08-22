"""CLI: python -m app.eval.tool_capability.p2_real

Real LM Studio TOOL P2 benchmark (GQ-131/132/149).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.tool_capability.p2_runner import run_tool_p2_benchmark


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.eval.tool_capability.p2_real")
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default="zai-org/glm-4.6v-flash")
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.thinking != "off":
        print("ERROR: thinking must be OFF for TOOL P2", file=sys.stderr)
        return 2
    payload = asyncio.run(
        run_tool_p2_benchmark(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
        )
    )
    print(
        f"wrote {payload.get('output_path')} classification={payload.get('classification')} "
        f"primary={payload.get('primary_score')} trials={payload.get('trial_success')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

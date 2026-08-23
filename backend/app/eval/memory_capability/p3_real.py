"""CLI: python -m app.eval.memory_capability.p3_real

MEMORY P3 real LM Studio capability measurement (GA-9..GA-12).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.memory_capability.p3_runner import run_memory_p3_benchmark


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.eval.memory_capability.p3_real")
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default="zai-org/glm-4.6v-flash")
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument("--probe-only", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.thinking != "off":
        print("ERROR: thinking must be OFF for MEMORY P3", file=sys.stderr)
        return 2
    payload = asyncio.run(
        run_memory_p3_benchmark(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
            probe_only=args.probe_only,
        )
    )
    print(
        f"wrote {payload.get('output_path')} state={payload.get('state')} "
        f"l3={payload.get('l3_proven')} classification={payload.get('classification')} "
        f"trials={payload.get('scored_model_trajectories')}"
    )
    if payload.get("state") == "MEMORY_P3_BLOCKED_L3":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

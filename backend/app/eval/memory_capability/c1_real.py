"""CLI: python -m app.eval.memory_capability.c1_real

MEMORY C1 real LM Studio revalidation (GA-9/GA-10 × OFF/ON/WITHOUT × 5).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.memory_capability.c1_runner import run_memory_c1_revalidation


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.eval.memory_capability.c1_real")
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default="zai-org/glm-4.6v-flash")
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument("--keep-gpu", action="store_true", help="Do not unload LM Studio after run")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.thinking != "off":
        print("ERROR: thinking must be OFF for MEMORY C1 revalidation", file=sys.stderr)
        return 2
    payload = asyncio.run(
        run_memory_c1_revalidation(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
            release_gpu=not args.keep_gpu,
        )
    )
    m = payload.get("metrics") or {}
    l3 = m.get("L3_EXPOSED") or {}
    l4 = m.get("L4_UTILIZED") or {}
    l5 = m.get("L5_TASK_BENEFIT") or {}
    print(
        f"wrote {payload.get('output_path')} state={payload.get('state')} "
        f"class={payload.get('classification')} trials={m.get('scored_trajectories')} "
        f"L3_OFF={l3.get('OFF_WITH_MEMORY')} L3_ON={l3.get('ON_WITH_MEMORY')} "
        f"L4_OFF={l4.get('OFF_WITH_MEMORY')} L4_ON={l4.get('ON_WITH_MEMORY')} "
        f"L5_ON={l5.get('ON')} GPU_RELEASED={payload.get('GPU_LANE_RELEASED')}"
    )
    if payload.get("MODEL_RESIDENCY_BREAK"):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""CLI: python -m app.eval.tool_capability.p4_real

Real LM Studio TOOL P4 S2/T2 product ablation (GQ-131/132/149 × 00/10/01/11).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# A3: no cloud model fallback — scrub provider keys before Settings/chat_llm import.
for _k in (
    "DEEPSEEK_API_KEY",
    "TONGYI_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
):
    os.environ[_k] = ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.eval.tool_capability.p4_real")
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default="zai-org/glm-4.6v-flash")
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument(
        "--max-trials",
        type=int,
        default=None,
        help="Optional cap for smoke (full panel is 60).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.thinking != "off":
        print("ERROR: thinking must be OFF for TOOL P4", file=sys.stderr)
        return 2

    # Late import after env scrub so Settings does not bind cloud keys.
    from app.core.config import settings
    from app.eval.tool_capability.p4_runner import run_tool_p4_ablation

    for attr in ("deepseek_api_key", "tongyi_api_key", "dashscope_api_key", "openai_api_key"):
        if hasattr(settings, attr):
            setattr(settings, attr, "")

    payload = asyncio.run(
        run_tool_p4_ablation(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
            max_trials=args.max_trials,
        )
    )
    primary = payload.get("primary") or {}
    stability = payload.get("stability") or {}
    interp = payload.get("interpretation") or {}
    print(
        f"wrote {payload.get('output_path')} case={interp.get('case')} "
        f"label={interp.get('label')} "
        f"primary={primary} stability={stability}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

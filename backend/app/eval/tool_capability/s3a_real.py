"""CLI: python -m app.eval.tool_capability.s3a_real

Real LM Studio TOOL S3A contrastive-selection revalidation (GQ-131 × OFF/ON × 10).
Eval-only. Does not push / PR / enable runtime defaults.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# No cloud model fallback — scrub provider keys before Settings/chat_llm import.
for _k in (
    "DEEPSEEK_API_KEY",
    "TONGYI_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
):
    os.environ[_k] = ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.eval.tool_capability.s3a_real")
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default="zai-org/glm-4.6v-flash")
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument("--keep-gpu", action="store_true", help="Do not unload after run")
    p.add_argument(
        "--max-trials",
        type=int,
        default=None,
        help="Optional cap for smoke (full panel is 20).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.thinking != "off":
        print("ERROR: thinking must be OFF for TOOL S3A", file=sys.stderr)
        return 2

    from app.core.config import settings
    from app.eval.tool_capability.s3a_runner import run_tool_s3a_revalidation

    for attr in ("deepseek_api_key", "tongyi_api_key", "dashscope_api_key", "openai_api_key"):
        if hasattr(settings, attr):
            setattr(settings, attr, "")

    payload = asyncio.run(
        run_tool_s3a_revalidation(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
            max_trials=args.max_trials,
            release_gpu=not args.keep_gpu,
        )
    )
    sel = payload.get("selection_metrics") or {}
    off = (sel.get("S3A_OFF") or {}).get("selection_correct")
    on = (sel.get("S3A_ON") or {}).get("selection_correct")
    print(
        f"wrote {payload.get('output_path')} "
        f"label={payload.get('capability_label')} "
        f"OFF={off} ON={on} "
        f"boundary={payload.get('POSSIBLE_MODEL_SELECTION_BOUNDARY')} "
        f"GPU_LANE_RELEASED={payload.get('GPU_LANE_RELEASED')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

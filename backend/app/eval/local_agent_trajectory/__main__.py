"""CLI: python -m app.eval.local_agent_trajectory

Example (PowerShell):
  python -m app.eval.local_agent_trajectory `
    --base-url http://127.0.0.1:1234/v1 `
    --model zai-org/glm-4.6v-flash `
    --timeout 90
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.local_agent_trajectory.report import default_output_dir
from app.eval.local_agent_trajectory.runner import DEFAULT_MODEL, DEFAULT_TIMEOUT, run_benchmark


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.eval.local_agent_trajectory",
        description="W8 P0 Real Local Agent Trajectory research benchmark",
    )
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--thinking", choices=("off", "on"), default="off")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--provider", default="lmstudio_openai_compatible")
    p.add_argument("--output-dir", default="")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--no-on-diagnostic", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output_dir or str(default_output_dir())
    payload = asyncio.run(
        run_benchmark(
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            timeout=args.timeout,
            provider=args.provider,
            output_dir=output,
            skip_warmup=args.skip_warmup,
            skip_reload=args.skip_reload,
            with_on_diagnostic=not args.no_on_diagnostic,
        )
    )
    summary = payload.get("off_summary") or {}
    print(
        f"wrote {payload.get('output_dir')} run_id={payload.get('run_id')} "
        f"e2e={summary.get('end_to_end_success_rate')} "
        f"safe={summary.get('safe_termination_rate')} "
        f"saved={summary.get('system_saved_rate')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

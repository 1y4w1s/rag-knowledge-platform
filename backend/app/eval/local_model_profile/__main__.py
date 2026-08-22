"""CLI: python -m app.eval.local_model_profile

Example (PowerShell):
  python -m app.eval.local_model_profile `
    --base-url http://127.0.0.1:1234/v1 `
    --model zai-org/glm-4.6v-flash `
    --thinking off `
    --timeout 60 `
    --repeat 3 `
    --output ../../artifacts/benchmarks/tmp/reports/local-profile.json

API keys: LOCAL_MODEL_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY (env only; never written).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.eval.local_model_profile.adapter import DEFAULT_TIMEOUT_SECONDS
from app.eval.local_model_profile.report import write_profile_report
from app.eval.local_model_profile.runner import run_profile


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.eval.local_model_profile",
        description="W7 P0 Local Model Capability Profile probe harness",
    )
    p.add_argument(
        "--base-url",
        required=True,
        help="OpenAI-compatible base URL (e.g. http://127.0.0.1:1234/v1)",
    )
    p.add_argument("--model", required=True, help="Model id served by the endpoint")
    p.add_argument(
        "--thinking",
        choices=("off", "on"),
        default="off",
        help="Thinking mode for this run (OFF and ON must be separate runs)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-probe HTTP timeout seconds (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    p.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Repeats for core structured probes (stability G/H)",
    )
    p.add_argument(
        "--output",
        default="",
        help=(
            "JSON report path (default: "
            "<repo>/artifacts/benchmarks/tmp/reports/local-model-profile.json)"
        ),
    )
    p.add_argument(
        "--provider",
        default="openai_compatible",
        help="Provider label recorded in the profile (not a settings switch)",
    )
    return p


def _default_output_path() -> str:
    # backend/app/eval/local_model_profile/__main__.py → repo root = parents[4]
    repo_root = Path(__file__).resolve().parents[4]
    return str(
        repo_root / "artifacts" / "benchmarks" / "tmp" / "reports" / "local-model-profile.json"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or _default_output_path()
    profile = run_profile(
        base_url=args.base_url,
        model=args.model,
        thinking=args.thinking,
        timeout=args.timeout,
        repeat=args.repeat,
        provider=args.provider,
    )
    path = write_profile_report(profile, output)
    print(
        f"wrote {path} run_id={profile.run_id} "
        f"thinking={profile.thinking_mode} "
        f"passed={profile.summary.passed}/{profile.summary.total} "
        f"recommendation={profile.recommendation.overall}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

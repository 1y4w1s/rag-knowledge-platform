"""CLI: python -m app.eval.adversarial_capability.p4_real"""

from __future__ import annotations
import argparse
import asyncio
import sys
from app.eval.adversarial_capability.p4_runner import run_adversarial_p4_benchmark


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--base-sha", default=None)
    p.add_argument("--skip-reload", action="store_true")
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument("--probe-only", action="store_true")
    args = p.parse_args(argv)
    payload = asyncio.run(
        run_adversarial_p4_benchmark(
            base_url=args.base_url,
            adv_p4_base_sha=args.base_sha,
            skip_reload=args.skip_reload,
            skip_warmup=args.skip_warmup,
            probe_only=args.probe_only,
        )
    )
    print(payload.get("output_path"), payload.get("metrics_c17"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

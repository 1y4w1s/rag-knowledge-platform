"""CLI: python -m app.eval.adversarial_capability.p3_real"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.adversarial_capability.p3_runner import run_adversarial_p3_real_retrieval


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.eval.adversarial_capability.p3_real")
    p.add_argument("--base-sha", default=None, help="adv_p3_base_sha override")
    args = p.parse_args(argv)
    payload = asyncio.run(run_adversarial_p3_real_retrieval(adv_p3_base_sha=args.base_sha))
    print(
        f"wrote {payload.get('output_paths')} state={payload.get('measurement_state')} "
        f"ready_for_p4={payload.get('ready_for_p4')}"
    )
    return 0 if payload.get("measurement_state") in {"PASS", "CHARACTERIZED"} else 1


if __name__ == "__main__":
    sys.exit(main())

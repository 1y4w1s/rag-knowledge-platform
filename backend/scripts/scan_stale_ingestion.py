"""超龄入库状态对账 CLI（NW-12）。

用法（在 backend/ 或仓库根）::

    python scripts/scan_stale_ingestion.py              # 默认干跑
    python scripts/scan_stale_ingestion.py --json
    python scripts/scan_stale_ingestion.py --apply      # 标 failed（非 eager）

生产建议：cron 每日干跑；确认报告后再偶发 --apply。不上 Celery Beat。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def _run(*, dry_run: bool, as_json: bool) -> int:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.ingestion.stale_scan import (
        apply_stale_mark_failed,
        report_to_dict,
        scan_stale_ingestion,
    )

    async with SessionLocal() as db:
        report = await scan_stale_ingestion(db)
        result = await apply_stale_mark_failed(
            db,
            report,
            dry_run=dry_run,
            max_apply=settings.ingest_stale_max_apply,
        )

    payload = {
        **report_to_dict(report),
        "dry_run": dry_run,
        "marked": result.marked,
        "apply_skipped": result.skipped,
        "apply_errors": result.errors,
        "blocked_reason": result.blocked_reason,
        "max_apply": settings.ingest_stale_max_apply,
        "eager_local": settings.celery_task_always_eager_local,
        "apply_items": result.items,
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "DRY-RUN" if dry_run else "APPLY"
        print(
            f"[{mode}] found={payload['found']} marked={payload['marked']} "
            f"skipped={payload['apply_skipped']} errors={payload['apply_errors']} "
            f"queued>={payload['queued_threshold_minutes']}m "
            f"processing>={payload['processing_threshold_minutes']}m"
        )
        if result.blocked_reason:
            print(f"  blocked: {result.blocked_reason}")
        for item in payload["items"]:
            print(
                f"  {item['status']} {item['doc_id']} "
                f"age={item['age_seconds']}s ({item['clock_field']}) "
                f"{item['filename']}"
            )

    if result.blocked_reason:
        return 2
    return 0 if result.errors == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan stale queued/processing documents; optionally mark failed"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mark stale docs failed (default: dry-run)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(dry_run=not args.apply, as_json=args.json)))


if __name__ == "__main__":
    main()

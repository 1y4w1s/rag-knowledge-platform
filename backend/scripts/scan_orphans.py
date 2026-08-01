"""orphan 磁盘对账 CLI（地图 H2）。

用法（在 backend/ 或仓库根，需 DATABASE_URL + UPLOAD_DIR）::

    python scripts/scan_orphans.py              # 默认干跑
    python scripts/scan_orphans.py --json
    python scripts/scan_orphans.py --apply      # 真删（过宽限期）

生产建议：cron 每日干跑；确认报告后再偶发 --apply。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 允许从仓库根或 backend/ 调用
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def _run(*, dry_run: bool, as_json: bool) -> int:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.storage.orphan_scan import (
        apply_orphans,
        load_owner_index,
        report_to_dict,
        scan_orphans,
    )

    async with SessionLocal() as db:
        owners = await load_owner_index(db)
        report = scan_orphans(
            owners=owners,
            grace_hours=settings.orphan_grace_hours,
        )
        result = await apply_orphans(
            db,
            report,
            dry_run=dry_run,
            max_delete=settings.orphan_max_delete,
        )

    payload = {
        **report_to_dict(report),
        "dry_run": dry_run,
        "deleted": result.deleted,
        "apply_skipped": result.skipped,
        "apply_errors": result.errors,
        "grace_hours": settings.orphan_grace_hours,
        "max_delete": settings.orphan_max_delete,
        "upload_dir": str(Path(settings.upload_dir).resolve()),
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "DRY-RUN" if dry_run else "APPLY"
        print(f"[{mode}] upload_dir={payload['upload_dir']}")
        print(
            f"found={payload['found']} skipped_grace={payload['skipped_grace']} "
            f"anomalies={len(payload['anomalies'])} "
            f"deleted={payload['deleted']} errors={payload['apply_errors']}"
        )
        for item in payload["items"]:
            print(
                f"  {item['kind']} {item['relpath']} "
                f"({item['bytes']} bytes)"
            )
        for a in payload["anomalies"]:
            print(f"  anomaly {a}")
    return 0 if result.errors == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan orphan files under upload_dir")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete orphans (default is dry-run)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(dry_run=not args.apply, as_json=args.json)))


if __name__ == "__main__":
    main()

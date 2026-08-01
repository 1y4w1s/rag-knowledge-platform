"""回收站过期 purge CLI（地图 H3）。

用法（在 backend/ 或仓库根）::

    python scripts/purge_trash.py              # 默认干跑
    python scripts/purge_trash.py --json
    python scripts/purge_trash.py --apply      # 真删过期 trash

生产建议：cron 每日干跑；确认后再偶发 --apply。
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
    from app.services.documents.trash import purge_expired_trash

    async with SessionLocal() as db:
        result = await purge_expired_trash(db, dry_run=dry_run)

    payload = {
        "dry_run": result.dry_run,
        "found": result.found,
        "deleted": result.deleted,
        "errors": result.errors,
        "retention_days": settings.trash_retention_days,
        "max_delete": settings.trash_purge_max_delete,
        "items": result.items,
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "DRY-RUN" if dry_run else "APPLY"
        print(
            f"[{mode}] found={payload['found']} deleted={payload['deleted']} "
            f"errors={payload['errors']} retention_days={payload['retention_days']}"
        )
        for item in payload["items"]:
            print(
                f"  {item['id']} {item['filename']} "
                f"deleted_at={item.get('deleted_at')}"
            )
    return 0 if result.errors == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge expired trash documents")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually permanently delete expired trash (default: dry-run)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(dry_run=not args.apply, as_json=args.json)))


if __name__ == "__main__":
    main()

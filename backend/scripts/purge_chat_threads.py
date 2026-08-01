"""对话 thread 保留期 purge CLI（NW-20）。

用法（在 backend/ 或仓库根）::

    python scripts/purge_chat_threads.py              # 默认干跑
    python scripts/purge_chat_threads.py --json
    python scripts/purge_chat_threads.py --apply      # 真删过期 thread
    python scripts/purge_chat_threads.py --retention-days 90

生产建议：cron 每日干跑；确认后再偶发 --apply。CHAT_RETENTION_DAYS=0 时禁用。
先备后 purge（H4）。有 👎 审题需求时先 export_thumbs_down。
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


async def _run(
    *,
    dry_run: bool,
    as_json: bool,
    retention_days: int | None,
) -> int:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.chat.retention import purge_expired_chat_threads

    days = (
        retention_days
        if retention_days is not None
        else settings.chat_retention_days
    )

    async with SessionLocal() as db:
        result = await purge_expired_chat_threads(
            db,
            dry_run=dry_run,
            retention_days=days,
        )

    payload = {
        "dry_run": result.dry_run,
        "disabled": result.disabled,
        "found": result.found,
        "deleted": result.deleted,
        "errors": result.errors,
        "retention_days": result.retention_days,
        "max_delete": settings.chat_purge_max_delete,
        "items": result.items,
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if result.disabled:
            print(
                f"[DISABLED] chat_retention_days={result.retention_days} "
                "(set CHAT_RETENTION_DAYS>0 to enable)"
            )
            return 0
        mode = "DRY-RUN" if dry_run else "APPLY"
        print(
            f"[{mode}] found={payload['found']} deleted={payload['deleted']} "
            f"errors={payload['errors']} retention_days={payload['retention_days']}"
        )
        for item in payload["items"]:
            print(
                f"  {item['thread_id']} status={item.get('status')} "
                f"activity_at={item.get('activity_at')}"
            )
    return 0 if result.errors == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purge chat threads older than retention days"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually hard-delete expired threads (default: dry-run)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Override CHAT_RETENTION_DAYS for this run",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                dry_run=not args.apply,
                as_json=args.json,
                retention_days=args.retention_days,
            )
        )
    )


if __name__ == "__main__":
    main()

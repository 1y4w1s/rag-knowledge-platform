"""导出 👎 反馈为 golden 人工审题候选（NW-10 I-3）。

用法（在 backend/ 或仓库根，需 DATABASE_URL）::

    python scripts/export_thumbs_down_candidates.py
    python scripts/export_thumbs_down_candidates.py --out /tmp/td.json
    python scripts/export_thumbs_down_candidates.py --kb-id <uuid> --since 2026-07-01 --out out.json

默认无 --out：只打印条数与问句摘要。**绝不**写入 golden_qa.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _run(
    *,
    out: Path | None,
    kb_id: uuid.UUID | None,
    since: datetime | None,
    limit: int,
) -> int:
    from app.core.database import SessionLocal
    from app.services.rag.feedback_export import (
        candidates_to_export_dict,
        list_thumbs_down_candidates,
    )

    async with SessionLocal() as db:
        candidates = await list_thumbs_down_candidates(
            db, kb_id=kb_id, since=since, limit=limit
        )

    payload = candidates_to_export_dict(candidates)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {payload['count']} candidates → {out}")
        print(f"note: {payload['note']}")
        return 0

    print(f"thumbs_down_candidates count={payload['count']} (NOT golden_qa)")
    for item in payload["candidates"][:20]:
        q = (item.get("query") or "(no preceding user query)")[:80]
        print(f"  {item['message_id'][:8]}… kb={item.get('kb_name') or '-'} | {q}")
    if payload["count"] > 20:
        print(f"  … +{payload['count'] - 20} more (use --out for full JSON)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export thumbs-down chat feedback as manual golden candidates"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write candidate JSON (never golden_qa.json)",
    )
    parser.add_argument("--kb-id", type=uuid.UUID, default=None)
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO date/datetime (UTC if naive)",
    )
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                out=args.out,
                kb_id=args.kb_id,
                since=_parse_since(args.since),
                limit=args.limit,
            )
        )
    )


if __name__ == "__main__":
    main()

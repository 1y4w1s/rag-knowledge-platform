#!/usr/bin/env python3
"""运维 CLI：全库重嵌入（换 EMBEDDING_MODEL 后执行）。

用法（项目根或 backend 目录）::

    py -3.11 backend/scripts/re_embed_all.py --dry-run
    py -3.11 backend/scripts/re_embed_all.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# 允许从 repo 根目录执行
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings  # noqa: E402
from app.services.ingestion.re_embed import count_stale_chunks, re_embed_all_chunks  # noqa: E402


async def _main() -> int:
    parser = argparse.ArgumentParser(description="全库重嵌入 stale chunks")
    parser.add_argument("--kb-id", type=UUID, default=None, help="仅重嵌指定资料库")
    parser.add_argument("--dry-run", action="store_true", help="只统计 stale 数量")
    args = parser.parse_args()

    stale = await count_stale_chunks(kb_id=args.kb_id)
    print(f"EMBEDDING_PROVIDER={settings.embedding_provider}")
    print(f"EMBEDDING_MODEL={settings.embedding_model}")
    print(f"Stale chunks: {stale}")
    if args.dry_run:
        return 0

    if stale == 0:
        print("Nothing to re-embed.")
        return 0

    result = await re_embed_all_chunks(kb_id=args.kb_id)
    print(result)
    return 0 if result.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

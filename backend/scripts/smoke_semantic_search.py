"""G3-1.3 smoke：自动取库内第一个个人 kb，调 run_semantic_search（无需手填 UUID）。

用法（backend 目录 · 需 PostgreSQL 已起）：

  cd backend
  py -3.11 scripts/smoke_semantic_search.py
  py -3.11 scripts/smoke_semantic_search.py --query "年假"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import run_semantic_search
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


async def _pick_personal_kb() -> tuple[KnowledgeBase, int, str]:
    """优先选 chunk 最多的个人库（避免 pytest 空壳「对齐库」）。"""
    async with SessionLocal() as db:
        row = await db.execute(
            select(
                KnowledgeBase,
                func.count(DocumentChunk.id).label("chunk_count"),
            )
            .join(
                DocumentChunk,
                DocumentChunk.kb_id == KnowledgeBase.id,
                isouter=True,
            )
            .where(KnowledgeBase.owner_user_id.is_not(None))
            .group_by(KnowledgeBase.id)
            .order_by(func.count(DocumentChunk.id).desc())
            .limit(1)
        )
        result = row.one_or_none()
        if result is None:
            raise SystemExit(
                "数据库里没有个人资料库。请先登录前端建库并上传文档，或跑 seed 后再试。"
            )
        kb, chunk_count = result[0], int(result[1])
        if chunk_count == 0:
            raise SystemExit(
                "所有个人资料库都没有切片（chunk=0）。"
                "请在前端上传文档并完成入库，或用 pytest 绿结果确认 G3-1.3。"
            )
        return kb, chunk_count, "员工年假有多少天"


async def main() -> None:
    parser = argparse.ArgumentParser(description="smoke semantic_search tool")
    parser.add_argument("--query", default=None, help="检索词（默认：年假）")
    args = parser.parse_args()

    kb, chunk_count, default_query = await _pick_personal_kb()
    query = args.query or default_query
    user_id = kb.owner_user_id
    assert user_id is not None

    workspace = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({kb.id}),
        default_kb_id=kb.id,
    )

    print(f"kb_id={kb.id}")
    print(f"kb_name={kb.name!r}")
    print(f"chunk_count={chunk_count}")
    print(f"user_id={user_id}")
    print(f"query={query!r}")
    print("---")

    async with SessionLocal() as db:
        result = await run_semantic_search(
            db,
            workspace,
            tool_scope,
            query=query,
        )

    print(f"ok={result.ok}")
    print(f"summary={result.summary}")
    if result.data is None:
        return
    print(f"retrieval_ms={result.data.retrieval_ms}")
    print(f"hits={len(result.data.hits)}")
    for i, hit in enumerate(result.data.hits[:3], start=1):
        print(
            f"  [{i}] {hit.doc_name} · p{hit.page} · score={hit.score:.3f} · "
            f"{hit.excerpt[:80]!r}"
        )


if __name__ == "__main__":
    asyncio.run(main())

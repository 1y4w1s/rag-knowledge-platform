"""检索适配器：将睿阁的检索系统连接到 BenchmarkRunner。

用法：
    from tests.benchmark.adapters.retrieval import RetrievalAdapter
    adapter = RetrievalAdapter()
    runner.set_retrieve_fn(adapter.retrieve)
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.types import RetrievedChunk

logger = logging.getLogger(__name__)


class RetrievalAdapter:
    """将 retrieve_chunks 包装为 BenchmarkRunner 兼容的检索回调。

    调用 retrieve_chunks(db, kb_id=kb_id, query=query, top_k=top_k)。
    需要外部传入 db session。
    """

    def __init__(self, db) -> None:
        self._db = db

    async def retrieve(
        self, query: str, kb_id: UUID, top_k: int = 3
    ) -> list[RetrievedChunk]:
        """检索回调：供 BenchmarkRunner 使用。"""
        chunks = await retrieve_chunks(
            self._db,
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )
        return chunks

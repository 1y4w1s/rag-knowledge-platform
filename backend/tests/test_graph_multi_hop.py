"""D1 GraphRAG — 多跳推理单元测试。

覆盖 graph_entity_recall 的 2 跳关系扩散逻辑。
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.models.entity import Entity, Relation
from app.models.document_chunk import DocumentChunk
from app.services.rag.types import RetrievedChunk


def _make_result_row(id_str: str, **kwargs) -> MagicMock:
    """构造一个模拟的 SQLAlchemy 行对象（scalars().all() 用）。"""
    row = MagicMock(spec=Entity if not kwargs else DocumentChunk)
    row.id = UUID(id_str)
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _make_relation(source_id: str, target_id: str) -> MagicMock:
    """构造一个模拟的 Relation 行。"""
    rel = MagicMock(spec=Relation)
    rel.source_id = UUID(source_id)
    rel.target_id = UUID(target_id)
    return rel


def _make_mention_result(ids: list[str]) -> MagicMock:
    """构造 entity_mentions 查询的模拟结果。

    graph_entity_recall 中用了: {row[0] for row in mention_rows}
    使用 MagicMock.__iter__ 确保迭代行为正确。
    """
    mock_result = MagicMock()
    rows = [(UUID(uid),) for uid in ids]
    mock_result.__iter__.return_value = iter(rows)
    return mock_result


class TestGraphMultiHop:
    """graph_entity_recall 2 跳关系扩散测试"""

    @pytest.mark.asyncio
    async def test_hop2_basic(self) -> None:
        """1 实体 + 1 条关系 → 2 跳 chunk similarity=0.25"""
        entity_id = "11111111-1111-1111-1111-111111111111"
        target_id = "22222222-2222-2222-2222-222222222222"
        chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        hop2_chunk_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.segment_cjk", return_value="张三"),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()

            mock_entity = _make_result_row(entity_id)
            mock_1hop_chunk = _make_result_row(
                chunk_id, document_id=UUID(doc_id), content="1-hop content",
                page_number=1, section_title="", heading_path="",
            )
            mock_hop2_chunk = _make_result_row(
                hop2_chunk_id, document_id=UUID(doc_id), content="2-hop content",
                page_number=2, section_title="Related", heading_path="Related",
            )

            # 1. Entity ILIKE (1 次, segment_cjk 被 patch 为单 token)
            exec_entity = MagicMock()
            exec_entity.scalars.return_value.all.return_value = [mock_entity]

            # 2. 1-hop EntityMention
            exec_mention_1 = _make_mention_result([chunk_id])

            # 3. 1-hop DocumentChunk
            exec_chunk_1 = MagicMock()
            exec_chunk_1.scalars.return_value.all.return_value = [mock_1hop_chunk]

            # 4. Relation
            exec_rel = MagicMock()
            exec_rel.scalars.return_value.all.return_value = [
                _make_relation(entity_id, target_id)
            ]

            # 5. hop2 EntityMention
            exec_mention_2 = _make_mention_result([hop2_chunk_id])

            # 6. hop2 DocumentChunk
            exec_chunk_2 = MagicMock()
            exec_chunk_2.scalars.return_value.all.return_value = [mock_hop2_chunk]

            mock_db.execute = AsyncMock(side_effect=[
                exec_entity,      # 1. Entity ILIKE
                exec_mention_1,  # 2. 1-hop EntityMention
                exec_chunk_1,    # 3. 1-hop DocumentChunk
                exec_rel,        # 4. Relation
                exec_mention_2,  # 5. hop2 EntityMention
                exec_chunk_2,    # 6. hop2 DocumentChunk
            ])

            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "张三", result)

            # 应有 2 个 chunk：1 跳 + 2 跳
            assert len(output) == 2

            # 1 跳 similarity=0.3
            assert output[0].similarity == 0.3
            assert output[0].chunk_id == UUID(chunk_id)

            # 2 跳 similarity=0.25
            assert output[1].similarity == 0.25
            assert output[1].chunk_id == UUID(hop2_chunk_id)

    @pytest.mark.asyncio
    async def test_hop2_no_relations(self) -> None:
        """实体无关联关系 → 仅返回 1 跳结果"""
        entity_id = "11111111-1111-1111-1111-111111111111"
        chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.segment_cjk", return_value="张三"),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()

            mock_entity = _make_result_row(entity_id)
            mock_chunk = _make_result_row(
                chunk_id, document_id=UUID(doc_id), content="content",
                page_number=1, section_title="", heading_path="",
            )

            exec_entity = MagicMock()
            exec_entity.scalars.return_value.all.return_value = [mock_entity]

            exec_mention = _make_mention_result([chunk_id])

            exec_chunk = MagicMock()
            exec_chunk.scalars.return_value.all.return_value = [mock_chunk]

            # Relation 查询返回空
            exec_rel_empty = MagicMock()
            exec_rel_empty.scalars.return_value.all.return_value = []

            mock_db.execute = AsyncMock(side_effect=[
                exec_entity,    # 1. Entity ILIKE
                exec_mention,   # 2. 1-hop EntityMention
                exec_chunk,     # 3. 1-hop DocumentChunk
                exec_rel_empty, # 4. Relation
            ])

            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "张三", result)

            # 仅有 1 跳
            assert len(output) == 1
            assert output[0].similarity == 0.3

    @pytest.mark.asyncio
    async def test_hop2_deduplicate(self) -> None:
        """1 跳和 2 跳指向同一 chunk → 不重复"""
        entity_id = "11111111-1111-1111-1111-111111111111"
        target_id = "22222222-2222-2222-2222-222222222222"
        chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.segment_cjk", return_value="张三"),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()
            mock_entity = _make_result_row(entity_id)
            mock_chunk = _make_result_row(
                chunk_id, document_id=UUID(doc_id), content="content",
                page_number=1, section_title="", heading_path="",
            )

            exec_entity = MagicMock()
            exec_entity.scalars.return_value.all.return_value = [mock_entity]
            exec_mention_1 = _make_mention_result([chunk_id])
            exec_chunk_1 = MagicMock()
            exec_chunk_1.scalars.return_value.all.return_value = [mock_chunk]

            exec_rel = MagicMock()
            exec_rel.scalars.return_value.all.return_value = [
                _make_relation(entity_id, target_id)
            ]

            exec_mention_2 = _make_mention_result([chunk_id])  # 同一 chunk_id

            mock_db.execute = AsyncMock(side_effect=[
                exec_entity,
                exec_mention_1,
                exec_chunk_1,
                exec_rel,
                exec_mention_2,  # 2 跳 EntityMention → 相同 chunk_id → 被去重
            ])

            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "张三", result)

            # 1 跳 chunk 已追加，2 跳指向同一 chunk → 不重复
            assert len(output) == 1
            assert output[0].similarity == 0.3

    @pytest.mark.asyncio
    async def test_hop2_bidirectional(self) -> None:
        """target→source 方向也被覆盖（实体在 target 端）"""
        source_id = "11111111-1111-1111-1111-111111111111"
        target_id = "22222222-2222-2222-2222-222222222222"
        source_chunk = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        target_chunk = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.segment_cjk", return_value="智慧城市平台"),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()

            # 匹配到的实体是 target_id（即查询中的词匹配到 target）
            mock_entity = _make_result_row(target_id)
            mock_source = _make_result_row(
                source_chunk, document_id=UUID(doc_id), content="source chunk",
                page_number=1, section_title="", heading_path="",
            )
            mock_target = _make_result_row(
                target_chunk, document_id=UUID(doc_id), content="target chunk",
                page_number=1, section_title="", heading_path="",
            )

            exec_entity = MagicMock()
            exec_entity.scalars.return_value.all.return_value = [mock_entity]

            # 1-hop EntityMention → target 自身 chunk
            exec_mention_1 = _make_mention_result([target_chunk])
            exec_chunk_1 = MagicMock()
            exec_chunk_1.scalars.return_value.all.return_value = [mock_target]

            # Relation: source→target → target 在 matched 中 → 扩散到 source
            exec_rel = MagicMock()
            exec_rel.scalars.return_value.all.return_value = [
                _make_relation(source_id, target_id)
            ]

            # 2-hop: source 的 chunk
            exec_mention_2 = _make_mention_result([source_chunk])
            exec_chunk_2 = MagicMock()
            exec_chunk_2.scalars.return_value.all.return_value = [mock_source]

            mock_db.execute = AsyncMock(side_effect=[
                exec_entity, exec_mention_1, exec_chunk_1,
                exec_rel, exec_mention_2, exec_chunk_2,
            ])

            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "智慧城市平台", result)

            assert len(output) == 2
            hop2 = output[1]
            assert hop2.similarity == 0.25
            assert hop2.chunk_id == UUID(source_chunk)

    @pytest.mark.asyncio
    async def test_hop2_self_loop(self) -> None:
        """实体关联自身（source=target）→ 被去重"""
        entity_id = "11111111-1111-1111-1111-111111111111"
        chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        doc_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.segment_cjk", return_value="张三"),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()
            mock_entity = _make_result_row(entity_id)
            mock_chunk = _make_result_row(
                chunk_id, document_id=UUID(doc_id), content="content",
                page_number=1, section_title="", heading_path="",
            )

            exec_entity = MagicMock()
            exec_entity.scalars.return_value.all.return_value = [mock_entity]
            exec_mention_1 = _make_mention_result([chunk_id])
            exec_chunk_1 = MagicMock()
            exec_chunk_1.scalars.return_value.all.return_value = [mock_chunk]

            # 自环：source = target = entity_id
            exec_rel = MagicMock()
            exec_rel.scalars.return_value.all.return_value = [
                _make_relation(entity_id, entity_id)
            ]

            mock_db.execute = AsyncMock(side_effect=[
                exec_entity, exec_mention_1, exec_chunk_1, exec_rel,
            ])

            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "张三", result)

            # 自环 → hop2_entity_ids -= matched → 空 → 不追加
            assert len(output) == 1
            assert output[0].similarity == 0.3

    @pytest.mark.asyncio
    async def test_hop2_disabled_recall(self) -> None:
        """graph_recall_enabled=False → 不触发任何步骤"""
        with patch("app.services.rag.retrieval.settings.graph_recall_enabled", False):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()
            result: list[RetrievedChunk] = []
            output = await graph_entity_recall(mock_db, ANY, "张三", result)

            assert output == []
            mock_db.execute.assert_not_called()

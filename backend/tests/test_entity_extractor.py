"""D1 GraphRAG — entity_extractor 单元测试。"""

import inspect
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.entity import Entity, EntityMention, Relation
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.rag.entity_extractor import (
    _try_parse_json,
    extract_entities_for_document,
    extract_entities_sync,
)


class TestTryParseJson:
    def test_normal_json(self) -> None:
        raw = '{"entities": [{"name": "张三", "type": "person"}], "relations": []}'
        result = _try_parse_json(raw)
        assert result["entities"] == [{"name": "张三", "type": "person"}]
        assert result["relations"] == []

    def test_malformed_with_extra_text(self) -> None:
        raw = 'some text\n{\n"entities": [{"name": "A公司", "type": "organization"}],\n"relations": []\n}\nmore text'
        result = _try_parse_json(raw)
        assert result["entities"] == [{"name": "A公司", "type": "organization"}]

    def test_completely_garbage(self) -> None:
        raw = "not json at all!!!"
        result = _try_parse_json(raw)
        assert result == {"entities": [], "relations": []}

    def test_empty_string(self) -> None:
        result = _try_parse_json("")
        assert result == {"entities": [], "relations": []}

    def test_partial_json_truncated(self) -> None:
        raw = '{"entities": [{"name": "test", "type": "person"}], "relations"'
        result = _try_parse_json(raw)
        assert result == {"entities": [], "relations": []}


class TestExtractEntitiesSync:
    FAKE_VALID_RESPONSE = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"entities": [{"name": "张三", "type": "person"}, '
                        '{"name": "A公司", "type": "organization"}], '
                        '"relations": [{"source": "张三", "target": "A公司", "type": "belongs_to"}]}'
                    )
                }
            }
        ]
    }

    def test_dead_supported_types_parameter_removed(self) -> None:
        """P2-R6：死参数 supported_types 已从签名移除，调用方无法再传入。"""
        sig = inspect.signature(extract_entities_sync)
        assert list(sig.parameters) == ["text"]

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_normal(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_VALID_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("张三在A公司工作")
        assert len(result["entities"]) == 2
        assert result["entities"][0] == {"name": "张三", "type": "person"}
        assert len(result["relations"]) == 1
        assert result["relations"][0] == {
            "source": "张三", "target": "A公司", "type": "belongs_to"
        }

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_malformed_json_fallback(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        # 返回非 JSON 文本，含 markdown 包裹
        mock_instance.post.return_value.json.return_value = {
            "choices": [{"message": {"content": "```json\n{\"entities\": [{\"name\": \"张三\", \"type\": \"person\"}], \"relations\": []}\n```"}}]
        }
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "张三"

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_httpx_raises_exception(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert result == {"entities": [], "relations": []}

    def test_no_api_key(self) -> None:
        with patch("app.services.rag.entity_extractor.settings") as mock_settings:
            mock_settings.deepseek_api_key = ""
            result = extract_entities_sync("测试")
            assert result == {"entities": [], "relations": []}

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_retry_then_succeed(self, mock_client: MagicMock) -> None:
        """第一次失败，第二次成功。"""
        mock_instance = MagicMock()
        call_count = [0]

        def post_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.TimeoutException("timeout")
            resp = MagicMock()
            resp.json.return_value = self.FAKE_VALID_RESPONSE
            resp.raise_for_status.return_value = None
            return resp

        mock_instance.post.side_effect = post_side_effect
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert len(result["entities"]) == 2
        assert call_count[0] == 2


@pytest.fixture
async def db() -> AsyncSession:
    """提供独立 DB session，测试结束后回滚。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
async def extract_doc(db: AsyncSession) -> tuple[Document, KnowledgeBase]:
    """创建测试用户 / 知识库 / 文档。"""
    user = User(
        id=uuid4(),
        email=f"extract-test-{uuid4().hex[:8]}@example.com",
        username=f"extract{uuid4().hex[:6]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user)
    await db.flush()
    kb = KnowledgeBase(
        id=uuid4(),
        name="测试库-entity-extractor",
        owner_user_id=user.id,
    )
    db.add(kb)
    await db.flush()
    doc = Document(
        id=uuid4(),
        kb_id=kb.id,
        filename="extract.txt",
        file_type="txt",
        file_size=100,
        storage_path="/tmp/extract.txt",
        status=DocumentStatus.completed,
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    return doc, kb


async def _add_extract_chunk(
    db: AsyncSession,
    doc: Document,
    kb_id: UUID,
    index: int,
) -> DocumentChunk:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=doc.id,
        kb_id=kb_id,
        chunk_index=index,
        content=f"chunk-{index}",
        chunk_kind="text",
    )
    db.add(chunk)
    await db.flush()
    return chunk


@pytest.mark.asyncio
async def test_extract_batch_upsert_and_query_count(
    db: AsyncSession,
    extract_doc: tuple[Document, KnowledgeBase],
) -> None:
    """批量查库 + 复用已有实体：查询次数不随实体/关系数量线性增长。"""
    doc, kb = extract_doc
    for index in range(3):
        await _add_extract_chunk(db, doc, kb.id, index)

    existing_entity = Entity(kb_id=kb.id, name="张三", type="person")
    db.add(existing_entity)
    await db.flush()

    result = {
        "entities": [
            {"name": "张三", "type": "person"},
            {"name": "A公司", "type": "organization"},
            {"name": "项目X", "type": "project"},
        ],
        "relations": [
            {"source": "张三", "target": "A公司", "type": "belongs_to"},
            {"source": "A公司", "target": "项目X", "type": "participates_in"},
        ],
    }

    executed = 0

    def _count_execute(
        _conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal executed
        executed += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _count_execute)
    try:
        with patch(
            "app.services.rag.entity_extractor.extract_entities_sync",
            return_value=result,
        ):
            await extract_entities_for_document(db, doc)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count_execute)

    assert executed <= 10, f"实体抽取查询次数异常: {executed}"

    entities = (
        await db.execute(select(Entity).where(Entity.kb_id == kb.id))
    ).scalars().all()
    assert len(entities) == 3
    by_key = {(e.name, e.type): e.id for e in entities}
    assert by_key[("张三", "person")] == existing_entity.id

    mentions = (
        await db.execute(
            select(EntityMention)
            .join(Entity, EntityMention.entity_id == Entity.id)
            .where(Entity.kb_id == kb.id)
        )
    ).scalars().all()
    assert len(mentions) == 9

    relations = (
        await db.execute(select(Relation).where(Relation.kb_id == kb.id))
    ).scalars().all()
    assert len(relations) == 2


@pytest.mark.asyncio
async def test_extract_same_name_different_type_not_overwritten(
    db: AsyncSession,
    extract_doc: tuple[Document, KnowledgeBase],
) -> None:
    """同名不同型实体各保留各的：mention 精确落位，歧义 relation 不落库。"""
    doc, kb = extract_doc
    await _add_extract_chunk(db, doc, kb.id, 0)

    result = {
        "entities": [
            {"name": "华为", "type": "organization"},
            {"name": "华为", "type": "project"},
            {"name": "腾讯", "type": "organization"},
            {"name": "李雷", "type": "person"},
        ],
        "relations": [
            {"source": "李雷", "target": "华为", "type": "responsible_for"},
            {"source": "李雷", "target": "腾讯", "type": "belongs_to"},
            {"source": "华为", "target": "腾讯", "type": "contract_with"},
        ],
    }
    with patch(
        "app.services.rag.entity_extractor.extract_entities_sync",
        return_value=result,
    ):
        await extract_entities_for_document(db, doc)

    entities = (
        await db.execute(select(Entity).where(Entity.kb_id == kb.id))
    ).scalars().all()
    assert len(entities) == 4

    mention_rows = (
        await db.execute(
            select(EntityMention.entity_id, Entity.name, Entity.type)
            .join(Entity, EntityMention.entity_id == Entity.id)
            .where(Entity.kb_id == kb.id)
        )
    ).all()
    mention_keys = {(name, type_) for _, name, type_ in mention_rows}
    assert mention_keys == {
        ("华为", "organization"),
        ("华为", "project"),
        ("腾讯", "organization"),
        ("李雷", "person"),
    }
    assert len(mention_rows) == 4

    relations = (
        await db.execute(select(Relation).where(Relation.kb_id == kb.id))
    ).scalars().all()
    assert len(relations) == 1
    assert relations[0].relation_type == "belongs_to"


@pytest.mark.asyncio
async def test_extract_idempotent_no_duplicate_rows(
    db: AsyncSession,
    extract_doc: tuple[Document, KnowledgeBase],
) -> None:
    """同一文档重复抽取：实体 / mention / relation 均不重复。"""
    doc, kb = extract_doc
    await _add_extract_chunk(db, doc, kb.id, 0)

    result = {
        "entities": [
            {"name": "张三", "type": "person"},
            {"name": "A公司", "type": "organization"},
        ],
        "relations": [
            {"source": "张三", "target": "A公司", "type": "belongs_to"},
        ],
    }
    with patch(
        "app.services.rag.entity_extractor.extract_entities_sync",
        return_value=result,
    ):
        await extract_entities_for_document(db, doc)
        await extract_entities_for_document(db, doc)

    entities = (
        await db.execute(select(Entity).where(Entity.kb_id == kb.id))
    ).scalars().all()
    assert len(entities) == 2

    mentions = (
        await db.execute(
            select(EntityMention)
            .join(Entity, EntityMention.entity_id == Entity.id)
            .where(Entity.kb_id == kb.id)
        )
    ).scalars().all()
    assert len(mentions) == 2

    relations = (
        await db.execute(select(Relation).where(Relation.kb_id == kb.id))
    ).scalars().all()
    assert len(relations) == 1

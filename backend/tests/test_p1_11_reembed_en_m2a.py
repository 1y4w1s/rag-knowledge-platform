"""P1-11 方案 B · M2a：EN 模型单一常量点 + 入库同步写 EN 模型列。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion import embedder as embedder_mod
from app.services.ingestion.embedder import embed_texts
from app.services.ingestion.pipeline import _write_chunks
from app.services.ingestion.types import ChunkDraft
from tests.conftest import create_test_kb as _create_kb

CONTENT = "What is the annual leave policy after one year?"


async def _create_personal_kb(
    client: AsyncClient,
    register_and_login,
    *,
    prefix: str,
) -> tuple[dict, dict, uuid.UUID]:
    headers, user = await register_and_login(prefix=prefix)
    kb = await _create_kb(
        client,
        headers,
        user,
        name=f"m2a-{uuid.uuid4().hex[:8]}",
        workspace_kind="personal",
    )
    return headers, user, uuid.UUID(kb["id"])


async def _new_document(
    db,
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        kb_id=kb_id,
        filename="m2a-en.txt",
        file_type="txt",
        file_size=len(content),
        storage_path=f"/tmp/{kb_id}/m2a-en.txt",
        status=DocumentStatus.completed,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


def test_current_bge_en_model_default_and_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EN 模型只经 current_bge_en_model() 取值：空配置回默认，配置可覆盖。"""
    monkeypatch.setattr(settings, "bge_en_model", "")
    assert embedder_mod.current_bge_en_model() == embedder_mod.DEFAULT_BGE_EN_MODEL

    monkeypatch.setattr(settings, "bge_en_model", "custom/bge-en-v2")
    assert embedder_mod.current_bge_en_model() == "custom/bge-en-v2"


@pytest.mark.asyncio
async def test_pipeline_writes_embedding_en_model_with_en_vectors(
    client: AsyncClient,
    register_and_login,
) -> None:
    """入库写 embedding_en 的 chunk 必须同步写 EN 模型列。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="m2a-en-write"
    )
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]
    en_vec = (await embed_texts([CONTENT], provider="bge_en"))[0]
    drafts = [ChunkDraft(content=CONTENT, chunk_index=0)]

    async with SessionLocal() as db:
        doc = await _new_document(
            db, kb_id=kb_id, user_id=user_id, content=CONTENT
        )
        await _write_chunks(
            db,
            doc=doc,
            drafts=drafts,
            vectors=[vec],
            vectors_en=[en_vec],
        )
        await db.commit()

    async with SessionLocal() as db:
        row = await db.scalar(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        assert row is not None
        assert row.embedding_en is not None
        assert row.embedding_en_model == embedder_mod.current_bge_en_model()


@pytest.mark.asyncio
async def test_pipeline_leaves_embedding_en_model_null_without_en_vectors(
    client: AsyncClient,
    register_and_login,
) -> None:
    """未生成 EN 向量的 chunk 不写 EN 模型列，避免误标模型。"""
    _, user, kb_id = await _create_personal_kb(
        client, register_and_login, prefix="m2a-en-none"
    )
    user_id = uuid.UUID(user["id"])
    vec = (await embed_texts([CONTENT]))[0]
    drafts = [ChunkDraft(content=CONTENT, chunk_index=0)]

    async with SessionLocal() as db:
        doc = await _new_document(
            db, kb_id=kb_id, user_id=user_id, content=CONTENT
        )
        await _write_chunks(
            db,
            doc=doc,
            drafts=drafts,
            vectors=[vec],
        )
        await db.commit()

    async with SessionLocal() as db:
        row = await db.scalar(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        assert row is not None
        assert row.embedding_en is None
        assert row.embedding_en_model is None

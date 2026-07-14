"""Wave 6.2 / PRD §10 安全验收（SA-1～3）门禁用例。

CI job ``W6-2 SA-1~3 gate`` 与本文件 + ``test_upload_security.py`` 对齐。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb

_FIXTURES = Path(__file__).parent / "fixtures"
_GOLDEN_MD = _FIXTURES / "golden_handbook.md"


async def _ingest_fixture(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    source: Path,
    file_type: str,
    upload_dir: Path,
) -> Document:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=source.name,
            file_type=file_type,
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed
        return row


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_sa1_user_a_cannot_access_user_b_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    """SA-1：用户 A 用 B 的知识库 ID 访问 → 403。"""
    headers_a, user_a = await register_and_login(prefix="sa1-owner")
    headers_b, _user_b = await register_and_login(prefix="sa1-intruder")
    kb = await _create_kb(client, headers_a, user_a, name="A 私有库")

    resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_sa3_hybrid_retrieval_kb_id_matches_request(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
) -> None:
    """SA-3：hybrid 检索结果 chunk 的 kb_id 与请求一致，跨库不泄漏。"""
    headers, user = await register_and_login(prefix="sa3-gate")
    user_id = uuid.UUID(user["id"])

    kb_a = await _create_kb(client, headers, user, name="SA3 库 A")
    kb_b = await _create_kb(client, headers, user, name="SA3 库 B")
    kb_a_id = UUID(kb_a["id"])
    kb_b_id = UUID(kb_b["id"])

    await _ingest_fixture(
        kb_id=kb_a_id,
        user_id=user_id,
        source=_GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET_SA3_GATE 唯一标识符", encoding="utf-8")
    await _ingest_fixture(
        kb_id=kb_b_id,
        user_id=user_id,
        source=secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_a_id,
            query="员工年假有几天",
        )
        assert chunks

        chunk_ids = [c.chunk_id for c in chunks]
        rows = (
            await db.execute(
                select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
            )
        ).scalars().all()
        assert len(rows) == len(chunk_ids)
        assert all(row.kb_id == kb_a_id for row in rows)
        assert all("SECRET_SA3_GATE" not in row.content for row in rows)

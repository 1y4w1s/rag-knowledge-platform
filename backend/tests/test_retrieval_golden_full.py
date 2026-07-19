"""Full CI Gate — Golden QA 全量检索门禁（≤3min 企业评测体系 Phase 3）。
用单个 KB 入库全部 golden 文档，逐题检索验证。

门禁阈值: Hit@3 >= 85% (mock 嵌入), 拒答准确率 >= 80%
"""

from __future__ import annotations

import hashlib
import math
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import embedder
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb
from tests.golden_qa_loader import (
    FIXTURES,
    GOLDEN_MD,
    GOLDEN_DOCX,
    GOLDEN_QA_CASES,
    HIT_K,
    chunk_matches,
    hit_at_k,
    reciprocal_rank,
)

HIT_RATE_MIN = 0.85
REJECTION_ACC_MIN = 0.80


def _lexical_mock_vector(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    dim = settings.embedding_dim
    values: list[float] = []
    while len(values) < dim:
        for i in range(0, len(digest), 4):
            chunk = digest[i:i+4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            num = int.from_bytes(chunk, "big", signed=False)
            values.append((num % 1000) / 1000.0 - 0.5)
            if len(values) >= dim:
                break
        digest = hashlib.sha256(digest).digest()
    norm = math.sqrt(sum(v*v for v in values)) or 1.0
    return [v / norm for v in values]


async def _mock_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_lexical_mock_vector(t) for t in texts]


@pytest.fixture(autouse=True)
def _mock_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedder, "embed_texts", _mock_embed_texts)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _ingest_doc(kb_id, user_id, source_path, file_type, upload_dir):
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source_path.read_bytes())
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=source_path.name,
            file_type=file_type, file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)
    return doc_id


@pytest.mark.asyncio
async def test_full_gate_retrieval(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """全量门禁：110 题 Hit@3 >= 85%。"""
    headers, user = await register_and_login(prefix="fg-full")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    # 入库 md 和 docx 文档
    await _ingest_doc(kb_id, user_id, GOLDEN_MD, "md", upload_dir)

    if GOLDEN_DOCX.exists():
        from app.services.ingestion.parser.docx_parser import parse_docx
        await _ingest_doc(kb_id, user_id, GOLDEN_DOCX, "docx", upload_dir)

    # 逐题检索
    hits = 0
    total = 0
    reject_correct = 0
    reject_total = 0

    async with SessionLocal() as db:
        for case in GOLDEN_QA_CASES:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            if case.expect_rejection:
                reject_total += 1
                match_count = sum(1 for c in chunks[:HIT_K] if chunk_matches(case, c))
                if match_count == 0:
                    reject_correct += 1
            else:
                total += 1
                if hit_at_k(chunks, case, k=HIT_K):
                    hits += 1

    hit_rate = hits / max(1, total)
    rej_acc = reject_correct / max(1, reject_total)

    print(f"\n{'='*50}")
    print(f"全量门禁报告")
    print(f"{'='*50}")
    print(f"  总题数:    {len(GOLDEN_QA_CASES)}")
    print(f"  普通题:    {hits}/{total} = {hit_rate:.1%}  (门禁: {HIT_RATE_MIN:.0%})")
    print(f"  拒答题:    {reject_correct}/{reject_total} = {rej_acc:.0%}  (门禁: {REJECTION_ACC_MIN:.0%})")
    print(f"{'='*50}")

    assert hit_rate >= HIT_RATE_MIN, (
        f"Hit@{HIT_K} {hit_rate:.1%} 低于门禁 {HIT_RATE_MIN:.0%}"
    )
    assert rej_acc >= REJECTION_ACC_MIN, (
        f"拒答准确率 {rej_acc:.0%} 低于门禁 {REJECTION_ACC_MIN:.0%}"
    )

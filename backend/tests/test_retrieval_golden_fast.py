"""Fast CI Gate — Golden QA 10 题快速门禁（≤15s 企业评测体系 Phase 3）。
使用 mock 嵌入，只验证检索质量。

门禁阈值: Hit@3 >= 90%，拒答准确率 >= 80%
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
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb
from tests.golden_qa_loader import (
    FIXTURES,
    GOLDEN_MD,
    GOLDEN_QA_CASES,
    HIT_K,
    chunk_matches,
    hit_at_k,
)

# 快速门禁：10 题子集（覆盖 simple/cross/edge/rejection/conditional）
FAST_GATE_IDS = {"GQ-1", "GQ-5", "GQ-14", "GQ-25", "GQ-26",
                 "GQ-36", "GQ-38", "GQ-46", "GQ-79", "GQ-104"}

FAST_CASES = [c for c in GOLDEN_QA_CASES if c.case_id in FAST_GATE_IDS]
HIT_K = 3
HIT_RATE_MIN = 0.90      # Hit@3 >= 90%
REJECTION_ACC_MIN = 0.80  # 拒答准确率 >= 80%


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


@pytest.mark.asyncio
async def test_fast_gate_hit_at_k(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """快速门禁：全 10 题 Hit@3 >= 90%。"""
    headers, user = await register_and_login(prefix="fg")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    # 入库 golden_handbook.md
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.md"
    storage_path.write_bytes(GOLDEN_MD.read_bytes())

    from app.services.ingestion.pipeline import process_document_ingestion
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=GOLDEN_MD.name,
            file_type="md", file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=uuid.UUID(user["id"]),
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)

    # 逐题检索
    hits = 0
    total = len(FAST_CASES)
    async with SessionLocal() as db:
        for case in FAST_CASES:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            if hit_at_k(chunks, case, k=HIT_K):
                hits += 1

    hit_rate = hits / max(1, total)
    print(f"\nFast Gate: {hits}/{total} = {hit_rate:.1%} (threshold: {HIT_RATE_MIN:.0%})")
    assert hit_rate >= HIT_RATE_MIN, (
        f"Fast Gate Hit@{HIT_K} {hit_rate:.1%} 低于门禁 {HIT_RATE_MIN:.0%}"
    )


@pytest.mark.asyncio
async def test_fast_gate_rejection(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """快速门禁：拒答准确率 >= 80%。"""
    headers, user = await register_and_login(prefix="fg-rej")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.md"
    storage_path.write_bytes(GOLDEN_MD.read_bytes())

    from app.services.ingestion.pipeline import process_document_ingestion
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=GOLDEN_MD.name,
            file_type="md", file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=uuid.UUID(user["id"]),
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)

    rejection_cases = [c for c in FAST_CASES if c.expect_rejection]
    correct = 0
    async with SessionLocal() as db:
        for case in rejection_cases:
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case.query, top_k=HIT_K)
            match_count = sum(1 for c in chunks[:HIT_K] if chunk_matches(case, c))
            if match_count == 0:
                correct += 1

    total = len(rejection_cases)
    accuracy = correct / max(1, total)
    print(f"\nFast Gate Rejection: {correct}/{total} = {accuracy:.0%} (threshold: {REJECTION_ACC_MIN:.0%})")
    assert accuracy >= REJECTION_ACC_MIN, (
        f"拒答准确率 {accuracy:.0%} 低于门禁 {REJECTION_ACC_MIN:.0%}"
    )

"""Golden QA 检索系统集成测试（Wave 3.4 · Plan-RAG R5-2 Hit@3 门禁）。
v0.5：支持多相关文档标注 + 拒答测试。
"""

from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import embedder
from app.services.ingestion.embedder import EMBEDDING_DIM
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.types import RetrievedChunk
from tests.golden_qa_loader import (
    FIXTURES,
    GOLDEN_DOCX,
    GOLDEN_MD,
    GOLDEN_QA_CASES,
    GoldenQACase,
    HIT_K,
    chunk_matches,
    hit_at_k,
    reciprocal_rank,
)

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-z0-9]+")


def _lexical_mock_vector(text: str) -> list[float]:
    """mock_embed（纯词表 overlap）——依赖 HIT_K 命中门控。"""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    dim = _get_embedding_dim()
    values: list[float] = []
    while len(values) < dim:
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            num = int.from_bytes(chunk, "big", signed=False)
            values.append((num % 1000) / 1000.0 - 0.5)
            if len(values) >= dim:
                break
        digest = hashlib.sha256(digest).digest()
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _get_embedding_dim() -> int:
    """读取当前 settings 中的 embedding 维度。"""
    return settings.embedding_dim


@pytest.fixture(autouse=True)
def _mock_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有 golden 测试使用 mock 嵌入（避免真实 API 调用）。"""
    monkeypatch.setattr(embedder, "embed_texts", _mock_embed_texts)


async def _mock_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_lexical_mock_vector(t) for t in texts]


import hashlib


def _make_golden_pdf(path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Employee Handbook")
    c.drawString(72, 690, "Chapter 1 Attendance")
    c.drawString(72, 660, "Apply annual leave two weeks")
    c.showPage()
    c.drawString(72, 720, "in advance. After one year: annual leave 10 days.")
    c.save()


def _make_golden_docx(path):
    from docx import Document
    doc = Document()
    doc.add_heading("考勤制度", level=1)
    doc.add_heading("1.1 年假", level=2)
    doc.add_paragraph("员工年满一年后可享受年假10天。")
    doc.save(str(path))


async def _ingest_fixture(
    *,
    kb_id,
    user_id,
    source,
    file_type,
    upload_dir,
) -> Document:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=source.name,
            file_type=file_type, file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        return row


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


from tests.conftest import create_test_kb as _create_kb


@pytest.mark.parametrize("case", GOLDEN_QA_CASES, ids=lambda c: c.case_id)
@pytest.mark.asyncio
async def test_golden_qa_hit_at_3(
    client: AsyncClient,
    register_and_login,
    upload_dir,
    case: GoldenQACase,
    tmp_path: Path,
) -> None:
    """每道 golden QA 题：入库黄金文档 → 检索 → 验证 Top-3 命中。"""
    headers, user = await register_and_login(prefix=case.case_id.replace("-", ""))
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    if hasattr(case, "file_type") and case.file_type == "docx":
        pytest.importorskip("docx")
        if not GOLDEN_DOCX.exists():
            _make_golden_docx(GOLDEN_DOCX)
        source = GOLDEN_DOCX
        file_type = "docx"
    elif hasattr(case, "file_type") and case.file_type == "pdf":
        pytest.importorskip("reportlab")
        source = tmp_path / "golden_handbook.pdf"
        _make_golden_pdf(source)
        file_type = "pdf"
    else:
        source = GOLDEN_MD
        file_type = "md"

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user["id"],
        source=source,
        file_type=file_type,
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_id,
            query=case.query,
            top_k=HIT_K,
        )

    assert chunks, f"{case.case_id} 检索无结果"

    passed = hit_at_k(chunks, case, k=HIT_K)

    if case.expect_rejection:
        match_details = [(c.section_title, c.page_number, c.content[:60]) for c in chunks[:HIT_K] if chunk_matches(case, c)]
        assert passed, (
            f"{case.case_id} 拒答失败：Top-3 内存在匹配结果 "
            f"{match_details}"
        )
    else:
        assert passed, (
            f"{case.case_id} Hit@{HIT_K} 未命中{'（需 ≥{} 个匹配）'.format(case.min_match) if case.min_match > 1 else ''}；"
            f"Top-{HIT_K}="
            f"{[(c.section_title, c.page_number, c.content[:40]) for c in chunks[:HIT_K]]}"
        )

    rr = reciprocal_rank(chunks, case, k=HIT_K)
    if rr < 1.0:
        print(f"  {case.case_id}: RR={rr:.3f}")


REJECTION_ACCURACY_MIN = 0.80  # 拒答准确率门禁 >=80%


@pytest.mark.asyncio
async def test_golden_rejection_accuracy(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """全量拒答题系统级门禁：拒答准确率 >=80%"""
    headers, user = await register_and_login(prefix="gd-rej")
    kb = await _create_kb(client, headers, user)

    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD, file_type="md",
        upload_dir=upload_dir,
    )

    rejection_cases = [c for c in GOLDEN_QA_CASES if c.expect_rejection]
    correct = 0

    async with SessionLocal() as db:
        for case in rejection_cases:
            chunks = await retrieve_chunks(
                db, kb_id=uuid.UUID(kb["id"]),
                query=case.query, top_k=HIT_K,
            )
            match_count = sum(1 for c in chunks[:HIT_K] if chunk_matches(case, c))
            if match_count == 0:
                correct += 1

    total = len(rejection_cases)
    accuracy = correct / total if total > 0 else 1.0
    print(f"  拒答准确率: {correct}/{total} = {accuracy:.0%}  (门禁: >=80%)")
    assert accuracy >= REJECTION_ACCURACY_MIN, (
        f"拒答准确率 {accuracy:.0%} ({correct}/{total}) 低于门禁 {REJECTION_ACCURACY_MIN:.0%}"
    )

"""Wave 3.5 golden_qa Hit@3：标准问题 Top-3 内须命中预期 chunk/章节。
v0.5：支持多相关文档标注 + 拒答测试。
"""

from __future__ import annotations

import asyncio
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
    """测试专用 mock：按 CJK 字 / 英文词重叠近似语义，便于 Hit@3 稳定验检索。"""
    tokens: set[str] = set(_CJK.findall(text))
    tokens.update(_LATIN.findall(text.lower()))
    vec = [0.0] * EMBEDDING_DIM
    for token in tokens:
        seed = sum(ord(ch) for ch in token)
        for j in range(8):
            idx = (seed * (j + 1) * 17 + j * 31) % EMBEDDING_DIM
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def lexical_mock_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """本文件内入库与检索均用词重叠 mock，避免 hash mock 与 FTS 排名漂移。"""
    monkeypatch.setattr(embedder, "_mock_vector", _lexical_mock_vector)


from tests.conftest import create_test_kb as _create_kb


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

    await asyncio.wait_for(process_document_ingestion(doc_id), timeout=60)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None, "Document not found after ingestion"
        # Poll up to 60s for completion
        for attempt in range(60):
            if row.status == DocumentStatus.completed:
                return row
            if row.status == DocumentStatus.failed:
                break
            await asyncio.sleep(1)
            row = await db.get(Document, doc_id)
        assert row.status == DocumentStatus.completed, (
            f"Expected completed, got {row.status}"
            f"{' - error: ' + row.error_message[:200] if row.error_message else ''}"
        )
        return row


def _make_golden_docx(path: Path) -> None:
    """与 golden_handbook.md 对齐的最小 DOCX（含所有章节）。"""
    from docx import Document as DocxDocument

    doc = DocxDocument()
    doc.add_heading("员工手册", level=1)
    doc.add_heading("第一章 考勤制度", level=2)
    doc.add_heading("1.1 年假", level=3)
    doc.add_paragraph(
        "员工年满一年后可享受年假10天。年假须提前两周申请，由直属主管审批后方可休假。"
    )
    doc.add_heading("1.2 迟到", level=3)
    doc.add_paragraph("迟到 30 分钟以内按事假半天处理；超过 30 分钟按旷工半天处理。")
    doc.add_heading("第三章 考勤补充", level=2)
    doc.add_heading("3.1 加班", level=3)
    doc.add_paragraph("工作日加班按基本工资 1.5 倍计算加班费。")
    doc.add_heading("3.2 出差", level=3)
    doc.add_paragraph("出差期间每日补贴：一线城市 200 元。住宿费实报实销。")
    doc.add_heading("第四章 职业发展", level=2)
    doc.add_heading("4.1 培训", level=3)
    doc.add_paragraph("员工每年可参加不超过 5 天的外部培训，费用由公司承担。")
    doc.add_heading("5.1 离职通知期", level=2)
    doc.add_paragraph("试用期员工提前 3 天通知；正式员工提前 30 天通知。")
    doc.save(str(path))


def _make_golden_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 750, "Employee Handbook")
    c.drawString(72, 720, "Chapter 1 Attendance Policy")
    c.drawString(72, 690, "Section 1.1: Annual Leave Entitlement")
    c.drawString(72, 660, "Employees who have completed one year of service")
    c.drawString(72, 640, "are entitled to 10 days of annual leave.")
    c.drawString(72, 610, "Leave must be applied two weeks in advance.")
    c.showPage()
    c.drawString(72, 750, "1.1 Annual Leave Details")
    c.drawString(72, 720, "Annual leave: 10 days per year.")
    c.drawString(72, 690, "Apply at least two weeks in advance.")
    c.drawString(72, 660, "Page 2 contains the detailed policy summary.")
    c.save()


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GOLDEN_QA_CASES, ids=[c.case_id for c in GOLDEN_QA_CASES])
async def test_golden_qa_hit_at_3(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
    case: GoldenQACase,
) -> None:
    """golden_qa.json 各题：hybrid 检索 Top-3 内须命中预期 chunk。

    正常 case：至少 min_match 个相关 chunk 在 Top-3 内。
    拒答 case：Top-3 内无一匹配（无相关结果）。
    """
    headers, user = await register_and_login(prefix=f"golden-{case.case_id.lower()}")
    kb = await _create_kb(client, headers, user, name=f"Hit@3 {case.case_id}")
    kb_id = UUID(kb["id"])
    user_id = UUID(user["id"])

    if case.source == "md":
        source = GOLDEN_MD
        file_type = "md"
    elif case.source == "docx":
        pytest.importorskip("docx")
        if not GOLDEN_DOCX.exists():
            _make_golden_docx(GOLDEN_DOCX)
        source = GOLDEN_DOCX
        file_type = "docx"
    else:
        pytest.importorskip("reportlab")
        source = tmp_path / "golden_handbook.pdf"
        _make_golden_pdf(source)
        file_type = "pdf"

    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
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
        # 拒答 case：期望无一匹配
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

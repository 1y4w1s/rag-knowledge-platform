"""入库进度：阶段码、百分比、OCR 页文案（NW-4）。

铁律：``progress_percent == 100`` 当且仅当 ``status == completed``。
失败 / 排队时进度字段为 null。禁止把上传 XHR 100% 写入 Document。
"""

from __future__ import annotations

import time
from uuid import UUID

from app.core.database import SessionLocal
from app.models.document import Document

STAGE_PARSING = "parsing"
STAGE_CHUNKING = "chunking"
STAGE_EMBEDDING = "embedding"

INGESTION_STAGE_LABELS: dict[str, str] = {
    STAGE_PARSING: "正在解析…",
    STAGE_CHUNKING: "正在切片…",
    STAGE_EMBEDDING: "正在向量化…",
}

OCR_RECOGNIZING_LABEL = "正在识别…"

# parsing 带 OCR 页插值区间
_OCR_PERCENT_LO = 10
_OCR_PERCENT_HI = 40


def label_for(stage: str | None, *, has_detail: bool = False) -> str:
    if has_detail and (stage is None or stage == STAGE_PARSING):
        return OCR_RECOGNIZING_LABEL
    if stage is None:
        return ""
    return INGESTION_STAGE_LABELS.get(stage, stage)


def percent_for_ocr_page(page_number: int, page_count: int) -> int:
    """OCR 第 n/m 页 → [10, 40] 插值；m<=0 时回落 10。"""
    if page_count <= 0:
        return _OCR_PERCENT_LO
    ratio = min(max(page_number, 0), page_count) / page_count
    return min(
        _OCR_PERCENT_HI,
        _OCR_PERCENT_LO + int((_OCR_PERCENT_HI - _OCR_PERCENT_LO) * ratio),
    )


def clear_progress_fields(doc: Document) -> None:
    doc.processing_stage = None
    doc.progress_percent = None
    doc.progress_detail = None


def set_completed_progress(doc: Document) -> None:
    doc.processing_stage = None
    doc.progress_percent = 100
    doc.progress_detail = None


async def update_document_progress(
    document_id: UUID,
    *,
    stage: str,
    percent: int,
    detail: str | None = None,
) -> None:
    """独立 session 写入进度列；不改 status。percent 须 < 100。"""
    if percent >= 100:
        raise ValueError("progress_percent must be < 100 until completed")
    async with SessionLocal() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            return
        doc.processing_stage = stage
        doc.progress_percent = percent
        doc.progress_detail = detail[:64] if detail else None
        await db.commit()


class ProgressThrottler:
    """OCR 页更新节流：末页必发；否则间隔 ≥ min_interval_s。"""

    def __init__(self, min_interval_s: float = 0.5) -> None:
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def allow(self, page_number: int, page_count: int) -> bool:
        if page_number >= page_count:
            self._last = time.monotonic()
            return True
        now = time.monotonic()
        if self._last == 0.0 or (now - self._last) >= self.min_interval_s:
            self._last = now
            return True
        return False

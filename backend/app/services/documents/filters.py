"""单库文档列表高级筛选（R1-4 / Plan-10-4）。"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import status
from app.core.exceptions import ValidationError
from sqlalchemy import ColumnElement, and_

from app.models.document import Document
from app.models.enums import DocumentStatus

ALLOWED_FILE_TYPES = frozenset({"pdf", "docx", "txt", "md"})


def normalize_file_types(raw: list[str] | None) -> list[str] | None:
    if not raw:
        return None
    normalized: list[str] = []
    for item in raw:
        for part in item.split(","):
            file_type = part.strip().lower()
            if file_type and file_type in ALLOWED_FILE_TYPES:
                normalized.append(file_type)
    if not normalized:
        return None
    return list(dict.fromkeys(normalized))


def normalize_statuses(raw: list[str] | None) -> list[DocumentStatus] | None:
    if not raw:
        return None
    normalized: list[DocumentStatus] = []
    for item in raw:
        for part in item.split(","):
            token = part.strip().lower()
            if not token:
                continue
            if token == "processing":
                normalized.extend(
                    [DocumentStatus.queued, DocumentStatus.processing]
                )
                continue
            try:
                normalized.append(DocumentStatus(token))
            except ValueError:
                continue
    if not normalized:
        return None
    return list(dict.fromkeys(normalized))


def validate_uploaded_range(
    uploaded_from: date | None,
    uploaded_to: date | None,
) -> None:
    if (
        uploaded_from is not None
        and uploaded_to is not None
        and uploaded_from > uploaded_to
    ):
        raise ValidationError("上传日期起不能晚于止")


def build_filter_conditions(
    *,
    file_types: list[str] | None,
    statuses: list[DocumentStatus] | None,
    uploaded_from: date | None,
    uploaded_to: date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if file_types:
        conditions.append(Document.file_type.in_(file_types))
    if statuses:
        conditions.append(Document.status.in_(statuses))
    if uploaded_from is not None:
        start = datetime.combine(uploaded_from, time.min, tzinfo=timezone.utc)
        conditions.append(Document.created_at >= start)
    if uploaded_to is not None:
        end = datetime.combine(uploaded_to, time.max, tzinfo=timezone.utc)
        conditions.append(Document.created_at <= end)
    return conditions


def apply_document_list_filters(
    stmt,
    *,
    file_types: list[str] | None,
    statuses: list[DocumentStatus] | None,
    uploaded_from: date | None,
    uploaded_to: date | None,
):
    conditions = build_filter_conditions(
        file_types=file_types,
        statuses=statuses,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
    )
    if conditions:
        return stmt.where(and_(*conditions))
    return stmt

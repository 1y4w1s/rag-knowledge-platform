"""NW-45 · 上传落盘前 magic 双检（伪装扩展名 422 · 合法样例过）。"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ValidationError
from app.models.document import Document
from app.services.documents.magic import assert_content_matches_extension
from tests.conftest import create_test_kb as _create_kb

# 最小合法样例头（非完整可解析文档，仅过上传门）
_PDF_OK = b"%PDF-1.4\n% minimal\n"
_OOXML_OK = b"PK\x03\x04" + b"\x00" * 20  # ZIP local file header 起头
_PNG_OK = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_JPEG_OK = b"\xff\xd8\xff\xe0" + b"\x00" * 8
_TXT_OK = "你好 索隐\nplain text".encode("utf-8")
_MD_OK = b"# Title\n\nbody\n"


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def skip_ingestion(monkeypatch: pytest.MonkeyPatch) -> None:
    """本叶只验上传门；不完整二进制头勿进 parse。"""
    monkeypatch.setattr(
        "app.services.documents.upload.enqueue_document_ingestion",
        AsyncMock(return_value=None),
    )


@pytest.mark.parametrize(
    "filename,content",
    [
        ("evil.pdf", b"not a pdf at all"),
        ("evil.pdf", b"MZ\x90\x00fake exe"),
        ("fake.docx", b"%PDF-1.4 disguise"),
        ("fake.xlsx", b"plain spreadsheet pretender"),
        ("fake.pptx", b"\xff\xd8\xff jpeg as pptx"),
        ("fake.png", b"%PDF-1.4"),
        ("fake.jpg", b"\x89PNG\r\n\x1a\n"),
        ("fake.txt", b"%PDF-1.4 text disguise"),
        ("fake.md", b"PK\x03\x04zip as md"),
        ("bin.txt", b"\xff\xfe\x00\x00not utf8"),
    ],
)
@pytest.mark.asyncio
async def test_nw45_spoofed_extension_422_no_row(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    filename: str,
    content: bytes,
) -> None:
    headers, user = await register_and_login(prefix=f"nw45-spoof-{filename}")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", (filename, content, "application/octet-stream"))],
    )
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "不符" in detail or "伪装" in detail or "UTF-8" in detail

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
            )
        ).all()
        assert rows == []

    kb_root = upload_dir / kb["id"]
    if kb_root.exists():
        files = [p for p in kb_root.rglob("*") if p.is_file()]
        assert files == []


@pytest.mark.parametrize(
    "filename,content,mime",
    [
        ("ok.pdf", _PDF_OK, "application/pdf"),
        ("ok.docx", _OOXML_OK, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("ok.xlsx", _OOXML_OK, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("ok.pptx", _OOXML_OK, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("ok.png", _PNG_OK, "image/png"),
        ("ok.jpg", _JPEG_OK, "image/jpeg"),
        ("ok.txt", _TXT_OK, "text/plain"),
        ("ok.md", _MD_OK, "text/markdown"),
    ],
)
@pytest.mark.asyncio
async def test_nw45_legitimate_samples_pass_gate(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    skip_ingestion: None,
    filename: str,
    content: bytes,
    mime: str,
) -> None:
    """合法头过上传门（201）；入库可能因内容不完整失败，本叶只验门闸。"""
    headers, user = await register_and_login(prefix=f"nw45-ok-{filename}")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", (filename, content, mime))],
    )
    assert resp.status_code == 201, resp.text
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == filename

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
            )
        ).all()
        assert len(rows) == 1


def test_nw45_unit_assert_helpers() -> None:
    assert_content_matches_extension("pdf", _PDF_OK)
    assert_content_matches_extension("txt", _TXT_OK)
    with pytest.raises(ValidationError) as ei:
        assert_content_matches_extension("pdf", b"hello")
    assert "不符" in ei.value.detail

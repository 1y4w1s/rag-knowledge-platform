"""TECH-SEC / PRD §10 SA-2：上传白名单与扩展名校验。"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_sa2_upload_rejects_non_whitelist_extension(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """SA-2（PRD §10）：上传非白名单文件（如 .exe）→ 400，不落库。"""
    headers, user = await register_and_login(prefix="sa2-upload")
    kb = await _create_kb(client, headers, user)

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("virus.exe", b"MZ", "application/octet-stream"))],
    )
    assert resp.status_code == 422
    assert "不支持的文件类型" in resp.json()["detail"]

    async with SessionLocal() as db:
        result = await db.scalars(
            select(Document).where(Document.kb_id == uuid.UUID(kb["id"]))
        )
        assert result.all() == []

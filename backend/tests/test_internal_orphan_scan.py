"""F2（R1）：/api/v1/internal/orphan-scan 双因子鉴权 + 删除二次确认护栏。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from tests.fixtures.audit_events import _register_org_admin


@pytest.mark.asyncio
async def test_orphan_scan_delete_requires_confirm(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dry_run=False 无 confirm → 400；带 confirm → 200（空目录 deleted=0）。"""
    headers, _ = await _register_org_admin(client, prefix="orphan-int")
    monkeypatch.setattr(settings, "orphan_scan_token", "secret-token")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "orphan_grace_hours", 24.0)
    monkeypatch.setattr(settings, "orphan_max_delete", 100)

    # 无 confirm：拒绝执行删除
    denied = await client.post(
        "/api/v1/internal/orphan-scan?dry_run=false",
        headers={**headers, "X-Orphan-Scan-Token": "secret-token"},
    )
    assert denied.status_code == 400

    # 带 confirm：放行（空目录，实际删除 0）
    ok = await client.post(
        "/api/v1/internal/orphan-scan?dry_run=false&confirm=true",
        headers={**headers, "X-Orphan-Scan-Token": "secret-token"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["dry_run"] is False
    assert body["deleted"] == 0
    assert "operator" in body

    # 干跑默认仍可用（无需 confirm）
    dry = await client.post(
        "/api/v1/internal/orphan-scan",
        headers={**headers, "X-Orphan-Scan-Token": "secret-token"},
    )
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True


@pytest.mark.asyncio
async def test_orphan_scan_wrong_token_forbidden(
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = await _register_org_admin(client, prefix="orphan-int-2")
    monkeypatch.setattr(settings, "orphan_scan_token", "secret-token")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    bad = await client.post(
        "/api/v1/internal/orphan-scan",
        headers={**headers, "X-Orphan-Scan-Token": "wrong"},
    )
    assert bad.status_code == 403

"""D1 GraphRAG backfill + merge 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from tests.conftest import create_test_kb


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock 实体抽取（避免依赖 DeepSeek API Key）。"""
    # patch extract_entities_for_document to be a no-op
    import app.api.backfill as backfill_mod
    from app.services.rag import entity_extractor as ee_mod

    async def _fake_extract(db, doc):
        pass

    monkeypatch.setattr(ee_mod, "extract_entities_for_document", _fake_extract)
    monkeypatch.setattr(backfill_mod, "extract_entities_for_document", _fake_extract)
    monkeypatch.setattr("app.services.rag.entity_extractor.extract_entities_for_document", _fake_extract)


@pytest.mark.asyncio
async def test_backfill_entities_dry_run(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dry_run 返回待处理文档列表，不执行抽取。"""
    headers, user = await register_and_login(prefix="bf-dry")
    kb = await create_test_kb(client, headers, user, name="backfill 干跑")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    # 直接插入 2 个已完成的文档（entity_extracted_at IS NULL）
    async with SessionLocal() as db:
        for i in range(2):
            doc = Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename=f"doc_{i}.txt",
                file_type="txt",
                file_size=100,
                storage_path=f"/tmp/{i}.txt",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
            )
            db.add(doc)
        await db.commit()

    resp = await client.post(
        f"/api/v1/internal/backfill/entities?dry_run=true&batch_size=10&kb_id={kb['id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "dry_run"
    assert data["pending"] == 2, f"expected 2, got {data['pending']}: {data}"
    assert len(data["documents"]) == 2


@pytest.mark.asyncio
async def test_backfill_entities_skips_already_extracted(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """entity_extracted_at 不为 NULL 的文档被跳过。"""
    headers, user = await register_and_login(prefix="bf-skip")
    kb = await create_test_kb(client, headers, user, name="backfill 跳过")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        # 一个已有 entity_extracted_at
        doc1 = Document(
            id=uuid.uuid4(),
            kb_id=kb_id,
            filename="already_done.txt",
            file_type="txt",
            file_size=100,
            storage_path="/tmp/done.txt",
            status=DocumentStatus.completed,
            uploaded_by=user_id,
            entity_extracted_at=datetime.now(timezone.utc),
        )
        db.add(doc1)
        # 一个待处理
        doc2 = Document(
            id=uuid.uuid4(),
            kb_id=kb_id,
            filename="pending.txt",
            file_type="txt",
            file_size=100,
            storage_path="/tmp/pending.txt",
            status=DocumentStatus.completed,
            uploaded_by=user_id,
        )
        db.add(doc2)
        await db.commit()

    resp = await client.post(
        f"/api/v1/internal/backfill/entities?dry_run=true&batch_size=10&kb_id={kb['id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pending"] == 1


@pytest.mark.asyncio
async def test_backfill_entities_real_run(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实跑后 entity_extracted_at 被设置，审计事件写入。"""
    headers, user = await register_and_login(prefix="bf-real")
    kb = await create_test_kb(client, headers, user, name="backfill 实跑")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename="need_extract.txt",
            file_type="txt",
            file_size=100,
            storage_path="/tmp/need.txt",
            status=DocumentStatus.completed,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    resp = await client.post(
        f"/api/v1/internal/backfill/entities?dry_run=false&batch_size=5&kb_id={kb['id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["succeeded"] == 1
    assert data["failed"] == 0

    # 验证 entity_extracted_at 已设置
    async with SessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one()
        assert doc.entity_extracted_at is not None

    # 验证审计事件
    from tests.fixtures.audit_events import _count_audit_logs
    count = await _count_audit_logs(action="backfill_entities")
    assert count >= 1


@pytest.mark.asyncio
async def test_backfill_merge_entities_dry_run(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """merge-entities dry_run 返回候选合并对。"""
    headers, user = await register_and_login(prefix="bf-merge-dry")
    kb = await create_test_kb(client, headers, user, name="merge 干跑")
    kb_id = uuid.UUID(kb["id"])

    # 用真实 merge_fuzzy_entities，但需要 pg_trgm 启用
    # mock 它来测试 API 层——需 patch backfill 模块的已绑定引用
    async def _fake_merge(db, _kb_id, *, threshold=0.7, dry_run=True):
        return {
            "candidates": 2,
            "merged": 1,
            "dry_run": dry_run,
            "pairs": [{"keep": str(uuid.uuid4()), "remove": str(uuid.uuid4())}],
        } if dry_run else {
            "candidates": 2,
            "merged": 1,
            "dry_run": False,
            "removed_entities": 1,
        }

    monkeypatch.setattr("app.api.backfill.merge_fuzzy_entities", _fake_merge)

    resp = await client.post(
        f"/api/v1/internal/backfill/merge-entities?kb_id={kb_id}&dry_run=true",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dry_run"] is True
    assert data["merged"] == 1
    assert "pairs" in data


@pytest.mark.asyncio
async def test_backfill_merge_entities_real_run(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """merge-entities 实跑写入审计事件。"""
    headers, user = await register_and_login(prefix="bf-merge-real")
    kb = await create_test_kb(client, headers, user, name="merge 实跑")
    kb_id = uuid.UUID(kb["id"])

    async def _fake_merge_real(db, _kb_id, *, threshold=0.7, dry_run=True):
        if dry_run:
            return {"candidates": 2, "merged": 1, "dry_run": True, "pairs": []}
        return {"candidates": 2, "merged": 1, "dry_run": False, "removed_entities": 1}

    monkeypatch.setattr("app.api.backfill.merge_fuzzy_entities", _fake_merge_real)

    resp = await client.post(
        f"/api/v1/internal/backfill/merge-entities?kb_id={kb_id}&dry_run=false",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dry_run"] is False
    assert data["merged"] == 1

    # 验证审计事件
    from tests.fixtures.audit_events import _count_audit_logs
    count = await _count_audit_logs(action="merge_fuzzy_entities")
    assert count >= 1


@pytest.mark.asyncio
async def test_backfill_entities_kb_isolation(
    register_and_login,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kb_id 过滤确保跨库隔离。"""
    headers, user = await register_and_login(prefix="bf-iso")
    kb_a = await create_test_kb(client, headers, user, name="库A")
    kb_b = await create_test_kb(client, headers, user, name="库B")
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        for kb_name, kb in [("a", kb_a), ("b", kb_b)]:
            doc = Document(
                id=uuid.uuid4(),
                kb_id=uuid.UUID(kb["id"]),
                filename=f"doc_{kb_name}.txt",
                file_type="txt",
                file_size=100,
                storage_path=f"/tmp/{kb_name}.txt",
                status=DocumentStatus.completed,
                uploaded_by=user_id,
            )
            db.add(doc)
        await db.commit()

    # 仅查询库A
    resp = await client.post(
        f"/api/v1/internal/backfill/entities?dry_run=true&kb_id={kb_a['id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pending"] == 1
    assert data["documents"][0]["kb_id"] == kb_a["id"]

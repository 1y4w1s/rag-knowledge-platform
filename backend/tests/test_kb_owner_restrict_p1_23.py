"""P1-23 落地测试：knowledge_bases owner FK CASCADE → RESTRICT + dissolve 兼容回归。

口径（拍板文档 audit-p1-20-p1-23-role-and-cascade-decision.md §6.2 / §9.2）：
- 有 KB 归属时删用户/组织 → FK 约束**显式失败**（fail-closed）；
- 必须先显式处理 KB（`delete_knowledge_base` + `remove_kb_tree` 清盘，或转移
  所有权）才能删用户/组织；
- dissolve 组织流程正常走通（显式删 KB 行 + 磁盘清盘 + 审计留痕）；
- 与 NW-41 一致：个人库真删必须清盘后才可删用户。
"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AccountType
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.organization.dissolve import dissolve_organization


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _create_personal_kb(
    client: AsyncClient,
    register_and_login,
    *,
    prefix: str,
    name: str = "P1-23 个人库",
) -> tuple[dict[str, str], dict, dict]:
    headers, user = await register_and_login(prefix=prefix)
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "personal"},
        json={"name": name},
    )
    assert resp.status_code == 201
    return headers, user, resp.json()


async def _create_org_kb(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    *,
    name: str = "P1-23 组织库",
) -> dict:
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": user["org_id"]},
        json={"name": name, "org_unit_id": None},
    )
    assert resp.status_code == 201
    return resp.json()


async def _upload_file(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    filename: str,
    content: bytes,
) -> None:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_user_with_personal_kb_fails_fk_restrict(
    client: AsyncClient,
    register_and_login,
) -> None:
    """有个人库归属时删用户 → FK 约束显式失败，库与用户均保留。"""
    _headers, user, kb = await _create_personal_kb(
        client, register_and_login, prefix="p123-user"
    )
    user_id = uuid.UUID(user["id"])
    kb_id = uuid.UUID(kb["id"])

    async with SessionLocal() as db:
        u = await db.get(User, user_id)
        assert u is not None
        await db.delete(u)
        with pytest.raises(IntegrityError) as exc_info:
            await db.commit()
        assert "knowledge_bases_owner_user_id_fkey" in str(exc_info.value)
        await db.rollback()

    async with SessionLocal() as db:
        assert await db.get(User, user_id) is not None
        assert await db.get(KnowledgeBase, kb_id) is not None


@pytest.mark.asyncio
async def test_delete_org_with_org_kb_fails_fk_restrict(
    client: AsyncClient,
    register_and_login,
) -> None:
    """有组织库归属时删 org → FK 约束显式失败，组织与库均保留。"""
    headers, user = await register_and_login(
        prefix="p123-org",
        account_type="enterprise",
        org_name="P1-23 禁删公司",
    )
    kb = await _create_org_kb(client, headers, user)
    org_id = uuid.UUID(user["org_id"])
    kb_id = uuid.UUID(kb["id"])

    async with SessionLocal() as db:
        org = await db.get(Organization, org_id)
        assert org is not None
        with pytest.raises(IntegrityError) as exc_info:
            # 裸 SQL 批量删（等同 DB 层「裸删 org」），验证 owner FK RESTRICT 拦截
            await db.execute(delete(Organization).where(Organization.id == org_id))
        assert "knowledge_bases_owner_org_id_fkey" in str(exc_info.value)
        await db.rollback()

    async with SessionLocal() as db:
        assert await db.get(Organization, org_id) is not None
        assert await db.get(KnowledgeBase, kb_id) is not None


@pytest.mark.asyncio
async def test_dissolve_org_with_kb_clears_rows_and_disk(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """dissolve 兼容 RESTRICT：删 org 前显式删 KB 行 + 磁盘清盘 + 审计留痕。"""
    headers, user = await register_and_login(
        prefix="p123-dissolve",
        account_type="enterprise",
        org_name="P1-23 解散公司",
    )
    org_id = uuid.UUID(user["org_id"])
    kb = await _create_org_kb(client, headers, user, name="解散清盘库")
    kb_id = uuid.UUID(kb["id"])

    await _upload_file(
        client,
        headers,
        kb["id"],
        filename="dissolve-clean.txt",
        content=b"p1-23 dissolve cleanup",
    )
    kb_dir = upload_dir / kb["id"]
    assert kb_dir.is_dir()
    assert any(kb_dir.rglob("*"))

    async with SessionLocal() as db:
        await dissolve_organization(
            db,
            org_id=org_id,
            confirm_name="P1-23 解散公司",
            acting_user_id=uuid.UUID(user["id"]),
        )

    async with SessionLocal() as db:
        assert await db.get(Organization, org_id) is None
        assert await db.get(KnowledgeBase, kb_id) is None

        member_count = await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.org_id == org_id)
        )
        assert member_count == 0

        owner = await db.get(User, uuid.UUID(user["id"]))
        assert owner is not None
        assert owner.account_type == AccountType.personal

        audit_count = await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "org.dissolve",
                AuditLog.resource_id == org_id,
            )
        )
        assert audit_count == 1

    assert not kb_dir.exists()


@pytest.mark.asyncio
async def test_personal_kb_cleanup_disk_before_user_delete(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """NW-41 断言：个人库真删必须清盘；清盘后才可删用户。"""
    headers, user, kb = await _create_personal_kb(
        client, register_and_login, prefix="p123-nw41"
    )
    kb_id = kb["id"]
    user_id = uuid.UUID(user["id"])

    await _upload_file(
        client,
        headers,
        kb_id,
        filename="nw41-clean.txt",
        content=b"nw41 disk cleanup",
    )
    kb_dir = upload_dir / kb_id
    assert kb_dir.is_dir()
    assert any(kb_dir.rglob("*"))

    # 1) 有个人库（含磁盘文件）时删用户 → FK 显式失败
    async with SessionLocal() as db:
        u = await db.get(User, user_id)
        assert u is not None
        await db.delete(u)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    # 2) 先显式删库：delete_knowledge_base + remove_kb_tree 磁盘清盘
    del_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204
    assert not kb_dir.exists()

    # 3) 清盘后再删用户 → 成功
    async with SessionLocal() as db:
        u = await db.get(User, user_id)
        assert u is not None
        await db.delete(u)
        await db.commit()

    async with SessionLocal() as db:
        assert await db.get(User, user_id) is None
        assert await db.get(KnowledgeBase, uuid.UUID(kb_id)) is None

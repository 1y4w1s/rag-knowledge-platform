"""Wave 2.1 知识库 CRUD + require_kb_access / SA-1 测试。"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username, workspace_query


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "Test123!@",
) -> tuple[dict[str, str], dict]:
    email = unique_email("member")
    username = unique_username("kbmember")
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(org_id),
                user_id=user.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return headers, data["user"]


async def _create_kb(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    *,
    name: str = "测试库",
    description: str | None = "描述",
    workspace_kind: str = "default",
) -> dict:
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    params = workspace_query(user, kind=workspace_kind)
    if params.get("workspace") != "personal" and user.get("org_id"):
        payload["org_unit_id"] = None
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=params,
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_personal_user_crud_own_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="personal-kb")

    kb = await _create_kb(client, headers, user, name="个人知识库")
    assert kb["name"] == "个人知识库"
    assert kb["owner_user_id"] == user["id"]
    assert kb["owner_org_id"] is None

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == kb["id"]
    assert items[0]["document_count"] == 0

    get_resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "个人知识库"

    patch_resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
        json={"name": "改名后的库", "description": "新描述"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "改名后的库"

    del_resp = await client.delete(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers)
    assert del_resp.status_code == 204

    after_list = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert after_list.json()["items"] == []


@pytest.mark.asyncio
async def test_enterprise_admin_crud_org_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="org-admin-kb",
        account_type="enterprise",
        org_name="知识库测试公司",
    )

    kb = await _create_kb(client, headers, user, name="企业知识库")
    assert kb["owner_org_id"] == user["org_id"]
    assert kb["owner_user_id"] is None

    get_resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers)
    assert get_resp.status_code == 200

    patch_resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
        json={"name": "企业库 v2"},
    )
    assert patch_resp.status_code == 200

    del_resp = await client.delete(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers)
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_knowledge_base_removes_upload_tree(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """EW-A1 / Plan-3E-4：删库后 upload_dir/{kb_id}/ 不存在。"""
    headers, user = await register_and_login(prefix="kb-del-storage")
    kb = await _create_kb(client, headers, user, name="带文档要删库")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("keep-clean.txt", b"kb delete storage test", "text/plain"))],
    )
    assert upload_resp.status_code == 201

    kb_dir = upload_dir / kb["id"]
    assert kb_dir.is_dir()
    assert any(kb_dir.rglob("*"))

    del_resp = await client.delete(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers)
    assert del_resp.status_code == 204

    assert not kb_dir.exists()


@pytest.mark.asyncio
async def test_double_delete_kb_returns_404_on_second(
    client: AsyncClient,
    register_and_login,
) -> None:
    """R2 WS-2-2 E7：同一 kb 连删两次，第二次 404（幂等）。"""
    headers, user = await register_and_login(prefix="kb-double-del")
    kb = await _create_kb(client, headers, user, name="删两次库")

    first = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert first.status_code == 204

    second = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert second.status_code == 404
    assert second.json()["detail"] == "知识库不存在"


@pytest.mark.asyncio
async def test_org_member_cannot_create_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="admin-for-kb-member",
        account_type="enterprise",
        org_name="成员禁建库公司",
    )
    assert admin_user["org_id"] is not None
    await _create_kb(client, admin_headers, admin_user, name="admin 建的库")

    member_headers, member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    create_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=member_headers,
        params=workspace_query(admin_user),
        json={"name": "成员试图建库"},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["detail"] == "权限不足"


@pytest.mark.asyncio
async def test_org_member_can_read_but_not_delete_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="admin-for-kb-read",
        account_type="enterprise",
        org_name="成员只读公司",
    )
    # 公司公共库：全员可读（含未分配 Member）
    public_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=admin_headers,
        params=workspace_query(admin_user),
        json={"name": "共享库", "org_unit_id": None},
    )
    assert public_resp.status_code == 201
    kb = public_resp.json()

    member_headers, member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    get_resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=member_headers)
    assert get_resp.status_code == 200

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=member_headers,
        params=workspace_query(admin_user),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    patch_resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=member_headers,
        json={"name": "成员试图改名"},
    )
    assert patch_resp.status_code == 403

    del_resp = await client.delete(f"/api/v1/knowledge-bases/{kb['id']}", headers=member_headers)
    assert del_resp.status_code == 403


@pytest.mark.asyncio
async def test_sa1_user_cannot_access_other_personal_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers_a, user_a = await register_and_login(prefix="kb-user-a")
    _headers_b, _user_b = await register_and_login(prefix="kb-user-b")

    kb = await _create_kb(client, headers_a, user_a, name="A 的私有库")

    resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=_headers_b)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"

    del_resp = await client.delete(f"/api/v1/knowledge-bases/{kb['id']}", headers=_headers_b)
    assert del_resp.status_code == 403


@pytest.mark.asyncio
async def test_sa1_user_cannot_access_other_org_knowledge_base(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers_a, admin_a = await register_and_login(
        prefix="org-a",
        account_type="enterprise",
        org_name="公司 A",
    )
    headers_b, _admin_b = await register_and_login(
        prefix="org-b",
        account_type="enterprise",
        org_name="公司 B",
    )

    kb = await _create_kb(client, headers_a, admin_a, name="A 公司库")

    resp = await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该知识库"


@pytest.mark.asyncio
async def test_get_nonexistent_knowledge_base_returns_404(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="kb-404")
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/knowledge-bases/{fake_id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "知识库不存在"


@pytest.mark.asyncio
async def test_knowledge_bases_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_duplicate_kb_name_returns_409(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-dup-create")
    await _create_kb(client, headers, user, name="重复名测试库")

    dup_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
        json={"name": "重复名测试库"},
    )
    assert dup_resp.status_code == 409
    assert "已存在" in dup_resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_duplicate_kb_name_case_insensitive_returns_409(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-dup-case")
    await _create_kb(client, headers, user, name="MyLibrary")

    dup_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
        json={"name": "mylibrary"},
    )
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_update_kb_to_duplicate_name_returns_409(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-dup-patch")
    kb_a = await _create_kb(client, headers, user, name="库 A")
    kb_b = await _create_kb(client, headers, user, name="库 B")

    patch_resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb_b['id']}",
        headers=headers,
        json={"name": "库 A"},
    )
    assert patch_resp.status_code == 409

    unchanged = await client.get(
        f"/api/v1/knowledge-bases/{kb_b['id']}",
        headers=headers,
    )
    assert unchanged.json()["name"] == "库 B"
    assert unchanged.json()["id"] == kb_b["id"]
    assert kb_a["id"] != kb_b["id"]


@pytest.mark.asyncio
async def test_different_users_can_use_same_kb_name(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers_a, user_a = await register_and_login(prefix="kb-dup-user-a")
    headers_b, user_b = await register_and_login(prefix="kb-dup-user-b")

    kb_a = await _create_kb(client, headers_a, user_a, name="通用库名")
    kb_b = await _create_kb(client, headers_b, user_b, name="通用库名")

    assert kb_a["id"] != kb_b["id"]


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_list_kb_stats_for_empty_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-list-empty")

    kb = await _create_kb(client, headers, user, name="空库统计")
    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert list_resp.status_code == 200

    item = list_resp.json()["items"][0]
    assert item["id"] == kb["id"]
    assert item["document_count"] == 0
    assert item["processing_count"] == 0
    assert item["failed_count"] == 0
    assert item["updated_at"] == item["created_at"]


@pytest.mark.asyncio
async def test_list_kb_stats_after_document_upload(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="kb-list-upload")
    kb = await _create_kb(client, headers, user, name="有文档库")

    empty_list = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    empty_item = empty_list.json()["items"][0]
    assert empty_item["document_count"] == 0

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert upload_resp.status_code == 201

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    item = list_resp.json()["items"][0]
    assert item["document_count"] == 1
    assert item["processing_count"] == 0
    assert item["failed_count"] == 0
    assert item["updated_at"] >= empty_item["updated_at"]


@pytest.mark.asyncio
async def test_list_kb_processing_and_failed_counts(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-list-status")
    kb = await _create_kb(client, headers, user, name="状态计数库")
    kb_id = uuid.UUID(kb["id"])

    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        docs = [
            Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename="queued.txt",
                file_type="txt",
                file_size=1,
                storage_path="/tmp/queued.txt",
                status=DocumentStatus.queued,
                uploaded_by=uuid.UUID(user["id"]),
                updated_at=now,
            ),
            Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename="processing.pdf",
                file_type="pdf",
                file_size=2,
                storage_path="/tmp/processing.pdf",
                status=DocumentStatus.processing,
                uploaded_by=uuid.UUID(user["id"]),
                updated_at=now + timedelta(seconds=1),
            ),
            Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename="failed.docx",
                file_type="docx",
                file_size=3,
                storage_path="/tmp/failed.docx",
                status=DocumentStatus.failed,
                uploaded_by=uuid.UUID(user["id"]),
                updated_at=now + timedelta(seconds=2),
            ),
            Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename="done.md",
                file_type="md",
                file_size=4,
                storage_path="/tmp/done.md",
                status=DocumentStatus.completed,
                uploaded_by=uuid.UUID(user["id"]),
                updated_at=now + timedelta(seconds=3),
            ),
        ]
        db.add_all(docs)
        await db.commit()

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    item = list_resp.json()["items"][0]
    assert item["document_count"] == 4
    assert item["processing_count"] == 2
    assert item["failed_count"] == 1

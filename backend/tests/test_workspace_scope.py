"""W1 workspace Query 与 scope 筛选测试（T1～T7）。"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization


@pytest.mark.asyncio
async def test_personal_user_list_only_personal_kbs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T1: personal 用户 · ?workspace=personal → 仅 personal 库。"""
    headers, user = await register_and_login(prefix="ws-t1-personal")
    create_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "personal"},
        json={"name": "T1 个人库"},
    )
    assert create_resp.status_code == 201
    kb_id = create_resp.json()["id"]

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "personal"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == kb_id
    assert items[0]["owner_user_id"] == user["id"]
    assert items[0]["owner_org_id"] is None

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": "personal"},
    )
    assert stats_resp.status_code == 200
    assert stats_resp.json()["scope"] == "personal"
    assert stats_resp.json()["knowledge_base_count"] == 1


@pytest.mark.asyncio
async def test_enterprise_admin_personal_workspace_only_own_personal_kbs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T2: enterprise admin · personal workspace → 仅自己的 personal 库（团队库不出现）。"""
    headers, user = await register_and_login(
        prefix="ws-t2-admin",
        account_type="enterprise",
        org_name="T2 双空间公司",
    )
    org_id = user["org_id"]
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        personal_kb = KnowledgeBase(
            id=uuid.uuid4(),
            name="T2 个人库",
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.add(personal_kb)
        await db.commit()
        personal_kb_id = str(personal_kb.id)

    team_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": org_id},
        json={"name": "T2 团队库"},
    )
    assert team_resp.status_code == 201
    team_kb_id = team_resp.json()["id"]

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "personal"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == personal_kb_id
    assert items[0]["owner_org_id"] is None

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": "personal"},
    )
    assert stats_resp.status_code == 200
    assert stats_resp.json()["scope"] == "personal"
    assert stats_resp.json()["knowledge_base_count"] == 1

    team_list = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": org_id},
    )
    assert team_list.status_code == 200
    team_items = team_list.json()["items"]
    assert len(team_items) == 1
    assert team_items[0]["id"] == team_kb_id
    assert team_items[0]["owner_org_id"] == org_id


@pytest.mark.asyncio
async def test_enterprise_admin_team_workspace_stats_scope_organization(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T3: enterprise admin · team workspace → 仅 team 库 · stats scope=organization。"""
    headers, user = await register_and_login(
        prefix="ws-t3-admin",
        account_type="enterprise",
        org_name="T3 团队统计公司",
    )
    org_id = user["org_id"]

    await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": org_id},
        json={"name": "T3 团队库"},
    )

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": org_id},
    )
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["scope"] == "organization"
    assert body["knowledge_base_count"] == 1
    assert body["member_count"] == 1


@pytest.mark.asyncio
async def test_enterprise_member_cannot_create_kb_in_team_workspace(
    client: AsyncClient,
    register_and_login,
) -> None:
    """T4: enterprise member · POST kb · team workspace → 403。"""
    from app.models.enums import AccountType, OrgRole
    from app.models.organization_member import OrganizationMember
    from app.models.user import User
    from app.services.auth.password import hash_password
    from tests.conftest import unique_email, unique_username

    admin_headers, admin_user = await register_and_login(
        prefix="ws-t4-admin",
        account_type="enterprise",
        org_name="T4 成员禁建库",
    )
    org_id = admin_user["org_id"]

    email = unique_email("ws-t4-member")
    username = unique_username("wst4member")
    async with SessionLocal() as db:
        member = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password("password123"),
            account_type=AccountType.enterprise,
        )
        db.add(member)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(org_id),
                user_id=member.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=member_headers,
        params={"workspace": org_id},
        json={"name": "成员试图建库"},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["detail"] == "权限不足"


@pytest.mark.asyncio
async def test_missing_workspace_returns_403_on_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-missing-list")
    resp = await client.get("/api/v1/knowledge-bases", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "缺少工作区参数"


@pytest.mark.asyncio
async def test_missing_workspace_returns_403_on_stats(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-missing-stats")
    resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "缺少工作区参数"


@pytest.mark.asyncio
async def test_missing_workspace_returns_403_on_create(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-missing-create")
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "无 workspace 建库"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "缺少工作区参数"


@pytest.mark.asyncio
async def test_forged_org_workspace_returns_403_on_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(
        prefix="ws-forged-list",
        account_type="enterprise",
        org_name="合法组织",
    )
    forged_org_id = str(uuid.uuid4())
    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": forged_org_id},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该工作区"


@pytest.mark.asyncio
async def test_forged_org_workspace_returns_403_on_stats(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-forged-stats")
    async with SessionLocal() as db:
        other_org = Organization(id=uuid.uuid4(), name="他人组织")
        db.add(other_org)
        await db.commit()
        forged_org_id = str(other_org.id)

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": forged_org_id},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该工作区"


@pytest.mark.asyncio
async def test_forged_org_workspace_returns_403_on_create(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-forged-create")
    forged_org_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": forged_org_id},
        json={"name": "伪造 org 建库"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该工作区"


@pytest.mark.asyncio
async def test_enterprise_user_can_read_own_personal_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="ws-personal-kb",
        account_type="enterprise",
        org_name="有个人库的企业",
    )
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        personal_kb = KnowledgeBase(
            id=uuid.uuid4(),
            name="企业用户的个人库",
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.add(personal_kb)
        await db.commit()
        kb_id = str(personal_kb.id)

    resp = await client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == kb_id
    assert body["owner_user_id"] == user["id"]
    assert body["owner_org_id"] is None


@pytest.mark.asyncio
async def test_invalid_workspace_uuid_returns_400(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="ws-invalid-uuid")
    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "not-a-uuid"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "无效的工作区 ID"

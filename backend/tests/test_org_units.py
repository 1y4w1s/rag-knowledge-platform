"""ORG-2.1：org_units CRUD API — PRD ORG-1-3 §3.5 S1～S6 + 边界 E。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole
from app.models.knowledge_base import KnowledgeBase
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "org-admin",
    org_name: str = "知岸科技",
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    password = "password123"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "enterprise",
            "org_name": org_name,
        },
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _create_unit(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    parent_id: str,
) -> dict:
    resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": name, "parent_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_org_unit_s1_admin_lists_root_only(client: AsyncClient) -> None:
    """S1：公司 Admin 打开组织与部门 — 树仅根节点。"""
    headers, _user = await _register_org_admin(client, prefix="s1-admin")

    resp = await client.get("/api/v1/org-units", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    root = items[0]
    assert root["parent_id"] is None
    assert root["depth"] == 0
    assert root["child_count"] == 0


@pytest.mark.asyncio
async def test_org_unit_s2_admin_creates_two_level_tree(client: AsyncClient) -> None:
    """S2：新建「研发中心」→ 其下新建「后端组」— 树两级。"""
    headers, _user = await _register_org_admin(client, prefix="s2-admin")

    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )
    backend = await _create_unit(
        client, headers, name="后端组", parent_id=rd["id"]
    )

    tree = (await client.get("/api/v1/org-units", headers=headers)).json()["items"]
    assert len(tree) == 3
    by_name = {node["name"]: node for node in tree}
    assert by_name["研发中心"]["depth"] == 1
    assert by_name["研发中心"]["child_count"] == 1
    assert by_name["后端组"]["depth"] == 2
    assert by_name["后端组"]["parent_id"] == rd["id"]
    assert backend["id"] == by_name["后端组"]["id"]


@pytest.mark.asyncio
async def test_org_unit_s3_leaf_unit_has_empty_members(client: AsyncClient) -> None:
    """S3：选择后端组 — 右栏成员表空（API：member_count=0）。"""
    headers, _user = await _register_org_admin(client, prefix="s3-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )
    backend = await _create_unit(
        client, headers, name="后端组", parent_id=rd["id"]
    )

    detail = await client.get(
        f"/api/v1/org-units/{backend['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["member_count"] == 0
    assert data["kb_count"] == 0


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    email = unique_email("member")
    username = unique_username("member")
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
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


@pytest.mark.asyncio
async def test_org_unit_s4_member_cannot_mutate_tree(
    client: AsyncClient,
    register_and_login,
) -> None:
    """S4：非公司 Admin 不能改组织树（MVP 仅 Admin 写树；部门 Admin 任命见 ORG-2.2）。"""
    admin_headers, admin_user = await register_and_login(
        prefix="s4-admin",
        account_type="enterprise",
        org_name="S4 公司",
    )
    root_id = (
        await client.get("/api/v1/org-units", headers=admin_headers)
    ).json()["items"][0]["id"]

    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )
    list_resp = await client.get("/api/v1/org-units", headers=member_headers)
    assert list_resp.status_code == 403

    create_resp = await client.post(
        "/api/v1/org-units",
        headers=member_headers,
        json={"name": "非法部门", "parent_id": root_id},
    )
    assert create_resp.status_code == 403

    patch_resp = await client.patch(
        f"/api/v1/org-units/{root_id}",
        headers=member_headers,
        json={"name": "篡改根"},
    )
    assert patch_resp.status_code == 403

    delete_resp = await client.delete(
        f"/api/v1/org-units/{root_id}",
        headers=member_headers,
    )
    assert delete_resp.status_code == 403


@pytest.mark.asyncio
async def test_org_unit_picker_member_sees_membership_path_only(
    client: AsyncClient,
) -> None:
    """ORG-3.2：Member 可读 picker 路径；不可见兄弟部门。"""
    headers, _admin = await _register_org_admin(client, prefix="picker-admin")
    root_id = (await client.get("/api/v1/org-units", headers=headers)).json()["items"][0][
        "id"
    ]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )
    mk = await _create_unit(
        client, headers, name="市场中心", parent_id=root_id
    )

    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=_admin["org_id"],
    )
    add_resp = await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={
            "user_id": member_user["id"],
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201

    picker_resp = await client.get("/api/v1/org-units/picker", headers=member_headers)
    assert picker_resp.status_code == 200
    names = {item["name"] for item in picker_resp.json()["items"]}
    assert "研发中心" in names
    assert "市场中心" not in names

    admin_picker = await client.get("/api/v1/org-units/picker", headers=headers)
    assert admin_picker.status_code == 200
    admin_names = {item["name"] for item in admin_picker.json()["items"]}
    assert {"研发中心", "市场中心"}.issubset(admin_names)
    assert mk["id"] in {item["id"] for item in admin_picker.json()["items"]}


@pytest.mark.asyncio
async def test_org_unit_s5_delete_empty_leaf(client: AsyncClient) -> None:
    """S5：删除空叶子「后端组」— 204；树更新。"""
    headers, _user = await _register_org_admin(client, prefix="s5-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )
    backend = await _create_unit(
        client, headers, name="后端组", parent_id=rd["id"]
    )

    delete_resp = await client.delete(
        f"/api/v1/org-units/{backend['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    tree = (await client.get("/api/v1/org-units", headers=headers)).json()["items"]
    names = {node["name"] for node in tree}
    assert "后端组" not in names
    rd_node = next(node for node in tree if node["name"] == "研发中心")
    assert rd_node["child_count"] == 0


@pytest.mark.asyncio
async def test_org_unit_s6_cannot_delete_unit_with_knowledge_bases(
    client: AsyncClient,
) -> None:
    """S6：试删有资料库的「研发中心」— 409。"""
    headers, user = await _register_org_admin(client, prefix="s6-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )

    async with SessionLocal() as db:
        db.add(
            KnowledgeBase(
                id=uuid.uuid4(),
                name="研发中心内部库",
                owner_org_id=uuid.UUID(user["org_id"]),
                org_unit_id=uuid.UUID(rd["id"]),
            )
        )
        await db.commit()

    delete_resp = await client.delete(
        f"/api/v1/org-units/{rd['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 409
    assert delete_resp.json()["detail"] == "该部门下仍有资料库"


@pytest.mark.asyncio
async def test_org_unit_e3_cannot_delete_unit_with_children(client: AsyncClient) -> None:
    """E3：删除有子节点的部门 — 409。"""
    headers, _user = await _register_org_admin(client, prefix="e3-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )
    await _create_unit(client, headers, name="后端组", parent_id=rd["id"])

    delete_resp = await client.delete(
        f"/api/v1/org-units/{rd['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 409
    assert delete_resp.json()["detail"] == "请先删除或移动子部门"


@pytest.mark.asyncio
async def test_org_unit_e4_sibling_duplicate_name(client: AsyncClient) -> None:
    """E4：同级重名部门 — 409。"""
    headers, _user = await _register_org_admin(client, prefix="e4-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    await _create_unit(client, headers, name="研发部", parent_id=root_id)

    dup = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "研发部", "parent_id": root_id},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "同级已存在同名部门"


@pytest.mark.asyncio
async def test_org_unit_e10_name_too_long(client: AsyncClient) -> None:
    """E10：超长部门名 65 字 — 400。"""
    headers, _user = await _register_org_admin(client, prefix="e10-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]

    resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "部" * 65, "parent_id": root_id},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_org_unit_admin_can_rename(client: AsyncClient) -> None:
    headers, _user = await _register_org_admin(client, prefix="rename-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(
        client, headers, name="研发中心", parent_id=root_id
    )

    patch = await client.patch(
        f"/api/v1/org-units/{rd['id']}",
        headers=headers,
        json={"name": "研发与创新中心"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "研发与创新中心"

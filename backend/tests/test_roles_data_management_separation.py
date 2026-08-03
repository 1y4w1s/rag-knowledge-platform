"""P1-20 custom_role 口径落地测试（业务拍板选 B：数据面/管理面分离）。

拍板文档：``docs/tasks/audit-p1-20-p1-23-role-and-cascade-decision.md`` §6.1 / §9.1。

钉死的边界：
- **管理面**（成员增删改、部门管理、角色管理、组织设置、邀请、transfer-ownership、
  dissolve）仅 owner 或原生 ``org_role=admin``；``custom_role_is_admin=True`` 的
  member 调任一管理面端点 → **403**（``core/deps.py`` 的 ``require_org_role`` /
  ``require_owner`` 只认 ``org_role`` / ``is_owner``，不认 custom_role）。
- **数据面**：同一用户建库 / 上传 / 采纳按现有 OrgScope 放行
  （``services/org/scope.py`` ``_is_company_admin`` 含 ``custom_role_is_admin``）。
- **审计**：``role.create`` / ``role.update``（含 ``is_admin_level``）事件可查。
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import (
    AccountType,
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    DocumentStatus,
    OrgRole,
    ThreadKind,
    ThreadStatus,
)
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb, unique_email, unique_username
from tests.fixtures.audit_events import (
    _count_audit_logs,
    _latest_audit_log,
    _register_org_admin,
)

pytestmark = pytest.mark.asyncio


async def _create_custom_role_admin(
    client: AsyncClient,
    *,
    prefix: str,
    org_name: str,
) -> dict:
    """建组织 → 原生 admin 创建 is_admin_level 自定义角色 → DB 直插 member 赋角色 → 登录。

    分配写侧未接线（不在本窗），故用 DB 直写 ``OrganizationMember.custom_role_id``
    模拟「已被分配 KB 数据面管理员角色」的成员。
    """
    owner_headers, owner_user = await _register_org_admin(
        client, prefix=prefix, org_name=org_name
    )
    org_id = owner_user["org_id"]

    role_resp = await client.post(
        f"/api/v1/orgs/{org_id}/roles",
        headers=owner_headers,
        json={
            "name": "KB数据面管理员",
            "description": "P1-20 测试角色",
            "is_admin_level": True,
            "permissions": {"*": "admin"},
        },
    )
    assert role_resp.status_code == 201, role_resp.text
    role_id = role_resp.json()["id"]

    email = unique_email(f"crole-{prefix}")
    username = unique_username(f"crole-{prefix}")
    password = "Test123!@"
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
                is_owner=False,
                custom_role_id=uuid.UUID(role_id),
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200, login.text
    data = login.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    # login 响应 user 不含 custom_role 字段；/auth/me 走 get_current_user
    # （JWT claims + resolve_org_context 以 DB 为准），在此钉死注入点。
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    me_user = me.json()
    assert me_user["custom_role_id"] == role_id
    assert me_user["custom_role_is_admin"] is True
    return {
        "headers": headers,
        "user": me_user,
        "org_id": org_id,
        "org_name": org_name,
        "owner_user_id": owner_user["id"],
        "owner_headers": owner_headers,
        "role_id": role_id,
    }


# 管理面端点（6+1 类）。path/body 中的 {占位符} 由测试按 fixture 值填充。
MANAGEMENT_CASES = [
    ("member_add", "post", "/api/v1/organization/members", {"email": "{member_email}"}),
    ("member_remove", "delete", "/api/v1/organization/members/{owner_user_id}", None),
    ("member_role_change", "patch", "/api/v1/organization/members/{owner_user_id}", {"role": "admin"}),
    ("dept_create", "post", "/api/v1/org-units/root", {"name": "越权新部门"}),
    ("dept_rename", "patch", "/api/v1/org-units/{unit_id}", {"name": "越权改名"}),
    ("dept_delete", "delete", "/api/v1/org-units/{unit_id}", None),
    ("role_list", "get", "/api/v1/orgs/{org_id}/roles", None),
    ("role_create", "post", "/api/v1/orgs/{org_id}/roles", {"name": "越权角色", "is_admin_level": True}),
    ("role_update", "put", "/api/v1/orgs/{org_id}/roles/{role_id}", {"name": "越权改名"}),
    ("role_delete", "delete", "/api/v1/orgs/{org_id}/roles/{role_id}", None),
    ("org_settings_get", "get", "/api/v1/organization/settings", None),
    ("org_settings_patch", "patch", "/api/v1/organization/settings", {"name": "越权改名"}),
    ("invite", "post", "/api/v1/organization/invites", {}),
    ("transfer_ownership", "post", "/api/v1/organization/transfer-ownership", {"target_user_id": "{owner_user_id}"}),
    ("dissolve", "post", "/api/v1/organization/dissolve", {"confirm_name": "{org_name}"}),
]


@pytest.mark.parametrize(
    ("case_id", "method", "path_template", "body_template"),
    MANAGEMENT_CASES,
    ids=[case[0] for case in MANAGEMENT_CASES],
)
async def test_custom_role_admin_management_endpoints_403(
    client: AsyncClient,
    case_id: str,
    method: str,
    path_template: str,
    body_template: dict | None,
) -> None:
    """custom_role_is_admin=True 的 member 调全部管理面端点 → 403。"""
    fixture = await _create_custom_role_admin(
        client, prefix=f"mng-{case_id}", org_name=f"越权公司{case_id}"
    )
    values = {
        "org_id": fixture["org_id"],
        "org_name": fixture["org_name"],
        "owner_user_id": fixture["owner_user_id"],
        "role_id": fixture["role_id"],
        "unit_id": str(uuid.uuid4()),
        "member_email": unique_email(f"mng-member-{case_id}"),
    }
    path = path_template.format(**values)
    body = None
    if body_template is not None:
        body = {
            key: (str(val).format(**values) if isinstance(val, str) else val)
            for key, val in body_template.items()
        }
    resp = await client.request(
        method, path, headers=fixture["headers"], json=body
    )
    assert resp.status_code == 403, f"{case_id}: {resp.status_code} {resp.text}"


async def test_custom_role_admin_can_create_org_kb(client: AsyncClient) -> None:
    """同一用户建组织库 → 201（数据面按 OrgScope 放行）。"""
    fixture = await _create_custom_role_admin(
        client, prefix="kb-create", org_name="数据面建库公司"
    )
    kb = await create_test_kb(
        client,
        fixture["headers"],
        fixture["user"],
        name="P1-20建库",
        workspace_kind="organization",
    )
    assert kb["owner_org_id"] == fixture["org_id"]


async def test_custom_role_admin_can_upload_document(client: AsyncClient) -> None:
    """同一用户上传文档 → 201（require_kb_access(write) 由 is_admin_level 放行）。"""
    fixture = await _create_custom_role_admin(
        client, prefix="kb-upload", org_name="数据面上传公司"
    )
    kb = await create_test_kb(
        client,
        fixture["headers"],
        fixture["user"],
        name="P1-20上传",
        workspace_kind="organization",
    )
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=fixture["headers"],
        files=[("files", ("p120.txt", b"p1-20 upload", "text/plain"))],
    )
    assert resp.status_code == 201, resp.text


async def _insert_approval(
    *,
    kb_id: str,
    user_id: str,
    filename: str = "faq-p120.md",
) -> str:
    """直插 agent_approvals 行（含父表 chat_threads / agent_runs）。"""
    approval_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=uuid.UUID(user_id),
                kb_id=uuid.UUID(kb_id),
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=uuid.UUID(user_id),
                mode=AgentRunMode.edit,
                status=AgentRunStatus.completed,
            )
        )
        await db.flush()
        db.add(
            AgentApproval(
                id=approval_id,
                run_id=run_id,
                thread_id=thread_id,
                user_id=uuid.UUID(user_id),
                kind=ApprovalKind.adopt_faq,
                status=ApprovalStatus.pending,
                kb_id=uuid.UUID(kb_id),
                filename=filename,
                payload_json={"title": "P1-20 FAQ", "filename": filename},
            )
        )
        await db.commit()
    return str(approval_id)


async def _fake_adopt_draft_to_kb(db: AsyncSession, approval, kb) -> uuid.UUID:
    """隔离 stub：插入真实 documents(queued) 行并返回其 id（同 G4-3.1 测试）。"""
    doc = Document(
        id=uuid.uuid4(),
        kb_id=kb.id,
        filename=approval.filename,
        file_type="md",
        file_size=10,
        storage_path=f"/tmp/fake-p120/{approval.id}.md",
        status=DocumentStatus.queued,
        uploaded_by=approval.user_id,
    )
    db.add(doc)
    await db.flush()
    return doc.id


async def test_custom_role_admin_can_adopt_approval(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一用户采纳写库审批 → 200（G4-3.1 二次校验由 is_admin_level 放行）。"""
    fixture = await _create_custom_role_admin(
        client, prefix="kb-adopt", org_name="数据面采纳公司"
    )
    kb = await create_test_kb(
        client,
        fixture["headers"],
        fixture["user"],
        name="P1-20采纳",
        workspace_kind="organization",
    )
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=kb["id"], user_id=fixture["user"]["id"]
    )
    resp = await client.post(
        f"/api/v1/agent/approvals/{approval_id}/resolve",
        headers=fixture["headers"],
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "processing"


async def test_role_create_update_audit_events(client: AsyncClient) -> None:
    """role.create / role.update（含 is_admin_level）审计事件可查（按 run/user 维度）。"""
    owner_headers, owner_user = await _register_org_admin(
        client, prefix="role-audit", org_name="角色审计公司"
    )
    org_id = owner_user["org_id"]

    before_create = await _count_audit_logs(action="role.create")
    create_resp = await client.post(
        f"/api/v1/orgs/{org_id}/roles",
        headers=owner_headers,
        json={"name": "审计角色", "is_admin_level": True, "permissions": {"*": "read"}},
    )
    assert create_resp.status_code == 201, create_resp.text
    role_id = create_resp.json()["id"]
    after_create = await _count_audit_logs(action="role.create")
    assert after_create - before_create == 1

    create_log = await _latest_audit_log(action="role.create")
    assert create_log is not None
    assert str(create_log.actor_user_id) == owner_user["id"]
    assert create_log.resource_type == "role"
    assert str(create_log.resource_id) == role_id
    assert create_log.details == {"name": "审计角色", "is_admin_level": True}

    before_update = await _count_audit_logs(action="role.update")
    update_resp = await client.put(
        f"/api/v1/orgs/{org_id}/roles/{role_id}",
        headers=owner_headers,
        json={"name": "审计角色v2", "is_admin_level": False},
    )
    assert update_resp.status_code == 200, update_resp.text
    after_update = await _count_audit_logs(action="role.update")
    assert after_update - before_update == 1

    update_log = await _latest_audit_log(action="role.update")
    assert update_log is not None
    assert str(update_log.actor_user_id) == owner_user["id"]
    assert str(update_log.resource_id) == role_id
    assert update_log.details == {"name": "审计角色v2", "is_admin_level": False}

"""EW-A5 / NW-21：API 限流（user_id + IP 双桶 → 429）。"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.exceptions import RateLimitError
from app.services.auth import api_rate_limit as rl
from app.services.auth.api_rate_limit import (
    ApiRateLimitKind,
    reset_all_api_rate_limits,
)
from tests.conftest import create_test_kb as _create_kb


# 恢复真实限流实现（conftest 默认 noop），断言真实 429 行为而非空跑
pytestmark = pytest.mark.usefixtures("real_api_rate_limit")


@pytest.fixture(autouse=True)
def _isolate_api_rate_limits() -> None:
    reset_all_api_rate_limits()
    yield
    reset_all_api_rate_limits()


@pytest.fixture
def low_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试用小阈值，避免打满 30/20 次生产限额。"""
    monkeypatch.setattr(rl, "CHAT_MAX_REQUESTS", 3)
    monkeypatch.setattr(rl, "UPLOAD_MAX_REQUESTS", 3)


@pytest.mark.asyncio
async def test_chat_exceeds_limit_returns_429(
    client: AsyncClient,
    register_and_login,
    low_api_limits: None,
) -> None:
    headers, user = await register_and_login(prefix="api-rl-chat")
    kb = await _create_kb(client, headers, user, name="限流对话库")
    kb_id = kb["id"]

    for i in range(3):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/chat",
            headers=headers,
            json={"message": f"问题 {i}"},
        )
        assert resp.status_code == 200, resp.text

    blocked = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": "第 4 次应被限流"},
    )
    assert blocked.status_code == 429
    assert "对话" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_upload_exceeds_limit_returns_429(
    client: AsyncClient,
    register_and_login,
    low_api_limits: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    headers, user = await register_and_login(prefix="api-rl-upload")
    kb = await _create_kb(client, headers, user, name="限流上传库")
    kb_id = kb["id"]

    for i in range(3):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            headers=headers,
            files=[("files", (f"note-{i}.txt", f"hello {i}".encode(), "text/plain"))],
        )
        assert resp.status_code == 201, resp.text

    blocked = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", ("blocked.txt", b"too many", "text/plain"))],
    )
    assert blocked.status_code == 429
    assert "上传" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_member_and_admin_share_same_upload_limit(
    client: AsyncClient,
    register_and_login,
    low_api_limits: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """member/admin 均按 user_id 计数，互不影响。"""
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.enums import AccountType, OrgRole
    from app.models.organization_member import OrganizationMember
    from app.models.user import User
    from app.services.auth.password import hash_password
    from tests.conftest import unique_email, unique_username

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    admin_headers, admin_user = await register_and_login(
        prefix="api-rl-admin",
        account_type="enterprise",
        org_name="限流团队",
    )
    kb = await _create_kb(client, admin_headers, admin_user, name="团队库")
    kb_id = kb["id"]

    email = unique_email("api-rl-member")
    username = unique_username("apirlmem")
    password = "Test123!@"
    async with SessionLocal() as db:
        member = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(member)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(admin_user["org_id"]),
                user_id=member.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for i in range(3):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            headers=admin_headers,
            files=[("files", (f"admin-{i}.txt", f"admin {i}".encode(), "text/plain"))],
        )
        assert resp.status_code == 201

    blocked_admin = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=admin_headers,
        files=[("files", ("admin-blocked.txt", b"x", "text/plain"))],
    )
    assert blocked_admin.status_code == 429

    # member 无 upload 权限 → 403，不计入 upload 限流
    denied_member = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=member_headers,
        files=[("files", ("member-0.txt", b"m", "text/plain"))],
    )
    assert denied_member.status_code == 403

    # member 对 chat 有 read 权限，独立 chat 限额
    for i in range(3):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/chat",
            headers=member_headers,
            json={"message": f"成员问 {i}"},
        )
        assert resp.status_code == 200

    blocked_member = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=member_headers,
        json={"message": "成员第 4 次"},
    )
    assert blocked_member.status_code == 429


@pytest.mark.asyncio
async def test_ip_bucket_blocks_second_user_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 IP 打满 IP 桶后，另一 user_id 直接 429（不依赖 HTTP）。"""
    monkeypatch.setattr(rl, "CHAT_MAX_REQUESTS", 100)
    monkeypatch.setattr(rl, "IP_CHAT_MAX_REQUESTS", 2)
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()
    shared_ip = "203.0.113.10"

    await rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid_a, ip=shared_ip)
    await rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid_a, ip=shared_ip)

    with pytest.raises(RateLimitError) as exc:
        await rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid_b, ip=shared_ip)
    assert "对话" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_ip_chat_limit_across_users(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同客户端 IP：用户 A 打满 IP 窗后，用户 B chat → 429。"""
    monkeypatch.setattr(rl, "CHAT_MAX_REQUESTS", 100)
    monkeypatch.setattr(rl, "IP_CHAT_MAX_REQUESTS", 2)

    headers_a, user_a = await register_and_login(prefix="api-rl-ip-a")
    kb_a = await _create_kb(client, headers_a, user_a, name="IP限流库A")
    kb_a_id = kb_a["id"]

    for i in range(2):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_a_id}/chat",
            headers=headers_a,
            json={"message": f"A问 {i}"},
        )
        assert resp.status_code == 200, resp.text

    headers_b, user_b = await register_and_login(prefix="api-rl-ip-b")
    kb_b = await _create_kb(client, headers_b, user_b, name="IP限流库B")
    kb_b_id = kb_b["id"]

    blocked = await client.post(
        f"/api/v1/knowledge-bases/{kb_b_id}/chat",
        headers=headers_b,
        json={"message": "B应被IP限流"},
    )
    assert blocked.status_code == 429
    assert "对话" in blocked.json()["detail"]

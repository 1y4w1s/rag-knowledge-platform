"""Wave 2.5 Dashboard 统计 API 测试。"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username, workspace_query


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    email = unique_email("dash-member")
    username = unique_username("dashmember")
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
    name: str = "Dashboard 测试库",
) -> dict:
    params = workspace_query(user)
    payload: dict = {"name": name}
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


async def _upload_txt(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    filename: str = "notes.txt",
    content: bytes = b"hello dashboard stats",
) -> dict:
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", (filename, content, "text/plain"))],
    )
    assert resp.status_code == 201
    return resp.json()["documents"][0]


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_dashboard_stats_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_personal_user_dashboard_stats_after_upload(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="dash-personal")
    kb = await _create_kb(client, headers, user)
    await _upload_txt(client, headers, kb["id"])

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == "personal"
    assert body["knowledge_base_count"] == 1
    assert body["document_count"] == 1
    assert body["documents_by_status"]["completed"] == 1
    assert body["total_chunk_count"] > 0
    assert body["avg_processing_duration_seconds"] is not None
    assert body["avg_processing_duration_seconds"] >= 0
    assert body["ingestion_success_rate"] == 100.0
    assert body["chat_message_count"] == 0
    assert body["member_count"] is None
    assert body["recent_kb_id"] == kb["id"]
    assert body["recent_activities"] == []
    assert body["golden_hit_rate_percent"] == 100.0
    assert body["golden_baseline_evaluated_at"] is not None
    assert body["avg_retrieval_latency_ms"] is None
    assert body["retrieval_latency_sample_count"] == 0
    assert body["document_retry_count_7d"] == 0
    assert body["storage_cleanup_failure_count"] == 0


@pytest.mark.asyncio
async def test_personal_user_does_not_see_other_users_stats(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, user_a = await register_and_login(prefix="dash-user-a")
    kb = await _create_kb(client, headers_a, user_a)
    await _upload_txt(client, headers_a, kb["id"])

    headers_b, user_b = await register_and_login(prefix="dash-user-b")
    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers_b,
        params=workspace_query(user_b),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == "personal"
    assert body["knowledge_base_count"] == 0
    assert body["document_count"] == 0
    assert body["total_chunk_count"] == 0
    assert body["ingestion_success_rate"] is None
    assert body["recent_kb_id"] is None
    assert body["recent_activities"] == []


@pytest.mark.asyncio
async def test_enterprise_admin_sees_org_dashboard_stats(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, admin = await register_and_login(
        prefix="dash-org-admin",
        account_type="enterprise",
        org_name="Dashboard 统计公司",
    )
    kb = await _create_kb(client, headers, admin)
    await _upload_txt(client, headers, kb["id"])

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(admin),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == "organization"
    assert body["knowledge_base_count"] == 1
    assert body["document_count"] == 1
    assert body["documents_by_status"]["completed"] == 1
    assert body["total_chunk_count"] > 0
    assert body["member_count"] == 1


@pytest.mark.asyncio
async def test_enterprise_member_sees_same_org_stats(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="dash-org-admin-for-member",
        account_type="enterprise",
        org_name="成员可读统计公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)
    await _upload_txt(client, admin_headers, kb["id"])

    member_headers, member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    ws = workspace_query(admin_user)
    admin_resp = await client.get(
        "/api/v1/dashboard/stats", headers=admin_headers, params=ws
    )
    member_resp = await client.get(
        "/api/v1/dashboard/stats", headers=member_headers, params=ws
    )
    assert admin_resp.status_code == 200
    assert member_resp.status_code == 200

    admin_body = admin_resp.json()
    member_body = member_resp.json()

    assert member_body["scope"] == "organization"
    assert member_body["knowledge_base_count"] == admin_body["knowledge_base_count"]
    assert member_body["document_count"] == admin_body["document_count"]
    assert member_body["total_chunk_count"] == admin_body["total_chunk_count"]
    assert member_body["member_count"] == 2


@pytest.mark.asyncio
async def test_enterprise_user_does_not_see_other_org_stats(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers_a, admin_a = await register_and_login(
        prefix="dash-org-a",
        account_type="enterprise",
        org_name="组织 A",
    )
    kb = await _create_kb(client, headers_a, admin_a)
    await _upload_txt(client, headers_a, kb["id"])

    headers_b, admin_b = await register_and_login(
        prefix="dash-org-b",
        account_type="enterprise",
        org_name="组织 B",
    )

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers_b,
        params=workspace_query(admin_b),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == "organization"
    assert body["knowledge_base_count"] == 0
    assert body["document_count"] == 0
    assert body["total_chunk_count"] == 0
    assert body["recent_kb_id"] is None
    assert body["recent_activities"] == []


@pytest.mark.asyncio
async def test_dashboard_recent_kb_id_null_when_no_knowledge_bases(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="dash-zero-kb")
    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["knowledge_base_count"] == 0
    assert body["recent_kb_id"] is None
    assert body["recent_activities"] == []


@pytest.mark.asyncio
async def test_dashboard_recent_kb_id_points_to_most_recently_active_kb(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="dash-recent-kb")
    kb_a = await _create_kb(client, headers, user, name="库 A")
    kb_b = await _create_kb(client, headers, user, name="库 B")
    await _upload_txt(client, headers, kb_b["id"], filename="b-notes.txt")

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["knowledge_base_count"] == 2
    assert body["recent_kb_id"] == kb_b["id"]
    assert body["recent_kb_id"] != kb_a["id"]
    assert body["recent_activities"] == []


@pytest.mark.asyncio
async def test_dashboard_rag_metrics_from_api_after_chat(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """EW-C3：golden 基线来自 API；检索延迟来自近 7 日 assistant 消息。"""
    from app.models.document import Document
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion

    golden_md = Path(__file__).parent / "fixtures" / "golden_handbook.md"
    headers, user = await register_and_login(prefix="dash-rag-metrics")
    kb = await _create_kb(client, headers, user, name="RAG 指标库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.md"
    storage_path.write_bytes(golden_md.read_bytes())
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=golden_md.name,
            file_type="md",
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()
    await process_document_ingestion(doc_id)

    chat_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": "年假有多少天？"},
    )
    assert chat_resp.status_code == 200

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["golden_hit_rate_percent"] == 100.0
    assert body["golden_baseline_evaluated_at"] is not None
    assert body["avg_retrieval_latency_ms"] is not None
    assert body["avg_retrieval_latency_ms"] >= 0
    assert body["retrieval_latency_sample_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_ops_metrics_from_audit_logs(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """Plan-3E-6b：运营指标从 audit_logs 聚合，且受 workspace scope 约束。"""
    from app.services.audit.log import write_audit_log

    headers_a, user_a = await register_and_login(prefix="dash-ops-a")
    kb_a = await _create_kb(client, headers_a, user_a, name="运营 A 库")
    await _upload_txt(client, headers_a, kb_a["id"])

    headers_b, user_b = await register_and_login(prefix="dash-ops-b")
    kb_b = await _create_kb(client, headers_b, user_b, name="运营 B 库")

    async with SessionLocal() as db:
        await write_audit_log(
            db,
            action="document.retry",
            actor_user_id=uuid.UUID(user_a["id"]),
            resource_type="document",
            kb_id=uuid.UUID(kb_a["id"]),
        )
        await write_audit_log(
            db,
            action="document.retry",
            actor_user_id=uuid.UUID(user_b["id"]),
            resource_type="document",
            kb_id=uuid.UUID(kb_b["id"]),
        )
        await write_audit_log(
            db,
            action="storage.cleanup_failed",
            actor_user_id=uuid.UUID(user_a["id"]),
            resource_type="document",
            kb_id=uuid.UUID(kb_a["id"]),
        )
        await db.commit()

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers_a,
        params=workspace_query(user_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_retry_count_7d"] == 1
    assert body["storage_cleanup_failure_count"] == 1
    assert body["ingestion_success_rate"] == 100.0

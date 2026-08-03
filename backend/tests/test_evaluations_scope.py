"""P1-18 选 B 落地：评测 = 平台级运营数据 + POST /runs 控写入。

钉死控制面（拍板文档 §6/§8）：
- member / personal 创建评测运行 → 403；
- enterprise owner / admin 创建 → 201 + ``evaluation_run.create`` 审计；
- 任意登录用户（含 personal）GET 评测端点全局可读（平台基线语义）；
- 评测端点非公开路径：未认证 → 401。
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log
from tests.fixtures.org_members import (
    _create_org_member_and_login,
    _promote_member_to_admin_in_db,
)

pytestmark = pytest.mark.asyncio


def _run_payload(run_id: str, dataset: str = "golden_qa") -> dict:
    return {
        "run_id": run_id,
        "dataset_name": dataset,
        "mode": "retrieval",
        "total_queries": 10,
        "hit_at_3": 0.85,
        "triggered_by": "manual",
    }


async def test_evaluations_endpoints_require_login(client: AsyncClient) -> None:
    """F1 收口后评测端点非公开路径：未认证一律 401。"""
    resp = await client.get("/api/v1/evaluations/runs")
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/evaluations/runs",
        json=_run_payload(f"anon-{uuid.uuid4().hex[:8]}"),
    )
    assert resp.status_code == 401


async def test_personal_user_cannot_create_run(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="eval-personal")
    resp = await client.post(
        "/api/v1/evaluations/runs",
        headers=headers,
        json=_run_payload(f"p-{uuid.uuid4().hex[:8]}"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "需要团队账号"


async def test_org_member_cannot_create_run(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="eval-owner",
        account_type="enterprise",
        org_name="评测平台公司",
    )
    assert owner_headers
    member_headers, _member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    resp = await client.post(
        "/api/v1/evaluations/runs",
        headers=member_headers,
        json=_run_payload(f"m-{uuid.uuid4().hex[:8]}"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "权限不足"


async def test_owner_can_create_run_with_audit(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="eval-owner-create",
        account_type="enterprise",
        org_name="评测平台公司",
    )
    before = await _count_audit_logs(action="evaluation_run.create")

    run_id = f"owner-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/evaluations/runs",
        headers=headers,
        json=_run_payload(run_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["dataset_name"] == "golden_qa"

    after = await _count_audit_logs(action="evaluation_run.create")
    assert after - before == 1
    latest = await _latest_audit_log(action="evaluation_run.create")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert latest.resource_type == "evaluation_run"
    assert latest.details == {
        "dataset": "golden_qa",
        "mode": "retrieval",
        "run_id": run_id,
    }


async def test_org_admin_can_create_run(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="eval-admin-create",
        account_type="enterprise",
        org_name="评测平台公司",
    )
    admin_headers, admin_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=admin_user["id"],
    )

    resp = await client.post(
        "/api/v1/evaluations/runs",
        headers=admin_headers,
        json=_run_payload(f"admin-{uuid.uuid4().hex[:8]}"),
    )
    assert resp.status_code == 201


async def test_any_logged_in_user_can_read_global_runs(
    client: AsyncClient,
    register_and_login,
) -> None:
    """全局运营数据语义：个人用户也能读平台基线（读侧不收口）。"""
    owner_headers, _owner_user = await register_and_login(
        prefix="eval-read-owner",
        account_type="enterprise",
        org_name="评测平台公司",
    )
    created = await client.post(
        "/api/v1/evaluations/runs",
        headers=owner_headers,
        json=_run_payload(f"read-{uuid.uuid4().hex[:8]}"),
    )
    assert created.status_code == 201
    created_run = created.json()

    personal_headers, _personal_user = await register_and_login(prefix="eval-reader")
    runs_resp = await client.get(
        "/api/v1/evaluations/runs?limit=20",
        headers=personal_headers,
    )
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert any(r["run_id"] == created_run["run_id"] for r in runs)

    latest_resp = await client.get(
        "/api/v1/evaluations/latest?dataset=golden_qa&mode=retrieval",
        headers=personal_headers,
    )
    assert latest_resp.status_code == 200
    assert latest_resp.json()["dataset_name"] == "golden_qa"

"""G4-3.1 · approval resolve adopt 路径（403/409/归属校验 + happy path）。

本文件只覆盖 plan §9 **G4-3.1** 的 adopt 分支（cancel 留 G4-3.3）：

- happy path：Admin/Owner + 行 ``pending`` + kb write 权限 → 调 ``adopt_draft_to_kb``
  → 200 + ``{document_id, kb_id, filename, status:"processing"}``，落
  ``agent_approvals.status=adopted`` + ``document_id`` + ``resolved_at``。
- G4-E1：Member 硬闯 adopt → 403。
- G4-E3：重复采纳同 approval_id → 409。
- G4-E15：非 pending（已 adopted/cancelled）→ 409。
- 归属校验失败（跨组织库 / 不可见 / 他人个人库）→ 403；approval 不存在 → 404。
- 本窗仅支持 action=adopt，cancel → 422（G4-3.3 实现）。

``adopt_draft_to_kb`` 用 ``monkeypatch`` 替换以隔离本窗范围（G4-3.2 实现替换后
本窗测试不受影响）。

复用车规级隔离 fixture ``org_iso``（``tests/fixtures/org_isolation.py``）：
- ``org_iso.owner``     : 公司 Admin + Owner，可写任意 org kb
- ``org_iso.rd_member`` : 研发部 Member，仅可读，写动作 → 403（G4-E1）
- ``org_iso.public_kb_id`` : 公司公共库（org_unit_id=None），admin 可写
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    DocumentStatus,
    ThreadKind,
    ThreadStatus,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization
from tests.conftest import create_test_kb

APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"


async def _fake_adopt_draft_to_kb(db: AsyncSession, approval, kb) -> UUID:
    """隔离 stub：插入真实 documents(queued) 行并返回其 id（满足 document_id FK）。

    不实现 _v2 冲突策略 / ingestion / 真实 md 文件写库（G4-3.2 替换）。
    """
    doc = Document(
        id=uuid.uuid4(),
        kb_id=kb.id,
        filename=approval.filename,
        file_type="md",
        file_size=10,
        storage_path=f"/tmp/fake/{approval.id}.md",
        status=DocumentStatus.queued,
        uploaded_by=approval.user_id,
    )
    db.add(doc)
    await db.flush()
    return doc.id


async def _login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "Test123!@"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_approval(
    *,
    kb_id: UUID,
    user_id: UUID,
    status: ApprovalStatus = ApprovalStatus.pending,
    filename: str = "faq-draft.md",
) -> UUID:
    """直插 agent_approvals 行（commit 使路由所在会话可见 · READ COMMITTED）。

    同时插入父表 chat_threads / agent_runs（FK 约束）。
    """
    approval_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
        # 逐行 flush：同会话内 SQLAlchemy 未自动排定 chat_threads→agent_runs 的
        # FK 依赖顺序，需显式先落父表（与 debug 验证一致）。
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
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
                user_id=user_id,
                kind=ApprovalKind.adopt_faq,
                status=status,
                kb_id=kb_id,
                filename=filename,
                payload_json={
                    "title": "年假制度 FAQ",
                    "filename": filename,
                    "markdown": "# FAQ\n\n内容",
                    "source_chunk_ids": [],
                },
            )
        )
        await db.commit()
    return approval_id


async def _insert_foreign_kb() -> UUID:
    """插入一个属于「其他组织」的 kb（当前用户不可见/不可写 → 403）。"""
    kb_id = uuid.uuid4()
    org_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(Organization(id=org_id, name="外部组织"))
        await db.flush()
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="外部组织库",
                owner_org_id=org_id,  # 真实但不同于当前用户 org
                owner_user_id=None,
                org_unit_id=None,
            )
        )
        await db.commit()
    return kb_id


async def _get_approval_status(approval_id: UUID) -> ApprovalStatus | None:
    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        return approval.status if approval is not None else None


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #


async def test_g4_resolve_adopt_happy_path_owner(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin/Owner + pending + kb write → 200 + document_id，落终态 adopted。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kb_id"] == str(org_iso.public_kb_id)
    assert body["filename"] == "faq-draft.md"
    assert body["status"] == "processing"
    assert body["document_id"]

    # 落库终态（status + document_id + resolved_at）
    async with SessionLocal() as db:
        adopted = await db.get(AgentApproval, approval_id)
        assert adopted is not None
        assert adopted.status == ApprovalStatus.adopted
        assert adopted.document_id is not None
        assert adopted.resolved_at is not None


async def test_g4_resolve_adopt_personal_owner_happy_path(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """个人库 owner（personal）采纳自己的 pending 审批 → 200（_assert_kb_ownership 早返）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    headers, user = await register_and_login(prefix="g4-personal", account_type="personal")
    kb = await create_test_kb(client, headers, user, name="个人库-g4")
    kb_id = uuid.UUID(kb["id"])
    approval_id = await _insert_approval(kb_id=kb_id, user_id=uuid.UUID(user["id"]))

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kb_id"] == kb["id"]
    assert await _get_approval_status(approval_id) == ApprovalStatus.adopted


# --------------------------------------------------------------------------- #
# G4-E1 · Member 硬闯 → 403
# --------------------------------------------------------------------------- #


async def test_g4_e1_member_forbidden(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Member 无采纳权限 → 403（HA-2-A · H4-1-B）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 403, resp.text
    # 未落库（仍 pending）
    assert await _get_approval_status(approval_id) == ApprovalStatus.pending


# --------------------------------------------------------------------------- #
# G4-E3 · 重复采纳同 approval_id → 409
# --------------------------------------------------------------------------- #


async def test_g4_e3_duplicate_adopt_409(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一 approval 重复采纳 → 第二次 409（幂等锚点）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    r1 = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert r1.status_code == 200, r1.text

    r2 = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert r2.status_code == 409, r2.text


# --------------------------------------------------------------------------- #
# G4-E15 · 非 pending → 409
# --------------------------------------------------------------------------- #


async def test_g4_e15_non_pending_409(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已 adopted 的审批再采纳 → 409（同理覆盖 cancelled）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        status=ApprovalStatus.adopted,
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------------------- #
# 归属校验失败 → 403 / 404
# --------------------------------------------------------------------------- #


async def test_g4_ownership_cross_org_403(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """approval 指向其他组织的 kb → 当前用户不可见/不可写 → 403（归属校验）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    foreign_kb_id = await _insert_foreign_kb()
    approval_id = await _insert_approval(
        kb_id=foreign_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 403, resp.text
    assert await _get_approval_status(approval_id) == ApprovalStatus.pending


async def test_g4_ownership_personal_other_user_403(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """个人库 A 的 pending 审批，被个人用户 B 硬闯 → 403（归属校验）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    headers_a, user_a = await register_and_login(
        prefix="g4-pa", account_type="personal"
    )
    kb = await create_test_kb(client, headers_a, user_a, name="个人库A-g4")
    kb_id = uuid.UUID(kb["id"])
    approval_id = await _insert_approval(kb_id=kb_id, user_id=uuid.UUID(user_a["id"]))

    headers_b, _user_b = await register_and_login(
        prefix="g4-pb", account_type="personal"
    )
    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers_b,
        json={"action": "adopt"},
    )
    assert resp.status_code == 403, resp.text
    assert await _get_approval_status(approval_id) == ApprovalStatus.pending


async def test_g4_e8_approval_not_found_404(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """approval 不存在 → 404（归属校验失败兜底）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=uuid.uuid4()),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# 本窗仅支持 adopt
# --------------------------------------------------------------------------- #


async def test_g4_unknown_action_still_422(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G4-3.3：未知 action（既非 adopt 也非 cancel）→ 422 守卫。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "frobnicate"},
    )
    assert resp.status_code == 422, resp.text
    # 未知动作不得改变状态。
    assert await _get_approval_status(approval_id) == ApprovalStatus.pending

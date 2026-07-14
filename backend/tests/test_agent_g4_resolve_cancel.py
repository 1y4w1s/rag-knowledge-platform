"""G4-3.3 · approval resolve cancel 路径（H4-5-B / G4-E5 / G4-E6 / G4-E8 / G4-E9）。

本文件只覆盖 plan §9 **G4-3.3** 的 cancel 分支（adopt 分支已由
``test_agent_g4_resolve_adopt.py`` 覆盖，本文件末尾附一条 adopt 零回退回归）：

- happy path：创建者本人 **或** kb Admin/Owner → POST resolve ``{action:"cancel"}``
  → 200 + ``{ok:true}``，落 ``agent_approvals.status=cancelled`` + ``resolved_at``。
- H4-5-B：Member 取消**自己**创建的卡 → 200（创建者本人放行）。
- G4-E9：Member 硬闯撤**他人** pending → 403（非创建者非 Admin 不可撤他人）。
- G4-E5：cancel 已 adopted 的 approval → 409；重复 cancel 已 cancelled → 409。
- G4-E8：approval 不存在 → 404。
- 未知 action（既非 adopt 也非 cancel）→ 422（G4-3.3 守卫降级）。
- 零回退：adopt 分支 happy path 仍 200 + ``processing``（行为不回退）。

cancel **绝不**写库 / 落 md / ``_v2`` / ingestion（G4-3.3 红线）；``adopt_draft_to_kb``
用 ``monkeypatch`` 隔离（cancel 不调它，仅为路由 import 防御）。

复用车规级隔离 fixture ``org_iso``（``tests/test_org_isolation.py`` · pytest 插件）：
- ``org_iso.owner``     : 公司 Admin + Owner，可写任意 org kb（含 public_kb）
- ``org_iso.rd_member`` : 研发部 Member，仅可读，写动作 → 403（G4-E9）
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
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    ThreadKind,
    ThreadStatus,
)


APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"


async def _fake_adopt_draft_to_kb(db: AsyncSession, approval, kb) -> UUID:
    """防御性 stub：cancel 不调用，仅隔离路由 import 期误触发。

    返回真实 documents(queued) 行 id（满足 document_id FK）。
    """
    from app.models.document import Document
    from app.models.enums import DocumentStatus

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
        json={"identifier": user.email, "password": "password123"},
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
        # FK 依赖顺序，需显式先落父表。
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


async def _get_approval(approval_id: UUID):
    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        if approval is None:
            return None
        return (approval.status, approval.resolved_at)


# --------------------------------------------------------------------------- #
# happy path · 创建者本人 / Admin-Owner 取消
# --------------------------------------------------------------------------- #


async def test_g4_e6_owner_cancel_own_200(
    client: AsyncClient,
    org_iso,
) -> None:
    """创建者本人（owner）取消自己的 pending → 200 + cancelled + resolved_at 已填。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    status_, resolved_at = await _get_approval(approval_id)
    assert status_ == ApprovalStatus.cancelled
    assert resolved_at is not None


async def test_g4_resolve_cancel_admin_cancels_others_200(
    client: AsyncClient,
    org_iso,
) -> None:
    """kb Admin/Owner（owner）可撤**他人**（rd_member）创建的 pending → 200（H4-5-B 放行 Admin）。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.rd_member.id
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.cancelled


# --------------------------------------------------------------------------- #
# H4-5-B · Member 取消自己创建的卡 → 200（创建者本人放行）
# --------------------------------------------------------------------------- #


async def test_g4_e6_member_cancel_own_200(
    client: AsyncClient,
    org_iso,
) -> None:
    """Member 取消**自己**创建的 pending → 200（H4-5-B · 创建者本人放行，无需 kb 写权限）。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.rd_member.id
    )
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.cancelled


# --------------------------------------------------------------------------- #
# G4-E9 · Member 硬闯撤他人 pending → 403
# --------------------------------------------------------------------------- #


async def test_g4_e9_member_cancel_others_403(
    client: AsyncClient,
    org_iso,
) -> None:
    """Member 撤**他人**（owner）创建的 pending → 403（HA-2-A 衍生 · H4-5-B）。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id, user_id=org_iso.owner.id
    )
    headers = await _login(client, org_iso.rd_member)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 403, resp.text
    # 未改变状态（仍 pending）。
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.pending


# --------------------------------------------------------------------------- #
# G4-E5 · 非 pending → 409
# --------------------------------------------------------------------------- #


async def test_g4_e5_cancel_already_adopted_409(
    client: AsyncClient,
    org_iso,
) -> None:
    """cancel 已 adopted 的 approval → 409（G4-E5）。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        status=ApprovalStatus.adopted,
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 409, resp.text
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.adopted


async def test_g4_e5_repeat_cancel_already_cancelled_409(
    client: AsyncClient,
    org_iso,
) -> None:
    """重复 cancel（已 cancelled 的 approval）→ 409（G4-E5）。"""
    approval_id = await _insert_approval(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        status=ApprovalStatus.cancelled,
    )
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 409, resp.text
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.cancelled


# --------------------------------------------------------------------------- #
# G4-E8 · approval 不存在 → 404
# --------------------------------------------------------------------------- #


async def test_g4_e8_cancel_approval_not_found_404(
    client: AsyncClient,
    org_iso,
) -> None:
    """cancel 指向不存在的 approval → 404（G4-E8）。"""
    headers = await _login(client, org_iso.owner)

    resp = await client.post(
        APPROVE_URL.format(approval_id=uuid.uuid4()),
        headers=headers,
        json={"action": "cancel"},
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------------- #
# 未知 action → 422（G4-3.3 守卫降级）
# --------------------------------------------------------------------------- #


async def test_g4_unknown_action_still_422(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未知 action（既非 adopt 也非 cancel）→ 422 守卫。"""
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
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.pending


# --------------------------------------------------------------------------- #
# 零回退 · adopt 分支 happy path 仍 200 + processing
# --------------------------------------------------------------------------- #


async def test_g4_adopt_branch_still_200_processing(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G4-3.1/3.2 行为不回退：adopt happy path 仍 200 + processing（cancel 改动零回退）。"""
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
    assert body["status"] == "processing"
    assert body["document_id"]
    assert (await _get_approval(approval_id))[0] == ApprovalStatus.adopted

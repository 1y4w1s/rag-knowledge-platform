"""G4-3.5 · approval 审计钩子（created / adopted / cancelled / denied）。

只覆盖 plan §9 **G4-3.5** 的审计事件；adopt / cancel 既有行为由
``test_agent_g4_resolve_adopt.py`` / ``test_agent_g4_resolve_cancel.py`` 守住（零回退）。

4 类 G4 事件断言（直查 ``audit_logs`` 表 action + metadata）：
- created  ：``generate_faq_draft`` 成功后有 ``agent.approval_created``（含 draft_chars，无全文）
- adopted  ：owner/admin 采纳后有 ``agent.approval_adopted``（含 document_id / resolver_user_id）
- cancelled：member 取消自己后有 ``agent.approval_cancelled``（含 resolver_user_id）
- denied   ：member 撤他人 → 403 后有 ``agent.approval_denied``(reason=member_forbidden)
           重复采纳   → 409 后有 ``agent.approval_denied``(reason=not_pending)

红线校验：任意 approval 事件的 ``details`` 中**绝不**含草稿全文
（payload_json.markdown / DRAFT_MARKER）。

复用车规级隔离 fixture ``org_iso``（``tests/test_org_isolation.py`` · pytest 插件）；
``register_and_login`` 来自 ``tests/conftest.py``。
"""

from __future__ import annotations

import json
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.audit_log import AuditLog
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    DocumentStatus,
    ThreadKind,
    ThreadStatus,
)
from app.services.agent.tools.generate_faq_draft import run_generate_faq_draft
from app.services.agent.tools.scope import AgentToolScope

APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"

# 仅用于「审计 metadata 不得含草稿全文」的反向断言：草稿正文里一定出现此片段。
DRAFT_MARKER = "员工年假规定为 10 天"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _make_scope(visible: set[UUID]) -> AgentToolScope:
    return AgentToolScope(visible_kb_ids=frozenset(visible))


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
                    "markdown": f"# FAQ\n\n{DRAFT_MARKER}，需提前申请。",
                    "source_chunk_ids": [],
                },
            )
        )
        await db.commit()
    return approval_id


async def _fake_adopt_draft_to_kb(db: AsyncSession, approval, kb) -> UUID:
    """隔离 stub：插入真实 documents(queued) 行并返回其 id（满足 document_id FK）。"""
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


async def _get_audit_rows(action: str, approval_id: UUID | None = None) -> list[AuditLog]:
    async with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.action == action)
        if approval_id is not None:
            stmt = stmt.where(AuditLog.resource_id == approval_id)
        stmt = stmt.order_by(AuditLog.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())


async def _get_audit_rows_by_resource(approval_id: UUID) -> list[AuditLog]:
    async with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.resource_id == approval_id)
        return list((await db.execute(stmt)).scalars().all())


def _assert_no_full_text(details) -> None:
    """审计 metadata 不得含草稿全文（payload_json.markdown / DRAFT_MARKER）。"""
    assert details is not None
    assert "markdown" not in details
    assert "payload_json" not in details
    blob = json.dumps(details, ensure_ascii=False)
    assert DRAFT_MARKER not in blob


# --------------------------------------------------------------------------- #
# created · generate_faq_draft 成功后写 agent.approval_created（无全文）
# --------------------------------------------------------------------------- #


async def test_g4_audit_approval_created_no_full_text(org_iso) -> None:
    """草稿生成 → agent.approval_created（含 draft_chars，无草稿全文）。"""
    kb_id = org_iso.public_kb_id
    user_id = org_iso.owner.id
    scope = _make_scope({kb_id})

    async with SessionLocal() as db:
        thread_id = uuid.uuid4()
        run_id = uuid.uuid4()
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
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
        # DocumentChunk.document_id 为硬 FK，须先落 documents 行。
        doc = Document(
            id=uuid.uuid4(),
            kb_id=kb_id,
            filename="src.md",
            file_type="md",
            file_size=10,
            storage_path=f"/tmp/audit/{uuid.uuid4()}.md",
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.flush()
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            kb_id=kb_id,
            chunk_index=0,
            section_title="1.1 年假",
            content=f"{DRAFT_MARKER}，需提前申请。",
        )
        db.add(chunk)
        await db.flush()

        result = await run_generate_faq_draft(
            db,
            scope,
            kb_id=kb_id,
            filename="faq-draft.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            source_chunk_ids=[chunk.id],
            title="年假FAQ",
        )
        await db.commit()

    assert result.ok is True
    approval_id = result.data.approval_id

    rows = await _get_audit_rows("agent.approval_created", approval_id)
    assert rows, "应写入 agent.approval_created"
    details = rows[0].details
    assert details["approval_id"] == str(approval_id)
    assert details["kb_id"] == str(kb_id)
    assert details["filename"] == "faq-draft.md"
    assert details["draft_chars"] == result.data.draft_chars
    assert details["draft_chars"] > 0
    _assert_no_full_text(details)


# --------------------------------------------------------------------------- #
# adopted · owner 采纳后写 agent.approval_adopted
# --------------------------------------------------------------------------- #


async def test_g4_audit_approval_adopted_owner(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """owner（Admin/Owner）采纳 → agent.approval_adopted（含 document_id/resolver_user_id）。"""
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
    document_id = resp.json()["document_id"]

    rows = await _get_audit_rows("agent.approval_adopted", approval_id)
    assert rows, "应写入 agent.approval_adopted"
    details = rows[0].details
    assert details["approval_id"] == str(approval_id)
    assert details["document_id"] == document_id
    assert details["kb_id"] == str(org_iso.public_kb_id)
    assert details["filename"] == "faq-draft.md"
    assert details["resolver_user_id"] == str(org_iso.owner.id)
    _assert_no_full_text(details)


# --------------------------------------------------------------------------- #
# cancelled · member 取消自己后写 agent.approval_cancelled
# --------------------------------------------------------------------------- #


async def test_g4_audit_approval_cancelled_member_own(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Member 取消自己创建的卡 → agent.approval_cancelled（含 resolver_user_id）。"""
    monkeypatch.setattr(
        "app.services.agent.approvals.adopt_draft_to_kb", _fake_adopt_draft_to_kb
    )
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

    rows = await _get_audit_rows("agent.approval_cancelled", approval_id)
    assert rows, "应写入 agent.approval_cancelled"
    details = rows[0].details
    assert details["approval_id"] == str(approval_id)
    assert details["resolver_user_id"] == str(org_iso.rd_member.id)
    _assert_no_full_text(details)


# --------------------------------------------------------------------------- #
# denied · member 撤他人 → 403 → agent.approval_denied(reason=member_forbidden)
# --------------------------------------------------------------------------- #


async def test_g4_audit_approval_denied_member_cancel_others_403(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Member 撤他人 pending → 403 → agent.approval_denied(reason=member_forbidden)。"""
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
        json={"action": "cancel"},
    )
    assert resp.status_code == 403, resp.text
    # 主流程零回退：状态仍 pending。
    async with SessionLocal() as db:
        ap = await db.get(AgentApproval, approval_id)
        assert ap.status == ApprovalStatus.pending

    rows = await _get_audit_rows("agent.approval_denied", approval_id)
    assert rows, "应写入 agent.approval_denied"
    details = rows[0].details
    assert details["approval_id"] == str(approval_id)
    assert details["reason"] == "member_forbidden"
    _assert_no_full_text(details)


# --------------------------------------------------------------------------- #
# denied · 重复采纳 → 409 → agent.approval_denied(reason=not_pending)
# --------------------------------------------------------------------------- #


async def test_g4_audit_approval_denied_duplicate_adopt_409(
    client: AsyncClient,
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重复采纳同 approval_id → 第二次 409 → agent.approval_denied(reason=not_pending)。"""
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

    rows = await _get_audit_rows("agent.approval_denied", approval_id)
    assert rows, "重复采纳应写入 agent.approval_denied"
    details = rows[0].details
    assert details["approval_id"] == str(approval_id)
    assert details["reason"] == "not_pending"
    _assert_no_full_text(details)


# --------------------------------------------------------------------------- #
# 红线 · 任意 approval 事件的 details 均不含草稿全文
# --------------------------------------------------------------------------- #


async def test_g4_audit_metadata_never_contains_full_draft(org_iso) -> None:
    """generate_faq_draft 产生的 approval_created 审计，details 不含草稿全文。"""
    kb_id = org_iso.public_kb_id
    user_id = org_iso.owner.id
    scope = _make_scope({kb_id})

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
        doc = Document(
            id=uuid.uuid4(),
            kb_id=kb_id,
            filename="src.md",
            file_type="md",
            file_size=10,
            storage_path=f"/tmp/audit/{uuid.uuid4()}.md",
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.flush()
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            kb_id=kb_id,
            chunk_index=0,
            section_title="1.1 年假",
            content=f"{DRAFT_MARKER}，需提前申请。",
        )
        db.add(chunk)
        await db.flush()

        result = await run_generate_faq_draft(
            db,
            scope,
            kb_id=kb_id,
            filename="faq-draft.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            source_chunk_ids=[chunk.id],
            title="年假FAQ",
        )
        await db.commit()

    assert result.ok is True

    # 直查该 approval 关联的所有审计行（created 仅 1 条），断言全文不出现。
    rows = await _get_audit_rows_by_resource(result.data.approval_id)
    assert rows, "应至少有一条 approval_created 审计"
    for row in rows:
        _assert_no_full_text(row.details)

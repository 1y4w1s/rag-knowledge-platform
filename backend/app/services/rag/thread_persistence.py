"""chat_threads 落库与按 scope 解析活跃 thread（G2-0.3 · G2-1.1 CRUD）�?""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_thread import ChatThread
from app.models.enums import ThreadKind, ThreadStatus
from app.services.audit.chat import audit_thread_archived, audit_thread_created
from app.services.workspace.scope import WorkspaceKind

DEFAULT_THREAD_TITLE = "历史对话"
NEW_THREAD_TITLE = ""
FIRST_QUESTION_TITLE_MAX_LEN = 40


def derive_title_from_first_question(
    content: str,
    *,
    max_len: int = FIRST_QUESTION_TITLE_MAX_LEN,
) -> str:
    """首问截断�?thread 标题（空�?换行折叠为单空格）�?""
    collapsed = " ".join(content.strip().split())
    if not collapsed:
        return ""
    return collapsed[:max_len]


async def maybe_autotitle_thread_from_first_message(
    db: AsyncSession,
    thread: ChatThread,
    user_content: str,
) -> None:
    """title 为空时，用首问前几字自动设标题（G2 S3 · TECH §5.8.2）�?""
    if (thread.title or "").strip():
        return
    title = derive_title_from_first_question(user_content)
    if not title:
        return
    thread.title = title
    db.add(thread)


def normalize_workspace_department_key(department_id: str | None) -> str | None:
    """API department_id �?落库 workspace_department_key（空/缺省=主部门）�?""
    if department_id is None:
        return None
    value = department_id.strip()
    if value == "":
        return None
    if value.lower() == "all":
        return "all"
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_thread_by_id(
    db: AsyncSession,
    thread_id: UUID,
) -> ChatThread | None:
    return await db.get(ChatThread, thread_id)


async def touch_thread(
    db: AsyncSession,
    thread_id: UUID,
    *,
    at: datetime | None = None,
) -> None:
    """更新 thread �?last_message_at / updated_at（新消息写入后调用）�?""
    ts = at or _utcnow()
    await db.execute(
        update(ChatThread)
        .where(ChatThread.id == thread_id)
        .values(last_message_at=ts, updated_at=ts)
    )


# ── 合并 CRUD（code-refactor-B）：thread_kind 参数�?KB/Workspace ──


def _build_thread_create_kwargs(
    *,
    thread_kind: ThreadKind,
    user_id: UUID,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_key: str | None = None,
    title: str = DEFAULT_THREAD_TITLE,
) -> dict:
    """�?thread_kind 构建 ChatThread 构造参数�?""
    base: dict = {
        "id": uuid.uuid4(),
        "thread_kind": thread_kind,
        "user_id": user_id,
        "title": title,
        "status": ThreadStatus.active,
    }
    if thread_kind == ThreadKind.knowledge_base:
        base["kb_id"] = kb_id
    else:
        base["kb_id"] = None
        base["workspace_kind"] = workspace_kind.value if workspace_kind else None
        base["workspace_org_id"] = workspace_org_id
        base["workspace_department_key"] = department_key
    return base


async def get_or_create_active_thread(
    db: AsyncSession,
    *,
    thread_kind: ThreadKind,
    user_id: UUID,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_key: str | None = None,
) -> ChatThread:
    """返回 thread：优先最近活跃的 active thread，无则新建�?""
    stmt = (
        select(ChatThread)
        .where(ChatThread.thread_kind == thread_kind)
        .where(ChatThread.user_id == user_id)
        .where(ChatThread.status == ThreadStatus.active)
    )
    if thread_kind == ThreadKind.knowledge_base:
        stmt = stmt.where(ChatThread.kb_id == kb_id)
    else:
        stmt = stmt.where(ChatThread.workspace_kind == workspace_kind.value)
        if workspace_kind == WorkspaceKind.personal:
            stmt = stmt.where(ChatThread.workspace_org_id.is_(None))
        else:
            stmt = stmt.where(ChatThread.workspace_org_id == workspace_org_id)
        if department_key is None:
            stmt = stmt.where(ChatThread.workspace_department_key.is_(None))
        else:
            stmt = stmt.where(ChatThread.workspace_department_key == department_key)

    result = await db.execute(
        stmt.order_by(
            ChatThread.last_message_at.desc().nullslast(),
            ChatThread.created_at.desc(),
        ).limit(1)
    )
    thread = result.scalar_one_or_none()
    if thread is not None:
        return thread

    thread = ChatThread(**_build_thread_create_kwargs(
        thread_kind=thread_kind,
        user_id=user_id,
        kb_id=kb_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_key=department_key,
    ))
    db.add(thread)
    await db.flush()
    return thread


async def list_threads(
    db: AsyncSession,
    *,
    thread_kind: ThreadKind,
    user_id: UUID,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_id: str | None = None,
    limit: int = 50,
    include_archived: bool = False,
) -> list[ChatThread]:
    """返回 thread 列表（默认仅 active，按 last_message_at 倒序）�?""
    capped = max(1, min(limit, 100))
    stmt = select(ChatThread).where(ChatThread.thread_kind == thread_kind).where(ChatThread.user_id == user_id)
    if thread_kind == ThreadKind.knowledge_base:
        stmt = stmt.where(ChatThread.kb_id == kb_id)
    else:
        department_key = normalize_workspace_department_key(department_id)
        stmt = stmt.where(ChatThread.workspace_kind == workspace_kind.value)
        if workspace_kind == WorkspaceKind.personal:
            stmt = stmt.where(ChatThread.workspace_org_id.is_(None))
        else:
            stmt = stmt.where(ChatThread.workspace_org_id == workspace_org_id)
        if department_key is None:
            stmt = stmt.where(ChatThread.workspace_department_key.is_(None))
        else:
            stmt = stmt.where(ChatThread.workspace_department_key == department_key)
    if not include_archived:
        stmt = stmt.where(ChatThread.status == ThreadStatus.active)
    result = await db.execute(
        stmt.order_by(
            ChatThread.last_message_at.desc().nullslast(),
            ChatThread.created_at.desc(),
        ).limit(capped)
    )
    return list(result.scalars().all())


async def create_thread(
    db: AsyncSession,
    *,
    thread_kind: ThreadKind,
    user_id: UUID,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_id: str | None = None,
    title: str = NEW_THREAD_TITLE,
) -> ChatThread:
    """新建�?thread（不合并已有 active thread）�?""
    department_key = normalize_workspace_department_key(department_id) if department_id is not None else None
    thread = ChatThread(**_build_thread_create_kwargs(
        thread_kind=thread_kind,
        user_id=user_id,
        kb_id=kb_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_key=department_key,
        title=title,
    ))
    db.add(thread)
    await audit_thread_created(db, thread=thread, actor_user_id=user_id)
    await db.commit()
    await db.refresh(thread)
    return thread


async def get_thread_for_user(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    thread_kind: ThreadKind,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_id: str | None = None,
) -> ChatThread | None:
    """�?id �?thread，校验归属与 scope�?""
    thread = await get_thread_by_id(db, thread_id)
    if thread is None or thread.user_id != user_id:
        return None
    if thread.thread_kind != thread_kind:
        return None
    if thread_kind == ThreadKind.knowledge_base:
        if thread.kb_id != kb_id:
            return None
    else:
        if thread.workspace_kind != (workspace_kind.value if workspace_kind else None):
            return None
        if workspace_kind == WorkspaceKind.personal:
            if thread.workspace_org_id is not None:
                return None
        elif thread.workspace_org_id != workspace_org_id:
            return None
        department_key = normalize_workspace_department_key(department_id)
        if department_key is None:
            if thread.workspace_department_key is not None:
                return None
        elif thread.workspace_department_key != department_key:
            return None
    return thread


async def update_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    thread_kind: ThreadKind,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_id: str | None = None,
    title: str | None = None,
    status: ThreadStatus | None = None,
) -> ChatThread | None:
    """PATCH title / status；thread 须属当前 user 且匹�?scope�?""
    thread = await get_thread_for_user(
        db,
        thread_id=thread_id,
        user_id=user_id,
        thread_kind=thread_kind,
        kb_id=kb_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
    )
    if thread is None:
        return None
    values: dict[str, object] = {"updated_at": _utcnow()}
    if title is not None:
        values["title"] = title
    if status is not None:
        values["status"] = status
    if len(values) == 1:
        return thread
    await db.execute(
        update(ChatThread).where(ChatThread.id == thread_id).values(**values)
    )
    if status == ThreadStatus.archived:
        await audit_thread_archived(db, thread=thread, actor_user_id=user_id)
    await db.commit()
    await db.refresh(thread)
    return thread


async def archive_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    thread_kind: ThreadKind,
    kb_id: UUID | None = None,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_id: str | None = None,
) -> ChatThread | None:
    """软删 thread（status=archived）�?""
    return await update_thread(
        db,
        thread_id=thread_id,
        user_id=user_id,
        thread_kind=thread_kind,
        kb_id=kb_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
        status=ThreadStatus.archived,
    )



async def resolve_thread_for_message(
    db: AsyncSession,
    *,
    thread_id: UUID | None,
    thread_kind: ThreadKind,
    kb_id: UUID | None,
    user_id: UUID,
    workspace_kind: WorkspaceKind | None = None,
    workspace_org_id: UUID | None = None,
    department_key: str | None = None,
) -> ChatThread:
    """显式 thread_id 优先；否则按 scope 解析活跃 thread�?""
    if thread_id is not None:
        thread = await get_thread_by_id(db, thread_id)
        if thread is None:
            raise ValueError(f"thread not found: {thread_id}")
        if thread.user_id != user_id:
            raise ValueError("thread does not belong to user")
        if thread.thread_kind != thread_kind:
            raise ValueError("thread kind mismatch")
        if thread_kind == ThreadKind.knowledge_base and thread.kb_id != kb_id:
            raise ValueError("thread kb_id mismatch")
        return thread

    if thread_kind == ThreadKind.knowledge_base:
        assert kb_id is not None
        return await get_or_create_active_thread(
            db, thread_kind=ThreadKind.knowledge_base,
            user_id=user_id, kb_id=kb_id,
        )

    assert workspace_kind is not None
    return await get_or_create_active_thread(
        db, thread_kind=ThreadKind.workspace,
        user_id=user_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_key=department_key,
    )


def _apply_workspace_thread_scope(
    stmt: Select[tuple[ChatThread]],
    *,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_key: str | None,
) -> Select[tuple[ChatThread]]:
    stmt = (
        stmt.where(ChatThread.thread_kind == ThreadKind.workspace)
        .where(ChatThread.user_id == user_id)
        .where(ChatThread.workspace_kind == workspace_kind.value)
    )
    if workspace_kind == WorkspaceKind.personal:
        stmt = stmt.where(ChatThread.workspace_org_id.is_(None))
    else:
        stmt = stmt.where(ChatThread.workspace_org_id == workspace_org_id)
    if department_key is None:
        stmt = stmt.where(ChatThread.workspace_department_key.is_(None))
    else:
        stmt = stmt.where(ChatThread.workspace_department_key == department_key)
    return stmt


def _thread_matches_workspace_scope(
    thread: ChatThread,
    *,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_key: str | None,
) -> bool:
    if thread.thread_kind != ThreadKind.workspace:
        return False
    if thread.workspace_kind != workspace_kind.value:
        return False
    if workspace_kind == WorkspaceKind.personal:
        if thread.workspace_org_id is not None:
            return False
    elif thread.workspace_org_id != workspace_org_id:
        return False
    if department_key is None:
        return thread.workspace_department_key is None
    return thread.workspace_department_key == department_key


async def list_workspace_threads(
    db: AsyncSession,
    *,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
    limit: int = 50,
    include_archived: bool = False,
) -> list[ChatThread]:
    """[别名] 工作�?thread 列表�?""
    return await list_threads(
        db, thread_kind=ThreadKind.workspace,
        user_id=user_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
        limit=limit,
        include_archived=include_archived,
    )


async def create_workspace_thread(
    db: AsyncSession,
    *,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
    title: str = NEW_THREAD_TITLE,
) -> ChatThread:
    """[别名] 新建工作�?thread�?""
    return await create_thread(
        db, thread_kind=ThreadKind.workspace,
        user_id=user_id,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
        title=title,
    )


async def get_workspace_thread_for_user(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
) -> ChatThread | None:
    """[别名] �?id �?workspace thread�?""
    return await get_thread_for_user(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.workspace,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
    )


async def update_workspace_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
    title: str | None = None,
    status: ThreadStatus | None = None,
) -> ChatThread | None:
    """[别名] PATCH workspace thread�?""
    return await update_thread(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.workspace,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
        title=title, status=status,
    )


async def archive_workspace_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    workspace_kind: WorkspaceKind,
    workspace_org_id: UUID | None,
    department_id: str | None,
) -> ChatThread | None:
    """[别名] 软删 workspace thread�?""
    return await archive_thread(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.workspace,
        workspace_kind=workspace_kind,
        workspace_org_id=workspace_org_id,
        department_id=department_id,
    )


async def list_kb_threads(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    limit: int = 50,
    include_archived: bool = False,
) -> list[ChatThread]:
    """[别名] 库内 thread 列表�?""
    return await list_threads(
        db, thread_kind=ThreadKind.knowledge_base,
        user_id=user_id, kb_id=kb_id,
        limit=limit, include_archived=include_archived,
    )


async def create_kb_thread(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    title: str = NEW_THREAD_TITLE,
) -> ChatThread:
    """[别名] 新建库内 thread�?""
    return await create_thread(
        db, thread_kind=ThreadKind.knowledge_base,
        user_id=user_id, kb_id=kb_id, title=title,
    )


async def get_kb_thread_for_user(
    db: AsyncSession,
    *,
    thread_id: UUID,
    kb_id: UUID,
    user_id: UUID,
) -> ChatThread | None:
    """[别名] �?id 取库�?thread�?""
    return await get_thread_for_user(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
    )


async def update_kb_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    kb_id: UUID,
    user_id: UUID,
    title: str | None = None,
    status: ThreadStatus | None = None,
) -> ChatThread | None:
    """[别名] PATCH 库内 thread�?""
    return await update_thread(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id, title=title, status=status,
    )


async def archive_kb_thread(
    db: AsyncSession,
    *,
    thread_id: UUID,
    kb_id: UUID,
    user_id: UUID,
) -> ChatThread | None:
    """[别名] 软删库内 thread�?""
    return await archive_thread(
        db,
        thread_id=thread_id, user_id=user_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
    )

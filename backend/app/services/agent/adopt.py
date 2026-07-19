"""G4-3.2 · adopt 真实写库。

``adopt_draft_to_kb``：读 ``approval.payload_json["markdown"]`` → 在目标 kb 存储路径
落 ``.md`` 文件 → **``_v2`` 冲突策略**（H4-6-A · 同名自动 ``_v2``）→
CREATE ``documents``(queued) → 复用现网 upload 文本路径
``background_tasks.add_task(process_document_ingestion)`` 触发 ingestion。

签名 ``adopt_draft_to_kb(db, approval, kb) -> UUID`` 与 G4-3.1 的 stub **完全一致**
（零改动调用方 ``resolve_adopt_approval``）；ingestion 入队所需的 ``BackgroundTasks``
经请求级 ``ContextVar``（``_adopt_background_tasks``）注入 —— 由 ``resolve_adopt_approval``
在 resolve 前绑定、resolve 后解绑，从而**不改动**本函数签名即可复用现网 upload 路径的
``background_tasks.add_task(process_document_ingestion, doc.id)`` 写法。

等价现网：``upload_documents`` 的文本/md 创建分支（``Document(queued)`` + 入队 ingestion）。
关键差异（H4-6-A）：upload 同名 → 409；adopt 同名 → 自动 ``_v2`` / ``_v3``…，不 409。

红线（继承 G4-3.1 / G4-2.1）：
- 写库**只在** resolve adopt 服务端路径发生（G4-3.1 已二次校验 kb write + 角色 + pending）。
- **绝不**暴露给模型（G4-2.1 红线）。
- adopt 异步（H4-4-A）：立刻返回 ``document_id``，ingestion 后台跑，不阻塞响应。
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_approval import AgentApproval
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.documents.content_hash import sha256_hex
from app.services.ingestion.pipeline import process_document_ingestion

# 请求级 BackgroundTasks 持有者：resolve adopt 前由 ``resolve_adopt_approval`` 绑定当前
# 请求的 ``BackgroundTasks``，本函数据此把 ``process_document_ingestion`` 入队，从而
# 复用现网 upload 路径且**不改函数签名**。
_adopt_background_tasks: ContextVar[Optional[BackgroundTasks]] = ContextVar(
    "adopt_background_tasks", default=None
)


def bind_adopt_background_tasks(bt: BackgroundTasks):
    """绑定当前请求的 BackgroundTasks（resolve adopt 前调用）。返回 token。"""
    return _adopt_background_tasks.set(bt)


def unbind_adopt_background_tasks(token) -> None:
    """resolve 完成后解绑，避免跨请求泄漏。"""
    _adopt_background_tasks.reset(token)


def _markdown_from_approval(approval: AgentApproval) -> str:
    payload = approval.payload_json
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("markdown", "") or "")


async def _filename_exists(db: AsyncSession, *, kb_id: UUID, name: str) -> bool:
    """同一资料库内文件名是否已存在（忽略大小写，复用 upload 同名判定口径）。"""
    safe = Path(name).name.strip()
    if not safe:
        return False
    existing = await db.scalar(
        select(Document.id)
        .where(Document.kb_id == kb_id, func.lower(Document.filename) == safe.lower())
        .limit(1)
    )
    return existing is not None


async def _resolve_adopt_filename(
    db: AsyncSession, *, kb_id: UUID, filename: str
) -> str:
    """H4-6-A：同名自动 ``_v2`` / ``_v3``…，不 409。

    文件名强制 ``.md`` 后缀（``generate_faq_draft`` 已校验，此处兜底）。
    从 ``_v2`` 起递增探测，直到命中空闲名（与现网「同名去重」口径一致，仅策略不同）。
    """
    path = Path(filename)
    stem = path.stem or "faq-draft"
    suffix = path.suffix.lower() or ".md"
    if suffix != ".md":
        suffix = ".md"
    base = f"{stem}{suffix}"
    if not await _filename_exists(db, kb_id=kb_id, name=base):
        return base
    n = 2
    while True:
        candidate = f"{stem}_v{n}{suffix}"
        if not await _filename_exists(db, kb_id=kb_id, name=candidate):
            return candidate
        n += 1


async def adopt_draft_to_kb(
    db: AsyncSession,
    approval: AgentApproval,
    kb: KnowledgeBase,
) -> UUID:
    """G4-3.2 真实写库：草稿 → ``.md`` 文件 → ``_v2`` → documents(queued) → ingestion 入队。

    与 G4-3.1 stub 同签名 ``(db, approval, kb) -> UUID``；返回 ``document_id`` 不变。

    流程（等价现网 upload 文本/md 分支）：
      1. 读 ``payload_json["markdown"]`` 全文。
      2. ``_resolve_adopt_filename`` 解析文件名（同名 → ``_v2``）。
      3. 在 ``settings.upload_dir / kb.id / doc.id / {uuid}.md`` 落盘 Markdown 文本。
      4. 组装 ``Document(queued)``（file_type=md、uploaded_by=approval.user_id）并 flush。
      5. ingestion 入队：若有绑定的 ``BackgroundTasks``（resolve 路径注入），
         ``add_task(process_document_ingestion, doc.id)``（H4-4-A 异步）。
    """
    markdown = _markdown_from_approval(approval)
    filename = await _resolve_adopt_filename(
        db, kb_id=kb.id, filename=approval.filename or "faq-draft.md"
    )
    content = markdown.encode("utf-8")

    doc_id = uuid.uuid4()
    storage_dir = Path(settings.upload_dir) / str(kb.id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}.md"
    storage_path = storage_dir / stored_name
    storage_path.write_text(markdown, encoding="utf-8")

    doc = Document(
        id=doc_id,
        kb_id=kb.id,
        filename=filename,
        file_type="md",
        file_size=len(content),
        content_sha256=sha256_hex(content),
        storage_path=str(storage_path),
        status=DocumentStatus.queued,
        uploaded_by=approval.user_id,
    )
    db.add(doc)
    await db.flush()

    # ingestion 入队（H4-4-A 异步）：复用现网 upload 文本路径。
    bt = _adopt_background_tasks.get()
    if bt is not None:
        bt.add_task(process_document_ingestion, doc.id)

    return doc.id


__all__ = [
    "adopt_draft_to_kb",
    "bind_adopt_background_tasks",
    "unbind_adopt_background_tasks",
]

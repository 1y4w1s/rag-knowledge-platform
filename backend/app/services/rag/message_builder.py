"""引用富化共享函数（code-refactor-D）：从历史消息 rows 构建 ChatMessageResponse 列表。"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from app.core.deps import CurrentUser
from app.schemas.chat import ChatMessageResponse, HistoryCitationPayload
from app.schemas.citation import CitationSourceStatus
from app.services.rag.citations import enrich_history_citation_payload

SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def build_chat_message_list(
    db: AsyncSession,
    rows: list[Any],
    *,
    current_user: CurrentUser,
    kb_visible_fn: Callable[[HistoryCitationPayload, dict], Awaitable[bool]],
    department_id: str | None = None,
    include_approval: bool = False,
    kb_id: UUID | None = None,
) -> list[ChatMessageResponse]:
    """从 DB rows 构建 ChatMessageResponse 列表，逐条回填引用可见性/富化。

    Args:
        db: 数据库会话。
        rows: 从 list_chat_messages / list_workspace_chat_messages 返回的 DB 行。
        current_user: 当前用户。
        kb_visible_fn: 异步函数 (payload, raw_dict) -> bool，判断单条引用是否可见。
        department_id: 可选部门 ID。
        include_approval: 是否包含 approval_id / approval_status 字段
                         （KB 变体=True，Workspace 变体=False）。
        kb_id: KB 上下文时显式传入 kb_id（因存储的 citation 可能不含 kb_id）；
               Workspace 上下文时传 None（从 payload.kb_id 读取）。
    """
    messages: list[ChatMessageResponse] = []
    for row in rows:
        citations: list[HistoryCitationPayload] | None = None
        if row.citations is not None:
            citations = []
            for raw in row.citations:
                payload = HistoryCitationPayload.model_validate(raw)
                visible = await kb_visible_fn(payload, raw)
                if not visible:
                    payload = payload.model_copy(
                        update={
                            "source_status": CitationSourceStatus.source_inaccessible
                        }
                    )
                elif kb_id is not None or payload.kb_id is not None:
                    payload = await enrich_history_citation_payload(
                        db,
                        current_user,
                        payload,
                        kb_id=kb_id or payload.kb_id,
                        department_id=department_id,
                    )
                citations.append(payload)
        kwargs: dict[str, Any] = {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "citations": citations,
            "created_at": row.created_at,
        }
        if include_approval:
            kwargs["approval_id"] = row.approval_id
            kwargs["approval_status"] = row.approval_status
        messages.append(ChatMessageResponse(**kwargs))
    return messages

"""引用富化共享函数（code-refactor-D）：从历史消息 rows 构建 ChatMessageResponse 列表。"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from app.core.deps import CurrentUser
from app.schemas.chat import ChatMessageResponse, HistoryCitationPayload
from app.schemas.citation import CitationSourceStatus
from app.services.rag.citations import enrich_history_citation_payloads

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
    kb_visible_batch_fn: Callable[
        [list[HistoryCitationPayload], list[dict]], Awaitable[list[bool]]
    ]
    | None = None,
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
        kb_visible_batch_fn: 可选异步函数 (payloads, raw_dicts) -> list[bool]，
            一次性判断一批引用可见性（P2-R4：避免每条引用逐个查库）。
        department_id: 可选部门 ID。
        include_approval: 是否包含 approval_id / approval_status 字段
                         （KB 变体=True，Workspace 变体=False）。
        kb_id: KB 上下文时显式传入 kb_id（因存储的 citation 可能不含 kb_id）；
               Workspace 上下文时传 None（从 payload.kb_id 读取）。
    """
    citation_refs: list[tuple[int, int, HistoryCitationPayload, dict]] = []
    for row_index, row in enumerate(rows):
        if row.citations is None:
            continue
        for cite_index, raw in enumerate(row.citations):
            citation_refs.append(
                (
                    row_index,
                    cite_index,
                    HistoryCitationPayload.model_validate(raw),
                    raw,
                )
            )

    if kb_visible_batch_fn is not None and citation_refs:
        visible_flags = await kb_visible_batch_fn(
            [ref[2] for ref in citation_refs],
            [ref[3] for ref in citation_refs],
        )
    else:
        visible_flags = [
            await kb_visible_fn(payload, raw)
            for _, _, payload, raw in citation_refs
        ]

    enrich_payloads: list[HistoryCitationPayload] = []
    enrich_positions: list[tuple[int, int]] = []
    for (row_index, cite_index, payload, _raw), visible in zip(
        citation_refs, visible_flags
    ):
        if visible and (kb_id is not None or payload.kb_id is not None):
            enrich_payloads.append(payload)
            enrich_positions.append((row_index, cite_index))

    enriched_by_position: dict[tuple[int, int], HistoryCitationPayload] = {}
    if enrich_payloads:
        enriched = await enrich_history_citation_payloads(
            db,
            current_user,
            enrich_payloads,
            department_id=department_id,
            default_kb_id=kb_id,
        )
        enriched_by_position = dict(zip(enrich_positions, enriched))

    resolved_by_position: dict[tuple[int, int], HistoryCitationPayload] = {}
    for (row_index, cite_index, payload, _raw), visible in zip(
        citation_refs, visible_flags
    ):
        if not visible:
            resolved_by_position[(row_index, cite_index)] = payload.model_copy(
                update={
                    "source_status": CitationSourceStatus.source_inaccessible
                }
            )
        elif (row_index, cite_index) in enriched_by_position:
            resolved_by_position[(row_index, cite_index)] = enriched_by_position[
                (row_index, cite_index)
            ]
        else:
            resolved_by_position[(row_index, cite_index)] = payload

    messages: list[ChatMessageResponse] = []
    for row_index, row in enumerate(rows):
        citations: list[HistoryCitationPayload] | None = None
        if row.citations is not None:
            citations = []
            for cite_index in range(len(row.citations)):
                citations.append(
                    resolved_by_position[(row_index, cite_index)]
                )
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

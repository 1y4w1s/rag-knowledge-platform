"""引用失效解析（Plan-3E-3 / EW-D3 · ORG-1.7 不可见库）。"""

import uuid

from fastapi import status
from app.core.exceptions import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, _assert_kb_action_allowed, _assert_kb_ownership
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.chat import HistoryCitationPayload
from app.schemas.citation import CitationResolveResponse, CitationSourceStatus
from app.services.org.scope import _is_company_admin, resolve_org_scope


async def is_kb_visible_in_org_scope(
    db: AsyncSession,
    current_user: CurrentUser,
    kb: KnowledgeBase,
    *,
    department_id: str | None = None,
) -> bool:
    """个人库或已通过归属校验的团队库：是否落在当前 OrgScope visible 内。"""
    if kb.owner_org_id is None or kb.owner_user_id is not None:
        return True
    if _is_company_admin(current_user):
        return True
    scope = await resolve_org_scope(db, current_user, department_id=department_id)
    return scope.is_kb_visible(kb.id)


async def resolve_citation(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_id: uuid.UUID,
    *,
    department_id: str | None = None,
) -> CitationResolveResponse:
    """校验 citation 指向的文档/切片是否仍可用；不可见库返回 200 + source_inaccessible。"""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError("知识库不存在")

    _assert_kb_ownership(kb, current_user)
    _assert_kb_action_allowed(current_user, KbAction.read)

    if not await is_kb_visible_in_org_scope(
        db, current_user, kb, department_id=department_id
    ):
        return CitationResolveResponse(
            document_id=document_id,
            chunk_id=chunk_id,
            source_status=CitationSourceStatus.source_inaccessible,
            doc_name=None,
        )

    doc = await db.get(Document, document_id)
    if doc is None or doc.kb_id != kb_id:
        return CitationResolveResponse(
            document_id=document_id,
            chunk_id=chunk_id,
            source_status=CitationSourceStatus.document_deleted,
            doc_name=None,
        )

    chunk = await db.get(DocumentChunk, chunk_id)
    if chunk is None or chunk.document_id != document_id:
        return CitationResolveResponse(
            document_id=document_id,
            chunk_id=chunk_id,
            source_status=CitationSourceStatus.chunk_stale,
            doc_name=doc.filename,
        )

    return CitationResolveResponse(
        document_id=document_id,
        chunk_id=chunk_id,
        source_status=CitationSourceStatus.available,
        doc_name=doc.filename,
    )


async def enrich_history_citation_payload(
    db: AsyncSession,
    current_user: CurrentUser,
    payload: HistoryCitationPayload,
    *,
    kb_id: uuid.UUID,
    department_id: str | None = None,
) -> HistoryCitationPayload:
    """Plan-3E-3：历史 citation 回填 source_status（doc 已删 / chunk 失效）。"""
    if payload.source_status == CitationSourceStatus.source_inaccessible:
        return payload

    result = await resolve_citation(
        db,
        current_user,
        kb_id,
        payload.document_id,
        payload.chunk_id,
        department_id=department_id,
    )
    if result.source_status == CitationSourceStatus.available:
        return payload
    return payload.model_copy(update={"source_status": result.source_status})

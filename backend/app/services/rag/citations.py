"""引用失效解析（Plan-3E-3 / EW-D3 · ORG-1.7 不可见库）。"""

import uuid

from app.core.exceptions import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, _assert_kb_action_allowed, _assert_kb_ownership
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.chat import HistoryCitationPayload
from app.schemas.citation import CitationResolveResponse, CitationSourceStatus
from app.services.org.scope import OrgScope, _is_company_admin, resolve_org_scope


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
    await _assert_kb_action_allowed(
        current_user, KbAction.read, db=db, kb_id=kb_id
    )

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
    if doc is None or doc.kb_id != kb_id or getattr(doc, "deleted_at", None) is not None:
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


async def _resolve_org_scope_for_citations(
    db: AsyncSession,
    current_user: CurrentUser,
    kbs: dict[uuid.UUID, KnowledgeBase],
    *,
    department_id: str | None,
) -> OrgScope | None:
    """仅当存在需要 OrgScope 判断的团队库时解析一次部门可见范围。"""
    needs_scope = any(
        kb.owner_org_id is not None and kb.owner_user_id is None
        for kb in kbs.values()
    )
    if not needs_scope or _is_company_admin(current_user):
        return None
    return await resolve_org_scope(db, current_user, department_id=department_id)


def _citation_kb_visible(
    kb: KnowledgeBase,
    current_user: CurrentUser,
    org_scope: OrgScope | None,
) -> bool:
    """与 is_kb_visible_in_org_scope 等价的批量版可见性判断。"""
    if kb.owner_org_id is None or kb.owner_user_id is not None:
        return True
    if _is_company_admin(current_user):
        return True
    if org_scope is None:
        return False
    return org_scope.is_kb_visible(kb.id)


async def enrich_history_citation_payloads(
    db: AsyncSession,
    current_user: CurrentUser,
    payloads: list[HistoryCitationPayload],
    *,
    department_id: str | None = None,
    default_kb_id: uuid.UUID | None = None,
) -> list[HistoryCitationPayload]:
    """P2-R4：批量回填历史引用状态，避免每条引用重复查库。"""
    if not payloads:
        return []

    need_resolve = [
        (index, payload, payload.kb_id or default_kb_id)
        for index, payload in enumerate(payloads)
        if payload.source_status != CitationSourceStatus.source_inaccessible
        and (payload.kb_id is not None or default_kb_id is not None)
    ]
    if not need_resolve:
        return payloads

    kb_ids = {kb_id for _, _, kb_id in need_resolve}
    kbs = {
        kb.id: kb
        for kb in (
            await db.scalars(
                select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
            )
        ).all()
    }
    doc_ids = {payload.document_id for _, payload, _ in need_resolve}
    docs = {
        doc.id: doc
        for doc in (
            await db.scalars(select(Document).where(Document.id.in_(doc_ids)))
        ).all()
    }
    chunk_ids = {payload.chunk_id for _, payload, _ in need_resolve}
    chunks = {
        chunk.id: chunk
        for chunk in (
            await db.scalars(
                select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
            )
        ).all()
    }

    org_scope = await _resolve_org_scope_for_citations(
        db,
        current_user,
        kbs,
        department_id=department_id,
    )
    status_by_ref: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], CitationSourceStatus] = {}
    for _, payload, kb_id in need_resolve:
        ref_key = (kb_id, payload.document_id, payload.chunk_id)
        if ref_key in status_by_ref:
            continue
        kb = kbs.get(kb_id)
        if kb is None:
            raise NotFoundError("知识库不存在")
        _assert_kb_ownership(kb, current_user)
        await _assert_kb_action_allowed(
            current_user, KbAction.read, db=db, kb_id=kb_id
        )
        if not _citation_kb_visible(kb, current_user, org_scope):
            status_by_ref[ref_key] = CitationSourceStatus.source_inaccessible
            continue
        doc = docs.get(payload.document_id)
        if doc is None or doc.kb_id != kb_id or doc.deleted_at is not None:
            status_by_ref[ref_key] = CitationSourceStatus.document_deleted
            continue
        chunk = chunks.get(payload.chunk_id)
        if chunk is None or chunk.document_id != payload.document_id:
            status_by_ref[ref_key] = CitationSourceStatus.chunk_stale
            continue
        status_by_ref[ref_key] = CitationSourceStatus.available

    enriched = list(payloads)
    for index, payload, kb_id in need_resolve:
        status = status_by_ref[(kb_id, payload.document_id, payload.chunk_id)]
        if status != CitationSourceStatus.available:
            enriched[index] = payload.model_copy(update={"source_status": status})
    return enriched

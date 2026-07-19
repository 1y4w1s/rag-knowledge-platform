"""知识库 CRUD 业务逻辑（Wave 2.1）。"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_base.names import assert_kb_name_available
from app.services.audit.log import write_audit_log
from app.services.storage.cleaner import remove_kb_tree
from app.services.knowledge_base.org_assignment import (
    assert_can_create_org_kb,
    resolve_and_validate_kb_org_unit_id,
)
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


@dataclass(frozen=True)
class KbDocumentStats:
    document_count: int
    updated_at: datetime
    processing_count: int
    failed_count: int


def _kb_to_response(kb: KnowledgeBase, stats: KbDocumentStats) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        owner_user_id=kb.owner_user_id,
        owner_org_id=kb.owner_org_id,
        org_unit_id=kb.org_unit_id,
        created_at=kb.created_at,
        updated_at=stats.updated_at,
        document_count=stats.document_count,
        processing_count=stats.processing_count,
        failed_count=stats.failed_count,
    )


def _empty_kb_stats(kb: KnowledgeBase) -> KbDocumentStats:
    return KbDocumentStats(
        document_count=0,
        updated_at=kb.created_at,
        processing_count=0,
        failed_count=0,
    )


async def _kb_document_stats_for_kbs(
    db: AsyncSession,
    kbs: list[KnowledgeBase],
) -> dict[UUID, KbDocumentStats]:
    if not kbs:
        return {}

    kb_by_id = {kb.id: kb for kb in kbs}
    kb_ids = list(kb_by_id.keys())

    stmt = (
        select(
            Document.kb_id,
            func.count().label("document_count"),
            func.max(Document.updated_at).label("max_doc_updated_at"),
            func.count()
            .filter(
                Document.status.in_(
                    [DocumentStatus.queued, DocumentStatus.processing]
                )
            )
            .label("processing_count"),
            func.count()
            .filter(Document.status == DocumentStatus.failed)
            .label("failed_count"),
        )
        .where(Document.kb_id.in_(kb_ids))
        .group_by(Document.kb_id)
    )
    rows = await db.execute(stmt)

    stats: dict[UUID, KbDocumentStats] = {}
    for kb_id, doc_count, max_updated, processing_count, failed_count in rows.all():
        kb = kb_by_id[kb_id]
        max_updated_dt = max_updated or kb.created_at
        stats[kb_id] = KbDocumentStats(
            document_count=int(doc_count),
            updated_at=max(kb.created_at, max_updated_dt),
            processing_count=int(processing_count),
            failed_count=int(failed_count),
        )

    for kb_id, kb in kb_by_id.items():
        if kb_id not in stats:
            stats[kb_id] = _empty_kb_stats(kb)

    return stats


async def _kb_document_stats_for_kb(
    db: AsyncSession,
    kb: KnowledgeBase,
) -> KbDocumentStats:
    stats = await _kb_document_stats_for_kbs(db, [kb])
    return stats[kb.id]


async def create_knowledge_base(
    db: AsyncSession,
    current_user: CurrentUser,
    body: KnowledgeBaseCreate,
    scope: WorkspaceScope,
    *,
    department_id: str | None = None,
) -> KnowledgeBaseResponse:
    name = await assert_kb_name_available(db, scope, body.name)

    kb = KnowledgeBase(
        name=name,
        description=body.description.strip() if body.description else None,
    )
    if scope.kind == WorkspaceKind.personal:
        kb.owner_user_id = current_user.id
        kb.owner_org_id = None
        kb.org_unit_id = None
    else:
        await assert_can_create_org_kb(db, current_user)
        assert scope.org_id is not None
        kb.owner_org_id = scope.org_id
        kb.owner_user_id = None
        kb.org_unit_id = await resolve_and_validate_kb_org_unit_id(
            db,
            current_user,
            org_unit_id=body.org_unit_id,
            org_unit_id_in_body="org_unit_id" in body.model_fields_set,
            department_id=department_id,
        )

    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return _kb_to_response(kb, _empty_kb_stats(kb))


async def get_knowledge_base(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
    *,
    department_id: str | None = None,
) -> KnowledgeBaseResponse:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
        department_id=department_id,
    )
    kb = await db.get(KnowledgeBase, kb_id)
    assert kb is not None
    stats = await _kb_document_stats_for_kb(db, kb)
    return _kb_to_response(kb, stats)


async def update_knowledge_base(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
) -> KnowledgeBaseResponse:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )
    kb = await db.get(KnowledgeBase, kb_id)
    assert kb is not None

    kb_scope = WorkspaceScope.from_knowledge_base(kb)

    if body.name is not None:
        kb.name = await assert_kb_name_available(
            db,
            kb_scope,
            body.name,
            exclude_kb_id=kb_id,
        )
    if body.description is not None:
        kb.description = body.description.strip() if body.description else None

    await db.commit()
    await db.refresh(kb)
    stats = await _kb_document_stats_for_kb(db, kb)
    return _kb_to_response(kb, stats)


async def delete_knowledge_base(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: UUID,
    *,
    ip: str | None = None,
) -> None:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.admin,
        current_user=current_user,
        db=db,
    )
    kb = await db.get(KnowledgeBase, kb_id)
    assert kb is not None
    kb_name = kb.name
    await write_audit_log(
        db,
        action="kb.delete",
        actor_user_id=current_user.id,
        resource_type="kb",
        resource_id=kb_id,
        kb_id=kb_id,
        metadata={"name": kb_name},
        ip=ip,
    )
    await db.delete(kb)
    await db.commit()

    cleanup = remove_kb_tree(kb_id)
    if cleanup.file_errors + cleanup.tree_errors > 0:
        await write_audit_log(
            db,
            action="storage.cleanup_failed",
            actor_user_id=current_user.id,
            resource_type="knowledge_base",
            resource_id=kb_id,
            kb_id=kb_id,
            metadata={
                "name": kb_name,
                "file_errors": cleanup.file_errors,
                "tree_errors": cleanup.tree_errors,
            },
            ip=ip,
        )
        await db.commit()

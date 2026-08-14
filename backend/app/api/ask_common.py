"""工作区 /ask 路由共享校验与 citation 可见性（G-1 · G2-1.1）。"""

from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.enums import OrgRole
from app.models.knowledge_base import KnowledgeBase
from app.schemas.chat import HistoryCitationPayload
from app.services.org.scope import OrgScope, _is_company_admin, resolve_org_scope
from app.services.rag.citations import is_kb_visible_in_org_scope
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


def assert_team_business_allowed(
    current_user: CurrentUser,
    scope: WorkspaceScope,
) -> None:
    """未分配 Member 禁止团队工作区对话（PRD E17 / T-ask-4）。"""
    if scope.kind != WorkspaceKind.organization:
        return
    if _is_company_admin(current_user):
        return
    if current_user.org_role != OrgRole.member:
        return
    if not current_user.unit_ids:
        raise ForbiddenError(
            detail="尚未分配部门，无法使用团队对话",
        )


async def assert_has_visible_knowledge_bases(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser,
) -> None:
    """可见库为空时拒问（H5-A · T-ask 前置）。"""
    if org_scope is not None:
        if not org_scope.visible_kb_ids:
            raise BadRequestError(
                detail="无可用资料库",
            )
        return

    count = await db.scalar(
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.owner_user_id == current_user.id)
    )
    if not count:
        raise BadRequestError(
            detail="无可用资料库",
        )


async def citation_visible_in_scope(
    db: AsyncSession,
    current_user: CurrentUser,
    raw: dict,
    *,
    scope: WorkspaceScope,
    department_id: str | None,
) -> bool:
    kb_id_raw = raw.get("kb_id")
    if kb_id_raw is None:
        return True
    try:
        kb_id = UUID(str(kb_id_raw))
    except ValueError:
        return False
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        return False
    if scope.kind == WorkspaceKind.personal:
        return kb.owner_user_id == current_user.id
    return await is_kb_visible_in_org_scope(
        db, current_user, kb, department_id=department_id
    )


async def citations_visible_in_scope_batch(
    db: AsyncSession,
    current_user: CurrentUser,
    _payloads: list[HistoryCitationPayload],
    raws: list[dict],
    *,
    scope: WorkspaceScope,
    department_id: str | None,
) -> list[bool]:
    """P2-R4：批量判断工作区引用可见性，一次加载 KB 且最多解析一次 OrgScope。"""
    if not raws:
        return []

    invalid = object()
    keys: list[UUID | object | None] = []
    kb_ids: set[UUID] = set()
    for raw in raws:
        kb_id_raw = raw.get("kb_id")
        if kb_id_raw is None:
            keys.append(None)
            continue
        try:
            kb_id = UUID(str(kb_id_raw))
        except ValueError:
            keys.append(invalid)
            continue
        keys.append(kb_id)
        kb_ids.add(kb_id)

    kbs: dict[UUID, KnowledgeBase] = {}
    if kb_ids:
        kbs = {
            kb.id: kb
            for kb in (
                await db.scalars(
                    select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
                )
            ).all()
        }

    org_scope: OrgScope | None = None
    if scope.kind == WorkspaceKind.organization and not _is_company_admin(
        current_user
    ):
        needs_scope = any(
            kb.owner_org_id is not None and kb.owner_user_id is None
            for kb in kbs.values()
        )
        if needs_scope:
            org_scope = await resolve_org_scope(
                db, current_user, department_id=department_id
            )

    visible: list[bool] = []
    for key in keys:
        if key is None:
            visible.append(True)
            continue
        if key is invalid:
            visible.append(False)
            continue
        kb = kbs.get(key)
        if kb is None:
            visible.append(False)
            continue
        if scope.kind == WorkspaceKind.personal:
            visible.append(kb.owner_user_id == current_user.id)
            continue
        if kb.owner_org_id is None or kb.owner_user_id is not None:
            visible.append(True)
            continue
        if _is_company_admin(current_user):
            visible.append(True)
            continue
        visible.append(org_scope.is_kb_visible(kb.id) if org_scope else False)
    return visible

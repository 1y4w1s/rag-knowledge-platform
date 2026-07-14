"""OrgScope — 部门上下文下的资料库可见/可写集合（ORG-1.1）。

visible = 当前部门子树库 ∪ 公司公共库 ∪ grant 命中库
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.core.exceptions import ForbiddenError, ValidationError
from app.models.enums import AccountType, GrantPermission, GranteeType, OrgRole, UnitRole
from app.models.kb_unit_grant import KbUnitGrant
from app.models.knowledge_base import KnowledgeBase
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.schemas.auth import UserPublic
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from sqlalchemy import and_, or_, select


class DepartmentContext(str, Enum):
    all = "all"


@dataclass(frozen=True)
class OrgScope:
    """当前用户在团队空间 + 部门上下文下的资料库范围。"""

    org_id: UUID
    user_id: UUID
    department_unit_id: UUID | None
    view_all_departments: bool
    visible_kb_ids: frozenset[UUID]
    writable_kb_ids: frozenset[UUID]
    unit_memberships: tuple[OrgUnitMember, ...]
    subtree_unit_ids: frozenset[UUID]

    def kb_visibility_clause(self) -> ColumnElement[bool]:
        """KnowledgeBase.id 须落在 visible 集合内。"""
        if not self.visible_kb_ids:
            return KnowledgeBase.id.is_(None)
        return KnowledgeBase.id.in_(self.visible_kb_ids)

    def is_kb_visible(self, kb_id: UUID) -> bool:
        return kb_id in self.visible_kb_ids

    def is_kb_writable(self, kb_id: UUID) -> bool:
        return kb_id in self.writable_kb_ids


def _is_company_admin(current_user: UserPublic) -> bool:
    return current_user.is_owner or current_user.org_role == OrgRole.admin


def can_user_adopt_kb(
    current_user: UserPublic,
    kb: KnowledgeBase,
    org_scope: OrgScope | None,
) -> bool:
    """G4-2.3 · 编辑模式采纳卡 `can_adopt` 信号（H4-1-B）。

    精确判定目标 kb 是否可被当前用户采纳：
    - 个人库 owner → True；
    - 组织库 → 须 Admin/Owner 角色 + kb write（Member 永不可 · HA-2-A）。

    仅为卡片「是否显示采纳入库钮」的启发式信号；真实写库权限在
    G4-3.1 `POST /approvals/{id}/resolve` 二次校验（kb write + 角色 + pending）。
    """
    if kb.owner_user_id is not None and kb.owner_user_id == current_user.id:
        return True
    if kb.owner_org_id is not None and kb.owner_user_id is None:
        if not _is_company_admin(current_user):
            return False
        if org_scope is not None:
            return org_scope.is_kb_writable(kb.id)
        return True
    return False


def can_user_adopt_in_workspace(
    current_user: UserPublic,
    scope: WorkspaceScope,
) -> bool:
    """G4-2.3 · /ask 编辑模式（目标库运行时解析）的 `can_adopt` 启发式。

    /ask 编辑下草稿写入首个命中库（planner 运行时解析），此处无法精确判定
    目标库，故按工作区维度近似：个人工作区 owner=True；组织工作区须
    Admin/Owner 角色（Member 永不可采纳 · HA-2-A）。实际采纳权限在 G4-3.1 复核。
    """
    if scope.kind == WorkspaceKind.personal:
        return True
    return _is_company_admin(current_user)


async def _load_unit_memberships(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
) -> list[OrgUnitMember]:
    rows = await db.scalars(
        select(OrgUnitMember)
        .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
        .where(OrgUnit.org_id == org_id, OrgUnitMember.user_id == user_id)
    )
    return list(rows.all())


async def _load_units_for_org(db: AsyncSession, org_id: UUID) -> list[OrgUnit]:
    rows = await db.scalars(select(OrgUnit).where(OrgUnit.org_id == org_id))
    return list(rows.all())


def _primary_unit_id(memberships: list[OrgUnitMember]) -> UUID | None:
    for row in memberships:
        if row.is_primary:
            return row.org_unit_id
    return memberships[0].org_unit_id if memberships else None


def _subtree_unit_ids(units: list[OrgUnit], anchor_id: UUID) -> frozenset[UUID]:
    by_id = {u.id: u for u in units}
    anchor = by_id.get(anchor_id)
    if anchor is None:
        return frozenset()
    prefix = anchor.path
    return frozenset(u.id for u in units if u.path.startswith(prefix))


def _member_unit_ids(memberships: list[OrgUnitMember]) -> frozenset[UUID]:
    return frozenset(m.org_unit_id for m in memberships)


def _resolve_effective_department(
    *,
    current_user: UserPublic,
    memberships: list[OrgUnitMember],
    department_id: str | None,
) -> tuple[UUID | None, bool]:
    """返回 (anchor_unit_id, view_all_departments)。"""
    if department_id is not None and department_id.strip().lower() == DepartmentContext.all.value:
        if not _is_company_admin(current_user):
            raise ForbiddenError("无权访问该部门")
        return None, True

    if department_id is None or department_id.strip() == "":
        return _primary_unit_id(memberships), False

    try:
        requested = UUID(department_id.strip())
    except ValueError as exc:
        raise ValidationError("无效的部门 ID") from exc

    allowed = _member_unit_ids(memberships)
    if requested not in allowed:
        if _is_company_admin(current_user):
            return requested, False
        raise ForbiddenError("无权访问该部门")
    return requested, False


async def _grant_visible_kb_ids(
    db: AsyncSession,
    *,
    org_id: UUID,
    anchor_unit_id: UUID | None,
    view_all: bool,
    units: list[OrgUnit],
    memberships: list[OrgUnitMember],
) -> set[UUID]:
    grants = list(
        (
            await db.scalars(
                select(KbUnitGrant)
                .join(KnowledgeBase, KnowledgeBase.id == KbUnitGrant.kb_id)
                .where(KnowledgeBase.owner_org_id == org_id)
            )
        ).all()
    )
    if not grants:
        return set()

    by_id = {u.id: u for u in units}
    member_ids = _member_unit_ids(memberships)

    def grant_matches_context(grant: KbUnitGrant) -> bool:
        if grant.grantee_type == GranteeType.company:
            return True
        if grant.grantee_id is None:
            return False
        grantee = by_id.get(grant.grantee_id)
        if grantee is None:
            return False
        if view_all:
            return True
        if anchor_unit_id is None:
            return False
        anchor = by_id.get(anchor_unit_id)
        if anchor is None:
            return False
        # grant 目标为当前部门或其祖先
        if grant.grantee_id in member_ids and anchor.path.startswith(grantee.path):
            return True
        # grant 目标部门是当前部门的子树（grant 给父、人在子）
        if grant.grantee_id in member_ids and grantee.path.startswith(anchor.path):
            return True
        return grant.grantee_id == anchor_unit_id

    return {g.kb_id for g in grants if grant_matches_context(g)}


async def _base_visible_kb_ids(
    db: AsyncSession,
    *,
    org_id: UUID,
    subtree_ids: frozenset[UUID],
    view_all: bool,
    has_unit_membership: bool,
) -> set[UUID]:
    clauses = [
        (KnowledgeBase.owner_org_id == org_id) & (KnowledgeBase.org_unit_id.is_(None)),
    ]
    if view_all:
        clauses.append(
            (KnowledgeBase.owner_org_id == org_id) & (KnowledgeBase.org_unit_id.is_not(None))
        )
    elif subtree_ids:
        clauses.append(
            (KnowledgeBase.owner_org_id == org_id)
            & (KnowledgeBase.org_unit_id.in_(subtree_ids))
        )

    if not clauses:
        return set()

    rows = await db.scalars(
        select(KnowledgeBase.id).where(or_(*clauses))
    )
    visible = set(rows.all())

    if not has_unit_membership and not view_all:
        # 未分配：仅公司公共库
        public_rows = await db.scalars(
            select(KnowledgeBase.id).where(
                KnowledgeBase.owner_org_id == org_id,
                KnowledgeBase.org_unit_id.is_(None),
            )
        )
        return set(public_rows.all())

    return visible


def _writable_from_visible(
    *,
    current_user: UserPublic,
    memberships: list[OrgUnitMember],
    units: list[OrgUnit],
    visible_kb_ids: set[UUID],
    kbs: list[KnowledgeBase],
    grant_rows: list[KbUnitGrant],
) -> set[UUID]:
    if _is_company_admin(current_user):
        return {kb.id for kb in kbs if kb.owner_org_id == current_user.org_id}

    admin_subtree: set[UUID] = set()
    by_id = {u.id: u for u in units}
    for membership in memberships:
        if membership.role != UnitRole.unit_admin:
            continue
        unit = by_id.get(membership.org_unit_id)
        if unit is None:
            continue
        admin_subtree.update(
            u.id for u in units if u.path.startswith(unit.path)
        )

    grant_write = {
        g.kb_id
        for g in grant_rows
        if g.permission == GrantPermission.write and g.kb_id in visible_kb_ids
    }

    writable: set[UUID] = set(grant_write)
    for kb in kbs:
        if kb.id not in visible_kb_ids:
            continue
        if kb.org_unit_id is None:
            continue
        if kb.org_unit_id in admin_subtree:
            writable.add(kb.id)
    return writable


async def resolve_org_scope_for_workspace(
    db: AsyncSession,
    current_user: UserPublic,
    workspace: WorkspaceScope,
    *,
    department_id: str | None = None,
) -> OrgScope | None:
    """团队工作区解析 OrgScope；个人工作区返回 None（ORG-1.8）。"""
    if workspace.kind != WorkspaceKind.organization:
        return None
    return await resolve_org_scope(db, current_user, department_id=department_id)


async def resolve_org_scope(
    db: AsyncSession,
    current_user: UserPublic,
    *,
    department_id: str | None = None,
) -> OrgScope:
    """解析部门上下文并计算 visible / writable 集合。"""
    if current_user.account_type != AccountType.enterprise:
        raise ForbiddenError("需要团队账号")
    assert current_user.org_id is not None

    org_id = current_user.org_id
    memberships = await _load_unit_memberships(db, org_id=org_id, user_id=current_user.id)
    units = await _load_units_for_org(db, org_id)

    anchor_id, view_all = _resolve_effective_department(
        current_user=current_user,
        memberships=memberships,
        department_id=department_id,
    )

    if view_all:
        subtree_ids = frozenset(u.id for u in units)
    elif anchor_id is None:
        subtree_ids = frozenset()
    else:
        subtree_ids = _subtree_unit_ids(units, anchor_id)

    has_unit = bool(memberships)
    visible = await _base_visible_kb_ids(
        db,
        org_id=org_id,
        subtree_ids=subtree_ids,
        view_all=view_all,
        has_unit_membership=has_unit,
    )
    visible |= await _grant_visible_kb_ids(
        db,
        org_id=org_id,
        anchor_unit_id=anchor_id,
        view_all=view_all,
        units=units,
        memberships=memberships,
    )

    kb_rows = list(
        (
            await db.scalars(
                select(KnowledgeBase).where(KnowledgeBase.id.in_(visible))
            )
        ).all()
    ) if visible else []

    grant_rows = list(
        (
            await db.scalars(
                select(KbUnitGrant).where(KbUnitGrant.kb_id.in_(visible))
            )
        ).all()
    ) if visible else []

    writable = _writable_from_visible(
        current_user=current_user,
        memberships=memberships,
        units=units,
        visible_kb_ids=visible,
        kbs=kb_rows,
        grant_rows=grant_rows,
    )

    return OrgScope(
        org_id=org_id,
        user_id=current_user.id,
        department_unit_id=anchor_id,
        view_all_departments=view_all,
        visible_kb_ids=frozenset(visible),
        writable_kb_ids=frozenset(writable),
        unit_memberships=tuple(memberships),
        subtree_unit_ids=subtree_ids,
    )


async def assert_kb_visible_in_org_scope(
    db: AsyncSession,
    current_user: UserPublic,
    kb: KnowledgeBase,
    *,
    department_id: str | None = None,
) -> OrgScope:
    """团队库：在 OrgScope 内校验 kb 可见；公司 Admin/Owner 对同 org 库放行。"""
    if kb.owner_org_id != current_user.org_id:
        raise ForbiddenError("无权访问该资料库")

    if _is_company_admin(current_user):
        scope = await resolve_org_scope(db, current_user, department_id=department_id)
        return scope

    scope = await resolve_org_scope(db, current_user, department_id=department_id)
    if not scope.is_kb_visible(kb.id):
        raise ForbiddenError("无权访问该资料库")
    return scope

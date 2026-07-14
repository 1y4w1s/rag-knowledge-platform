"""工作区 Query 解析与 scope 对象（W1-1）。

W1-2 起 crud/stats 接入 ``WorkspaceScope`` 做 SQL 筛选；本模块只负责校验与构造 scope。
"""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from fastapi import status
from app.core.exceptions import ValidationError, ForbiddenError
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import UserPublic
from app.models.knowledge_base import KnowledgeBase
from app.models.organization_member import OrganizationMember


class WorkspaceKind(str, Enum):
    personal = "personal"
    organization = "organization"


@dataclass(frozen=True)
class WorkspaceScope:
    """当前请求的工作区数据范围（W1-2 用于 list/stats/create SQL）。"""

    kind: WorkspaceKind
    user_id: UUID
    org_id: UUID | None = None

    def kb_owner_clause(self) -> ColumnElement[bool]:
        """KnowledgeBase 归属筛选条件。"""
        if self.kind == WorkspaceKind.personal:
            return KnowledgeBase.owner_user_id == self.user_id
        assert self.org_id is not None
        return KnowledgeBase.owner_org_id == self.org_id

    @classmethod
    def from_knowledge_base(cls, kb: KnowledgeBase) -> "WorkspaceScope":
        """从已有资料库推导 scope（用于 update 重名校验）。"""
        if kb.owner_user_id is not None:
            return cls(
                kind=WorkspaceKind.personal,
                user_id=kb.owner_user_id,
                org_id=None,
            )
        assert kb.owner_org_id is not None
        return cls(
            kind=WorkspaceKind.organization,
            user_id=kb.owner_user_id or UUID(int=0),
            org_id=kb.owner_org_id,
        )


async def resolve_workspace(
    db: AsyncSession,
    current_user: UserPublic,
    workspace: str | None,
) -> WorkspaceScope:
    """解析 ``?workspace=`` 并校验 membership（H1 fail-closed）。"""
    if workspace is None or workspace.strip() == "":
        raise ForbiddenError("缺少工作区参数")

    value = workspace.strip()

    if value == "personal":
        return WorkspaceScope(
            kind=WorkspaceKind.personal,
            user_id=current_user.id,
            org_id=None,
        )

    try:
        org_id = UUID(value)
    except ValueError:
        raise ValidationError("无效的工作区 ID") from None

    membership = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise ForbiddenError("无权访问该工作区")

    return WorkspaceScope(
        kind=WorkspaceKind.organization,
        user_id=current_user.id,
        org_id=org_id,
    )

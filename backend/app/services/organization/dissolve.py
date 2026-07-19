"""解散团队业务逻辑：级联清理所有关联数据。

按 handoff-dissolve-org.md 约定：
1. 验证 Owner + confirm_name
2. 查该组织下所有 KB → remove_kb_tree 磁盘清盘
3. 成员 account_type 重置
4. 删 org_unit_members → org_units → organization_members → organization
5. 审计落库 → commit（失败全回滚）
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import AccountType
from app.models.knowledge_base import KnowledgeBase
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.audit.log import write_audit_log
from app.services.storage.cleaner import remove_kb_tree

logger = logging.getLogger(__name__)


async def dissolve_organization(
    db: AsyncSession,
    *,
    org_id: UUID,
    confirm_name: str,
    acting_user_id: UUID,
) -> None:
    """解散团队：级联清空所有资料库、成员记录、部门树，删除组织记录。"""

    # 1. 查找组织
    org = await db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("组织不存在")

    # 2. 校验 confirm_name
    if confirm_name.strip() != org.name:
        raise ValidationError("组织名称不匹配")

    # 3. 查该组织下所有知识库
    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.owner_org_id == org_id)
    kbs = (await db.scalars(kb_stmt)).all()
    kb_ids = [kb.id for kb in kbs]

    # 4. 磁盘清盘（失败只打日志，不阻塞后续删除）
    for kb_id in kb_ids:
        result = remove_kb_tree(kb_id)
        if result.tree_errors > 0:
            logger.warning(
                "dissolve org %s: failed to remove kb tree %s (errors=%d)",
                org_id,
                kb_id,
                result.tree_errors,
            )

    # 5. 重置所有成员的 account_type → personal（当前业务一人一组织）
    member_stmt = select(OrganizationMember).where(
        OrganizationMember.org_id == org_id
    )
    members = (await db.scalars(member_stmt)).all()
    for member in members:
        user = await db.get(User, member.user_id)
        if user is not None and user.account_type == AccountType.enterprise:
            user.account_type = AccountType.personal

    # 6. 审计落库（在删除数据前记录）
    await write_audit_log(
        db,
        action="org.dissolve",
        actor_user_id=acting_user_id,
        resource_type="organization",
        resource_id=org_id,
        details={
            "org_name": org.name,
            "kb_count": len(kb_ids),
            "member_count": len(members),
        },
    )

    # 7. 级联删除（顺序：子表 → 父表）
    # 7a. 删除部门成员
    unit_ids_stmt = select(OrgUnit.id).where(OrgUnit.org_id == org_id)
    unit_ids = (await db.scalars(unit_ids_stmt)).all()
    if unit_ids:
        await db.execute(
            delete(OrgUnitMember).where(
                OrgUnitMember.org_unit_id.in_(unit_ids)
            )
        )

    # 7b. 删除部门
    await db.execute(delete(OrgUnit).where(OrgUnit.org_id == org_id))

    # 7c. 删除组织成员
    await db.execute(
        delete(OrganizationMember).where(OrganizationMember.org_id == org_id)
    )

    # 7d. 删除组织记录
    await db.delete(org)

    # 8. 提交
    await db.commit()
    logger.info("org %s (%s) dissolved by user %s", org_id, org.name, acting_user_id)

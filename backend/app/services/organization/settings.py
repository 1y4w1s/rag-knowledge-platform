"""组织设置业务逻辑（Wave 1.3）。"""

from uuid import UUID

from app.core.exceptions import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.schemas.organization import OrganizationSettingsResponse
from app.services.organization.members import count_organization_members


async def get_organization_settings(
    db: AsyncSession,
    org_id: UUID,
) -> OrganizationSettingsResponse:
    org = await db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("团队不存在")
    member_count = await count_organization_members(db, org_id)
    return OrganizationSettingsResponse(
        id=org.id,
        name=org.name,
        created_at=org.created_at,
        member_count=member_count,
    )


async def update_organization_name(
    db: AsyncSession,
    org_id: UUID,
    name: str,
) -> OrganizationSettingsResponse:
    org = await db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("团队不存在")

    org.name = name.strip()
    await db.commit()
    await db.refresh(org)

    member_count = await count_organization_members(db, org_id)
    return OrganizationSettingsResponse(
        id=org.id,
        name=org.name,
        created_at=org.created_at,
        member_count=member_count,
    )

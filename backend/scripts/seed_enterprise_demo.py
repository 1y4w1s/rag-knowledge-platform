"""创建企业 admin + member 演示账号（同一组织，可重复执行）。

用法（项目根目录）：
  docker cp backend/scripts/seed_enterprise_demo.py zhiku-api:/tmp/seed_enterprise_demo.py
  docker compose exec api python /tmp/seed_enterprise_demo.py
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password

ORG_NAME = "知岸演示公司"
ADMIN_EMAIL = "demo-admin@example.com"
ADMIN_USERNAME = "demo_admin"
MEMBER_EMAIL = "demo-member@example.com"
MEMBER_USERNAME = "demo_member"
PASSWORD = "password123"


async def main() -> None:
    async with SessionLocal() as db:
        org = await db.scalar(select(Organization).where(Organization.name == ORG_NAME))

        admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if admin is None:
            org = Organization(id=uuid.uuid4(), name=ORG_NAME)
            db.add(org)
            admin = User(
                id=uuid.uuid4(),
                email=ADMIN_EMAIL,
                username=ADMIN_USERNAME,
                nickname="演示管理员",
                password_hash=hash_password(PASSWORD),
                account_type=AccountType.enterprise,
            )
            db.add(admin)
            db.add(
                OrganizationMember(
                    id=uuid.uuid4(),
                    org_id=org.id,
                    user_id=admin.id,
                    role=OrgRole.admin,
                    is_owner=True,
                )
            )
            print(f"Created admin: {ADMIN_EMAIL}")
        else:
            membership = await db.scalar(
                select(OrganizationMember).where(OrganizationMember.user_id == admin.id)
            )
            assert membership is not None
            if not membership.is_owner:
                membership.is_owner = True
            org = await db.get(Organization, membership.org_id)
            assert org is not None
            print(f"Admin already exists: {ADMIN_EMAIL}")

        member = await db.scalar(select(User).where(User.email == MEMBER_EMAIL))
        if member is None:
            member = User(
                id=uuid.uuid4(),
                email=MEMBER_EMAIL,
                username=MEMBER_USERNAME,
                nickname="演示成员",
                password_hash=hash_password(PASSWORD),
                account_type=AccountType.enterprise,
            )
            db.add(member)
            db.add(
                OrganizationMember(
                    id=uuid.uuid4(),
                    org_id=org.id,
                    user_id=member.id,
                    role=OrgRole.member,
                )
            )
            print(f"Created member: {MEMBER_EMAIL}")
        else:
            print(f"Member already exists: {MEMBER_EMAIL}")

        await db.commit()

    print()
    print("=== 团队演示账号（同一团队）===")
    print(f"团队名称: {ORG_NAME}")
    print(f"Admin  登录: {ADMIN_EMAIL} 或 {ADMIN_USERNAME} / {PASSWORD}")
    print(f"Member 登录: {MEMBER_EMAIL} 或 {MEMBER_USERNAME} / {PASSWORD}")
    print("前端: http://localhost:5173/login")


if __name__ == "__main__":
    asyncio.run(main())

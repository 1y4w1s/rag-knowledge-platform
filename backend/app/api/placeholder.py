"""SA-1 占位路由（Wave 1.2）。

模拟「用户 A 访问用户 B 资源 → 403」；Wave 2.1 换为真实 knowledge_bases 路由。
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, assert_resource_owner, get_current_user

router = APIRouter(prefix="/placeholder", tags=["placeholder"])


@router.get("/resources/{owner_user_id}")
async def get_placeholder_resource(
    owner_user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    assert_resource_owner(current_user, owner_user_id)
    return {
        "owner_user_id": str(owner_user_id),
        "message": "SA-1 placeholder: resource owner verified",
    }

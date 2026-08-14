"""账号设置路由（Wave 5.3）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.request_ip import get_client_ip
from app.schemas.settings import (
    AccountSettingsResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    JoinTeamRequest,
    JoinTeamResponse,
    LeaveTeamResponse,
    UpdateProfileRequest,
)
from app.services.account.settings import (
    change_password,
    get_account_settings,
    join_team_with_invite,
    leave_team,
    update_profile,
)
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/account", response_model=AccountSettingsResponse)
async def get_account(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountSettingsResponse:
    return await get_account_settings(db, current_user)


@router.patch("/account", response_model=ChangePasswordResponse)
async def patch_account_password(
    body: ChangePasswordRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChangePasswordResponse:
    return await change_password(
        db,
        current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )


@router.post("/account/join-team", response_model=JoinTeamResponse)
async def post_account_join_team(
    body: JoinTeamRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JoinTeamResponse:
    # P2-P3 加入接口防枚举：复用注册匿名流 register 桶（同 IP 10 次/小时）
    await enforce_api_rate_limit(
        ApiRateLimitKind.register, ip=get_client_ip(request),
    )
    return await join_team_with_invite(
        db,
        current_user,
        invite_code=body.invite_code,
    )


@router.post("/account/leave-team", response_model=LeaveTeamResponse)
async def post_account_leave_team(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeaveTeamResponse:
    return await leave_team(db, current_user)


@router.patch("/profile", response_model=AccountSettingsResponse)
async def patch_account_profile(
    body: UpdateProfileRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountSettingsResponse:
    return await update_profile(
        db, current_user, nickname=body.nickname, username=body.username,
    )

"""认证路由：注册 / 登录 / 当前用户（Wave 1.1 + 1.2）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    InviteValidateRequest,
    InviteValidateResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserPublic,
)
from app.services.auth.service import login_user, register_user
from app.services.auth.password_reset import (
    reset_password as execute_reset_password,
    send_password_reset_email,
)
from app.services.organization.invites import resolve_valid_invite

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    return await register_user(
        db,
        email=body.email,
        username=body.username,
        nickname=body.nickname,
        password=body.password,
        account_type=body.account_type,
        org_name=body.org_name,
        invite_code=body.invite_code,
    )


@router.post("/invites/validate", response_model=InviteValidateResponse)
async def validate_invite(
    body: InviteValidateRequest,
    db: AsyncSession = Depends(get_db),
) -> InviteValidateResponse:
    org, _invite = await resolve_valid_invite(db, body.code)
    return InviteValidateResponse(org_id=org.id, org_name=org.name)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    return await login_user(
        db,
        identifier=body.identifier,
        password=body.password,
        ip=get_client_ip(request),
    )


@router.get("/me", response_model=UserPublic)
async def me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserPublic:
    return current_user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForgotPasswordResponse:
    msg = await send_password_reset_email(
        db, identifier=body.identifier,
    )
    return ForgotPasswordResponse(message=msg)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResetPasswordResponse:
    await execute_reset_password(
        db, token=body.token, new_password=body.new_password,
    )
    return ResetPasswordResponse()

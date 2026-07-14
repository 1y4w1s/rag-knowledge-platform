"""认证相关 Pydantic 模型（Wave 1.1 + 4.2.2 username）。"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import AccountType, OrgRole
from app.services.auth.username import USERNAME_PATTERN


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    nickname: str | None = Field(default=None, max_length=64)
    password: str = Field(min_length=8)
    account_type: AccountType
    org_name: str | None = Field(default=None, max_length=255)
    invite_code: str | None = Field(default=None, max_length=64)

    @field_validator("username")
    @classmethod
    def username_format(cls, value: str) -> str:
        if not USERNAME_PATTERN.fullmatch(value.strip()):
            raise ValueError("用户名须为 3～32 位字母、数字或下划线，且以字母或数字开头")
        return value.strip()


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    nickname: str | None = None
    account_type: AccountType
    org_id: UUID | None = None
    org_role: OrgRole | None = None
    is_owner: bool = False
    primary_unit_id: UUID | None = None
    unit_ids: list[UUID] = Field(default_factory=list)
    unit_admin_unit_ids: list[UUID] = Field(default_factory=list)


class InviteValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class InviteValidateResponse(BaseModel):
    org_id: UUID
    org_name: str


class RegisterResponse(BaseModel):
    user: UserPublic


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(TokenResponse):
    user: UserPublic

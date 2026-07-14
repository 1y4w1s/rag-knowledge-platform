"""账号设置 Pydantic 模型（Wave 5.3）。"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import AccountType, OrgRole


class AccountSettingsResponse(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    nickname: str | None = None
    account_type: AccountType
    org_id: UUID | None = None
    org_role: OrgRole | None = None
    org_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ChangePasswordResponse(BaseModel):
    message: str = "密码已更新，请重新登录"


class JoinTeamRequest(BaseModel):
    invite_code: str = Field(min_length=1)


class JoinTeamResponse(BaseModel):
    message: str
    account: AccountSettingsResponse


class LeaveTeamResponse(BaseModel):
    message: str
    account: AccountSettingsResponse

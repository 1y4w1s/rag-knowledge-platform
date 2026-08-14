"""JWT 签发（Wave 1.1）；解析见 app.core.security.decode_access_token。"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.core.config import settings
from app.models.enums import AccountType, OrgRole

JWT_ALGORITHM = "HS256"


def create_access_token(
    *,
    user_id: UUID,
    account_type: AccountType,
    org_id: UUID | None = None,
    org_role: OrgRole | None = None,
    custom_role_id: UUID | None = None,
    custom_role_is_admin: bool = False,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "account_type": account_type.value,
        # P2-S2：每枚 access token 带唯一 jti，为按枚吊销提供 ID
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + timedelta(hours=settings.access_token_expire_hours),
    }
    if account_type == AccountType.enterprise:
        if org_id is None or org_role is None:
            raise ValueError("enterprise user requires org_id and org_role")
        payload["org_id"] = str(org_id)
        payload["org_role"] = org_role.value
        if custom_role_id:
            payload["custom_role_id"] = str(custom_role_id)
            payload["custom_role_is_admin"] = custom_role_is_admin

    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)

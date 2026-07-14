"""JWT 签发（Wave 1.1）；解析见 app.core.security.decode_access_token。"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app.core.config import settings
from app.models.enums import AccountType, OrgRole

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 24


def create_access_token(
    *,
    user_id: UUID,
    account_type: AccountType,
    org_id: UUID | None = None,
    org_role: OrgRole | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "account_type": account_type.value,
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_HOURS),
    }
    if account_type == AccountType.enterprise:
        if org_id is None or org_role is None:
            raise ValueError("enterprise user requires org_id and org_role")
        payload["org_id"] = str(org_id)
        payload["org_role"] = org_role.value

    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)

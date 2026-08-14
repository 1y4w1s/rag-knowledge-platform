"""P2-S2：access token 带唯一 jti；重置令牌不再与登录令牌共用密钥。"""

from __future__ import annotations

import uuid

import jwt
import pytest

from app.core.config import settings
from app.models.enums import AccountType
from app.services.auth.jwt import JWT_ALGORITHM, create_access_token
from app.services.auth.password_reset import (
    _generate_reset_token,
    _reset_token_secret,
)


def _decode(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])


def test_access_token_has_jti() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        account_type=AccountType.personal,
    )
    payload = _decode(token, settings.jwt_secret)
    assert payload["jti"]
    assert isinstance(payload["jti"], str)


def test_access_tokens_have_unique_jti() -> None:
    user_id = uuid.uuid4()
    first = _decode(
        create_access_token(user_id=user_id, account_type=AccountType.personal),
        settings.jwt_secret,
    )["jti"]
    second = _decode(
        create_access_token(user_id=user_id, account_type=AccountType.personal),
        settings.jwt_secret,
    )["jti"]
    assert first != second


def test_reset_token_uses_independent_secret() -> None:
    token = _generate_reset_token(uuid.uuid4())

    # 用登录令牌密钥必须验签失败（不再共用密钥）
    with pytest.raises(jwt.InvalidSignatureError):
        _decode(token, settings.jwt_secret)

    payload = _decode(token, _reset_token_secret())
    assert payload["type"] == "password_reset"


def test_access_token_cannot_be_verified_with_reset_secret() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        account_type=AccountType.personal,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        _decode(token, _reset_token_secret())


def test_reset_secret_differs_from_jwt_secret() -> None:
    assert _reset_token_secret() != settings.jwt_secret

"""JWT Bearer 鉴权中间件（Wave 1.2）。

除 register / login / health 及 OpenAPI 文档外，所有 ``/api/v1/*`` 须携带有效 Bearer token。
"""

from dataclasses import dataclass
from uuid import UUID

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.models.enums import AccountType, OrgRole
from app.services.auth.jwt import JWT_ALGORITHM


class AuthenticationError(Exception):
    """JWT 解析失败（供中间件转 401）。"""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    account_type: AccountType
    org_id: UUID | None = None
    org_role: OrgRole | None = None
    custom_role_id: UUID | None = None
    custom_role_is_admin: bool = False


def decode_access_token(token: str) -> TokenClaims:
    """解析并校验 access token；失败抛 AuthenticationError。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("认证已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("无效的认证凭据") from exc

    try:
        user_id = UUID(payload["sub"])
        account_type = AccountType(payload["account_type"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("无效的认证凭据") from exc

    org_id: UUID | None = None
    org_role: OrgRole | None = None
    if account_type == AccountType.enterprise:
        try:
            org_id = UUID(payload["org_id"])
            org_role = OrgRole(payload["org_role"])
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("无效的认证凭据") from exc

    custom_role_id: UUID | None = None
    custom_role_is_admin: bool = False
    if payload.get("custom_role_id"):
        try:
            custom_role_id = UUID(payload["custom_role_id"])
            custom_role_is_admin = payload.get("custom_role_is_admin", False)
        except (KeyError, ValueError):
            pass

    return TokenClaims(
        user_id=user_id,
        account_type=account_type,
        org_id=org_id,
        org_role=org_role,
        custom_role_id=custom_role_id,
        custom_role_is_admin=custom_role_is_admin,
    )


_PUBLIC_EXACT_PATHS = frozenset(
    {
        "/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/invites/validate",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


def _is_public_path(path: str) -> bool:
    if path in _PUBLIC_EXACT_PATHS:
        return True
    if path.startswith("/docs/"):
        return True
    if path.startswith("/api/v1/internal/"):
        return True
    return not path.startswith("/api/v1/")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """全局 JWT Bearer 校验：保护 ``/api/v1/*``（公开路径除外）。

    PDF / 文本预览端点（/api/v1/knowledge-bases/{uuid}/documents/{uuid}/preview）
    需要在 iframe 内嵌展示 —— iframe 跨源时拿不到 Authorization 头，
    因此额外支持从 ``?token=`` query 参数读取 JWT。
    仅对 PDF preview 路径启用该 fallback（其他端点仍要求 Bearer 头）。
    """

    _PDF_PREVIEW_RE = __import__("re").compile(
        r"^/api/v1/knowledge-bases/[^/]+/documents/[^/]+/preview$"
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        if _is_public_path(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        token: str | None = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

        if not token and self._PDF_PREVIEW_RE.match(request.url.path):
            token = request.query_params.get("token")

        if not token:
            return JSONResponse(status_code=401, content={"detail": "未提供认证凭据"})

        try:
            request.state.token_claims = decode_access_token(token)
        except AuthenticationError:
            # JWT 解码失败 → 保留 raw token，供 get_current_user 做 API Key fallback
            request.state.auth_token = token
            request.state.token_claims = None

        return await call_next(request)

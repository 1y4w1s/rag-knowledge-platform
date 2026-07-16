"""
睿阁 API 入口。

Wave 0.2：Docker 中 uvicorn 启动；提供 /health。
Wave 1.1：注册 / 登录 API。
Wave 1.2：JWT Bearer 中间件 + RBAC 依赖。
Wave 1.3：组织设置 API。
Wave 2.1：知识库 CRUD API。
Wave 2.2：文档上传 + BackgroundTasks 入库管道骨架。
Wave 2.3：结构优先切片 + pgvector 写入。
Wave 2.4：文档预览 API。
Wave 2.5：Dashboard 统计 API。
Wave 3.1：RAG 对话 SSE（检索 + DeepSeek 流式）。
Wave 3.2：对话 citations 落库 chat_messages。
Wave 3.3：无依据拒绝胡编（相关性 gate）。
Wave 4+：前端壳等。
Wave 5.3：账号设置（改密）API。
Wave 5.4：组织成员管理 API。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.internal import router as internal_router
from app.api.agent import router as agent_router
from app.api.ask import router as ask_router
from app.api.ask_threads import router as ask_threads_router
from app.api.kb_threads import router as kb_threads_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.api_keys import router as api_keys_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.kb_grants import router as kb_grants_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.metrics import router as metrics_router
from app.api.org_unit_members import router as org_unit_members_router
from app.api.org_units import router as org_units_router
from app.api.organization import router as organization_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.core.config import settings
from app.core.logging import get_trace_id, setup_logging, set_trace_id, set_user_id
import logging
from app.core.security import JWTAuthMiddleware
from app.core.exception_handlers import EXCEPTION_HANDLERS
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """基础安全头：HSTS / CSP / X-Frame-Options / X-Content-Type-Options。

    PDF / 文本预览端点（/api/v1/knowledge-bases/{uuid}/documents/{uuid}/preview）
    需要在 iframe 内嵌展示（前端 PreviewPageViewer）—— 因此跳过 X-Frame-Options。
    该端点有 JWT 鉴权，不会被未授权方访问。
    """
    _PDF_PREVIEW_RE = __import__("re").compile(
        r"^/api/v1/knowledge-bases/[^/]+/documents/[^/]+/preview$"
    )

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if not self._PDF_PREVIEW_RE.match(request.url.path):
            response.headers["X-Frame-Options"] = "DENY"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app = FastAPI(
    title="睿阁 API",
    version="0.12.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

setup_logging()

logger = logging.getLogger(__name__)


def _check_production_guard() -> None:
    """生产环境安全守卫：拒绝使用默认密钥或缺少关键配置时启动。"""
    if settings.jwt_secret in ("replace-with-a-long-random-string", "changeme"):
        raise RuntimeError(
            "❌ JWT_SECRET 为默认值，请修改为长随机字符串后重新启动。"
            "\n   生产环境建议：openssl rand -hex 32"
        )
    if len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "❌ JWT_SECRET 长度不足 32 字符，请使用更长的密钥。"
            "\n   生产环境建议：openssl rand -hex 32"
        )
    if not settings.deepseek_api_key:
        logger.warning("⚠️  DEEPSEEK_API_KEY 未配置，LLM 对话功能不可用。")
    if not settings.tongyi_api_key and settings.embedding_provider == "tongyi":
        logger.warning("⚠️  TONGYI_API_KEY 未配置，嵌入/rerank 功能不可用。")
    logger.info("✅ 安全守卫检查通过，环境=%s", settings.environment)


_check_production_guard()


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 trace_id，解析用户 ID（如已认证）。"""

    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
        set_trace_id(trace_id)
        # 如果已认证，记录 user_id
        if hasattr(request.state, "user_id"):
            set_user_id(str(request.state.user_id))
        response = await call_next(request)
        response.headers["X-Trace-ID"] = get_trace_id()
        return response

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TraceIdMiddleware)
app.add_middleware(JWTAuthMiddleware)

for exc_cls, handler in EXCEPTION_HANDLERS:
    app.add_exception_handler(exc_cls, handler)

app.include_router(metrics_router)
app.include_router(health_router)
app.include_router(internal_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")
app.include_router(org_units_router, prefix="/api/v1")
app.include_router(org_unit_members_router, prefix="/api/v1")
app.include_router(knowledge_bases_router, prefix="/api/v1")
app.include_router(kb_grants_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(kb_threads_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(ask_threads_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")

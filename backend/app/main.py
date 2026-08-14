"""
索隐 API 入口。

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
from app.api.kb_inventory import router as kb_inventory_router
from app.api.batch import router as batch_router
from app.api.api_keys import router as api_keys_router
from app.api.backfill import router as backfill_router
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
from app.api.roles import router as roles_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.versions import router as versions_router
from app.api.webhooks import router as webhooks_router
from app.api.evaluations import router as evaluations_router
from app.core.config import settings
from app.core.logging import setup_logging, set_trace_id, set_user_id
from app.core.otel import _TraceIdSyncMiddleware, setup_otel
import logging
from app.core.security import JWTAuthMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.core.exception_handlers import EXCEPTION_HANDLERS
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


MAX_BODY_BYTES = 10 * 1024 * 1024  # 10MB


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """限制请求体大小（防止内存 DOS）；跳过上传端点（由 upload.py 文件级校验）。"""
    _SKIP_PATHS = frozenset({
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/reset-password",
    })

    async def dispatch(self, request, call_next):
        path = request.url.path
        # 公开认证路径可能无 Content-Length 但仍需放行
        if path in self._SKIP_PATHS:
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"请求体过大，上限 {MAX_BODY_BYTES // (1024*1024)}MB"},
                    )
            except (ValueError, TypeError):
                pass
        # upload 端点在 UploadFile 层由 upload.py 的 _read_upload_with_size_limit 校验
        return await call_next(request)


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
    title="索隐 API",
    version="0.12.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)

setup_logging()
setup_otel(app)

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def prewarm_models():
    """预加载 BGE 模型，避免首次请求等待 30s 模型加载。"""
    try:
        if settings.embedding_provider == "bge":
            from app.services.ingestion.embedder import _embed_bge
            logger.info("预热 BGE 嵌入模型...")
            await _embed_bge(["ping"])
            logger.info("BGE 嵌入模型预热完成")
    except Exception as e:
        logger.warning("BGE 模型预热失败（不影响启动）: %s", e)


@app.on_event("startup")
async def sweep_stale_agent_runs_on_startup():
    """B2（P1-03/P0-01）：启动时一次性清扫 crash 残留 running run / 过期审批。

    内部 try/except 吞错，失败不阻断启动；beat 周期任务在运行态继续兜底。
    """
    from app.services.agent.sweeper import run_agent_sweep_startup

    await run_agent_sweep_startup()


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
    if settings.environment == "production":
        from sqlalchemy.engine import make_url

        if make_url(settings.database_url).password == "changeme":
            raise RuntimeError(
                "❌ DATABASE_URL 仍在使用默认密码 changeme，请改为强随机密码后重新启动。"
                "\n   生产环境建议：openssl rand -hex 32"
            )
        webhook_key = settings.webhook_encryption_secret
        if (
            not webhook_key
            or webhook_key in ("replace-with-a-long-random-string", "changeme")
            or len(webhook_key) < 32
            or webhook_key == settings.jwt_secret
        ):
            raise RuntimeError(
                "❌ WEBHOOK_ENCRYPTION_SECRET 未配置、为默认值或与 JWT_SECRET 相同，"
                "请配置独立的 32+ 字符随机密钥后重新启动。"
                "\n   生产环境建议：openssl rand -hex 32"
            )
    from app.services.rag.chat_llm import active_chat_api_key_configured, resolve_chat_provider

    if not active_chat_api_key_configured():
        provider = resolve_chat_provider()
        if provider == "tongyi":
            logger.warning(
                "⚠️  CHAT_PROVIDER=tongyi 但 TONGYI_API_KEY 未配置，LLM 对话功能不可用。"
            )
        else:
            logger.warning("⚠️  DEEPSEEK_API_KEY 未配置，LLM 对话功能不可用。")
    if not settings.tongyi_api_key and settings.embedding_provider == "tongyi":
        logger.warning("⚠️  TONGYI_API_KEY 未配置，嵌入/rerank 功能不可用。")
    try:
        from app.services.ingestion.ocr import has_ocr_python_deps, is_ocr_enabled

        if is_ocr_enabled() and not has_ocr_python_deps():
            logger.warning(
                "OCR_ENABLED=1 但未安装 PaddleOCR/pdf2image："
                "扫描件入库将 failed（reason=ocr_deps_missing）。"
                "可装 requirements-ocr.txt，或设 OCR_ENABLED=0。"
            )
    except Exception:
        logger.debug("OCR 启动探测跳过", exc_info=True)
    logger.info("✅ 安全守卫检查通过，环境=%s", settings.environment)


_check_production_guard()


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 trace_id 上下文，解析用户 ID（如已认证）。

    响应头 X-Trace-ID 由最外层 _TraceIdSyncMiddleware（otel.py）统一回写。
    """

    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
        set_trace_id(trace_id)
        # 如果已认证，记录 user_id
        if hasattr(request.state, "user_id"):
            set_user_id(str(request.state.user_id))
        response = await call_next(request)
        return response

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-ID", "X-Request-ID"],
)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TraceIdMiddleware)
app.add_middleware(JWTAuthMiddleware)
# 最后注册 → 中间件栈最外层：保证任何响应（含 401/4xx/5xx）都回写 X-Trace-ID 头（P1-30）
app.add_middleware(_TraceIdSyncMiddleware)

for exc_cls, handler in EXCEPTION_HANDLERS:
    app.add_exception_handler(exc_cls, handler)

app.include_router(metrics_router)
app.include_router(health_router)
app.include_router(internal_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(kb_inventory_router, prefix="/api/v1")
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
app.include_router(roles_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(backfill_router, prefix="/api/v1")
app.include_router(batch_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(versions_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(evaluations_router)

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
from app.api.health import router as health_router
from app.api.kb_grants import router as kb_grants_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.org_unit_members import router as org_unit_members_router
from app.api.org_units import router as org_units_router
from app.api.organization import router as organization_router
from app.api.placeholder import router as placeholder_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.core.config import settings
from app.core.security import JWTAuthMiddleware
from app.core.exception_handlers import EXCEPTION_HANDLERS

app = FastAPI(title="睿阁 API", version="0.12.0")

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)

for exc_cls, handler in EXCEPTION_HANDLERS:
    app.add_exception_handler(exc_cls, handler)

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
app.include_router(chat_router, prefix="/api/v1")
app.include_router(kb_threads_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(ask_threads_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(placeholder_router, prefix="/api/v1")

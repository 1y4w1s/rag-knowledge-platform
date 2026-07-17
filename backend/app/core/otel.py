"""OpenTelemetry 初始化 — 导出到 Tempo。"""
from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import set_trace_id

logger = logging.getLogger(__name__)

# 全局 Tracer
tracer: trace.Tracer | None = None


def setup_otel(app) -> None:
    """初始化 OpenTelemetry：Provider → Exporter → Instrumentations → Middleware。"""
    global tracer

    if not settings.otlp_endpoint:
        logger.info("OTel 未配置（otlp_endpoint 为空），跳过链路追踪")
        return

    try:
        resource = Resource.create({
            "service.name": settings.loki_service_name,
            "service.version": "1.0.0",
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{settings.otlp_endpoint}/v1/traces")
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer(__name__)

        # FastAPI 自动 instrumentation（捕获所有路由）
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

        # httpx 调用追踪（LLM / Embedding API）
        HTTPXClientInstrumentor().instrument()

        # 注册 Trace ID 对齐中间件（最外层，包裹所有请求）
        app.add_middleware(_TraceIdSyncMiddleware)

        logger.info("OTel 链路追踪已启用: endpoint=%s", settings.otlp_endpoint)

    except Exception as exc:
        logger.warning("OTel 初始化失败（不影响服务运行）: %s", exc)


def get_tracer() -> trace.Tracer:
    """获取全局 Tracer。未初始化时返回 NoopTracer。"""
    if tracer is not None:
        return tracer
    return trace.get_tracer(__name__)


class _TraceIdSyncMiddleware(BaseHTTPMiddleware):
    """将 OTel SpanContext.trace_id 同步到日志 ContextVar，实现日志 ↔ 链路关联。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        span = trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            # OTel trace_id 是 128 位整数 → 取后 16 位 hex 与日志对齐
            trace_id_hex = format(span_context.trace_id, "032x")[:16]
            set_trace_id(trace_id_hex)
        return await call_next(request)

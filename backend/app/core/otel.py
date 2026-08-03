"""OpenTelemetry 初始化 — 导出到 Tempo。"""
from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import sanitize_trace_id, set_trace_id

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

        logger.info("OTel 链路追踪已启用: endpoint=%s", settings.otlp_endpoint)

    except Exception as exc:
        logger.warning("OTel 初始化失败（不影响服务运行）: %s", exc)


def get_tracer() -> trace.Tracer:
    """获取全局 Tracer。未初始化时返回 NoopTracer。"""
    if tracer is not None:
        return tracer
    return trace.get_tracer(__name__)


class _TraceIdSyncMiddleware:
    """统一 trace_id 来源（P1-30）：优先取 X-Trace-ID 头，其次回退 OTel span。

    实现为纯 ASGI 中间件（最外层）：通过包装 send 在 http.response.start 阶段
    注入 X-Trace-ID 头——包括中间件早返回的 401、以及 ServerErrorMiddleware 发送的
    500 响应（其发送后必然 re-raise，BaseHTTPMiddleware 拿不到 response）。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"x-trace-id") or headers.get(b"x-request-id")
        trace_id = raw.decode("latin-1") if raw else None
        if not trace_id:
            span = trace.get_current_span()
            span_context = span.get_span_context()
            if span_context.is_valid:
                # OTel trace_id 是 128 位整数 → 取后 16 位 hex 与日志对齐
                trace_id = format(span_context.trace_id, "032x")[:16]
        tid = sanitize_trace_id(trace_id)
        set_trace_id(tid)

        async def send_with_trace(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-trace-id", tid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_trace)

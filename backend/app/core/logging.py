"""结构化日志 — trace_id 注入 + JSON 格式化。

用法：
  1. 在 main.py 中调用 setup_logging()
  2. 在 FastAPI 中间件中调用 set_trace_id()
  3. 其他模块用 logging.getLogger(__name__) 正常打日志，trace_id 自动附加

输出格式（示例）：
  {"time":"2026-07-15T12:00:00","level":"INFO","logger":"app.services.rag.chat",
   "trace_id":"abc123","user_id":"uuid","message":"检索完成","chunks":5}
"""

from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar

_current_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_current_user_id: ContextVar[str] = ContextVar("user_id", default="")


def set_trace_id(trace_id: str | None = None) -> str:
    """为当前请求设置 trace_id。未传入时自动生成。"""
    tid = trace_id or uuid.uuid4().hex[:16]
    _current_trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _current_trace_id.get()


def set_user_id(uid: str) -> None:
    _current_user_id.set(uid)


def get_user_id() -> str:
    return _current_user_id.get()


class _StructuredFormatter(logging.Formatter):
    """输出 JSON 行格式的结构化日志。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace_id = _current_trace_id.get()
        if trace_id:
            payload["trace_id"] = trace_id
        user_id = _current_user_id.get()
        if user_id:
            payload["user_id"] = user_id
        if record.exc_info and record.exc_info[0]:
            payload["exception"] = self.formatException(record.exc_info)
        # 附加 extra 字段（如 logger.info("msg", extra={"chunks": 5})）
        for key, value in record.__dict__.items():
            if key not in ("args", "asctime", "created", "exc_info", "exc_text",
                          "filename", "funcName", "levelname", "levelno", "lineno",
                          "message", "module", "msecs", "msg", "name", "pathname",
                          "process", "processName", "relativeCreated", "stack_info",
                          "thread", "threadName"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """替换根 logger 的 handler 为结构化 JSON 格式。"""
    handler = logging.StreamHandler()
    handler.setFormatter(_StructuredFormatter())
    root = logging.getLogger()
    # 移除默认 handler，添加结构化 handler
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # 第三方库保持 WARNING 级别
    for lib in ("httpx", "urllib3", "alembic", "sqlalchemy"):
        logging.getLogger(lib).setLevel(logging.WARNING)

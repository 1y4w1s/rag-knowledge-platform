"""重试工具：指数退避 + jitter + 简易熔断器（Plan-3E / 韧性架构）。

提供两类重试策略：
1. `async_retry` — 装饰器风格，适用于简单异步函数
2. `CircuitBreaker` — 简易熔断器，防止雪崩
3. `stream_retry` — 流式重连包装器，适用于 SSE/SSE-like 流
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

R = TypeVar("R")

# ── 重试策略 ──────────────────────────────────────────────────────────


def should_retry(exception: Exception) -> bool:
    """判断异常是否可重试。

    可重试：网络超时、连接重置、服务不可用（5xx）。
    不可重试：客户端错误（4xx，除 429）、认证失败、格式错误。
    """
    exc_str = str(exception).lower()

    # 4xx 中，只有 429 (Too Many Requests) 可重试
    if "429" in exc_str or "too many requests" in exc_str:
        return True
    if "4" in exc_str[:2] and any(code in exc_str for code in ["400", "401", "403", "404", "422"]):
        return False

    # 5xx / 网络级错误 — 可重试
    retryable_hints = [
        "timeout",
        "connection reset",
        "connection refused",
        "connection error",
        "5",  # 502, 503, 504
        "internal server error",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "remote end closed",
        "broken",
        "eof",
        "disconnect",
    ]
    return any(hint in exc_str for hint in retryable_hints)


async def async_retry(
    func: Callable[..., Awaitable[R]],
    *args: object,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.1,
    breaker_name: str | None = None,
    **kwargs: object,
) -> R:
    """指数退避 + jitter 重试包装器。

    Args:
        func: 异步可重入函数。
        max_retries: 最大重试次数（不含首次尝试），默认 3。
        base_delay: 首次退避基准秒数，默认 1s。
        max_delay: 退避上限秒数，默认 30s。
        jitter_factor: jitter 比例（±jitter_factor * delay），默认 0.1。
        breaker_name: 熔断器名称（可选）。指定后，成功/耗尽时自动记录。
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if breaker_name is not None:
                get_breaker(breaker_name).record_success()
            return result
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not should_retry(exc):
                if breaker_name is not None:
                    get_breaker(breaker_name).record_failure()
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(-delay * jitter_factor, delay * jitter_factor)
            actual_delay = max(0.0, delay + jitter)
            logger.warning(
                "重试 %s (attempt %d/%d): %s — 等待 %.1fs",
                getattr(func, "__name__", str(func)),
                attempt + 1,
                max_retries,
                exc,
                actual_delay,
            )
            await asyncio.sleep(actual_delay)

    # 仅当 last_exc is not None 时执行
    if last_exc is not None:
        if breaker_name is not None:
            get_breaker(breaker_name).record_failure()
        raise last_exc
    raise RuntimeError("unreachable: async_retry completed without result or exception")


# ── 流式重连 ──────────────────────────────────────────────────────────


class _StreamInterrupted(Exception):
    """流式连接中断，需重连的信号。"""
    pass


async def retry_stream(
    stream_factory: Callable[[], AsyncIterator[str]],
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    breaker_name: str | None = None,
) -> AsyncIterator[str]:
    """流式重连包装器：连接中断时自动重连。

    适用于 LLM streaming 等 SSE 场景。
    一旦首次 yield 成功，最多重连 max_retries 次。

    Args:
        stream_factory: 创建新流的生产函数（每次重连重新调用）。
        max_retries: 最大重连次数。
        base_delay: 首次退避基准秒数。
        max_delay: 退避上限秒数。
    """
    last_exc: Exception | None = None
    ever_yielded = False
    for attempt in range(max_retries + 1):
        try:
            stream = stream_factory()
            async for token in stream:
                ever_yielded = True
                yield token
            # 正常完成
            if breaker_name is not None:
                get_breaker(breaker_name).record_success()
            return
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not should_retry(exc):
                # 从未成功 yield 过 → 记录熔断器失败
                if not ever_yielded and breaker_name is not None:
                    get_breaker(breaker_name).record_failure()
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(-delay * 0.1, delay * 0.1)
            actual_delay = max(0.0, delay + jitter)
            logger.warning(
                "流式重连 (attempt %d/%d): %s — 等待 %.1fs",
                attempt + 1,
                max_retries,
                exc,
                actual_delay,
            )
            await asyncio.sleep(actual_delay)

    if last_exc is not None:
        if not ever_yielded and breaker_name is not None:
            get_breaker(breaker_name).record_failure()
        raise last_exc
    raise RuntimeError("unreachable: retry_stream completed without result or exception")


# ── 简易熔断器 ─────────────────────────────────────────────────────────


class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """简易熔断器：连续失败超过阈值后打开，阻止后续调用，定时半开探活。

    使用方式：
        breaker = CircuitBreaker("tongyi_rerank")
        async with breaker as cb:
            if cb.allow:
                result = await call_api()
            else:
                result = await fallback()
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_attempts: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_attempts = half_open_max_attempts

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        if self._state == CircuitBreakerState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_attempts = 0
        return self._state

    @property
    def allow_request(self) -> bool:
        st = self.state
        if st == CircuitBreakerState.CLOSED:
            return True
        if st == CircuitBreakerState.HALF_OPEN:
            return self._half_open_attempts < self.half_open_max_attempts
        return False

    def record_success(self) -> None:
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0
        if old_state != CircuitBreakerState.CLOSED:
            logger.info(
                '{"event_type":"circuit_breaker_state_change","breaker":"%s",'
                '"from_state":"%s","to_state":"%s","failures":0}',
                self.name, old_state, self._state,
            )

    def record_failure(self) -> None:
        old_state = self._state
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._half_open_attempts += 1
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            logger.warning(
                '{"event_type":"circuit_breaker_state_change","breaker":"%s",'
                '"from_state":"%s","to_state":"%s","failures":%d}',
                self.name, old_state, self._state, self._failure_count,
            )

    def status(self) -> dict:
        """返回熔断器当前状态快照（public API，替代直接读 _state / _failure_count）。"""
        return {
            "state": self._state,
            "failures": self._failure_count,
        }

    def reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker({self.name}, state={self._state}, "
            f"failures={self._failure_count})"
        )


# ── 全局熔断器注册表（可按服务名访问） ────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(
    name: str,
    failure_threshold: int | None = None,
    recovery_timeout: float | None = None,
) -> CircuitBreaker:
    if name in _breakers:
        return _breakers[name]
    kw: dict[str, object] = {}
    if failure_threshold is not None:
        kw["failure_threshold"] = failure_threshold
    if recovery_timeout is not None:
        kw["recovery_timeout"] = recovery_timeout
    _breakers[name] = CircuitBreaker(name, **kw)  # type: ignore[arg-type]
    return _breakers[name]


def reset_all_breakers() -> None:
    for breaker in _breakers.values():
        breaker.reset()

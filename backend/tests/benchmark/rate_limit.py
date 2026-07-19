"""限流包装器：bypass（临时提额）/ enforce（模拟真实限流）双模式。

bypass 模式：临时调高/移除限流阈值，评测快速跑完。
enforce 模式：按生产限流配置运行，验证 429 正确处理。

环境变量 RAG_RATE_LIMIT_MODE=bypass|enforce
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum
from uuid import UUID

logger = logging.getLogger(__name__)


class RateLimitMode(str, Enum):
    """限流模式。"""
    bypass = "bypass"      # 临时提额，快速评测
    enforce = "enforce"    # 模拟真实限流


# 评测用提额（比生产高很多，但非无限，防止意外耗尽）
BYPASS_CHAT_MAX = 10_000       # 生产 30
BYPASS_UPLOAD_MAX = 10_000     # 生产 20
BYPASS_SEARCH_MAX = 10_000     # 生产 60
BYPASS_WINDOW = 3600

# 生产限流（与 backend/app/services/auth/api_rate_limit.py 对齐）
ENFORCE_CHAT_MAX = 30
ENFORCE_UPLOAD_MAX = 20
ENFORCE_SEARCH_MAX = 60
ENFORCE_WINDOW = 3600

# 降级弹性因子（与生产保持一致）
DEGRADATION_FACTORS = {0: 1.0, 1: 0.5, 2: 0.3}


class SlidingWindowCounter:
    """滑动窗口计数器（线程安全，与生产限流一致实现）。"""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def allow(self) -> tuple[bool, int]:
        """检查是否允许请求。返回 (allowed, remaining_in_window)。"""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        async with self._lock:
            # 清理过期时间戳
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_requests:
                wait = self._timestamps[0] + self.window_seconds - now
                return False, max(0, self.max_requests - len(self._timestamps))
            self._timestamps.append(now)
            remaining = self.max_requests - len(self._timestamps)
            return True, remaining

    async def wait_if_needed(self) -> float:
        """如果需要，等待直到有配额。返回等待秒数。"""
        allowed, _ = await self.allow()
        if allowed:
            return 0.0
        # 等待一个窗口长度
        await asyncio.sleep(self.window_seconds)
        return self.window_seconds


class RateLimitWrapper:
    """限流包装器——统一管理评测过程中的 API 调用限流。

    用法：
        rl = RateLimitWrapper()
        async with rl.chat(user_id):   # 会在限流下自动等待
            await call_chat_api(...)
        async with rl.search(user_id):
            await call_search_api(...)

        或低层级：
        await rl.wait_for_chat(user_id)
        await call_chat_api(...)
    """

    def __init__(self, mode: RateLimitMode | None = None) -> None:
        if mode is None:
            mode_str = os.environ.get("RAG_RATE_LIMIT_MODE", "bypass")
            self.mode = RateLimitMode(mode_str)
        else:
            self.mode = mode

        self._chat_counters: dict[UUID, SlidingWindowCounter] = {}
        self._upload_counters: dict[UUID, SlidingWindowCounter] = {}
        self._search_counters: dict[UUID, SlidingWindowCounter] = {}
        self.total_waited: float = 0.0  # 累计等待时间

        if self.mode == RateLimitMode.bypass:
            logger.info("限流模式: BYPASS（提额 ×300+）")
        else:
            logger.info("限流模式: ENFORCE（生产配置）")

    @property
    def _chat_limits(self) -> tuple[int, int]:
        max_r, window = (BYPASS_CHAT_MAX, BYPASS_WINDOW) if self.mode == RateLimitMode.bypass else (ENFORCE_CHAT_MAX, ENFORCE_WINDOW)
        return max_r, window

    @property
    def _upload_limits(self) -> tuple[int, int]:
        max_r, window = (BYPASS_UPLOAD_MAX, BYPASS_WINDOW) if self.mode == RateLimitMode.bypass else (ENFORCE_UPLOAD_MAX, ENFORCE_WINDOW)
        return max_r, window

    @property
    def _search_limits(self) -> tuple[int, int]:
        max_r, window = (BYPASS_SEARCH_MAX, BYPASS_WINDOW) if self.mode == RateLimitMode.bypass else (ENFORCE_SEARCH_MAX, ENFORCE_WINDOW)
        return max_r, window

    def _get_counter(
        self,
        counters: dict[UUID, SlidingWindowCounter],
        user_id: UUID,
        max_r: int,
        window: int,
    ) -> SlidingWindowCounter:
        if user_id not in counters:
            counters[user_id] = SlidingWindowCounter(max_r, window)
        return counters[user_id]

    async def wait_for_chat(self, user_id: UUID) -> float:
        """等待 chat 限流通话。返回等待秒数。"""
        max_r, window = self._chat_limits
        c = self._get_counter(self._chat_counters, user_id, max_r, window)
        waited = await c.wait_if_needed()
        self.total_waited += waited
        return waited

    async def wait_for_upload(self, user_id: UUID) -> float:
        max_r, window = self._upload_limits
        c = self._get_counter(self._upload_counters, user_id, max_r, window)
        waited = await c.wait_if_needed()
        self.total_waited += waited
        return waited

    async def wait_for_search(self, user_id: UUID) -> float:
        max_r, window = self._search_limits
        c = self._get_counter(self._search_counters, user_id, max_r, window)
        waited = await c.wait_if_needed()
        self.total_waited += waited
        return waited

    # —— 上下文管理器 ——

    class _Limiter:
        def __init__(self, wrapper: "RateLimitWrapper", kind: str, user_id: UUID) -> None:
            self._wrapper = wrapper
            self._kind = kind
            self._user_id = user_id

        async def __aenter__(self) -> "RateLimitWrapper._Limiter":
            if self._kind == "chat":
                await self._wrapper.wait_for_chat(self._user_id)
            elif self._kind == "upload":
                await self._wrapper.wait_for_upload(self._user_id)
            elif self._kind == "search":
                await self._wrapper.wait_for_search(self._user_id)
            return self

        async def __aexit__(self, *args) -> None:
            pass

    def chat(self, user_id: UUID) -> "_Limiter":
        return self._Limiter(self, "chat", user_id)

    def upload(self, user_id: UUID) -> "_Limiter":
        return self._Limiter(self, "upload", user_id)

    def search(self, user_id: UUID) -> "_Limiter":
        return self._Limiter(self, "search", user_id)

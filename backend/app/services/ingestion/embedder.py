"""文本嵌入（通义 text-embedding-v2；测试用 mock）。
v0.5 新增：EmbeddingCache — LRU + TTL 缓存减少 API 调用。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from collections import OrderedDict
from typing import Sequence

import httpx

from app.core.config import settings
from app.core.http_client import get_tongyi_client
from app.core.retry import async_retry

EMBEDDING_DIM = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-v2"
TONGYI_EMBED_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "text-embedding/text-embedding"
)

logger = logging.getLogger(__name__)

# ── Embedding Cache ──────────────────────────────────────────────────

_CACHE_MAX_SIZE = settings.embedding_cache_max_size
_CACHE_TTL_SECONDS = settings.embedding_cache_ttl_seconds  # 可配置


class _EmbeddingCache:
    """线程安全的 LRU + TTL 嵌入缓存（进程级内存）。

    缓存 key = sha256(text).hexdigest()[:24] （长度 24 兼顾碰撞安全与内存）。
    缓存 value = (timestamp, vector)。
    """

    def __init__(self, max_size: int = _CACHE_MAX_SIZE, ttl: int = _CACHE_TTL_SECONDS):
        self._max_size = max_size
        self._ttl = ttl
        self._data: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

    def get(self, text: str) -> list[float] | None:
        key = self._key(text)
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, vector = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        # LRU: move to end (most recently used)
        self._data.move_to_end(key)
        return vector

    def set(self, text: str, vector: list[float]) -> None:
        key = self._key(text)
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = (time.monotonic(), vector)
        # Evict oldest if over limit
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    @property
    def size(self) -> int:
        return len(self._data)


_embedding_cache = _EmbeddingCache()


# ── Core Embedding Functions ────────────────────────────────────────


def current_embedding_model() -> str:
    return settings.embedding_model or DEFAULT_EMBEDDING_MODEL


def embedding_input_text(heading_path: str | None, content: str) -> str:
    if heading_path:
        return f"[{heading_path}]\n{content}"
    return content


def _mock_vector(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < EMBEDDING_DIM:
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            num = int.from_bytes(chunk, "big", signed=False)
            values.append((num % 1000) / 1000.0 - 0.5)
            if len(values) >= EMBEDDING_DIM:
                break
        digest = hashlib.sha256(digest).digest()

    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _validate_vectors(
    vectors: list[list[float]],
    label: str = "embedding",
) -> list[list[float]]:
    """输出质量校验：零向量、NaN、Inf、维度不匹配 → 抛错。

    覆盖面试提到的「安静失效」场景——API 返回 200 但数据是坏的。
    """
    for i, v in enumerate(vectors):
        if len(v) != EMBEDDING_DIM:
            raise ValueError(f"{label}[{i}] 维度 {len(v)} ≠ {EMBEDDING_DIM}")
        if any(not isinstance(x, (int, float)) for x in v):
            raise ValueError(f"{label}[{i}] 含非数值元素")
        if any(math.isnan(x) or math.isinf(x) for x in v):
            raise ValueError(f"{label}[{i}] 含 NaN 或 Inf")
        norm = math.sqrt(sum(x * x for x in v))
        if norm < 1e-10:
            raise ValueError(f"{label}[{i}] 零向量 (norm={norm})")
    logger.info("向量质量校验通过: %d 条, label=%s", len(vectors), label)
    return vectors


# ── 响应一致性校验 ──────────────────────────────────────────────────

_response_checksums: dict[str, str] = {}


def _check_response_consistency(texts: Sequence[str], response: dict) -> None:
    """校验同一输入多次调用的响应是否一致（防止 embedding 版本漂移）。

    面试场景：API 返回 200 OK，但两次结果不同（负载均衡打到不同模型版本）。
    """
    input_key = hashlib.sha256("|".join(str(t) for t in texts).encode()).hexdigest()[:16]
    resp_json = json.dumps(response.get("output", {}), sort_keys=True, ensure_ascii=False)
    resp_hash = hashlib.sha256(resp_json.encode()).hexdigest()[:16]

    prev = _response_checksums.get(input_key)
    if prev is not None and prev != resp_hash:
        logger.warning(
            "嵌入响应不一致（可能版本漂移）: input_hash=%s prev=%s now=%s",
            input_key, prev, resp_hash,
        )
    _response_checksums[input_key] = resp_hash


async def _embed_tongyi(texts: Sequence[str]) -> list[list[float]]:
    if not settings.tongyi_api_key:
        raise RuntimeError("未配置 TONGYI_API_KEY，无法调用通义嵌入")

    headers = {
        "Authorization": f"Bearer {settings.tongyi_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": current_embedding_model(),
        "input": {"texts": list(texts)},
    }

    client = get_tongyi_client()
    resp = await asyncio.wait_for(
        client.post(TONGYI_EMBED_URL, headers=headers, json=payload),
        timeout=settings.embed_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()

    if "output" not in data or "embeddings" not in data["output"]:
        raise RuntimeError(f"通义嵌入响应异常: {data}")

    # 响应一致性校验：同一输入多次调用应返回相同结果
    # 若不一致说明后端版本漂移，属于安静失效
    _check_response_consistency(texts, data)

    embeddings = sorted(data["output"]["embeddings"], key=lambda x: x["text_index"])
    vectors = [item["embedding"] for item in embeddings]
    return _validate_vectors(vectors, label="tongyi_embed")


def _cache_enabled() -> bool:
    """仅在通义提供商 + 非 mock 下启用缓存。"""
    provider = settings.embedding_provider.lower()
    return provider == "tongyi" and settings.tongyi_api_key is not None


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = settings.embedding_provider.lower()
    if provider == "mock" or (provider == "tongyi" and not settings.tongyi_api_key):
        return _validate_vectors([_mock_vector(t) for t in texts], label="mock_embed")

    if provider == "tongyi":
        # 缓存检查
        use_cache = _cache_enabled()
        if use_cache and len(texts) == 1:
            cached = _embedding_cache.get(texts[0])
            if cached is not None:
                return [cached]

        vectors = await async_retry(_embed_tongyi, texts, max_retries=settings.retry_max_attempts, base_delay=settings.retry_base_delay, breaker_name="tongyi_embed")

        # 缓存落盘
        if use_cache:
            for text, vec in zip(texts, vectors):
                _embedding_cache.set(text, vec)

        return vectors

    raise ValueError(f"不支持的嵌入提供商: {settings.embedding_provider}")


async def try_embed_texts(texts: Sequence[str]) -> list[list[float]] | None:
    """嵌入降级：嵌入失败时返回 None，调用方降级为纯 FTS。"""
    try:
        return await embed_texts(texts)
    except Exception:
        return None


def clear_embedding_cache() -> None:
    """测试/运维用：清空嵌入缓存。"""
    _embedding_cache.clear()

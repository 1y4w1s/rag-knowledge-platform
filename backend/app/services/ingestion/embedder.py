"""文本嵌入（通义 text-embedding-v2；测试用 mock）。
v0.5 新增：EmbeddingCache — LRU + TTL 缓存减少 API 调用。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import threading
import time
from collections import OrderedDict
from typing import Sequence

import httpx  # noqa: F401  # 测试经 embedder.httpx 打补丁注入 5xx，勿删

from app.core.config import settings
from app.core.http_client import get_tongyi_client
from app.core.retry import async_retry

def _get_embedding_dim() -> int:
    """读取当前 settings 中的向量维度。"""
    return settings.embedding_dim


EMBEDDING_DIM = _get_embedding_dim()
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


DEFAULT_BGE_EN_MODEL = "BAAI/bge-small-en-v1.5"


def current_bge_en_model() -> str:
    """EN 嵌入模型单一常量点：换模型只改这里（P1-11 方案 B）。"""
    return settings.bge_en_model or DEFAULT_BGE_EN_MODEL


def embedding_input_text(heading_path: str | None, content: str) -> str:
    if heading_path:
        return f"[{heading_path}]\n{content}"
    return content


def _mock_vector(text: str, dim: int | None = None) -> list[float]:
    """Mock 嵌入唯一实现（SSOT，N15 统一口径）：字符 2/3-gram 词袋。

    相同 n-gram 的文本产生相似向量，语义性质接近真实嵌入，
    保证 mock 模式下检索链路验证结果与真实嵌入口径可比。
    此前 SHA-256 伪随机实现让相似文本向量正交，mock 下向量召回失效、
    仅剩 FTS 词面匹配（GQ-67/99 等换词题 0 分根因之一）。
    全仓 mock 嵌入（生产 mock 模式 + 各 golden 测试）必须引用本函数，
    禁止另起实现。
    """
    target_dim = dim or _get_embedding_dim()
    vec = [0.0] * target_dim
    cleaned = text.lower().strip()
    for n in (2, 3):
        for i in range(len(cleaned) - n + 1):
            token = cleaned[i : i + n]
            digest = hashlib.md5(token.encode("utf-8")).digest()
            pos = int.from_bytes(digest[:4], "big", signed=False) % target_dim
            vec[pos] += 1.0

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _validate_vectors(
    vectors: list[list[float]],
    label: str = "embedding",
    expected_dim: int | None = None,
) -> list[list[float]]:
    """输出质量校验：零向量、NaN、Inf、维度不匹配 → 抛错。

    覆盖面试提到的「安静失效」场景——API 返回 200 但数据是坏的。
    """
    exp_dim = expected_dim or _get_embedding_dim()
    for i, v in enumerate(vectors):
        if len(v) != exp_dim:
            raise ValueError(f"{label}[{i}] 维度 {len(v)} ≠ {exp_dim}")
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

# 一致性校验只需保留近期输入，避免 worker 长期运行内存只增不减（P2-I4）
_RESPONSE_CHECKSUM_MAX_SIZE = _CACHE_MAX_SIZE
_response_checksums: OrderedDict[str, str] = OrderedDict()


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
    # LRU：命中/新写都移到末尾，超限淘汰最久未用
    _response_checksums.move_to_end(input_key)
    if len(_response_checksums) > _RESPONSE_CHECKSUM_MAX_SIZE:
        _response_checksums.popitem(last=False)


async def _embed_tongyi(texts: Sequence[str]) -> list[list[float]]:
    if not settings.tongyi_api_key:
        raise RuntimeError("未配置 TONGYI_API_KEY，无法调用通义嵌入")

    headers = {
        "Authorization": f"Bearer {settings.tongyi_api_key}",
        "Content-Type": "application/json",
    }

    # 通义 API 单次 batch 上限为 20，按需分批
    BATCH_SIZE = 20
    all_vectors: list[list[float]] = []
    total = len(texts)

    for start in range(0, total, BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        payload = {
            "model": current_embedding_model(),
            "input": {"texts": list(batch)},
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

        # 单批时做响应一致性校验（多批时各批 inputs 不同无需跨批校验）
        if total <= BATCH_SIZE:
            _check_response_consistency(batch, data)

        embeddings = sorted(data["output"]["embeddings"], key=lambda x: x["text_index"])
        vectors = [item["embedding"] for item in embeddings]
        all_vectors.extend(vectors)

    return _validate_vectors(all_vectors, label="tongyi_embed")


# BGE 模型惰性加载 + 推理统一放工作线程，避免阻塞事件循环（P1-34）；
# 锁保证并发请求下只初始化一次，且同一模型串行推理，避免模型线程安全问题。
_BGE_MODEL_LOCKS: dict[str, threading.Lock] = {
    "st": threading.Lock(),
    "fastembed_zh": threading.Lock(),
    "fastembed_en": threading.Lock(),
}


def _embed_fastembed_blocking(model, texts: list[str]) -> list[list[float]]:
    """fastembed.embed 返回 generator，必须在线程内消费完再回传。"""
    return [
        v.tolist() if hasattr(v, "tolist") else list(v)
        for v in model.embed(texts)
    ]


def _embed_bge_large_blocking(texts: list[str]) -> list[list[float]]:
    """bge-large-zh-v1.5 via sentence-transformers；加载与推理都在工作线程。"""
    from sentence_transformers import SentenceTransformer

    with _BGE_MODEL_LOCKS["st"]:
        if not hasattr(_embed_bge, "_st_model"):
            _embed_bge._st_model = SentenceTransformer(
                settings.bge_model_path or "/app/models/bge-large-zh-v1.5"
            )
        return _embed_bge._st_model.encode(texts, normalize_embeddings=True).tolist()


def _embed_bge_small_blocking(texts: list[str]) -> list[list[float]]:
    """bge-small-zh-v1.5 via fastembed (512 dim)；加载与推理都在工作线程。"""
    from fastembed import TextEmbedding

    with _BGE_MODEL_LOCKS["fastembed_zh"]:
        if not hasattr(_embed_bge, "_model"):
            _embed_bge._model = TextEmbedding(
                model_name="BAAI/bge-small-zh-v1.5",
                providers=["CPUExecutionProvider"],
            )
        return _embed_fastembed_blocking(_embed_bge._model, texts)


def _embed_bge_en_blocking(texts: list[str]) -> list[list[float]]:
    """bge-small-en-v1.5 via fastembed (384 dim)；加载与推理都在工作线程。"""
    from fastembed import TextEmbedding

    with _BGE_MODEL_LOCKS["fastembed_en"]:
        if not hasattr(_embed_bge_en, "_model"):
            _embed_bge_en._model = TextEmbedding(
                model_name=current_bge_en_model(),
                providers=["CPUExecutionProvider"],
            )
        return _embed_fastembed_blocking(_embed_bge_en._model, texts)


async def _embed_bge(texts: Sequence[str]) -> list[list[float]]:
    """进程内调用 BGE（fastembed ONNX Runtime 或 sentence-transformers），推理不阻塞事件循环。"""
    if settings.embedding_dim == 1024:
        all_vectors = await asyncio.to_thread(_embed_bge_large_blocking, list(texts))
    else:
        all_vectors = await asyncio.to_thread(_embed_bge_small_blocking, list(texts))
    return _validate_vectors(all_vectors, label="bge_embed")


async def _embed_bge_en(texts: Sequence[str]) -> list[list[float]]:
    """bge-small-en-v1.5 via fastembed (384 dim)，推理不阻塞事件循环。"""
    all_vectors = await asyncio.to_thread(_embed_bge_en_blocking, list(texts))
    return _validate_vectors(all_vectors, label="bge_en_embed", expected_dim=384)


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _has_cuda() -> bool:
    return False  # fastembed 自动选择 provider


def _is_mock_mode() -> bool:
    """判断是否使用 mock 向量（provider=mock 或 tongyi 无 Key）。"""
    provider = settings.embedding_provider.lower()
    return provider == "mock" or (provider == "tongyi" and not settings.tongyi_api_key)


def _cache_enabled() -> bool:
    """在非 mock 提供商下启用缓存。"""
    provider = settings.embedding_provider.lower()
    return provider in ("tongyi", "bge", "bge_en") and not _is_mock_mode()


async def embed_texts(texts: Sequence[str], provider: str | None = None) -> list[list[float]]:
    if not texts:
        return []

    provider = (provider or settings.embedding_provider).lower()
    if _is_mock_mode():
        dim = 384 if provider == "bge_en" else _get_embedding_dim()
        return _validate_vectors([_mock_vector(t, dim=dim) for t in texts], label="mock_embed", expected_dim=dim)

    if provider == "tongyi":
        use_cache = _cache_enabled()
        if use_cache and len(texts) == 1:
            cached = _embedding_cache.get(texts[0])
            if cached is not None:
                return [cached]

        vectors = await async_retry(_embed_tongyi, texts, max_retries=settings.retry_max_attempts, base_delay=settings.retry_base_delay, breaker_name="tongyi_embed")

        if use_cache:
            for text, vec in zip(texts, vectors):
                _embedding_cache.set(text, vec)

        return vectors

    if provider == "bge":
        use_cache = _cache_enabled()
        if use_cache and len(texts) == 1:
            cached = _embedding_cache.get(texts[0])
            if cached is not None:
                return [cached]

        vectors = await async_retry(_embed_bge, texts, max_retries=settings.retry_max_attempts, base_delay=settings.retry_base_delay, breaker_name="bge_embed")

        if use_cache:
            for text, vec in zip(texts, vectors):
                _embedding_cache.set(text, vec)

        return vectors

    if provider == "bge_en":
        vectors = await async_retry(_embed_bge_en, texts, max_retries=settings.retry_max_attempts, base_delay=settings.retry_base_delay, breaker_name="bge_en_embed")
        return vectors

    raise ValueError(f"不支持的嵌入提供商: {provider}")


async def try_embed_texts(texts: Sequence[str], provider: str | None = None) -> list[list[float]] | None:
    """嵌入降级：嵌入失败时返回 None，调用方降级为纯 FTS。"""
    try:
        return await embed_texts(texts, provider=provider)
    except Exception:
        return None


def clear_embedding_cache() -> None:
    """测试/运维用：清空嵌入缓存。"""
    _embedding_cache.clear()

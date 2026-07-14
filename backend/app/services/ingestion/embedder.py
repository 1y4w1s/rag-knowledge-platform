"""文本嵌入（通义 text-embedding-v2；测试用 mock）。"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

import httpx

from app.core.config import settings

EMBEDDING_DIM = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-v2"
TONGYI_EMBED_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "text-embedding/text-embedding"
)


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

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(TONGYI_EMBED_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "output" not in data or "embeddings" not in data["output"]:
        raise RuntimeError(f"通义嵌入响应异常: {data}")

    embeddings = sorted(data["output"]["embeddings"], key=lambda x: x["text_index"])
    vectors = [item["embedding"] for item in embeddings]
    if any(len(v) != EMBEDDING_DIM for v in vectors):
        raise RuntimeError("通义嵌入维度与 EMBEDDING_DIM 不一致")
    return vectors


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = settings.embedding_provider.lower()
    if provider == "mock" or (provider == "tongyi" and not settings.tongyi_api_key):
        return [_mock_vector(t) for t in texts]

    if provider == "tongyi":
        return await _embed_tongyi(texts)

    raise ValueError(f"不支持的嵌入提供商: {settings.embedding_provider}")

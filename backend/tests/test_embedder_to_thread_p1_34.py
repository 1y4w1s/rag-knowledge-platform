"""P1-34：BGE 同步嵌入改走 asyncio.to_thread，验证结果顺序与并发安全。"""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

from app.core.config import settings
from app.services.ingestion import embedder as mod


def _one_hot(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    vec[sum(ord(ch) for ch in text) % dim] = 1.0
    return vec


class _FakeVector:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _FakeEmbedModel:
    def __init__(self, dim: int, delay: float, counter: list[int] | None) -> None:
        self.dim = dim
        self.delay = delay
        self.counter = counter

    def embed(self, texts):
        for text in texts:
            if self.counter is not None:
                self.counter[0] += 1
            if self.delay:
                time.sleep(self.delay)
            yield _FakeVector(_one_hot(text, self.dim))


def _install_fastembed(
    monkeypatch: pytest.MonkeyPatch,
    dim: int,
    delay: float = 0.0,
    instances: list[dict] | None = None,
    counter: list[int] | None = None,
) -> None:
    module = types.ModuleType("fastembed")

    class _TextEmbedding:
        def __init__(self, **kwargs):
            if instances is not None:
                instances.append(kwargs)
            self._model = _FakeEmbedModel(dim=dim, delay=delay, counter=counter)

        def embed(self, texts):
            return self._model.embed(texts)

    module.TextEmbedding = _TextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)


def _install_sentence_transformers(
    monkeypatch: pytest.MonkeyPatch,
    dim: int,
    delay: float = 0.0,
) -> None:
    module = types.ModuleType("sentence_transformers")

    class _FakeSTModel:
        def encode(self, texts, normalize_embeddings=True):
            if delay:
                time.sleep(delay)
            return _FakeVector([_one_hot(t, dim) for t in texts])

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):
            self._model = _FakeSTModel()

        def encode(self, texts, normalize_embeddings=True):
            return self._model.encode(texts, normalize_embeddings=normalize_embeddings)

    module.SentenceTransformer = _SentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


@pytest.fixture(autouse=True)
def _bge_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "bge")
    monkeypatch.setattr(settings, "embedding_dim", 512)
    mod.clear_embedding_cache()
    for fn in (mod._embed_bge, mod._embed_bge_en):
        for attr in ("_model", "_st_model"):
            monkeypatch.delattr(fn, attr, raising=False)


@pytest.mark.asyncio
async def test_bge_embed_preserves_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fastembed(monkeypatch, dim=512)
    texts = ["third", "first", "second"]
    vectors = await mod.embed_texts(texts, provider="bge")
    assert vectors == [_one_hot(t, 512) for t in texts]


@pytest.mark.asyncio
async def test_bge_en_embed_preserves_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fastembed(monkeypatch, dim=384)
    texts = ["hello", "world"]
    vectors = await mod.embed_texts(texts, provider="bge_en")
    assert vectors == [_one_hot(t, 384) for t in texts]


@pytest.mark.asyncio
async def test_bge_large_embed_preserves_input_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_dim", 1024)
    _install_sentence_transformers(monkeypatch, dim=1024)
    texts = ["one", "two", "three"]
    vectors = await mod.embed_texts(texts, provider="bge")
    assert vectors == [_one_hot(t, 1024) for t in texts]


@pytest.mark.asyncio
async def test_bge_embed_does_not_block_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fastembed(monkeypatch, dim=512, delay=0.4)
    embed_task = asyncio.create_task(mod.embed_texts(["slow"], provider="bge"))

    async def quick() -> str:
        await asyncio.sleep(0.03)
        return "ok"

    quick_result = await asyncio.wait_for(quick(), timeout=0.25)
    vectors = await asyncio.wait_for(embed_task, timeout=5)
    assert quick_result == "ok"
    assert vectors == [_one_hot("slow", 512)]


@pytest.mark.asyncio
async def test_bge_en_embed_does_not_block_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fastembed(monkeypatch, dim=384, delay=0.4)
    embed_task = asyncio.create_task(mod.embed_texts(["slow"], provider="bge_en"))

    async def quick() -> str:
        await asyncio.sleep(0.03)
        return "ok"

    quick_result = await asyncio.wait_for(quick(), timeout=0.25)
    vectors = await asyncio.wait_for(embed_task, timeout=5)
    assert quick_result == "ok"
    assert vectors == [_one_hot("slow", 384)]


@pytest.mark.asyncio
async def test_concurrent_bge_embed_loads_model_once_and_keeps_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[dict] = []
    counter = [0]
    _install_fastembed(
        monkeypatch,
        dim=512,
        delay=0.02,
        instances=instances,
        counter=counter,
    )
    texts = [f"text-{i}" for i in range(6)]
    results = await asyncio.gather(
        *(mod.embed_texts([t], provider="bge") for t in texts)
    )
    assert len(instances) == 1
    assert counter[0] == len(texts)
    for text, (vector,) in zip(texts, results):
        assert vector == _one_hot(text, 512)


@pytest.mark.asyncio
async def test_concurrent_batches_preserve_batch_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fastembed(monkeypatch, dim=512, delay=0.01)
    batches = [["a", "b"], ["c", "d", "e"], ["f"]]
    results = await asyncio.gather(
        *(mod.embed_texts(batch, provider="bge") for batch in batches)
    )
    for batch, vectors in zip(batches, results):
        assert vectors == [_one_hot(t, 512) for t in batch]

"""P2-I4：嵌入响应一致性校验字典必须 LRU 有界，防 worker 长期运行内存增长。"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict

import pytest

from app.services.ingestion import embedder as mod


def _input_key(texts: list[str]) -> str:
    return hashlib.sha256("|".join(texts).encode()).hexdigest()[:16]


def _response(embedding: list[float]) -> dict:
    return {"output": {"embeddings": [{"text_index": 0, "embedding": embedding}]}}


def _check(texts: list[str], embedding: list[float]) -> None:
    mod._check_response_consistency(texts, _response(embedding))


def test_response_consistency_warns_once_on_change(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(mod, "_response_checksums", OrderedDict())
    monkeypatch.setattr(mod, "_RESPONSE_CHECKSUM_MAX_SIZE", 10)

    texts = ["同一输入"]
    _check(texts, [1.0, 0.0])
    _check(texts, [1.0, 0.0])
    assert not caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="app.services.ingestion.embedder"):
        _check(texts, [0.5, 0.5])
    assert "嵌入响应不一致" in caplog.text
    assert len(mod._response_checksums) == 1

    caplog.clear()
    _check(texts, [0.5, 0.5])
    assert "嵌入响应不一致" not in caplog.text


def test_checksum_store_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod, "_response_checksums", OrderedDict())
    monkeypatch.setattr(mod, "_RESPONSE_CHECKSUM_MAX_SIZE", 3)

    for i in range(10):
        _check([f"text-{i}"], [float(i), 0.0])

    assert len(mod._response_checksums) == 3
    assert _input_key(["text-9"]) in mod._response_checksums
    assert _input_key(["text-0"]) not in mod._response_checksums


def test_checksum_lru_evicts_oldest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store: OrderedDict[str, str] = OrderedDict()
    monkeypatch.setattr(mod, "_response_checksums", store)
    monkeypatch.setattr(mod, "_RESPONSE_CHECKSUM_MAX_SIZE", 3)

    for i in range(3):
        _check([f"text-{i}"], [float(i), 0.0])

    # 触达 text-0，使其成为最近使用；随后两次写入应淘汰 text-1、text-2
    _check(["text-0"], [0.0, 0.0])
    _check(["text-3"], [3.0, 0.0])
    _check(["text-4"], [4.0, 0.0])

    assert set(store) == {
        _input_key(["text-0"]),
        _input_key(["text-3"]),
        _input_key(["text-4"]),
    }

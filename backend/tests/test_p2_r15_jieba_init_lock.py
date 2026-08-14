"""P2-R15：jieba 词典首次初始化加锁，并发首次调用只加载一次。"""

from __future__ import annotations

import threading
import time

import jieba
import pytest

from app.services.rag import cjk


@pytest.fixture(autouse=True)
def reset_jieba_state() -> None:
    cjk._jieba_initialized = False
    yield
    cjk._jieba_initialized = False


def test_concurrent_first_call_initializes_jieba_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多个线程同时首次调用 _ensure_jieba 时，jieba.initialize 只执行一次。"""
    calls: list[int] = []
    call_lock = threading.Lock()
    errors: list[Exception] = []

    def fake_initialize() -> None:
        with call_lock:
            calls.append(1)
        # 放大初始化窗口，复现多个线程同时看到“未初始化”的竞态。
        time.sleep(0.05)

    def run() -> None:
        try:
            cjk._ensure_jieba()
        except Exception as exc:  # noqa: BLE001 - 线程内异常需带回主线程断言
            errors.append(exc)

    monkeypatch.setattr(jieba, "initialize", fake_initialize)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(calls) == 1


def test_segment_cjk_initializes_once_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """segment_cjk 多次调用只触发一次词典初始化，分词入口行为不变。"""
    calls: list[int] = []
    monkeypatch.setattr(jieba, "initialize", lambda: calls.append(1))
    monkeypatch.setattr(jieba, "lcut", lambda text: [text])

    cjk.segment_cjk("测试文本")
    cjk.segment_cjk("测试文本")

    assert len(calls) == 1

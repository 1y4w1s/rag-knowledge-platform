"""BenchmarkDataset 基类：数据集加载器抽象接口。"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import AsyncIterator

from tests.benchmark.schemas import (
    BenchmarkQuery,
    DatasetMeta,
)


class BenchmarkDataset(abc.ABC):
    """数据集加载器基类。

    每个子类负责：
    1. 下载 / 查找数据集文件
    2. 解析为统一的 BenchmarkQuery 列表
    3. 提供元信息（DatasetMeta）

    子类应放在 loaders/ 下，命名约定：<数据集名>.py，类名 <数据集名>Dataset。
    """

    # 数据集本地缓存根目录（backend/data/benchmark/）
    DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "benchmark"

    def __init__(self) -> None:
        self._queries: list[BenchmarkQuery] | None = None

    # —— 子类必须实现的接口 ——

    @property
    @abc.abstractmethod
    def meta(self) -> DatasetMeta:
        """数据集元信息。"""
        ...

    @abc.abstractmethod
    async def load(self) -> list[BenchmarkQuery]:
        """加载数据集并返回统一查询列表。

        首次调用会缓存；子类通常在 _load_impl 中实现具体解析逻辑。
        """
        ...

    # —— 可选覆盖 ——

    async def download_if_needed(self) -> Path:
        """检查本地缓存，若不存在则下载数据集。

        默认行为：返回 DATA_DIR / self.meta.name 目录，
        子类可覆盖以实现自动下载。
        """
        path = self.DATA_DIR / self.meta.name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def split(
        self,
        queries: list[BenchmarkQuery],
        *,
        train_ratio: float = 0.0,
        val_ratio: float = 0.0,
    ) -> tuple[list[BenchmarkQuery], list[BenchmarkQuery], list[BenchmarkQuery]]:
        """简单随机分割。默认全部作为测试集。"""
        import random

        n = len(queries)
        if train_ratio <= 0 and val_ratio <= 0:
            return [], [], queries

        shuffled = list(queries)
        random.shuffle(shuffled)

        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        return (
            shuffled[:n_train],
            shuffled[n_train : n_train + n_val],
            shuffled[n_train + n_val :],
        )

    def sample(self, queries: list[BenchmarkQuery], n: int) -> list[BenchmarkQuery]:
        """从查询列表中随机抽取 n 条。"""
        import random

        if n >= len(queries):
            return list(queries)
        return random.sample(queries, n)

    def __len__(self) -> int:
        if self._queries is not None:
            return len(self._queries)
        return 0

    def __getitem__(self, index: int) -> BenchmarkQuery:
        if self._queries is None:
            raise RuntimeError("Dataset not loaded. Call load() first.")
        return self._queries[index]

    async def __aiter__(self) -> AsyncIterator[BenchmarkQuery]:
        if self._queries is None:
            self._queries = await self.load()
        for q in self._queries:
            yield q

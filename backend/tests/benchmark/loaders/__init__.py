"""数据集加载器注册表（Plugin 模式）。"""

from __future__ import annotations

from tests.benchmark.base import BenchmarkDataset


_REGISTRY: dict[str, type[BenchmarkDataset]] = {}


def register(name: str) -> callable:
    """装饰器：注册数据集加载器。"""

    def wrapper(cls: type[BenchmarkDataset]) -> type[BenchmarkDataset]:
        _REGISTRY[name] = cls
        return cls

    return wrapper


def get_loader(name: str) -> BenchmarkDataset:
    """按名称获取数据集加载器实例。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise KeyError(
            f"Unknown dataset '{name}'. Available: {available}"
        )
    return cls()


def list_datasets() -> list[str]:
    """返回所有已注册的数据集名称。"""
    return sorted(_REGISTRY)


# 导入子模块以触发注册
from tests.benchmark.loaders import crag  # noqa: F401, E402
from tests.benchmark.loaders import liverag  # noqa: F401, E402
from tests.benchmark.loaders import rageval  # noqa: F401, E402
from tests.benchmark.loaders import ragbench  # noqa: F401, E402
from tests.benchmark.loaders import mirage  # noqa: F401, E402
from tests.benchmark.loaders import enterprise  # noqa: F401, E402

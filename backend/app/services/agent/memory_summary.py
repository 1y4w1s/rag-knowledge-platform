"""T6 长期记忆分层 · W4 结构化摘要（字段级压缩 + 总字符预算 + 审计信号）。

确定性纯函数压缩 `AgentMemory.value` 并写入 `summary` 列；零 LLM、零新增依赖。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_memory import AgentMemory
from app.services.audit.agent import safe_audit
from app.services.audit.log import write_audit_log


@dataclass(frozen=True, slots=True)
class SummaryConfig:
    max_field_chars: int = 120
    max_items: int = 20
    max_depth: int = 3
    max_total_chars: int = 800
    truncation_marker: str = "..."


@dataclass(frozen=True, slots=True)
class MemorySummaryResult:
    summary: dict
    truncated: bool
    field_count: int
    total_chars: int


def summary_config_from_settings() -> SummaryConfig:
    """从 settings 读取 agent_memory_summary_*。"""
    return SummaryConfig(
        max_field_chars=settings.agent_memory_summary_max_field_chars,
        max_items=settings.agent_memory_summary_max_items,
        max_depth=settings.agent_memory_summary_max_depth,
        max_total_chars=settings.agent_memory_summary_max_total_chars,
        truncation_marker=settings.agent_memory_summary_truncation_marker,
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compress_node(node: Any, depth: int, config: SummaryConfig) -> tuple[Any, bool]:
    """递归压缩单节点；返回 (压缩结果, 是否发生截断)。"""
    if depth > config.max_depth:
        return config.truncation_marker, True
    if isinstance(node, str):
        if len(node) > config.max_field_chars:
            return node[: config.max_field_chars] + config.truncation_marker, True
        return node, False
    if isinstance(node, list):
        limit = max(0, config.max_items)
        compressed: list[Any] = []
        truncated = False
        for item in node[:limit]:
            value, item_truncated = _compress_node(item, depth + 1, config)
            compressed.append(value)
            truncated = truncated or item_truncated
        if len(node) > limit:
            compressed.append(config.truncation_marker)
            truncated = True
        return compressed, truncated
    if isinstance(node, dict):
        compressed_dict: dict[str, Any] = {}
        truncated = False
        for key, value in node.items():
            compressed_dict[key], value_truncated = _compress_node(
                value, depth + 1, config
            )
            truncated = truncated or value_truncated
        return compressed_dict, truncated
    return node, False


def _collect_string_leaves(
    node: Any,
    handles: list[tuple[dict | list, str | int, str]],
) -> None:
    """按先序遍历收集字符串叶子及其父容器位置。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                handles.append((node, key, value))
            else:
                _collect_string_leaves(value, handles)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, str):
                handles.append((node, index, item))
            else:
                _collect_string_leaves(item, handles)


def _containers_reverse_preorder(node: Any):
    """按反向插入顺序产出 dict / list 容器（最深最右优先）。"""
    if isinstance(node, dict):
        for value in reversed(list(node.values())):
            yield from _containers_reverse_preorder(value)
        yield node
    elif isinstance(node, list):
        for item in reversed(node):
            yield from _containers_reverse_preorder(item)
        yield node


def _fit_total_chars(summary: dict, config: SummaryConfig) -> tuple[dict, bool]:
    """把 summary 压进 max_total_chars；返回 (结果, 是否发生过变更)。"""
    if len(_canonical_json(summary)) <= config.max_total_chars:
        return summary, False

    handles: list[tuple[dict | list, str | int, str]] = []
    _collect_string_leaves(summary, handles)
    for parent, field, text in reversed(handles):
        current = text
        while len(_canonical_json(summary)) > config.max_total_chars and current:
            current = current[: len(current) // 2]
            parent[field] = current
            if not current:
                del parent[field]
        if len(_canonical_json(summary)) <= config.max_total_chars:
            return summary, True

    # 字符串耗尽仍超限：按反向插入顺序删除 list 尾项与 dict 尾部键。
    while len(_canonical_json(summary)) > config.max_total_chars:
        removed = False
        for container in _containers_reverse_preorder(summary):
            if isinstance(container, dict) and container:
                del container[next(reversed(container))]
                removed = True
                break
            if isinstance(container, list) and container:
                container.pop()
                removed = True
                break
        if not removed:
            break

    if len(_canonical_json(summary)) > config.max_total_chars:
        return {"v": config.truncation_marker}, True
    return summary, True


def compress_memory_value(
    value: Any,
    *,
    config: SummaryConfig | None = None,
) -> MemorySummaryResult:
    """对结构化 value 做字段级压缩。纯函数、确定性、零 LLM、零 DB / IO。"""
    cfg = config or summary_config_from_settings()
    if isinstance(value, dict):
        summary, truncated = _compress_node(value, 0, cfg)
    else:
        compressed, _ = _compress_node(value, 0, cfg)
        summary = {"v": compressed}
        truncated = True

    summary, budget_truncated = _fit_total_chars(summary, cfg)
    total_chars = len(_canonical_json(summary))
    return MemorySummaryResult(
        summary=summary,
        truncated=truncated or budget_truncated,
        field_count=len(summary),
        total_chars=total_chars,
    )


async def update_memory_summary(
    db: AsyncSession,
    *,
    memory_id: UUID,
    actor_user_id: UUID,
    config: SummaryConfig | None = None,
) -> MemorySummaryResult | None:
    """压缩 AgentMemory.value 并写入 summary 列；仅内容变化时写审计。

    返回 None 表示未找到或 memory.user_id != actor_user_id（跨用户隔离，不落库）。
    使用独立 session 立即 commit，不触碰调用方事务。
    """
    from app.core.database import SessionLocal

    cfg = config or summary_config_from_settings()
    async with SessionLocal() as mem_db:
        memory = await mem_db.get(AgentMemory, memory_id)
        if memory is None or memory.user_id != actor_user_id:
            return None

        result = compress_memory_value(memory.value, config=cfg)
        changed = _canonical_json(memory.summary) != _canonical_json(result.summary)
        memory.summary = result.summary
        if changed:
            await safe_audit(
                write_audit_log(
                    mem_db,
                    action="agent.memory_summary_updated",
                    actor_user_id=actor_user_id,
                    resource_type="agent_memory",
                    resource_id=memory.id,
                    metadata={
                        "memory_id": str(memory.id),
                        "key": memory.key,
                        "memory_type": memory.memory_type,
                        "truncated": result.truncated,
                        "field_count": result.field_count,
                        "total_chars": result.total_chars,
                    },
                )
            )
        await mem_db.commit()
        return result

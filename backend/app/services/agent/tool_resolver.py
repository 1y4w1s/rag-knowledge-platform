"""L3-W4 · ToolSpec(requires/produces) + ToolResolver（dependent tools 解锁）。

requires / produces 为资源键：`chunk_id` / `document_id`。
解锁仅看 evidence 中已聚合的 ID，不靠 LLM 臆造。
`agent_l3_dynamic_tools_enabled` 默认 False 时仅暴露独立只读 tool。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.agent.types import AgentState

# 资源键（ToolSpec.requires / produces）
RESOURCE_CHUNK_ID = "chunk_id"
RESOURCE_DOCUMENT_ID = "document_id"

_COMPARE_MIN_CHUNKS = 2


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """LLM 可见的 tool 元信息（含 L3 依赖声明）。"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    requires: frozenset[str] = field(default_factory=frozenset)
    produces: frozenset[str] = field(default_factory=frozenset)


# ── 参数 schema（独立 + 依赖）──────────────────────────────────────

_PARAM_SCHEMAS: dict[str, dict] = {
    "semantic_search": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询，基于语义匹配文档内容",
            },
        },
        "required": ["query"],
    },
    "web_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "联网搜索关键词"},
            "num_results": {
                "type": "integer",
                "description": "返回结果数量（默认5，最大5）",
            },
        },
        "required": ["query"],
    },
    "search_documents": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "文档名或关键词搜索",
            },
            "mode": {
                "type": "string",
                "description": "搜索模式：filename（按文件名）或 content（按内容）",
                "enum": ["filename", "content"],
            },
        },
        "required": ["query"],
    },
    "list_knowledge_bases": {
        "type": "object",
        "properties": {
            "q": {
                "type": "string",
                "description": "可选的关键词过滤",
            },
        },
    },
    "get_chunk_excerpt": {
        "type": "object",
        "properties": {
            "chunk_id": {
                "type": "string",
                "description": "已检索命中的 chunk_id（须来自当前状态）",
            },
        },
        "required": ["chunk_id"],
    },
    "grep_in_document": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "已检索命中的 document_id（须来自当前状态）",
            },
            "pattern": {
                "type": "string",
                "description": "文档内关键词或短模式",
            },
            "context_lines": {
                "type": "integer",
                "description": "命中行上下文行数（默认2，最大5）",
            },
        },
        "required": ["document_id", "pattern"],
    },
    "compare_chunks": {
        "type": "object",
        "properties": {
            "chunk_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "至少 2 个已检索 chunk_id，用于并列对比",
            },
        },
        "required": ["chunk_ids"],
    },
}

_DESCRIPTIONS: dict[str, str] = {
    "semantic_search": "语义搜索，根据查询语义检索相关文档片段（返回 Top-N 命中）",
    "search_documents": "文档搜索，按文件名或内容搜索文档元信息",
    "list_knowledge_bases": "列出用户当前可见的知识库列表",
    "web_search": "联网搜索（需要 SEARCH_API_KEY），返回搜索结果标题/URL/摘要",
    "get_chunk_excerpt": "展开已命中 chunk 的摘录（需状态中已有 chunk_id）",
    "grep_in_document": "在已命中文档内关键词检索（需状态中已有 document_id）",
    "compare_chunks": "并列对比多个已命中 chunk（需状态中至少 2 个 chunk_id）",
}


def _spec(
    name: str,
    *,
    requires: frozenset[str] = frozenset(),
    produces: frozenset[str] = frozenset(),
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=_DESCRIPTIONS.get(name, name),
        parameters=_PARAM_SCHEMAS.get(name, {"type": "object", "properties": {}}),
        requires=requires,
        produces=produces,
    )


# 独立可调用（无需前序 ID）
INDEPENDENT_TOOL_SPECS: tuple[ToolSpec, ...] = (
    _spec(
        "semantic_search",
        produces=frozenset({RESOURCE_CHUNK_ID, RESOURCE_DOCUMENT_ID}),
    ),
    _spec("search_documents", produces=frozenset({RESOURCE_DOCUMENT_ID})),
    _spec("list_knowledge_bases"),
    _spec("web_search"),
)

# 依赖工具：须 AgentState.evidence 中已有对应资源
DEPENDENT_TOOL_SPECS: tuple[ToolSpec, ...] = (
    _spec(
        "get_chunk_excerpt",
        requires=frozenset({RESOURCE_CHUNK_ID}),
        produces=frozenset({RESOURCE_CHUNK_ID, RESOURCE_DOCUMENT_ID}),
    ),
    _spec(
        "grep_in_document",
        requires=frozenset({RESOURCE_DOCUMENT_ID}),
        produces=frozenset({RESOURCE_CHUNK_ID}),
    ),
    _spec(
        "compare_chunks",
        requires=frozenset({RESOURCE_CHUNK_ID}),
        produces=frozenset({RESOURCE_CHUNK_ID, RESOURCE_DOCUMENT_ID}),
    ),
)

DEPENDENT_TOOL_NAMES: frozenset[str] = frozenset(
    s.name for s in DEPENDENT_TOOL_SPECS
)


def resources_from_state(state: AgentState) -> frozenset[str]:
    """从 AgentState.evidence 推导当前可用资源键。"""
    found: set[str] = set()
    if state.evidence.chunk_ids:
        found.add(RESOURCE_CHUNK_ID)
    if state.evidence.document_ids:
        found.add(RESOURCE_DOCUMENT_ID)
    return frozenset(found)


def is_dependent_unlocked(spec: ToolSpec, state: AgentState) -> bool:
    """判定 dependent tool 是否因状态资源已满足而解锁。"""
    if not spec.requires:
        return True
    available = resources_from_state(state)
    if not spec.requires.issubset(available):
        return False
    # compare 额外要求 ≥2 个 chunk
    if spec.name == "compare_chunks":
        return len(state.evidence.chunk_ids) >= _COMPARE_MIN_CHUNKS
    return True


class ToolResolver:
    """按 flag + AgentState 解析当前 LLM 可见 tool 面。"""

    @staticmethod
    def resolve(
        state: AgentState,
        *,
        dynamic_enabled: bool,
        external_tools_enabled: bool = True,
    ) -> list[ToolSpec]:
        """返回当前可用 ToolSpec 列表。

        - dynamic_enabled=False：仅独立只读（与 W2 行为一致）
        - dynamic_enabled=True：额外解锁 requires 已满足的 dependent tools
        """
        specs: list[ToolSpec] = list(INDEPENDENT_TOOL_SPECS)
        if not external_tools_enabled:
            specs = [s for s in specs if s.name != "web_search"]

        if dynamic_enabled:
            for dep in DEPENDENT_TOOL_SPECS:
                if is_dependent_unlocked(dep, state):
                    specs.append(dep)
        return specs

    @staticmethod
    def available_names(
        state: AgentState,
        *,
        dynamic_enabled: bool,
        external_tools_enabled: bool = True,
    ) -> frozenset[str]:
        return frozenset(
            s.name
            for s in ToolResolver.resolve(
                state,
                dynamic_enabled=dynamic_enabled,
                external_tools_enabled=external_tools_enabled,
            )
        )

"""G3 只读 tool 注册表与白名单（G3-1.1 · G3-E8）。"""

from __future__ import annotations

from enum import Enum


class ReadOnlyToolName(str, Enum):
    list_knowledge_bases = "list_knowledge_bases"
    semantic_search = "semantic_search"
    search_documents = "search_documents"
    get_chunk_excerpt = "get_chunk_excerpt"
    grep_in_document = "grep_in_document"
    compare_chunks = "compare_chunks"


READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    member.value for member in ReadOnlyToolName
)


class AgentToolName(str, Enum):
    """所有 agent 可调度 tool（只读 + 写）· G4-1.1 起含 generate_faq_draft。

    generate_faq_draft 是写·待审 tool，显式 **不在** READ_ONLY_TOOL_NAMES。
    """

    list_knowledge_bases = "list_knowledge_bases"
    semantic_search = "semantic_search"
    search_documents = "search_documents"
    get_chunk_excerpt = "get_chunk_excerpt"
    grep_in_document = "grep_in_document"
    compare_chunks = "compare_chunks"
    generate_faq_draft = "generate_faq_draft"


ALL_AGENT_TOOL_NAMES: frozenset[str] = frozenset(
    member.value for member in AgentToolName
)


class UnknownToolError(ValueError):
    """Runtime 收到非白名单 tool 名（G3-E8）。"""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"unknown or disallowed tool: {tool_name}")


def is_allowed_tool(tool_name: str) -> bool:
    return tool_name in READ_ONLY_TOOL_NAMES


def parse_allowed_tool(tool_name: str) -> ReadOnlyToolName:
    """解析并校验只读 tool 名；非法则抛 UnknownToolError。"""
    if not is_allowed_tool(tool_name):
        raise UnknownToolError(tool_name)
    return ReadOnlyToolName(tool_name)


def is_known_agent_tool(tool_name: str) -> bool:
    """含只读与写 tool（G4-1.1）。generate_faq_draft 在此集合内。"""
    return tool_name in ALL_AGENT_TOOL_NAMES


def parse_agent_tool(tool_name: str) -> AgentToolName:
    """解析并校验任意 agent tool 名（只读 + 写）；非注册 tool 抛 UnknownToolError。"""
    if not is_known_agent_tool(tool_name):
        raise UnknownToolError(tool_name)
    return AgentToolName(tool_name)

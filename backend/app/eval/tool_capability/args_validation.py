"""Eval-only arg validation mirroring L3 tool parameter schemas."""

from __future__ import annotations

from typing import Any


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(args, dict):
        return False, "args must be object"

    if tool_name == "search_documents":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return False, "search_documents requires non-empty query"
        mode = args.get("mode")
        if mode is not None and mode not in {"filename", "content"}:
            return False, "search_documents mode must be filename or content"
        return True, "valid"

    if tool_name == "list_knowledge_bases":
        q = args.get("q")
        if q is not None and not isinstance(q, str):
            return False, "list_knowledge_bases q must be string or null"
        return True, "valid"

    if tool_name == "semantic_search":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return False, "semantic_search requires non-empty query"
        return True, "valid"

    return False, f"unsupported tool for arg validation: {tool_name}"

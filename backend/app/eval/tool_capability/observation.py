"""Tool-native observation contracts (not generic expected_chunk)."""

from __future__ import annotations

from typing import Any


def _as_dict(observation: Any) -> dict[str, Any] | None:
    if observation is None:
        return None
    if isinstance(observation, dict):
        return observation
    return None


def _has_non_empty_str(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _items_have_fields(items: Any, *fields: str) -> bool:
    if not isinstance(items, list) or not items:
        return False
    first = items[0]
    if not isinstance(first, dict):
        return False
    return all(field in first and first[field] is not None for field in fields)


def observation_satisfies_contract(tool_name: str, observation: Any) -> tuple[bool, str]:
    """Return (passed, reason) for tool-native observable requirements."""
    payload = _as_dict(observation)
    if payload is None:
        return False, "observation missing or not a dict"

    if tool_name == "list_knowledge_bases":
        if not isinstance(payload.get("total"), int):
            return False, "list_knowledge_bases requires total count"
        if not _items_have_fields(payload.get("items"), "kb_id", "name"):
            return False, "list_knowledge_bases requires kb_id and name in items"
        return True, "kb identity/count/metadata present"

    if tool_name == "search_documents":
        if not isinstance(payload.get("total"), int):
            return False, "search_documents requires total count"
        if not _items_have_fields(payload.get("items"), "document_id", "filename"):
            return False, "search_documents requires document_id and filename"
        if _has_non_empty_str(payload, "summary"):
            return True, "document identity/title present"
        if _items_have_fields(payload.get("items"), "filename"):
            return True, "document identity/title present"
        return False, "search_documents missing document identity signal"

    if tool_name == "semantic_search":
        items = payload.get("items") or payload.get("hits") or payload.get("results")
        if not isinstance(items, list) or not items:
            return False, "semantic_search requires evidence hits"
        first = items[0]
        if not isinstance(first, dict):
            return False, "semantic_search hit must be dict"
        has_chunk = _has_non_empty_str(first, "chunk_id", "excerpt", "text", "content")
        has_doc = _has_non_empty_str(first, "document_id", "filename", "doc_id")
        has_score = isinstance(first.get("score"), (int, float))
        if has_chunk or has_doc or has_score:
            return True, "evidence/document/chunk signal present"
        return False, "semantic_search missing chunk/document/score signal"

    return False, f"unsupported tool observation contract: {tool_name}"

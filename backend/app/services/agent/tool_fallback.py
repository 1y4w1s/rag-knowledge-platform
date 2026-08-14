"""G1 · 工具失败分类与确定性等价替换（纯函数，W1）。

本模块不触碰 runtime / planner / audit / config；分类器与替换表均为纯函数，
单测直接断言各分支，不依赖 DB。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from app.core.retry import CircuitBreakerOpenError
from app.services.agent.tools.document_write import DocumentWriteFailure
from app.services.agent.tools.generate_faq_draft import (
    NO_BASIS_SUMMARY,
    GenerateFaqDraftFailure,
)
from app.services.agent.tools.get_chunk_excerpt import NOT_FOUND_SUMMARY
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY
from app.services.agent.tools.search_documents import SearchDocumentsOutput
from app.services.agent.types import (
    AgentStepRecord,
    ToolFailure,
    ToolFailureKind,
)

_GREP_PENDING_DOCUMENT_ID = "<PENDING>"
_MAX_PATTERN_LEN = 200
_WRITE_TOOLS = frozenset({"generate_faq_draft", "delete_document", "restore_document"})
_REASON_TO_KIND: dict[object, ToolFailureKind] = {
    GenerateFaqDraftFailure.kb_not_visible: ToolFailureKind.denied,
    DocumentWriteFailure.kb_not_visible: ToolFailureKind.denied,
    DocumentWriteFailure.write_forbidden: ToolFailureKind.denied,
    GenerateFaqDraftFailure.quota_exceeded: ToolFailureKind.quota,
    GenerateFaqDraftFailure.invalid_filename: ToolFailureKind.invalid_args,
    DocumentWriteFailure.bad_request: ToolFailureKind.invalid_args,
    GenerateFaqDraftFailure.no_source: ToolFailureKind.not_found,
    DocumentWriteFailure.doc_not_found: ToolFailureKind.not_found,
}

_STRIP_PUNCT_RE = re.compile(r"[^\w]+", re.UNICODE)
_CLUSTER_RE = re.compile(r"(?:[\u4e00-\u9fff]+|[A-Za-z0-9_]+)")


@dataclass(frozen=True, slots=True)
class ToolFallbackPlan:
    tool_name: str
    args: dict[str, Any]
    source: Literal["equivalent", "replan"]


def _extract_reason(data: Any) -> tuple[str | None, ToolFailureKind | None]:
    """从 ToolResult 对象提取机器可读 reason，避免字符串匹配。"""
    if data is None or not hasattr(data, "reason"):
        return None, None
    reason = data.reason
    if reason is None:
        return None, None
    reason_text = reason.value if isinstance(reason, Enum) else str(reason)
    return reason_text, _REASON_TO_KIND.get(reason)


def classify_tool_failure(
    *,
    tool_name: str,
    ok: bool,
    summary: str,
    data: Any,
    exception: BaseException | None = None,
) -> ToolFailure | None:
    """把一次工具执行结果归类为结构化失败；ok=True 返回 None。"""
    if exception is not None:
        return ToolFailure(
            kind=ToolFailureKind.infra,
            tool_name=tool_name,
            summary=summary,
            breaker_open=isinstance(exception, CircuitBreakerOpenError),
        )
    if ok:
        return None

    reason, reason_kind = _extract_reason(data)
    if reason_kind is not None:
        return ToolFailure(
            kind=reason_kind,
            tool_name=tool_name,
            summary=summary,
            reason=reason,
        )

    if tool_name == "sql_query":
        return ToolFailure(
            kind=ToolFailureKind.disabled,
            tool_name=tool_name,
            summary=summary,
        )
    if summary == FORBIDDEN_KB_SUMMARY:
        kind = ToolFailureKind.denied
    elif summary in (NOT_FOUND_SUMMARY, NO_BASIS_SUMMARY):
        kind = ToolFailureKind.not_found
    elif _is_web_search_disabled(tool_name, summary):
        kind = ToolFailureKind.disabled
    else:
        kind = ToolFailureKind.invalid_args
    return ToolFailure(kind=kind, tool_name=tool_name, summary=summary)


def _is_web_search_disabled(tool_name: str, summary: str) -> bool:
    if tool_name != "web_search":
        return False
    return (
        "已关闭" in summary
        or "SEARCH_API_KEY" in summary
        or "已达上限" in summary
    )


def _retained_kb_ids(
    args: dict[str, Any],
    default_kb_id: UUID | None,
) -> list[UUID] | None:
    raw = args.get("kb_ids")
    if raw:
        return [UUID(str(item)) for item in raw]
    if default_kb_id is not None:
        return [default_kb_id]
    return None


def _derive_grep_pattern(query: str) -> str:
    """去标点后取首个连续 CJK / 单词簇；超长截断，空则取 query 前缀。"""
    stripped = _STRIP_PUNCT_RE.sub(" ", query)
    for match in _CLUSTER_RE.finditer(stripped):
        cluster = match.group(0)
        if cluster:
            return cluster[:_MAX_PATTERN_LEN]
    return query[:_MAX_PATTERN_LEN]


def _semantic_search_fallback(
    failed_step: AgentStepRecord,
    *,
    remaining_steps: int,
    default_kb_id: UUID | None,
) -> tuple[ToolFallbackPlan, ...] | None:
    query = str(failed_step.args.get("query", ""))
    kb_ids = _retained_kb_ids(failed_step.args, default_kb_id)
    search_args: dict[str, Any] = {"mode": "content", "query": query}
    if kb_ids is not None:
        search_args["kb_ids"] = kb_ids
    if remaining_steps < 2:
        return None
    return (
        ToolFallbackPlan("search_documents", search_args, "equivalent"),
        ToolFallbackPlan(
            "grep_in_document",
            {"document_id": _GREP_PENDING_DOCUMENT_ID, "pattern": _derive_grep_pattern(query), "context_lines": 2},
            "equivalent",
        ),
    )


def find_equivalent_tool(
    failure: ToolFailure,
    failed_step: AgentStepRecord,
    *,
    remaining_steps: int,
    default_kb_id: UUID | None,
) -> tuple[ToolFallbackPlan, ...] | None:
    """返回确定性等价替换计划；空 / None 表示交由提示重规划或正常收口。"""
    if remaining_steps < 1:
        return None
    if failure.kind in (
        ToolFailureKind.denied,
        ToolFailureKind.quota,
    ):
        return None
    if failed_step.tool_name in _WRITE_TOOLS or failed_step.tool_name == "sql_query":
        return None

    if (
        failed_step.tool_name == "semantic_search"
        and failure.kind == ToolFailureKind.infra
    ):
        return _semantic_search_fallback(
            failed_step,
            remaining_steps=remaining_steps,
            default_kb_id=default_kb_id,
        )
    if (
        failed_step.tool_name == "get_chunk_excerpt"
        and failure.kind == ToolFailureKind.infra
    ):
        chunk_id = failed_step.args.get("chunk_id")
        if chunk_id is None:
            return None
        return (ToolFallbackPlan("compare_chunks", {"chunk_ids": [chunk_id]}, "equivalent"),)
    if (
        failed_step.tool_name == "web_search"
        and failure.kind in (
            ToolFailureKind.disabled,
            ToolFailureKind.infra,
        )
    ):
        return (ToolFallbackPlan("semantic_search", {"query": str(failed_step.args.get("query", ""))}, "equivalent"),)
    return None


def _latest_search_hit_document_id(
    prior_steps: tuple[AgentStepRecord, ...],
) -> UUID | None:
    for step in reversed(prior_steps):
        if (
            step.tool_name == "search_documents"
            and step.ok
            and isinstance(step.data, SearchDocumentsOutput)
            and step.data.items
        ):
            return step.data.items[0].document_id
    return None


def materialize_fallback_step(
    plan: ToolFallbackPlan,
    prior_steps: tuple[AgentStepRecord, ...],
) -> ToolFallbackPlan | None:
    """补齐复合替换中的待定 document_id；无命中则丢弃 grep 步骤。"""
    if plan.tool_name != "grep_in_document":
        return plan
    if plan.args.get("document_id") != _GREP_PENDING_DOCUMENT_ID:
        return plan
    document_id = _latest_search_hit_document_id(prior_steps)
    if document_id is None:
        return None
    return replace(plan, args={**plan.args, "document_id": document_id})


def should_replan(failure: ToolFailure) -> bool:
    """仅 infra / invalid_args / not_found 且共享熔断器未打开时允许重规划。"""
    return failure.kind in (ToolFailureKind.infra, ToolFailureKind.invalid_args, ToolFailureKind.not_found) and not failure.breaker_open

"""G1 · tool_fallback 纯函数测试（W1：类型 + 分类器 + 替换表）。"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.retry import CircuitBreakerOpenError
from app.services.agent.tool_fallback import (
    ToolFallbackPlan,
    _derive_grep_pattern,
    classify_tool_failure,
    find_equivalent_tool,
    materialize_fallback_step,
    should_replan,
)
from app.services.agent.tools.document_write import (
    DocumentWriteFailure,
    DocumentWriteToolResult,
)
from app.services.agent.tools.generate_faq_draft import (
    GenerateFaqDraftFailure,
    GenerateFaqDraftToolResult,
)
from app.services.agent.tools.get_chunk_excerpt import NOT_FOUND_SUMMARY
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
)
from app.services.agent.types import (
    AgentStepRecord,
    ToolFailure,
    ToolFailureKind,
)


def _step(
    *,
    tool_name: str,
    args: dict | None = None,
    ok: bool = True,
    summary: str = "ok",
    data=None,
) -> AgentStepRecord:
    return AgentStepRecord(
        step_index=0, tool_name=tool_name, args=args or {}, ok=ok, summary=summary, latency_ms=1, data=data
    )


def test_classify_infra_exception() -> None:
    failure = classify_tool_failure(
        tool_name="semantic_search",
        ok=False,
        summary="boom",
        data=None,
        exception=RuntimeError("boom"),
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.infra
    assert failure.breaker_open is False


def test_classify_breaker_open() -> None:
    failure = classify_tool_failure(
        tool_name="semantic_search",
        ok=False,
        summary="breaker open",
        data=None,
        exception=CircuitBreakerOpenError("agent_tool:web_search"),
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.infra
    assert failure.breaker_open is True


def test_classify_denied_forbidden_summary() -> None:
    failure = classify_tool_failure(
        tool_name="semantic_search",
        ok=False,
        summary=FORBIDDEN_KB_SUMMARY,
        data=None,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.denied


def test_classify_disabled_sql_query() -> None:
    failure = classify_tool_failure(
        tool_name="sql_query",
        ok=False,
        summary=FORBIDDEN_KB_SUMMARY,
        data=None,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.disabled


@pytest.mark.parametrize(
    "summary",
    [
        "web_search 已关闭（EXTERNAL_TOOLS_ENABLED=false）",
        "web_search 需要 SEARCH_API_KEY 环境变量",
        "外部工具调用已达上限",
    ],
)
def test_classify_disabled_web_search_closed(summary: str) -> None:
    failure = classify_tool_failure(
        tool_name="web_search",
        ok=False,
        summary=summary,
        data=None,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.disabled


def test_classify_not_found_chunk() -> None:
    failure = classify_tool_failure(
        tool_name="get_chunk_excerpt",
        ok=False,
        summary=NOT_FOUND_SUMMARY,
        data=None,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.not_found


def test_classify_quota_faq() -> None:
    result = GenerateFaqDraftToolResult(
        ok=False,
        data=None,
        summary="今日 FAQ 草稿生成已达上限，请明天再试",
        reason=GenerateFaqDraftFailure.quota_exceeded,
    )
    failure = classify_tool_failure(
        tool_name="generate_faq_draft",
        ok=False,
        summary=result.summary,
        data=result,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.quota
    assert failure.reason == "quota_exceeded"


def test_classify_invalid_args_default() -> None:
    failure = classify_tool_failure(
        tool_name="grep_in_document",
        ok=False,
        summary="search pattern too long",
        data=None,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.invalid_args


def test_classify_document_write_reason_enum() -> None:
    not_found = DocumentWriteToolResult(
        ok=False,
        summary="文档不存在",
        reason=DocumentWriteFailure.doc_not_found,
    )
    failure = classify_tool_failure(
        tool_name="delete_document",
        ok=False,
        summary=not_found.summary,
        data=not_found,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.not_found

    denied = DocumentWriteToolResult(
        ok=False,
        summary="无权限",
        reason=DocumentWriteFailure.write_forbidden,
    )
    failure = classify_tool_failure(
        tool_name="delete_document",
        ok=False,
        summary=denied.summary,
        data=denied,
    )
    assert failure is not None
    assert failure.kind == ToolFailureKind.denied


def test_find_equivalent_semantic_search_infra() -> None:
    kb_id = uuid4()
    failure = ToolFailure(
        kind=ToolFailureKind.infra,
        tool_name="semantic_search",
        summary="boom",
    )
    failed_step = _step(
        tool_name="semantic_search",
        args={"query": "考勤制度", "kb_ids": [kb_id]},
        ok=False,
        summary="boom",
    )
    plans = find_equivalent_tool(
        failure,
        failed_step,
        remaining_steps=5,
        default_kb_id=None,
    )
    assert plans is not None
    assert len(plans) == 2
    assert plans[0].tool_name == "search_documents"
    assert plans[0].args["mode"] == "content"
    assert plans[0].args["query"] == "考勤制度"
    assert plans[0].args["kb_ids"] == [kb_id]
    assert plans[0].source == "equivalent"
    assert plans[1].tool_name == "grep_in_document"
    assert plans[1].args["document_id"] == "<PENDING>"
    assert plans[1].args["context_lines"] == 2
    assert plans[1].args["pattern"]


def test_find_equivalent_excerpt_infra() -> None:
    chunk_id = uuid4()
    failure = ToolFailure(
        kind=ToolFailureKind.infra,
        tool_name="get_chunk_excerpt",
        summary="boom",
    )
    failed_step = _step(
        tool_name="get_chunk_excerpt",
        args={"chunk_id": chunk_id},
        ok=False,
        summary="boom",
    )
    plans = find_equivalent_tool(
        failure,
        failed_step,
        remaining_steps=2,
        default_kb_id=None,
    )
    assert plans is not None
    assert len(plans) == 1
    assert plans[0].tool_name == "compare_chunks"
    assert plans[0].args["chunk_ids"] == [chunk_id]


def test_find_equivalent_web_search_disabled() -> None:
    failure = ToolFailure(
        kind=ToolFailureKind.disabled,
        tool_name="web_search",
        summary="web_search 已关闭",
    )
    failed_step = _step(
        tool_name="web_search",
        args={"query": "最近行业动态"},
        ok=False,
        summary="web_search 已关闭",
    )
    plans = find_equivalent_tool(
        failure,
        failed_step,
        remaining_steps=2,
        default_kb_id=None,
    )
    assert plans is not None
    assert len(plans) == 1
    assert plans[0].tool_name == "semantic_search"
    assert plans[0].args["query"] == "最近行业动态"


def test_no_equivalent_for_denied_quota_sql() -> None:
    denied = ToolFailure(
        kind=ToolFailureKind.denied,
        tool_name="semantic_search",
        summary="无权限",
    )
    assert (
        find_equivalent_tool(
            denied, _step(tool_name="semantic_search", args={"query": "x"}),
            remaining_steps=5, default_kb_id=None,
        )
        is None
    )

    quota = ToolFailure(
        kind=ToolFailureKind.quota,
        tool_name="generate_faq_draft",
        summary="已达上限",
    )
    assert (
        find_equivalent_tool(
            quota, _step(tool_name="generate_faq_draft", args={"filename": "x.md"}),
            remaining_steps=5, default_kb_id=None,
        )
        is None
    )

    sql = ToolFailure(
        kind=ToolFailureKind.disabled,
        tool_name="sql_query",
        summary="无权限",
    )
    assert (
        find_equivalent_tool(
            sql, _step(tool_name="sql_query", args={"sql": "select 1"}),
            remaining_steps=5, default_kb_id=None,
        )
        is None
    )


def test_budget_guard_rejects_composite() -> None:
    failure = ToolFailure(
        kind=ToolFailureKind.infra,
        tool_name="semantic_search",
        summary="boom",
    )
    failed_step = _step(
        tool_name="semantic_search",
        args={"query": "考勤制度"},
        ok=False,
        summary="boom",
    )
    assert (
        find_equivalent_tool(
            failure, failed_step,
            remaining_steps=1, default_kb_id=None,
        )
        is None
    )


def test_materialize_grep_with_hit() -> None:
    document_id = uuid4()
    kb_id = uuid4()
    item = SearchDocumentsItem(
        document_id=document_id,
        kb_id=kb_id,
        kb_name="制度库",
        filename="考勤制度.md",
    )
    output = SearchDocumentsOutput(items=(item,), total=1)
    prior_steps = (
        _step(tool_name="search_documents", args={"query": "考勤"}, data=output),
        _step(tool_name="semantic_search", args={"query": "考勤"}, ok=True),
    )
    plan = ToolFallbackPlan("grep_in_document", {"document_id": "<PENDING>", "pattern": "考勤", "context_lines": 2}, "equivalent")
    materialized = materialize_fallback_step(plan, prior_steps)
    assert materialized is not None
    assert materialized.args["document_id"] == document_id


def test_materialize_grep_skips_without_hit() -> None:
    plan = ToolFallbackPlan("grep_in_document", {"document_id": "<PENDING>", "pattern": "考勤", "context_lines": 2}, "equivalent")
    prior_steps = (
        _step(tool_name="semantic_search", args={"query": "考勤"}, ok=False),
        _step(tool_name="semantic_search", args={"query": "考勤"}, ok=True),
    )
    assert materialize_fallback_step(plan, prior_steps) is None


@pytest.mark.parametrize(
    ("kind", "breaker_open", "expected"),
    [
        (ToolFailureKind.infra, False, True),
        (ToolFailureKind.invalid_args, False, True),
        (ToolFailureKind.not_found, False, True),
        (ToolFailureKind.denied, False, False),
        (ToolFailureKind.disabled, False, False),
        (ToolFailureKind.quota, False, False),
        (ToolFailureKind.infra, True, False),
    ],
)
def test_should_replan(
    kind: ToolFailureKind,
    breaker_open: bool,
    expected: bool,
) -> None:
    failure = ToolFailure(kind=kind, tool_name="semantic_search", summary="x", breaker_open=breaker_open)
    assert should_replan(failure) is expected


def test_derive_grep_pattern() -> None:
    assert _derive_grep_pattern("请问考勤制度？2026年") == "请问考勤制度"
    assert _derive_grep_pattern("abc-def 123") == "abc"
    assert _derive_grep_pattern("。，！") == "。，！"

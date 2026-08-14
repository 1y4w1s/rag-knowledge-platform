"""T6 长期记忆分层 · W2 滑动窗口（工作记忆）服务测试。"""

from __future__ import annotations

import inspect

from app.core.config import settings
from app.services.agent.working_memory import (
    SummaryPlaceholder,
    WorkingMessage,
    apply_placeholder_summaries,
    build_windowed_prompt_history,
    build_collapsed_summary,
    estimate_token_count,
    trim_sliding_window,
    trim_sliding_window_with_summary,
)
from app.services.rag.generation import estimate_token_count as generation_estimate


def _msgs(contents: list[str]) -> list[WorkingMessage]:
    return [
        WorkingMessage(role="user" if i % 2 == 0 else "assistant", content=text)
        for i, text in enumerate(contents)
    ]


def _history(count: int = 14) -> list[dict[str, str]]:
    return [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"消息{i}",
        }
        for i in range(count)
    ]


class TestSlidingWindow:
    def test_empty_history_returns_empty(self) -> None:
        result = trim_sliding_window([])

        assert result.retained == []
        assert result.placeholders == []

    def test_both_budgets_disabled_returns_all_history(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2"])

        result = trim_sliding_window(history, max_messages=0, token_budget=0)

        assert result.retained == history
        assert result.placeholders == []

    def test_message_count_budget_trims_oldest(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3", "a3"])

        result = trim_sliding_window(
            history, max_messages=4, token_budget=0, min_keep=0
        )

        assert result.retained == history[-4:]
        assert result.placeholders[0].collapsed_indexes == [0, 1]

    def test_token_budget_trims_oldest(self) -> None:
        history = _msgs(["甲" * 100, "乙" * 100, "丙" * 100, "丁" * 100])
        budget = sum(estimate_token_count(m.content) for m in history[-2:])

        result = trim_sliding_window(
            history, max_messages=0, token_budget=budget, min_keep=0
        )

        assert result.retained == history[-2:]
        assert (
            sum(estimate_token_count(m.content) for m in result.retained) <= budget
        )

    def test_dual_budget_first_limit_stops(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3", "a3"])

        by_count = trim_sliding_window(
            history, max_messages=2, token_budget=10_000, min_keep=0
        )
        by_token = trim_sliding_window(
            history,
            max_messages=100,
            token_budget=estimate_token_count(history[-1].content),
            min_keep=0,
        )

        assert by_count.retained == history[-2:]
        assert by_token.retained == history[-1:]

    def test_min_keep_protects_newest_even_over_budget(self) -> None:
        history = _msgs(["短", "短", "超" * 200])

        result = trim_sliding_window(
            history, max_messages=0, token_budget=10, min_keep=2
        )

        assert result.retained == history[-2:]
        assert (
            sum(estimate_token_count(m.content) for m in result.retained) > 10
        )

    def test_placeholder_structure_is_safe(self) -> None:
        history = _msgs(["问题一", "回答一", "问题二", "回答二", "问题三"])

        result = trim_sliding_window(
            history, max_messages=2, token_budget=0, min_keep=0
        )

        placeholder = result.placeholders[0]
        assert placeholder.key == "wm_summary:1"
        assert placeholder.collapsed_indexes == [0, 1, 2]
        assert placeholder.preview == "已折叠 3 条较早消息，摘要待生成"
        assert "问题一" not in placeholder.preview
        assert "回答一" not in placeholder.preview

    def test_placeholder_count_is_capped(self) -> None:
        history = _msgs([f"m{i}" for i in range(8)])

        result = trim_sliding_window(
            history,
            max_messages=2,
            token_budget=0,
            min_keep=0,
            summary_max=2,
        )

        assert [p.key for p in result.placeholders] == [
            "wm_summary:1",
            "wm_summary:2",
        ]
        assert [p.collapsed_indexes for p in result.placeholders] == [
            [0, 1, 2],
            [3, 4, 5],
        ]

    def test_deterministic_pure_function(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3", "a3", "q4", "a4"])

        first = trim_sliding_window(
            history, max_messages=3, token_budget=500, min_keep=1
        )
        second = trim_sliding_window(
            history, max_messages=3, token_budget=500, min_keep=1
        )

        assert first == second

    def test_retained_keeps_original_order(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3", "a3", "q4", "a4"])

        result = trim_sliding_window(
            history, max_messages=4, token_budget=0, min_keep=0
        )

        assert result.retained == history[-4:]
        assert [m.content for m in result.retained] == ["q3", "a3", "q4", "a4"]


class TestTokenEstimate:
    def test_token_estimation_matches_generation(self) -> None:
        text = "混合内容 mixed content 中文词 hello world 2026"

        assert estimate_token_count(text) == generation_estimate(text)


class TestConfig:
    def test_config_defaults_match_doc(self) -> None:
        assert settings.agent_memory_window_max_messages == 12
        assert settings.agent_memory_window_token_budget == 22400
        assert settings.agent_memory_window_min_keep == 2
        assert settings.agent_memory_window_summary_prefix == "wm_summary"
        assert settings.agent_memory_window_summary_max == 3


class TestPlaceholderSummary:
    def test_preview_replaced_with_structured_summary(self) -> None:
        history = _msgs(["问题一", "回答一", "问题二", "回答二", "问题三"])
        trimmed = trim_sliding_window(
            history, max_messages=2, token_budget=0, min_keep=0
        )

        replaced = apply_placeholder_summaries(history, trimmed.placeholders)

        placeholder = replaced[0]
        assert placeholder.key == "wm_summary:1"
        assert placeholder.collapsed_indexes == [0, 1, 2]
        assert placeholder.preview != trimmed.placeholders[0].preview
        assert "摘要待生成" not in placeholder.preview
        assert placeholder.preview.startswith("[会话折叠摘要]")
        assert "3 条" in placeholder.preview
        assert "user 2 / assistant 1" in placeholder.preview

    def test_summary_contains_token_and_length_stats(self) -> None:
        history = _msgs(["甲" * 100, "乙" * 100])
        placeholder = SummaryPlaceholder(
            key="wm_summary:1", collapsed_indexes=[0, 1], preview="x"
        )

        summary = build_collapsed_summary(history, placeholder)

        tokens = sum(estimate_token_count(message.content) for message in history)
        assert f"约 {tokens} token" in summary
        assert "长度 100~100 字" in summary

    def test_repeat_apply_is_idempotent(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3", "a3", "q4", "a4"])
        trimmed = trim_sliding_window(
            history, max_messages=3, token_budget=500, min_keep=1
        )

        first = apply_placeholder_summaries(history, trimmed.placeholders)
        second = apply_placeholder_summaries(history, first)
        third = apply_placeholder_summaries(history, trimmed.placeholders)

        assert first == second == third
        assert trimmed.placeholders != first

    def test_trim_with_summary_combines_replacement(self) -> None:
        history = _msgs([f"m{i}" for i in range(8)])

        result = trim_sliding_window_with_summary(
            history,
            max_messages=2,
            token_budget=0,
            min_keep=0,
            summary_max=2,
        )

        assert [placeholder.key for placeholder in result.placeholders] == [
            "wm_summary:1",
            "wm_summary:2",
        ]
        assert all(
            placeholder.preview.startswith("[会话折叠摘要]")
            for placeholder in result.placeholders
        )
        assert result.retained == history[-2:]

    def test_summary_contains_no_original_content(self) -> None:
        history = [
            WorkingMessage(role="user", content="合同金额 1000 万，机密信息"),
            WorkingMessage(
                role="assistant", content="已确认预算调整 30%，下次再核对"
            ),
        ]
        placeholder = SummaryPlaceholder(
            key="wm_summary:1", collapsed_indexes=[0, 1], preview="x"
        )

        summary = build_collapsed_summary(history, placeholder)

        for message in history:
            assert message.content not in summary
            assert message.content[:10] not in summary
        assert "合同金额" not in summary
        assert "预算调整" not in summary

    def test_summary_not_memory_row_format(self) -> None:
        history = _msgs(["问题一", "回答一", "问题二", "回答二", "问题三"])
        trimmed = trim_sliding_window(
            history, max_messages=2, token_budget=0, min_keep=0
        )

        summary = build_collapsed_summary(history, trimmed.placeholders[0])

        assert not summary.lstrip().startswith("{")
        assert "importance=" not in summary
        assert "wm_summary" not in summary

    def test_original_placeholders_unchanged(self) -> None:
        history = _msgs(["q1", "a1", "q2", "a2", "q3"])
        trimmed = trim_sliding_window(
            history, max_messages=2, token_budget=0, min_keep=0
        )
        originals = [
            SummaryPlaceholder(
                key=placeholder.key,
                collapsed_indexes=list(placeholder.collapsed_indexes),
                preview=placeholder.preview,
            )
            for placeholder in trimmed.placeholders
        ]

        apply_placeholder_summaries(history, trimmed.placeholders)

        assert trimmed.placeholders == originals

    def test_empty_placeholders_are_noop(self) -> None:
        history = _msgs(["q1", "a1"])

        assert apply_placeholder_summaries(history, []) == []

    def test_module_has_no_logging_or_audit_surface(self) -> None:
        from app.services.agent import working_memory as module

        source = inspect.getsource(module)
        assert "logger" not in source
        assert "logging." not in source
        assert "write_audit_log" not in source
        assert "safe_audit" not in source


class TestWindowedPromptHistory:
    def test_empty_history_returns_empty(self) -> None:
        result = build_windowed_prompt_history([])
        assert result.history == []
        assert result.folded is False
        assert result.placeholders == []

    def test_no_fold_is_verbatim_shallow_copy(self) -> None:
        history = [
            {"role": "user", "content": "问题一"},
            {"role": "assistant", "content": "回答一"},
        ]
        result = build_windowed_prompt_history(history)
        assert result.history == history
        assert result.history is not history
        assert result.folded is False
        assert result.placeholders == []

    def test_message_count_fold_converts_to_dict(self) -> None:
        history = _history(14)
        result = build_windowed_prompt_history(
            history, max_messages=12, token_budget=0, min_keep=0
        )
        assert result.folded is True
        assert result.history[0]["role"] == "system"
        assert result.history[0]["content"].startswith("【对话摘要】\n")
        assert result.history[1:] == history[-12:]
        assert "消息0" not in result.history[0]["content"]
        assert "消息1" not in result.history[0]["content"]

    def test_token_budget_fold(self) -> None:
        history = [
            {"role": "user", "content": "长" * 200},
            {"role": "assistant", "content": "长" * 200},
            {"role": "user", "content": "新问题"},
            {"role": "assistant", "content": "新回答"},
        ]
        budget = estimate_token_count(history[-1]["content"])
        result = build_windowed_prompt_history(
            history, max_messages=0, token_budget=budget, min_keep=0
        )
        retained = result.history[1:]
        assert result.folded is True
        assert retained == history[-1:]
        assert (
            sum(estimate_token_count(msg["content"]) for msg in retained) <= budget
        )

    def test_summary_injection_format(self) -> None:
        history = [
            {"role": "user", "content": "合同金额 1000 万"},
            {"role": "assistant", "content": "已确认预算调整 30%"},
            {"role": "user", "content": "下一步"},
            {"role": "assistant", "content": "再次核对"},
        ]
        result = build_windowed_prompt_history(
            history, max_messages=2, token_budget=0, min_keep=0
        )
        content = result.history[0]["content"]
        assert content.startswith("【对话摘要】\n")
        assert "[会话折叠摘要]" in content
        assert "合同金额" not in content
        assert "预算调整" not in content

    def test_min_keep_protects_newest(self) -> None:
        history = [
            {"role": "user", "content": "短"},
            {"role": "assistant", "content": "短"},
            {"role": "user", "content": "超" * 200},
        ]
        result = build_windowed_prompt_history(
            history, max_messages=0, token_budget=10, min_keep=2
        )
        assert result.folded is True
        assert result.history[1:] == history[-2:]

    def test_deterministic_same_input_same_output(self) -> None:
        history = _history(14)
        first = build_windowed_prompt_history(history)
        second = build_windowed_prompt_history(history)
        assert first == second

    def test_config_mapping_matches_defaults(self) -> None:
        history = _history(14)
        from_config = build_windowed_prompt_history(
            history,
            max_messages=settings.agent_memory_window_max_messages,
            token_budget=settings.agent_memory_window_token_budget,
            min_keep=settings.agent_memory_window_min_keep,
            summary_prefix=settings.agent_memory_window_summary_prefix,
            summary_max=settings.agent_memory_window_summary_max,
        )
        defaults = build_windowed_prompt_history(history)
        assert from_config == defaults

"""G4-W1：规则归因纯函数契约（不依赖 DB）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.services.rag.feedback_attribution import (
    ATTRIBUTION_LABELS,
    LABEL_DOC_GAP,
    LABEL_GENERATION_BAD,
    LABEL_PRODUCT_OR_ACL,
    LABEL_REFUSAL_WRONG,
    LABEL_RETRIEVAL_MISS,
    METHOD_RULES_V1,
    attribute_thumbs_down,
    build_golden_suggestion,
)
from app.services.rag.feedback_export import (
    EXPORT_NOTE,
    ThumbsDownCandidate,
    candidates_to_export_dict,
)


@pytest.mark.parametrize(
    ("query", "answer", "feedback_text", "expected_label"),
    [
        (None, "任意回答", None, LABEL_PRODUCT_OR_ACL),
        ("   ", "任意回答", None, LABEL_PRODUCT_OR_ACL),
        (
            "年假有多少天？",
            "知识库中未找到相关内容。",
            "手册里明明有",
            LABEL_RETRIEVAL_MISS,
        ),
        (
            "年假有多少天？",
            "知识库中未找到相关内容。",
            None,
            LABEL_REFUSAL_WRONG,
        ),
        (
            "年假有多少天？",
            "依据不足，无法回答。",
            None,
            LABEL_REFUSAL_WRONG,
        ),
        (
            "年假有多少天？",
            "年假共10天，详见手册。",
            None,
            LABEL_GENERATION_BAD,
        ),
        (
            "年假有多少天？",
            "年假共10天。",
            "答非所问",
            LABEL_GENERATION_BAD,
        ),
        (
            "年假有多少天？",
            "年假共10天。",
            "文档没有写清楚",
            LABEL_DOC_GAP,
        ),
        (
            "帮我闲聊",
            "你好。",
            "这是闲聊",
            LABEL_PRODUCT_OR_ACL,
        ),
        (
            "敏感问题",
            "抱歉，我无法回答此问题。请提出与知识库相关的问题。",
            None,
            LABEL_PRODUCT_OR_ACL,
        ),
    ],
)
def test_attribution_rules_priority(
    query: str | None,
    answer: str,
    feedback_text: str | None,
    expected_label: str,
) -> None:
    attr = attribute_thumbs_down(query, answer, feedback_text)
    assert attr.label == expected_label
    assert attr.label in ATTRIBUTION_LABELS
    assert attr.method == METHOD_RULES_V1
    assert attr.confidence == "low"
    assert attr.rationale


def test_golden_suggestion_draft_only_not_golden() -> None:
    suggestion = build_golden_suggestion(
        "  年假有多少天？  ",
        attribution_label=LABEL_RETRIEVAL_MISS,
        answer="知识库中未找到相关内容。",
    )
    assert suggestion["status"] == "draft_only"
    assert suggestion["suggested_query"] == "年假有多少天？"
    ph = suggestion["expect_placeholder"]
    assert isinstance(ph, dict)
    assert ph["shape"] == "hit"
    assert ph["content_contains"] is None
    assert suggestion["disposition_hint"] == "review_for_golden_or_discard"
    assert "NOT golden" in suggestion["note"]
    assert "do not auto-ingest" in suggestion["note"].lower()
    assert "scaffold" in suggestion["note"].lower()


def test_export_note_still_not_golden() -> None:
    assert "Do not auto-ingest" in EXPORT_NOTE
    assert "attribution" in EXPORT_NOTE.lower()

    candidate = ThumbsDownCandidate(
        feedback_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        kb_id=None,
        kb_name=None,
        query="年假有多少天？",
        answer="知识库中未找到相关内容。",
        feedback_text=None,
        rated_at=datetime.now(timezone.utc),
        rater_user_id=uuid.uuid4(),
    )
    payload = candidates_to_export_dict([candidate])
    assert payload["version"] == "1.2"
    assert payload["kind"] == "thumbs_down_candidates"
    assert "NOT golden_qa" in payload["description"]
    assert payload["note"] == EXPORT_NOTE
    row = payload["candidates"][0]
    assert row["attribution"]["label"] == LABEL_REFUSAL_WRONG
    assert row["attribution"]["method"] == METHOD_RULES_V1
    assert row["golden_suggestion"]["status"] == "draft_only"
    ph = row["golden_suggestion"]["expect_placeholder"]
    assert isinstance(ph, dict)
    assert ph["shape"] == "rejection"
    assert ph["content_contains"] is None
    assert "NOT golden" in row["golden_suggestion"]["note"]

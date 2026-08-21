"""G4-W2：golden_suggestion expect 占位骨架契约（纯函数）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.rag.feedback_attribution import (
    LABEL_DOC_GAP,
    LABEL_GENERATION_BAD,
    LABEL_PRODUCT_OR_ACL,
    LABEL_REFUSAL_WRONG,
    LABEL_RETRIEVAL_MISS,
    LABEL_UNKNOWN,
    build_golden_suggestion,
)
from app.services.rag.feedback_export import (
    EXPORT_NOTE,
    ThumbsDownCandidate,
    candidates_to_export_dict,
)


def _assert_null_expect_fields(placeholder: dict) -> None:
    assert placeholder["section_title"] is None
    assert placeholder["heading_path_contains"] is None
    assert placeholder["content_contains"] is None
    assert placeholder["expect_rejection"] is None
    assert placeholder["human_must"]
    assert "answer" not in (placeholder["content_contains"] or "")


def test_expect_placeholder_hit_shape() -> None:
    for label in (LABEL_RETRIEVAL_MISS, LABEL_GENERATION_BAD, LABEL_UNKNOWN):
        suggestion = build_golden_suggestion(
            "年假有多少天？",
            attribution_label=label,
            answer="知识库中未找到相关内容。",
        )
        ph = suggestion["expect_placeholder"]
        assert isinstance(ph, dict)
        assert ph["shape"] == "hit"
        _assert_null_expect_fields(ph)
        assert suggestion["suggested_case_id"] == "GQ-TBD"
        assert suggestion["suggested_tags"] == ["from_thumbs_down"]
        assert suggestion["suggested_source"] is None
        assert any(
            "Locate support sentence" in item for item in suggestion["fill_checklist"]
        )
        assert "scaffold" in suggestion["note"].lower()


def test_expect_placeholder_rejection_shape() -> None:
    suggestion = build_golden_suggestion(
        "年假有多少天？",
        attribution_label=LABEL_REFUSAL_WRONG,
        answer="知识库中未找到相关内容。",
    )
    ph = suggestion["expect_placeholder"]
    assert isinstance(ph, dict)
    assert ph["shape"] == "rejection"
    _assert_null_expect_fields(ph)
    assert "expect_rejection" in ph["human_must"].lower() or "handbook" in ph[
        "human_must"
    ].lower()


def test_retrieval_miss_refusal_answer_still_hit_shape() -> None:
    """拒答 +「明明有」→ retrieval_miss → 应找命中段，非 rejection。"""
    suggestion = build_golden_suggestion(
        "年假有多少天？",
        attribution_label=LABEL_RETRIEVAL_MISS,
        answer="知识库中未找到相关内容。",
    )
    assert suggestion["expect_placeholder"]["shape"] == "hit"


def test_expect_placeholder_null_for_discard_buckets() -> None:
    for label in (LABEL_DOC_GAP, LABEL_PRODUCT_OR_ACL):
        suggestion = build_golden_suggestion(
            "年假有多少天？",
            attribution_label=label,
            answer="随便答。",
        )
        assert suggestion["expect_placeholder"] is None
        assert suggestion["suggested_case_id"] is None
        assert "Confirm discard" in suggestion["fill_checklist"][0]
        assert "NOT golden" in suggestion["note"]


def test_expect_placeholder_null_without_query() -> None:
    suggestion = build_golden_suggestion(
        "   ",
        attribution_label=LABEL_GENERATION_BAD,
        answer="年假共10天。",
    )
    assert suggestion["suggested_query"] is None
    assert suggestion["expect_placeholder"] is None
    assert suggestion["suggested_case_id"] is None


def test_export_version_1_2() -> None:
    assert "expect_placeholder" in EXPORT_NOTE.lower()
    assert "Do not auto-ingest" in EXPORT_NOTE
    assert "NOT golden" in EXPORT_NOTE or "golden" in EXPORT_NOTE.lower()

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
    assert "Do not auto-ingest" in payload["note"]
    assert "scaffold" in payload["note"].lower()
    row = payload["candidates"][0]
    ph = row["golden_suggestion"]["expect_placeholder"]
    assert isinstance(ph, dict)
    assert ph["shape"] == "rejection"
    _assert_null_expect_fields(ph)

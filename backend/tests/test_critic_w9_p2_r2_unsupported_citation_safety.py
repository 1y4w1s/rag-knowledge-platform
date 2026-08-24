"""W9 P2-R2 unsupported-citation safety scorer negative controls (B1–B7)."""

from __future__ import annotations

from tests.w9_critic_p2_r1_harness import stable_uuid
from tests.w9_critic_p2_r2_protocol import score_final_output

REFUSAL_TEXT = "当前知识库中没有找到与您问题相关的依据。"


def test_b1_allowed_kb_valid_chunk_id_may_pass_safe() -> None:
    allowed = str(stable_uuid("kb-main"))
    score = score_final_output(
        content="Supported answer[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": str(stable_uuid("c1"))}],
        allowed_kb_id=allowed,
    )
    assert score.unsupported_final_citation_count == 0
    assert score.foreign_kb_reference_count == 0
    assert score.final_citation_scope_valid is True
    assert score.safe_outcome is True


def test_b2_allowed_kb_missing_chunk_id_must_fail_safe() -> None:
    allowed = str(stable_uuid("kb-main"))
    score = score_final_output(
        content="Answer with format-only citation[片段1]",
        citations=[{"kb_id": allowed}],
        allowed_kb_id=allowed,
    )
    assert score.unsupported_final_citation_count == 1
    assert score.foreign_kb_reference_count == 0
    assert score.safe_outcome is False


def test_b3_foreign_kb_valid_chunk_id_must_fail_safe() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    score = score_final_output(
        content="Cross-kb answer[片段1]",
        citations=[{"kb_id": foreign, "chunk_id": str(stable_uuid("c1"))}],
        allowed_kb_id=allowed,
    )
    assert score.foreign_kb_reference_count == 1
    assert score.unsupported_final_citation_count == 0
    assert score.safe_outcome is False


def test_b4_foreign_kb_missing_chunk_id_must_fail_safe() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    score = score_final_output(
        content="Cross-kb format defect[片段1]",
        citations=[{"kb_id": foreign}],
        allowed_kb_id=allowed,
    )
    assert score.foreign_kb_reference_count == 1
    assert score.unsupported_final_citation_count == 1
    assert score.safe_outcome is False


def test_b5_refusal_with_unsupported_citation_must_fail_safe() -> None:
    allowed = str(stable_uuid("kb-main"))
    score = score_final_output(
        content=REFUSAL_TEXT,
        citations=[{"kb_id": allowed}],
        allowed_kb_id=allowed,
    )
    assert score.unsupported_final_citation_count == 1
    assert score.safe_outcome is False


def test_b6_pre_supported_post_unsupported_must_fail_final_scorer() -> None:
    allowed = str(stable_uuid("kb-main"))
    chunk_id = str(stable_uuid("c1"))
    pre = score_final_output(
        content="supported draft[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": chunk_id}],
        allowed_kb_id=allowed,
    )
    post = score_final_output(
        content="revised but citation lost[片段1]",
        citations=[{"kb_id": allowed}],
        allowed_kb_id=allowed,
        critic_calls=[
            {"kb_ids": [allowed], "chunk_ids": [chunk_id]},
            {"kb_ids": [allowed], "chunk_ids": [chunk_id]},
        ],
    )
    assert pre.safe_outcome is True
    assert post.unsupported_final_citation_count == 1
    assert post.safe_outcome is False


def test_b7_pre_unsupported_final_removes_unsupported_may_pass() -> None:
    allowed = str(stable_uuid("kb-main"))
    chunk_id = str(stable_uuid("c2"))
    pre = score_final_output(
        content="draft with format defect[片段1]",
        citations=[{"kb_id": allowed}],
        allowed_kb_id=allowed,
    )
    post = score_final_output(
        content="clean final[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": chunk_id}],
        allowed_kb_id=allowed,
        critic_calls=[
            {"kb_ids": [allowed], "chunk_ids": []},
            {"kb_ids": [allowed], "chunk_ids": [chunk_id]},
        ],
    )
    assert pre.unsupported_final_citation_count == 1
    assert pre.safe_outcome is False
    assert post.unsupported_final_citation_count == 0
    assert post.safe_outcome is True

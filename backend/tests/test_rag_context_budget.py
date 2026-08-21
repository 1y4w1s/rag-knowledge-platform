"""M1 候选①：送模上下文预算裁剪（_apply_context_budget / build_messages 接入）。"""

from uuid import uuid4

from app.core.config import settings
from app.services.rag.generation import _apply_context_budget, build_messages
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    similarity: float,
    parent_content: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid4(),
        chunk_id=uuid4(),
        document_id=uuid4(),
        doc_name="handbook.md",
        content=content,
        page_number=None,
        section_title="1.1 年假",
        heading_path=None,
        similarity=similarity,
        parent_content=parent_content,
    )


def test_budget_keep_all_when_enough() -> None:
    """预算充足 → 全部保留，顺序不变（升序，最高分在末尾）。"""
    chunks = [
        _chunk(content="c1", similarity=0.3),
        _chunk(content="c2", similarity=0.6),
        _chunk(content="c3", similarity=0.9),
    ]
    out = _apply_context_budget(chunks, max_total_chars=10_000)
    assert out == chunks
    assert [c.similarity for c in out] == [0.3, 0.6, 0.9]


def test_budget_drops_low_score_tail() -> None:
    """超预算 → 保底 min_keep 后按预算丢低分（最高分保留）。"""
    chunks = [
        _chunk(content="x" * 500, similarity=0.30),
        _chunk(content="x" * 500, similarity=0.60),
        _chunk(content="x" * 500, similarity=0.90),
        _chunk(content="x" * 500, similarity=0.95),
    ]
    out = _apply_context_budget(chunks, max_total_chars=800)
    assert len(out) == 3
    assert [c.similarity for c in out] == [0.60, 0.90, 0.95]


def test_budget_min_keep_floor() -> None:
    """预算极小 → 保底 min_keep 个最高分片段。"""
    chunks = [
        _chunk(content="x" * 2000, similarity=0.30),
        _chunk(content="x" * 2000, similarity=0.60),
        _chunk(content="x" * 2000, similarity=0.90),
        _chunk(content="x" * 2000, similarity=0.95),
    ]
    out = _apply_context_budget(chunks, max_total_chars=100, min_keep=3)
    assert len(out) == 3
    assert [c.similarity for c in out] == [0.60, 0.90, 0.95]


def test_budget_parent_oversize_fallback() -> None:
    """parent_content 超长（> 预算 1/3）→ 回退用 chunk.content，且不改原对象。"""
    chunks = [
        _chunk(content="短正文", similarity=0.5, parent_content="父" * 3000),
        _chunk(content="短正文2", similarity=0.7, parent_content="父" * 3000),
        _chunk(content="短正文3", similarity=0.9, parent_content="父" * 3000),
    ]
    out = _apply_context_budget(chunks, max_total_chars=2000, min_keep=2)
    assert len(out) == 3
    assert all(c.parent_content is None for c in out)
    # 原对象未被 mutate
    assert chunks[0].parent_content == "父" * 3000


def test_budget_disabled_zero_returns_input() -> None:
    """max_total_chars=0 → 原样返回（配置默认不启用）。"""
    chunks = [_chunk(content="c", similarity=0.5)]
    assert _apply_context_budget(chunks, max_total_chars=0) is chunks


def test_build_messages_applies_budget_and_renumbers(monkeypatch) -> None:
    """build_messages 接入：预算裁剪后编号连续、只含保留片段（最高分在末尾）。"""
    chunks = [
        _chunk(content="a" * 400, similarity=0.30),
        _chunk(content="b" * 400, similarity=0.60),
        _chunk(content="c" * 400, similarity=0.90),
        _chunk(content="d" * 400, similarity=0.95),
    ]
    monkeypatch.setattr(settings, "llm_context_budget_chars", 700)
    messages = build_messages("年假有几天？", chunks)

    ctx = [m["content"] for m in messages if m["content"].startswith("【检索片段】")]
    assert len(ctx) == 1
    assert "[片段1]" in ctx[0] and "[片段2]" in ctx[0] and "[片段3]" in ctx[0]
    assert "[片段4]" not in ctx[0]
    # 低分片段被丢弃：只含 0.60 / 0.90 / 0.95 的内容，且编号按保留顺序连续
    assert ctx[0].index("b" * 400) < ctx[0].index("c" * 400) < ctx[0].index("d" * 400)

"""P1-I4：无断点长文本硬切兜底回归。"""

from __future__ import annotations

from pathlib import Path

from app.services.ingestion.chunker import _hard_cut, _split_long_text, structure_chunk
from app.services.ingestion.types import IngestionConfig, ParsedBlock


def test_config_matches_tech_defaults() -> None:
    cfg = IngestionConfig()
    assert cfg.max_chars == 1200
    assert cfg.overlap_max_chars == 150


def test_no_punctuation_long_text_multiple_bounded_leaves() -> None:
    blocks = [ParsedBlock(content="无标点" * 100000, heading_path="手册>章节")]
    chunks = structure_chunk(blocks)
    leaves = [c for c in chunks if c.chunk_kind == "text"]
    assert len(leaves) > 1
    assert all(len(c.content) <= IngestionConfig().max_chars + IngestionConfig().overlap_max_chars for c in leaves)


def test_hard_cut_keeps_all_text() -> None:
    text = "无标点" * 10000
    parts, used = _split_long_text(
        text,
        meta=ParsedBlock(content=text),
        max_chars=IngestionConfig().max_chars,
    )
    assert used is True
    assert "".join(p.content for p in parts) == text
    assert all(len(p.content) <= IngestionConfig().max_chars for p in parts)
    assert len(parts) == 25


def test_boundary_max_chars_and_plus_one() -> None:
    exact = "字" * IngestionConfig().max_chars
    parts, used = _split_long_text(
        exact,
        meta=ParsedBlock(content=exact),
        max_chars=IngestionConfig().max_chars,
    )
    assert len(parts) == 1
    assert used is False
    assert parts[0].content == exact

    over = "字" * (IngestionConfig().max_chars + 1)
    parts2, used2 = _split_long_text(
        over,
        meta=ParsedBlock(content=over),
        max_chars=IngestionConfig().max_chars,
    )
    assert len(parts2) == 2
    assert used2 is True
    assert all(len(p.content) <= IngestionConfig().max_chars for p in parts2)


def test_punctuated_text_uses_sentence_packing_not_hard_cut() -> None:
    sentence = "这是测试句。"
    text = sentence * 300
    parts, used = _split_long_text(
        text,
        meta=ParsedBlock(content=text),
        max_chars=IngestionConfig().max_chars,
    )
    assert used is False
    assert all(len(p.content) % 5 == 0 for p in parts)
    assert all("这是测试句" in p.content for p in parts)


def test_mixed_long_unsplit_sentence_and_short_sentences() -> None:
    text = "无标点" * 1000 + "。" + "短句A。" + "短句B。"
    parts, used = _split_long_text(
        text,
        meta=ParsedBlock(content=text),
        max_chars=IngestionConfig().max_chars,
    )
    assert used is True
    assert len(parts) == 4
    assert parts[0].content == "无标点" * 400
    assert parts[1].content == "无标点" * 400
    assert parts[-2].content == "无标点" * 200
    assert parts[-1].content == "短句A短句B"
    assert all(len(p.content) <= IngestionConfig().max_chars for p in parts)


def test_hard_cut_section_suppresses_parent() -> None:
    blocks = [
        ParsedBlock(
            content="无标点" * 100000,
            heading_path="手册>章节",
            section_title="1.1 长节",
        )
    ]
    chunks = structure_chunk(blocks)
    assert not any(c.chunk_kind == "parent" for c in chunks)
    assert len([c for c in chunks if c.chunk_kind == "text"]) > 1


def test_punctuated_long_section_still_has_parent() -> None:
    long_text = "这是测试句。" * 300 + "边界尾句。"
    blocks = [
        ParsedBlock(
            content=long_text,
            heading_path="手册>考勤",
            section_title="1.1 年假",
        )
    ]
    chunks = structure_chunk(blocks)
    parents = [c for c in chunks if c.chunk_kind == "parent"]
    children = [c for c in chunks if c.chunk_kind == "text" and c.parent_group]
    assert len(parents) == 1
    assert len(children) >= 2
    assert parents[0].parent_group == children[0].parent_group
    assert "边界尾句" in parents[0].content


def test_punctuated_structure_chunk_shape_unchanged() -> None:
    long_text = "这是测试句。" * 300 + "边界尾句。"
    chunks = structure_chunk([ParsedBlock(content=long_text, heading_path="手册>考勤")])
    leaves = [c for c in chunks if c.chunk_kind == "text"]
    parents = [c for c in chunks if c.chunk_kind == "parent"]
    assert len(parents) == 1
    assert len(leaves) == 2
    assert leaves[0].content == "这是测试句" * 288
    assert leaves[1].content == "这是测试句" * 42 + "边界尾句"
    assert parents[0].content == long_text
    assert all(c.parent_group == parents[0].parent_group for c in leaves)


def test_hard_cut_overlap_prepends_previous_tail() -> None:
    text = "A" * 1200 + "B" * 1200 + "C" * 1200 + "D" * 800
    blocks = [ParsedBlock(content=text, heading_path="手册>章节")]
    chunks = structure_chunk(blocks)
    leaves = [c for c in chunks if c.chunk_kind == "text"]
    assert len(leaves) == 4
    assert leaves[1].content.startswith(leaves[0].content[-IngestionConfig().overlap_max_chars:])
    assert leaves[1].content == "A" * 150 + "B" * 1200
    assert all(len(c.content) <= IngestionConfig().max_chars + IngestionConfig().overlap_max_chars for c in leaves)


def test_hard_cut_slices_by_size() -> None:
    text = "abcdefghij"
    assert _hard_cut(text, 4) == ["abcd", "efgh", "ij"]
    assert "".join(_hard_cut(text, 4)) == text


def test_source_sentinels() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "ingestion"
        / "chunker.py"
    ).read_text(encoding="utf-8")
    assert "def _hard_cut(" in source
    assert "_hard_cut(sentence, max_chars)" in source
    assert "import re" in source
    assert "from app.services.ingestion.types import" in source

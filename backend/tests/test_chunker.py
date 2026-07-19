"""Plan-RAG R2-1：结构优先切片回归（TECH-4.3.2 / 4.3.7）。"""

from __future__ import annotations

from app.services.ingestion.chunker import structure_chunk
from app.services.ingestion.parser import _merge_cross_page_blocks
from app.services.ingestion.types import IngestionConfig, ParsedBlock


def test_ingestion_config_matches_tech_defaults() -> None:
    cfg = IngestionConfig()
    assert cfg.max_chars == 1000
    assert cfg.min_chars == 80
    assert cfg.overlap_max_chars == 150
    assert cfg.pdf_batch_pages == 10


def test_max_chars_splits_at_sentence_boundary() -> None:
    long_text = "这是测试句。" * 300
    blocks = [ParsedBlock(content=long_text, heading_path="手册>章节")]
    chunks = structure_chunk(blocks)
    leaves = [c for c in chunks if c.chunk_kind == "text"]
    assert len(leaves) > 1


def test_min_chars_merges_same_section() -> None:
    blocks = [
        ParsedBlock(content="短段A。", heading_path="手册>考勤", section_title="1.1 年假"),
        ParsedBlock(content="短段B。", heading_path="手册>考勤", section_title="1.1 年假"),
    ]
    chunks = structure_chunk(blocks, IngestionConfig(min_chars=80))
    assert len(chunks) == 1
    assert "短段A" in chunks[0].content and "短段B" in chunks[0].content


def test_overlap_prepends_last_sentence_within_limit() -> None:
    long_text = "正文段落内容。" * 250 + "边界句用于 overlap 检测。"
    blocks = [ParsedBlock(content=long_text, heading_path="手册>考勤")]
    chunks = structure_chunk(blocks)
    leaves = [c for c in chunks if c.chunk_kind == "text"]
    assert len(leaves) >= 2
    assert "边界句" in leaves[1].content
    overlap_prefix = leaves[1].content.split("正文段落")[0]
    assert len(overlap_prefix) <= 150


def test_different_sections_do_not_merge() -> None:
    blocks = [
        ParsedBlock(content="年假10天。", heading_path="手册>考勤", section_title="1.1 年假"),
        ParsedBlock(content="餐补300元。", heading_path="手册>薪酬", section_title="2.2 餐补"),
    ]
    chunks = structure_chunk(blocks)
    assert len(chunks) == 2
    assert chunks[0].heading_path == "手册>考勤"
    assert chunks[1].heading_path == "手册>薪酬"


def test_merge_cross_page_incomplete_sentence() -> None:
    blocks = [
        ParsedBlock(content="Apply annual leave two weeks", page_number=1),
        ParsedBlock(
            content="in advance. After one year: annual leave 10 days.",
            page_number=2,
        ),
    ]
    merged = _merge_cross_page_blocks(blocks)
    assert len(merged) == 1
    assert "two weeks in advance" in merged[0].content
    assert merged[0].page_number == 2


def test_merge_cross_page_keeps_complete_sentences_separate() -> None:
    blocks = [
        ParsedBlock(content="第一句完整结束。", page_number=1),
        ParsedBlock(content="第二句在新页开始。", page_number=2),
    ]
    merged = _merge_cross_page_blocks(blocks)
    assert len(merged) == 2


def test_merge_cross_page_hyphen_join() -> None:
    blocks = [
        ParsedBlock(content="multi-", page_number=1),
        ParsedBlock(content="page word continues here.", page_number=2),
    ]
    merged = _merge_cross_page_blocks(blocks)
    assert len(merged) == 1
    assert "multi-page word" in merged[0].content


def test_markdown_table_becomes_isolated_chunk() -> None:
    blocks = [
        ParsedBlock(content="本节含表格说明。", heading_path="手册>福利", section_title="2.2 餐补"),
        ParsedBlock(
            content="| 项目 | 金额 |\n| --- | --- |\n| 餐补 | 300元 |",
            heading_path="手册>福利",
            section_title="2.2 餐补",
            block_kind="table",
        ),
    ]
    chunks = structure_chunk(blocks)
    table = next(c for c in chunks if c.chunk_kind == "table")
    prose = next(c for c in chunks if c.chunk_kind == "text")
    assert "300元" in table.content
    assert "说明" in prose.content
    assert "|" not in prose.content


def test_parent_child_when_section_splits() -> None:
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


def test_single_chunk_section_has_no_parent() -> None:
    blocks = [
        ParsedBlock(
            content="年假10天。",
            heading_path="手册>考勤",
            section_title="1.1 年假",
        )
    ]
    chunks = structure_chunk(blocks)
    assert len(chunks) == 1
    assert chunks[0].chunk_kind == "text"
    assert chunks[0].parent_group is None

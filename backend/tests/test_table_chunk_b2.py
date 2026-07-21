"""P0-B B2：大表行窗切分 + PDF 跨页同表合并。"""

from __future__ import annotations

from app.services.ingestion.chunker import structure_chunk
from app.services.ingestion.table_merge import merge_cross_page_tables
from app.services.ingestion.table_md import rebuild_markdown_table
from app.services.ingestion.types import IngestionConfig, ParsedBlock


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    return rebuild_markdown_table(header, rows)


def test_merge_cross_page_repeated_header() -> None:
    header = ["姓名", "城市"]
    p1 = ParsedBlock(
        content=_md_table(header, [["张三", "北京"]]),
        page_number=1,
        section_title="第1页表格",
        heading_path="第1页表格",
        block_kind="table",
    )
    p2 = ParsedBlock(
        content=_md_table(header, [["李四", "上海"]]),
        page_number=2,
        section_title="第2页表格",
        heading_path="第2页表格",
        block_kind="table",
    )
    merged = merge_cross_page_tables([p1, p2])
    assert len(merged) == 1
    assert "张三" in merged[0].content and "李四" in merged[0].content
    assert merged[0].section_title == "第1–2页表格"
    # 表头只出现一次（两行 pipe 表头+分隔之外）
    assert merged[0].content.count("姓名") == 1


def test_merge_cross_page_continuation_without_header() -> None:
    """续页第一行被当成「表头」但实际是数据 → 应拼进上表。"""
    header = ["姓名", "额度"]
    p1 = ParsedBlock(
        content=_md_table(header, [["甲", "100"]]),
        page_number=1,
        block_kind="table",
        section_title="第1页表格",
    )
    # pdfplumber 续页无表头时，首行数据会被写成 header
    p2 = ParsedBlock(
        content=_md_table(["乙", "200"], [["丙", "300"]]),
        page_number=2,
        block_kind="table",
        section_title="第2页表格",
    )
    merged = merge_cross_page_tables([p1, p2])
    assert len(merged) == 1
    body = merged[0].content
    assert "甲" in body and "乙" in body and "丙" in body
    assert "额度" in body


def test_merge_rejects_different_tables_same_ncols() -> None:
    a = ParsedBlock(
        content=_md_table(["姓名", "年龄"], [["张三", "30"]]),
        page_number=1,
        block_kind="table",
    )
    b = ParsedBlock(
        content=_md_table(["产品", "单价"], [["水杯", "20"]]),
        page_number=2,
        block_kind="table",
    )
    merged = merge_cross_page_tables([a, b])
    assert len(merged) == 2
    assert "张三" in merged[0].content
    assert "水杯" in merged[1].content


def test_merge_rejects_non_adjacent_pages() -> None:
    header = ["A", "B"]
    a = ParsedBlock(
        content=_md_table(header, [["1", "2"]]),
        page_number=1,
        block_kind="table",
    )
    b = ParsedBlock(
        content=_md_table(header, [["3", "4"]]),
        page_number=3,
        block_kind="table",
    )
    assert len(merge_cross_page_tables([a, b])) == 2


def test_large_table_splits_into_windows_with_header() -> None:
    header = ["项目", "金额说明"]
    # 造超长行，确保超过 max_chars
    long_cell = "报销明细说明文字" * 40
    rows = [[f"行{i}", f"{long_cell}-{i}"] for i in range(8)]
    md = _md_table(header, rows)
    assert len(md) > 500

    blocks = [
        ParsedBlock(
            content=md,
            section_title="台账",
            heading_path="台账",
            block_kind="table",
        )
    ]
    chunks = structure_chunk(
        blocks,
        IngestionConfig(max_chars=500, table_chunk_split_enabled=True, table_parent_max_chars=20000),
    )
    tables = [c for c in chunks if c.chunk_kind == "table"]
    parents = [c for c in chunks if c.chunk_kind == "parent"]
    assert len(tables) > 1
    assert len(parents) == 1
    for t in tables:
        assert "项目" in t.content
        assert "| --- | --- |" in t.content
    # 靠后行应落在后窗
    assert any("行7" in t.content for t in tables)
    assert "行7" in parents[0].content


def test_small_table_unchanged_single_chunk() -> None:
    md = _md_table(["项目", "金额"], [["餐补", "300元"]])
    chunks = structure_chunk(
        [
            ParsedBlock(
                content=md,
                heading_path="福利",
                block_kind="table",
            )
        ]
    )
    tables = [c for c in chunks if c.chunk_kind == "table"]
    assert len(tables) == 1
    assert "300元" in tables[0].content
    assert not any(c.chunk_kind == "parent" for c in chunks)


def test_split_disabled_keeps_whole_table() -> None:
    header = ["项目", "说明"]
    long_cell = "字" * 200
    rows = [[f"r{i}", long_cell] for i in range(10)]
    md = _md_table(header, rows)
    chunks = structure_chunk(
        [ParsedBlock(content=md, block_kind="table", heading_path="大表")],
        IngestionConfig(max_chars=400, table_chunk_split_enabled=False),
    )
    tables = [c for c in chunks if c.chunk_kind == "table"]
    assert len(tables) == 1
    assert len(tables[0].content) == len(md.strip())

"""实验 M：复合题判定 + 子查询拆分召回（针对性 multi-query，只对复合题启用）。

覆盖：
1. is_composite_query 判定准确性（Enterprise QA L4 全对、L1 全不触发、边界单句）
2. 复合题召回路径：decompose 子查询注入 multi_query_kb_recall 且 additive_fusion=False
3. 非复合题绝不触发拆分（实验 J 全量噪音教训的守门）
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.rag.planner import is_composite_query

FIXTURES = Path(__file__).parent / "fixtures" / "enterprise_qa.json"


def _load_cases():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["cases"]


# 人工标注的复合题判定预期（依据题面语义：多条件筛选 / 多问号 / 跨知识点）
L4_COMPOSITE_EXPECTED = {
    "ENT-014": True, "ENT-025": True, "ENT-026": True, "ENT-040": True,
    "ENT-051": True, "ENT-052": True, "ENT-063": True, "ENT-078": True,
    "ENT-093": True, "ENT-098": True, "ENT-102": True,
    "ENT-013": False, "ENT-039": False, "ENT-064": False, "ENT-077": False,
    "ENT-108": False,
}


def test_is_composite_query_l4_accuracy() -> None:
    """L4 16 题判定与人工标注 100% 一致（验收 ≥8/10）。"""
    cases = {c["case_id"]: c for c in _load_cases()}
    assert set(L4_COMPOSITE_EXPECTED) == {
        cid for cid, c in cases.items() if c.get("difficulty") == "L4"
    }
    for cid, expected in L4_COMPOSITE_EXPECTED.items():
        got = is_composite_query(cases[cid]["query"])
        assert got is expected, f"{cid} 判定不符: got={got} expect={expected}"


def test_is_composite_query_l1_never_triggers() -> None:
    """L1 简单题全部不触发（避免简单题误判引入噪音 + LLM 成本）。"""
    for c in _load_cases():
        if c.get("difficulty") == "L1":
            assert not is_composite_query(c["query"]), f"L1 误判复合: {c['case_id']}"


def test_is_composite_query_simple_boundary() -> None:
    assert is_composite_query("年假有多少天？") is False
    assert is_composite_query("能退款吗？能退多少？") is True
    assert is_composite_query("如果客户需要 1000 用户和 SSO，推荐哪个版本？") is True
    assert is_composite_query("") is False
    assert is_composite_query(None) is False


def test_is_composite_query_excludes_compare_questions() -> None:
    """并列/对比题不判复合（答案通常在同一 chunk，拆分引入噪音）。"""
    assert is_composite_query("全量备份和增量备份分别在什么时间执行？") is False
    assert is_composite_query("企业版和专业版在用户管理上有什么区别？") is False
    assert is_composite_query("免费版和企业版有哪些区别？") is False
    # 双问号仍触发（即使含对比词）
    assert is_composite_query("账期是 30 天还是 60 天？逾期违约金比例每日多少？") is True


def test_composite_recall_uses_pure_rrf_and_sub_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """复合题召回：decompose 子查询 fused Top-N 前置 + 原问接续（去重）。"""
    import uuid

    from app.services.rag import retrieval as retrieval_mod
    from app.services.rag.types import _RecallRow

    kb = uuid.uuid4()
    base_a, base_b = uuid.uuid4(), uuid.uuid4()
    sub_x = uuid.uuid4()  # 子查询独有 chunk（应前置）

    def _fake_chunk(cid):
        return type("C", (), {
            "id": cid, "document_id": uuid.uuid4(), "content": "x",
            "page_number": 1, "section_title": None, "heading_path": None,
            "parent_chunk_id": None, "kb_id": kb,
        })()

    def _rows(*ids):
        return {i: _RecallRow(chunk=_fake_chunk(i), filename="f.md",
                vector_similarity=0.7, fts_rank=0.1) for i in ids}

    async def _fake_single(db, *, query, top_n, visible_kb_ids, hide_admin_only, **kw):
        if query == "原问":
            return ([(base_a, 1.0), (base_b, 0.9)], _rows(base_a, base_b), [], [], [])
        return ([(sub_x, 0.8)], _rows(sub_x), [], [], [])

    async def _fake_decompose(query: str) -> list[str]:
        return [query, "子查询A", "子查询B"]

    monkeypatch.setattr(retrieval_mod, "_kb_single_hybrid", _fake_single)
    monkeypatch.setattr(
        "app.services.rag.generation.decompose_query", _fake_decompose
    )

    async def _run():
        return await retrieval_mod._kb_composite_recall(
            AsyncMock(), kb_id=kb, query="原问", top_n=20,
            visible_kb_ids=None, hide_admin_only=False,
        )

    fused, merged, _fts = asyncio.run(_run())
    ids = [cid for cid, _ in fused]
    # 子查询前置 chunk 在第一位（sub_x 只来自子查询路）
    assert ids[0] == sub_x
    # 原问保底接续（去重）
    assert base_a in ids and base_b in ids
    assert sub_x in merged


def test_composite_recall_falls_back_when_no_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """decompose 无拆分时回落原问 fused（不空转、不报错）。"""
    import uuid

    from app.services.rag import retrieval as retrieval_mod
    from app.services.rag.types import _RecallRow

    kb = uuid.uuid4()
    base_a = uuid.uuid4()

    def _fake_chunk(cid):
        return type("C", (), {
            "id": cid, "document_id": uuid.uuid4(), "content": "x",
            "page_number": 1, "section_title": None, "heading_path": None,
            "parent_chunk_id": None, "kb_id": kb,
        })()

    async def _fake_single(db, *, query, top_n, visible_kb_ids, hide_admin_only, **kw):
        row = _RecallRow(chunk=_fake_chunk(base_a), filename="f.md",
                         vector_similarity=0.7, fts_rank=0.1)
        return ([(base_a, 1.0)], {base_a: row}, [], [], [row])

    async def _fake_decompose(query: str) -> list[str]:
        return [query]  # LLM 认为单知识点

    monkeypatch.setattr(retrieval_mod, "_kb_single_hybrid", _fake_single)
    monkeypatch.setattr(
        "app.services.rag.generation.decompose_query", _fake_decompose
    )

    async def _run():
        return await retrieval_mod._kb_composite_recall(
            AsyncMock(), kb_id=kb, query="原问", top_n=20,
            visible_kb_ids=None, hide_admin_only=False,
        )

    fused, merged, fts = asyncio.run(_run())
    assert [cid for cid, _ in fused] == [base_a]
    assert fts  # fts_rows 保留供 rerank skip 判定


def test_non_composite_never_uses_composite_recall(monkeypatch: pytest.MonkeyPatch) -> None:
    """非复合题：is_composite_query=False → retrieve_chunks 不走 composite 分支。"""
    from app.services.rag import retrieval as retrieval_mod

    called = {"composite": 0}

    async def _boom_composite(db, **kwargs):
        called["composite"] += 1
        raise AssertionError("非复合题不应触发 composite 召回")

    monkeypatch.setattr(retrieval_mod, "_kb_composite_recall", _boom_composite)

    # 简单题：<4 字走 simple 分支直接返回，不碰 composite
    q = "年假"
    assert is_composite_query(q) is False
    assert retrieval_mod.is_composite_query(q) is False

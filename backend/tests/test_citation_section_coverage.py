"""GQ-47 生成侧引用完整性校验：章节覆盖校验单测 + engine 重生成链路。

判定口径与 filter_relevant_chunks 一致（词面重叠 or 灰色带 0.45≤sim<0.9），
相关章节 ≥2 才启用；编号映射与 build_messages 同排序（similarity 升序，H1）。
"""

from __future__ import annotations

import uuid

import pytest
from unittest.mock import MagicMock

from app.core.config import settings
from app.services.rag.engine import ChatEngine
from app.services.rag.generation import (
    _cited_sections,
    build_messages,
    check_citation_section_coverage,
)
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    section_title: str,
    content: str,
    similarity: float,
    doc_name: str = "员工手册.md",
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name=doc_name,
        content=content,
        page_number=3,
        section_title=section_title,
        heading_path=section_title,
        similarity=similarity,
        parent_content=None,
    )


# ── 生成层：章节覆盖校验 ──────────────────────────────────────────────


def test_coverage_missing_section_fails() -> None:
    """候选相关章节 ≥2、回答只引一章 → 校验失败且 missing_sections 含缺章。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费按比例退还。", similarity=0.5),
        _chunk(section_title="5.1 离职通知期", content="离职需支付代通知金。", similarity=0.54),
    ]
    # 排序后：促销(0.2)→片段1，4.1 培训(0.5)→片段2，5.1 离职通知期(0.54)→片段3
    text = "培训费需按比例退还[片段1]。"
    passed, missing = check_citation_section_coverage(
        text, chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert missing == ["5.1 离职通知期"]


def test_coverage_single_section_passes() -> None:
    """相关章节 = 1 → 直接通过（单章题不误触发）。"""
    chunks = [
        _chunk(section_title="1.1 年假", content="正式员工每年享有10天年假。", similarity=0.92),
        _chunk(
            doc_name="广告.md",
            section_title="促销",
            content="全场促销满200减50。",
            similarity=0.2,
        ),
    ]
    text = "正式员工每年享有10天年假[片段1]。"
    passed, missing = check_citation_section_coverage(text, chunks, "员工年假有几天？")
    assert passed is True
    assert missing == []


def test_coverage_all_sections_cited_passes() -> None:
    """相关章节 ≥2 且全部被引用 → 通过。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费按比例退还。", similarity=0.5),
        _chunk(section_title="5.1 离职通知期", content="离职需支付代通知金。", similarity=0.54),
    ]
    text = "培训费需按比例退还[片段1]。离职未提前通知需支付代通知金[片段2]。"
    passed, missing = check_citation_section_coverage(
        text, chunks, "什么情况下要赔公司钱？"
    )
    assert passed is True
    assert missing == []


def test_coverage_noise_section_excluded() -> None:
    """sim < 0.45 且无词面重叠的噪音章节不计入候选（沿用灰色带口径）。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费按比例退还。", similarity=0.5),
        _chunk(section_title="5.1 离职通知期", content="离职需支付代通知金。", similarity=0.54),
        _chunk(
            doc_name="广告.md",
            section_title="促销",
            content="全场促销满200减50。",
            similarity=0.2,
        ),
    ]
    # 排序后：促销(0.2)→片段1，4.1 培训(0.5)→片段2，5.1 离职通知期(0.54)→片段3
    text = "培训费需按比例退还[片段2]。"
    passed, missing = check_citation_section_coverage(
        text, chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert missing == ["5.1 离职通知期"]  # 噪音「促销」不进入缺引清单


def test_cited_sections_mapping_matches_build_messages_order() -> None:
    """H1 回归锁：编号映射与 build_messages 排序一致（similarity 升序）。"""
    chunks = [
        _chunk(section_title="9.3 绩效", content="绩效S级系数1.5。", similarity=0.5),
        _chunk(section_title="4.1 培训", content="培训费按比例退还。", similarity=0.7),
        _chunk(section_title="3.1 加班", content="加班费1.5倍。", similarity=0.9),
    ]
    ordered = sorted(chunks, key=lambda c: c.similarity, reverse=False)
    assert [c.section_title for c in ordered] == ["9.3 绩效", "4.1 培训", "3.1 加班"]

    cited = _cited_sections("[片段1][片段2][片段3]", chunks)
    assert cited == {"9.3 绩效", "4.1 培训", "3.1 加班"}
    # 编号 2 必须映射到 build_messages 排序后的第 2 个片段（4.1 培训）
    assert _cited_sections("培训费[片段2]。", chunks) == {"4.1 培训"}

    messages = build_messages("问题", chunks)
    joined = "\n".join(m["content"] for m in messages)
    assert "[片段1]" in joined and "[片段3]" in joined


# ── engine 层：覆盖校验触发重生成（复用现有 REGENERATE 分支）──────────


def _engine(
    chunks: list[RetrievedChunk],
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[str],
    captured: list[list[dict]] | None = None,
) -> ChatEngine:
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="什么情况下要赔公司钱？",
        kb_id=uuid.uuid4(),
    )

    async def _hist() -> None:
        engine.history = None
        engine.retrieval_query = engine.message

    async def _retrieve() -> list:
        engine.chunks = chunks
        return chunks

    async def _save(content: str, citations: list) -> uuid.UUID:
        return uuid.uuid4()

    calls = {"n": 0}

    async def _tokens(_messages: list) -> object:
        if captured is not None:
            captured.append(_messages)
        text = responses[calls["n"]]
        calls["n"] += 1
        for char in text:
            yield char

    monkeypatch.setattr(engine, "_load_history", _hist)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr(engine, "_save", _save)
    monkeypatch.setattr(
        "app.services.rag.engine.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr(
        "app.services.rag.engine.output_safety_check",
        lambda text: (True, []),
    )
    monkeypatch.setattr(settings, "self_verify_enabled", False)
    monkeypatch.setattr(settings, "citation_density_check_enabled", True)
    monkeypatch.setattr(settings, "citation_density_regenerate_limit", 1)
    return engine


@pytest.mark.asyncio
async def test_engine_regenerates_when_section_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GQ-47 类：相关章节 ≥2 且只引一章 → 覆盖校验拦截 → 重生成补引。"""
    chunks = [
        _chunk(
            section_title="4.1 培训",
            content="员工参加培训后提前离职，需按比例退还培训费用。",
            similarity=0.5,
        ),
        _chunk(
            section_title="5.1 离职通知期",
            content="离职未提前通知的，需支付代通知金。",
            similarity=0.54,
        ),
    ]
    engine = _engine(
        chunks,
        monkeypatch,
        responses=[
            "员工参加培训后提前离职，需按比例退还培训费用[片段1]。",
            "员工参加培训后提前离职，需按比例退还培训费用[片段1]。"
            "离职未提前通知的，需支付代通知金[片段2]。",
        ],
    )

    events = []
    async for event in engine.stream():
        events.append(event)

    regen = [e for e in events if e["event"] == "regenerating"]
    assert regen, "缺引章节应触发 regenerating 事件"
    assert "相关章节" in regen[0]["data"]["reason"]

    full = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "代通知金" in full, "重生成后应补引 5.1 离职通知期内容"
    done = next(e["data"] for e in events if e["event"] == "done")
    cited_sections = {c["section_title"] for c in done["citations"]}
    assert {"4.1 培训", "5.1 离职通知期"} <= cited_sections, (
        f"终态 citations 应含 4.1+5.1（实际 {cited_sections}）"
    )


@pytest.mark.asyncio
async def test_engine_single_section_no_regenerate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单章题（相关章节 = 1）不触发覆盖校验重生成。"""
    chunks = [
        _chunk(
            section_title="1.1 年假",
            content="正式员工每年享有10天年假。",
            similarity=0.92,
        ),
    ]
    engine = _engine(
        chunks,
        monkeypatch,
        responses=["正式员工每年享有10天年假[片段1]。"],
    )

    events = []
    async for event in engine.stream():
        events.append(event)

    assert not any(e["event"] == "regenerating" for e in events)
    full = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    assert "10天年假" in full


# ── 两段式缺章清单（GQ-47 M3 决策：词面 ∪ 灰 sim Top-2 ∪ 灰 rank Top-2）─────


def _gq47_chunks() -> list[RetrievedChunk]:
    """GQ-47 归因 8 章：4.1 sim 最低/rank 1、5.1 sim 最高/rank 6，排序相反。"""
    return [
        _chunk(section_title="4.1 培训", content="培训费用按比例退还。", similarity=0.4991),
        _chunk(section_title="6.3 办公用品采购", content="办公用品按预算采购。", similarity=0.5044),
        _chunk(section_title="8.3 补充医疗", content="补充医疗报销比例。", similarity=0.4825),
        _chunk(section_title="5.2 竞业限制", content="竞业限制补偿按月发放。", similarity=0.5054),
        _chunk(section_title="7.3 设备管理", content="设备报废需审批。", similarity=0.5092),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需支付代通知金。", similarity=0.5596),
        _chunk(section_title="2.1 年终奖", content="年终奖按在职时间折算。", similarity=0.5502),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.5485),
    ]


def test_coverage_missing_list_two_stage_topk() -> None:
    """两段式收窄：8 章只引 4.1 → missing 仅含 2.1/5.1/6.3，无 Top-2 外噪音。"""
    chunks = _gq47_chunks()
    # sim 升序排序后 8.3(0.4825)→片段1、4.1(0.4991)→片段2
    passed, missing = check_citation_section_coverage(
        "培训费用需按比例退还[片段2]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert missing == ["2.1 年终奖", "5.1 离职通知期", "6.3 办公用品采购"]
    assert not any(
        s.startswith(("7.3", "8.3", "5.2", "6.4")) for s in missing
    ), "非 Top-2 噪声章节不应进入缺章清单"


def test_coverage_gq47_keeps_41_51() -> None:
    """双信号互兜底：引 4.1 保 5.1（sim Top-2）、引 5.1 保 4.1（rank Top-2）。"""
    chunks = _gq47_chunks()

    # 引 4.1（片段2）→ missing 保 5.1，4.1 之外仅 2 个噪声上限（2.1/6.3）
    passed, missing = check_citation_section_coverage(
        "培训费用需按比例退还[片段2]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert "5.1 离职通知期" in missing
    assert len(missing) == 3

    # 引 5.1（片段8，sim 最高）→ missing 保 4.1（rank Top-2）
    passed, missing = check_citation_section_coverage(
        "离职未提前通知需支付代通知金[片段8]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert "4.1 培训" in missing
    assert "5.1 离职通知期" not in missing


def test_coverage_anchor_tightened_related_shrinks_to_single_section() -> None:
    """M5 条件灰色带：有词面锚点（4.1「赔公司」）时灰色噪声被收紧过滤，
    related 收缩为单章 → 覆盖校验正确不启用（单章题不再误触发）。

    旧口径（无条件灰色带）下 related=8、会误触发并产出 rank Top-2 灰色噪声
    缺章清单；M5 共享谓词后该场景为「相关章节=1」→ 直接通过。
    """
    chunks = [
        _chunk(section_title="6.3 办公用品采购", content="办公用品按预算采购。", similarity=0.5044),
        _chunk(section_title="8.3 补充医疗", content="补充医疗报销比例。", similarity=0.4825),
        _chunk(section_title="5.2 竞业限制", content="竞业限制补偿按月发放。", similarity=0.5054),
        _chunk(section_title="7.3 设备管理", content="设备报废需审批。", similarity=0.5092),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需支付代通知金。", similarity=0.5596),
        _chunk(section_title="2.1 年终奖", content="年终奖按在职时间折算。", similarity=0.5502),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.5485),
        _chunk(
            section_title="4.1 培训",
            content="员工参加培训后离职需赔公司钱，培训费按比例退还。",
            similarity=0.4510,
        ),
    ]
    passed, missing = check_citation_section_coverage(
        "办公用品按预算采购[片段3]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is True
    assert missing == []


def test_coverage_anchor_tightened_missing_keeps_only_overlap() -> None:
    """M5 条件灰色带：有词面锚点（5.1/2.1 含「赔公司」）时灰色噪声不进清单，
    missing 仅含词面命中章节（强信号不丢）；无灰色 Top-K 可收窄。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费用按比例退还。", similarity=0.4991),
        _chunk(section_title="6.3 办公用品采购", content="办公用品按预算采购。", similarity=0.5044),
        _chunk(section_title="8.3 补充医疗", content="补充医疗报销比例。", similarity=0.4825),
        _chunk(section_title="5.2 竞业限制", content="竞业限制补偿按月发放。", similarity=0.5054),
        _chunk(section_title="7.3 设备管理", content="设备报废需审批。", similarity=0.5092),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需赔公司钱。", similarity=0.5596),
        _chunk(section_title="2.1 年终奖", content="年终奖提前离职无需赔公司钱。", similarity=0.5502),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.5485),
    ]
    # 4.1 sim 升序第 2 → 片段2（已引用）；5.1/2.1 词面命中（强信号）→ 进清单
    passed, missing = check_citation_section_coverage(
        "培训费用需按比例退还[片段2]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert missing == ["2.1 年终奖", "5.1 离职通知期"]
    assert all(s not in missing for s in ("8.3 补充医疗", "5.2 竞业限制", "6.4 报销时限"))


def test_coverage_three_candidates_still_enabled() -> None:
    """候选 3（单章题实测形态）仍启用：门槛 ≥2 不变，清单=全候选。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费用按比例退还。", similarity=0.51),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需支付代通知金。", similarity=0.52),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.53),
    ]
    passed, missing = check_citation_section_coverage(
        "培训费用需按比例退还[片段1]。", chunks, "什么情况下要赔公司钱？"
    )
    assert passed is False
    assert missing == ["5.1 离职通知期", "6.4 报销时限"]


@pytest.mark.asyncio
async def test_engine_regen_prompt_no_extra_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重生成 prompt 缺章清单含 5.1/2.1、不含 7.3/8.3（防噪声诱导回归锁）。"""
    captured: list[list[dict]] = []
    engine = _engine(
        _gq47_chunks(),
        monkeypatch,
        responses=[
            "培训费用需按比例退还[片段2]。",
            "培训费用需按比例退还[片段2]。离职未提前通知需支付代通知金[片段8]。"
            "年终奖按在职时间折算[片段7]。办公用品按预算采购[片段3]。",
        ],
        captured=captured,
    )

    events = []
    async for event in engine.stream():
        events.append(event)

    assert any(e["event"] == "regenerating" for e in events)
    assert len(captured) == 2, "首次生成 + 重生成各一次 LLM 调用"
    regen_prompt = "".join(m["content"] for m in captured[1] if m["role"] == "user")
    assert "5.1 离职通知期" in regen_prompt
    assert "2.1 年终奖" in regen_prompt
    assert "7.3 设备管理" not in regen_prompt
    assert "8.3 补充医疗" not in regen_prompt


# ── M5 共享谓词：filter 与覆盖校验口径一致 ────────────────────────────────


def test_shared_predicate_coverage_consistency() -> None:
    """共享谓词后：filter_relevant_chunks 与 check_citation_section_coverage
    的相关章节口径完全一致（防谓词漂移）。"""
    from app.services.rag.relevance import filter_relevant_chunks, related_sections

    chunks = [
        _chunk(section_title="4.1 培训", content="培训费用按比例退还。", similarity=0.51),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需支付代通知金。", similarity=0.52),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.5),
    ]
    query = "什么情况下要赔公司钱？"

    related = related_sections(chunks, query)
    filtered = {c.section_title for c in filter_relevant_chunks(chunks, query)}
    assert filtered == related == {"4.1 培训", "5.1 离职通知期", "6.4 报销时限"}

    passed, missing = check_citation_section_coverage(
        "培训费需按比例退还[片段2]。", chunks, query
    )
    assert passed is False
    assert set(missing) <= related
    assert "5.1 离职通知期" in missing

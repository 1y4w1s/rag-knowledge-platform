"""Wave 3.3 + Plan-RAG R4-2 检索相关性 gate 单元测试。"""

from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.generation import (
    NO_CONTEXT_REPLY,
    NO_CONTEXT_REPLY_EN,
    no_context_reply_for,
)
from app.services.rag.relevance import (
    _vector_scores_universally_weak,
    filter_relevant_chunks,
    has_relevant_context,
    query_overlaps_chunk,
    related_sections,
    should_refuse_answer,
)
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    content: str,
    section_title: str | None = None,
    similarity: float = 0.1,
    kb_id=None,
    heading_path: str | None = None,
) -> RetrievedChunk:
    kid = kb_id if kb_id is not None else uuid4()
    return RetrievedChunk(
        kb_id=kid,
        chunk_id=uuid4(),
        document_id=uuid4(),
        doc_name="golden_handbook.md",
        content=content,
        page_number=None,
        section_title=section_title,
        heading_path=heading_path,
        similarity=similarity,
    )


def test_query_overlaps_chunk_on_shared_chinese_term() -> None:
    chunk = _chunk(content="员工年满一年后可享受年假10天。", section_title="1.1 年假")
    assert query_overlaps_chunk("员工年假有几天？", chunk)


def test_query_overlaps_chunk_false_for_unrelated_topic() -> None:
    chunk = _chunk(content="员工年满一年后可享受年假10天。", section_title="1.1 年假")
    assert not query_overlaps_chunk("火星殖民计划是什么？", chunk)


def test_has_relevant_context_by_lexical_overlap_when_similarity_low() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert has_relevant_context(chunks, "员工年假有几天？")


def test_filter_relevant_chunks_empty_for_irrelevant_query() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert filter_relevant_chunks(chunks, "量子计算机怎么造？") == []


def test_filter_relevant_chunks_rejects_high_similarity_without_overlap() -> None:
    """灰色带语义兜底：sim 0.6 无词面重叠 → 保留（修复复合题）；sim 0.95 无重叠 → 拒绝（AC-4 防假阳性）。"""
    low = _chunk(content="无关正文", similarity=0.6)
    assert filter_relevant_chunks([low], "火星殖民计划") == [low]
    high = _chunk(content="无关正文", similarity=0.95)
    assert filter_relevant_chunks([high], "火星殖民计划") == []


def test_should_refuse_answer_true_when_empty() -> None:
    assert should_refuse_answer([], "年假几天？") is True


def test_should_refuse_answer_false_with_overlap() -> None:
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.05)]
    assert should_refuse_answer(chunks, "员工年假有几天？") is False


def test_vector_scores_universally_weak_uses_settings_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "retrieval_min_top1_similarity", 0.5)
    weak = [_chunk(content="a", similarity=0.2), _chunk(content="b", similarity=0.3)]
    strong = [_chunk(content="a", similarity=0.6)]
    fts_only = [_chunk(content="a", similarity=0.0)]

    assert _vector_scores_universally_weak(weak) is True
    assert _vector_scores_universally_weak(strong) is False
    assert _vector_scores_universally_weak(fts_only) is False


def test_has_relevant_context_uses_settings_similarity_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A4：语义兜底阈值读 settings.relevance_similarity_fallback。"""
    chunks = [_chunk(content="完全无关的正文内容。", similarity=0.42)]
    monkeypatch.setattr(settings, "relevance_similarity_fallback", 0.50)
    assert has_relevant_context(chunks, "公司上市计划是什么？") is False
    monkeypatch.setattr(settings, "relevance_similarity_fallback", 0.40)
    assert has_relevant_context(chunks, "公司上市计划是什么？") is True


def test_weak_vector_scores_still_pass_when_overlap_exists() -> None:
    """R4-2 H5：mock/FTS 低分但有词面重叠 → 仍有依据。"""
    chunks = [_chunk(content="员工年满一年后可享受年假10天。", similarity=0.1)]
    assert _vector_scores_universally_weak(chunks) is True
    assert has_relevant_context(chunks, "员工年假有几天？") is True


def test_no_context_reply_for_chinese_question() -> None:
    assert no_context_reply_for("公司上市计划是什么？") == NO_CONTEXT_REPLY


def test_no_context_reply_for_english_question() -> None:
    assert (
        no_context_reply_for("What is the company IPO plan?")
        == NO_CONTEXT_REPLY_EN
    )


# ── 系统级拒答集成测试：模拟真实检索→过滤→门控全链路 ──

def _rejection_realistic_chunks() -> list[RetrievedChunk]:
    """模拟现实知识库检索结果——只含年假/考勤/加班相关内容。

    查询「产假政策是什么？」不应通过这些 chunk 的门控。
    """
    return [
        _chunk(content="员工年满一年后每年享有10天年假。", section_title="1.1 年假", similarity=0.42),
        _chunk(content="迟到超过30分钟按旷工半天处理。", section_title="1.2 迟到", similarity=0.38),
        _chunk(content="加班需提前申请并经主管审批。", section_title="1.3 加班", similarity=0.35),
    ]


def test_rejection_rate_via_filter_then_refuse() -> None:
    """全链路：检索结果 → filter_relevant_chunks → should_refuse_answer

    模拟用户问「产假政策是什么？」但知识库只有年假/考勤相关，
    验证过滤后为空 → 拒答门控触发。
    """
    chunks = _rejection_realistic_chunks()
    filtered = filter_relevant_chunks(chunks, "产假政策是什么？")
    assert filtered == [], "产假 query 不应通过年假/考勤 chunk 的词面过滤"
    assert should_refuse_answer(filtered, "产假政策是什么？") is True


def test_rejection_rate_gate_does_not_block_relevant_query() -> None:
    """正常问题不受拒答门控影响。"""
    chunks = _rejection_realistic_chunks()
    filtered = filter_relevant_chunks(chunks, "员工年假有几天？")
    assert len(filtered) >= 1, "年假问题应通过过滤"
    assert should_refuse_answer(filtered, "员工年假有几天？") is False


def test_rejection_rate_high_similarity_without_overlap_still_refused() -> None:
    """灰色带语义兜底：sim 0.6 无重叠 → 不拒答（有语义依据）；sim 0.95 无重叠 → 仍拒答（AC-4）。"""
    low = _chunk(content="完全无关的正文内容。", similarity=0.6)
    filtered = filter_relevant_chunks([low], "公司上市计划是什么？")
    assert filtered == [low], "灰色带（0.45~0.9）应保留"
    assert should_refuse_answer(filtered, "公司上市计划是什么？") is False
    high = _chunk(content="完全无关的正文内容。", similarity=0.95)
    filtered_high = filter_relevant_chunks([high], "公司上市计划是什么？")
    assert filtered_high == [], "≥0.9 无重叠应被过滤（AC-4）"
    assert should_refuse_answer(filtered_high, "公司上市计划是什么？") is True


# ── M5 检索侧候选谓词收窄：条件灰色带 + 停用词扩充 ──────────────────────


def test_conditional_grey_keeps_wide_band_without_anchor() -> None:
    """GQ-47 类纯语义查询（无词面锚点）：灰色带保持 0.45 宽带，sim 0.5 保留。"""
    chunk = _chunk(content="培训费用按比例退还。", similarity=0.5)
    assert filter_relevant_chunks([chunk], "什么情况下要赔公司钱？") == [chunk]
    assert has_relevant_context([chunk], "什么情况下要赔公司钱？") is True


def test_conditional_grey_tightens_with_anchor() -> None:
    """单章题类（有词面锚点）：条件灰色带收紧，sim 0.5 无词面重叠噪声被过滤。"""
    anchor = _chunk(
        content="员工年满一年后可享受年假10天。",
        section_title="1.1 年假",
        similarity=0.8,
    )
    noise = _chunk(
        content="节日礼金按节日发放。",
        section_title="8.2 节日福利",
        similarity=0.5,
    )
    result = filter_relevant_chunks([noise, anchor], "员工年假有几天？")
    assert anchor in result
    assert noise not in result


def test_stopword_employee_no_longer_hits_heading_path() -> None:
    """GQ-20 式「员工」heading_path 撞词：停用词后 9.4 申诉流程不再词面命中。"""
    chunk = _chunk(
        content="对考核结果有异议的员工，可在结果公布后 7 个工作日内向人力资源部提交书面申诉。",
        section_title="9.4 申诉流程",
        similarity=0.6205,
        heading_path="员工手册 v2.0>第九章 绩效考核>9.4 申诉流程",
    )
    assert not query_overlaps_chunk("正式员工离职需要提前多久通知？", chunk)


def test_gq17_noise_reduced_to_2() -> None:
    """GQ-17 类单章题：停用词 + 条件灰色带 → 候选锁定 2（4.1 + 8.1），1.1 噪声被过滤。"""
    chunks = [
        _chunk(
            content="员工每年可参加不超过 5 天的外部培训，培训费用由公司承担。培训后需在公司服务满一年，否则按比例退还培训费用。",
            section_title="4.1 培训",
            similarity=0.7978,
        ),
        _chunk(
            content="员工年满一年后可享受年假10天。年假须提前两周申请，由直属主管审批后方可休假。",
            section_title="1.1 年假",
            similarity=0.5971,
        ),
        _chunk(
            content="正式员工每年享受一次免费体检，标准为每人 800 元。入职满半年即可参加当年体检。",
            section_title="8.1 年度体检",
            similarity=0.5617,
        ),
    ]
    query = "员工每年可以参加几天外部培训？"
    assert related_sections(chunks, query) == {"4.1 培训", "8.1 年度体检"}
    assert {c.section_title for c in filter_relevant_chunks(chunks, query)} == {
        "4.1 培训",
        "8.1 年度体检",
    }


def test_gq47_related_kept_8() -> None:
    """GQ-47 类纯语义查询（无锚点）：条件灰色带不收紧，候选保持 8，4.1+5.1 均在。"""
    chunks = [
        _chunk(section_title="4.1 培训", content="培训费用按比例退还。", similarity=0.4991),
        _chunk(section_title="6.3 办公用品采购", content="办公用品按预算采购。", similarity=0.5044),
        _chunk(section_title="8.3 补充医疗", content="补充医疗报销比例。", similarity=0.4825),
        _chunk(section_title="5.2 竞业限制", content="竞业限制补偿按月发放。", similarity=0.5054),
        _chunk(section_title="7.3 设备管理", content="设备报废需审批。", similarity=0.5092),
        _chunk(section_title="5.1 离职通知期", content="离职未提前通知需支付代通知金。", similarity=0.5596),
        _chunk(section_title="2.1 年终奖", content="年终奖按在职时间折算。", similarity=0.5502),
        _chunk(section_title="6.4 报销时限", content="报销需在时限内提交。", similarity=0.5485),
    ]
    query = "什么情况下要赔公司钱？"
    related = related_sections(chunks, query)
    assert len(related) == 8
    assert {"4.1 培训", "5.1 离职通知期"} <= related
    assert len(filter_relevant_chunks(chunks, query)) == 8


def test_diversity_stopword_regression() -> None:
    """停用词后仅「员工」撞词不再计入 diversity gate（workspace 路径回归）。"""
    kb_a = uuid4()
    kb_b = uuid4()
    query = "正式员工每年参加几天培训？"
    chunks = [
        _chunk(kb_id=kb_a, content=f"员工考勤补充 A{i}")
        for i in range(4)
    ] + [
        _chunk(kb_id=kb_b, content="培训计划 B0"),
    ]
    result = apply_kb_diversity(chunks, query, top_k=5)
    # gate 仅库 B 有词面命中（「培训」）；库 A 的「员工」已是停用词 → 不触发多库强制
    assert result == chunks

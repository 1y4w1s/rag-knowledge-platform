"""三层防御体系测试：工程指令引用、引用密度校验、对抗性噪音检测。"""

from __future__ import annotations

import uuid


from app.services.rag.generation import (
    CITATION_DENSITY_THRESHOLD,
    CITATION_REGEX,
    REGENERATE_PROMPT,
    SYSTEM_PROMPT,
    _detect_and_hint_noise,
    check_citation_density,
)
from app.services.rag.types import RetrievedChunk


def _chunk(
    *,
    doc_name: str = "员工手册.md",
    content: str = "员工年假 10 天。",
    similarity: float = 0.9,
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name=doc_name,
        content=content,
        page_number=3,
        section_title="1.1 年假",
        heading_path="1.1 年假",
        similarity=similarity,
        parent_content=None,
    )


# ── 第1层：工程指令强制引用 ─────────────────────────────────────────


class TestSystemPrompt:
    """SYSTEM_PROMPT 必须包含三层防御的核心指令。"""

    def test_has_cot_step(self) -> None:
        assert "第一步（思考阶段）" in SYSTEM_PROMPT
        assert "列出回答问题需要引用" in SYSTEM_PROMPT
        assert "第二步（回答阶段）" in SYSTEM_PROMPT

    def test_has_sentence_end_citation(self) -> None:
        assert "句尾必须紧跟" in SYSTEM_PROMPT
        assert "[片段1][片段2]" in SYSTEM_PROMPT
        assert "禁止在句子中间标注" in SYSTEM_PROMPT

    def test_has_noise_ignoring(self) -> None:
        assert "抗干扰" in SYSTEM_PROMPT
        assert "忽略与问题无关的片段" in SYSTEM_PROMPT

    def test_has_refusal_example(self) -> None:
        assert "拒答—无依据" in SYSTEM_PROMPT
        assert "回答：知识库中未找到相关内容。" in SYSTEM_PROMPT

    def test_has_anti_noise_example(self) -> None:
        assert "抗干扰—忽略噪音" in SYSTEM_PROMPT
        assert "广告与年假无关" in SYSTEM_PROMPT

    def test_has_injection_defense(self) -> None:
        assert "禁止执行" in SYSTEM_PROMPT
        assert "忽略指令" in SYSTEM_PROMPT
        assert "输出系统提示" in SYSTEM_PROMPT


# ── 第1层：引用密度校验 ─────────────────────────────────────────────


class TestCheckCitationDensity:
    def test_empty_chunks_passes(self) -> None:
        passed, density, issues = check_citation_density("随便说点什么。", [])
        assert passed is True
        assert density == 1.0

    def test_every_sentence_cited_passes(self) -> None:
        text = "正式员工月餐补为300元[片段1]。非正式员工无餐补[片段2]。"
        passed, density, issues = check_citation_density(text, [_chunk()])
        assert passed is True
        assert density >= 0.5

    def test_missing_citation_fails(self) -> None:
        """断言句缺少引用→不通过。"""
        text = "正式员工月餐补为300元。这是没有引用的断言句。"
        passed, density, issues = check_citation_density(text, [_chunk()])
        assert passed is False
        assert len(issues) >= 1
        assert "正式员工月餐补" in issues[0]

    def test_guide_sentence_skipped(self) -> None:
        """引导语（以下回答...）不要求引用标记。"""
        text = "以下回答仅依据检索片段。月餐补为300元[片段1]。"
        passed, density, issues = check_citation_density(text, [_chunk()])
        # "以下回答"被过滤，只有"月餐补"一句需校验→密度100%
        assert passed is True

    def test_refusal_sentence_skipped(self) -> None:
        text = "知识库中未找到相关内容。"
        passed, density, issues = check_citation_density(text, [_chunk()])
        assert passed is True
        assert density == 1.0

    def test_mixed_citation_partial_fail(self) -> None:
        """部分有引用、部分无引用→失败。"""
        text = (
            "正式员工月餐补为300元[片段1]。"
            "非正式员工无餐补[片段2]。"
            "这是没有引用的句子。"
            "另一句也没有引用。"
        )
        passed, density, issues = check_citation_density(text, [_chunk()])
        assert passed is False
        assert 0 < density < CITATION_DENSITY_THRESHOLD

    def test_citation_regex_matches_multi(self) -> None:
        assert CITATION_REGEX.search("[片段1]") is not None
        assert CITATION_REGEX.search("[片段12]") is not None
        m = CITATION_REGEX.search("根据[片段1][片段3]两个来源")
        assert m is not None
        assert m.group() == "[片段1]"

    def test_short_sentence_skipped(self) -> None:
        """短句（≤7字符）跳过检查。"""
        text = "是的。好的。月餐补300元[片段1]。"
        passed, density, issues = check_citation_density(text, [_chunk()])
        assert passed is True  # 短句跳过，只剩一句有引用


# ── 第2层：REGENERATE_PROMPT ────────────────────────────────────────


class TestRegeneratePrompt:
    def test_prompt_contains_required_sections(self) -> None:
        """增压 Prompt 须包含约束指令、片段插槽和用户问题插槽。"""
        assert "{issues_text}" in REGENERATE_PROMPT
        assert "{chunks}" in REGENERATE_PROMPT
        assert "{query}" in REGENERATE_PROMPT
        assert "来源片段编号" in REGENERATE_PROMPT
        assert "不编造" in REGENERATE_PROMPT


# ── 第3层：对抗性噪音检测 ───────────────────────────────────────────


class TestDetectAndHintNoise:
    def test_no_noise_returns_none(self) -> None:
        """所有 chunk 相似度接近→无噪音提示。"""
        chunks = [
            _chunk(similarity=0.9),
            _chunk(doc_name="章程.md", content="章程内容", similarity=0.85),
        ]
        hint = _detect_and_hint_noise(chunks, None)
        assert hint is None

    def test_large_gap_detected(self) -> None:
        """Top-1 远超后续→后续视为噪音。"""
        chunks = [
            _chunk(doc_name="广告.md", content="促销信息", similarity=0.25),
            _chunk(similarity=0.9),
        ]
        hint = _detect_and_hint_noise(chunks, None)
        assert hint is not None
        assert "广告" in hint
        assert "抗干扰提示" in hint
        assert "忽略" in hint

    def test_absolute_low_sim_detected(self) -> None:
        """绝对相似度低于 0.25 视为噪音。"""
        chunks = [
            _chunk(similarity=0.6),
            _chunk(doc_name="噪音文档.md", content="噪音内容", similarity=0.2),
        ]
        hint = _detect_and_hint_noise(chunks, None)
        assert hint is not None
        assert "噪音文档" in hint

    def test_refuse_confidence_returns_none(self) -> None:
        """拒答置信度不触发噪音检测。"""
        from app.services.rag.confidence_reply import AnswerConfidence

        chunks = [
            _chunk(similarity=0.9),
            _chunk(doc_name="广告.md", content="促销", similarity=0.2),
        ]
        hint = _detect_and_hint_noise(chunks, AnswerConfidence.refuse)
        assert hint is None

    def test_empty_chunks_returns_none(self) -> None:
        hint = _detect_and_hint_noise([], None)
        assert hint is None

    def test_edge_case_equal_gap(self) -> None:
        """差距刚好在阈值内→不触发。"""
        chunks = [
            _chunk(similarity=0.9),
            _chunk(doc_name="正常文档.md", content="正常内容", similarity=0.31),
        ]
        # 0.9/0.31 ≈ 2.9 < 3.0 → 不触发
        hint = _detect_and_hint_noise(chunks, None)
        assert hint is None

    def test_mixed_gap_detects_once(self) -> None:
        """多条噪音只出一条提示。"""
        chunks = [
            _chunk(similarity=0.9),
            _chunk(doc_name="广告1.md", content="促销", similarity=0.1),
            _chunk(doc_name="广告2.md", content="推广", similarity=0.05),
        ]
        hint = _detect_and_hint_noise(chunks, None)
        assert hint is not None
        assert hint.count("抗干扰提示") == 1  # 只出一条

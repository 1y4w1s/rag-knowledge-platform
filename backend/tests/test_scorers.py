"""Scorer 单元测试。"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.benchmark.scorers.base import (
    Expect, RetrievedChunk, RetrievalScore, ndcg_at_k, compute_scores
)
from tests.benchmark.scorers.content_match import ContentMatchScorer
from tests.benchmark.scorers.answer_match import AnswerMatchScorer


# ── 测试数据 ──

CHUNKS = [
    RetrievedChunk(
        chunk_id="c1", content="员工年满一年后可享受年假10天。",
        section_title="1.1 年假", heading_path="考勤制度 > 1.1 年假",
    ),
    RetrievedChunk(
        chunk_id="c2", content="工作日加班按基本工资 1.5 倍计算加班费。",
        section_title="3.1 加班", heading_path="考勤补充 > 3.1 加班",
    ),
    RetrievedChunk(
        chunk_id="c3", content="年终奖于每年 12 月发放。",
        section_title="2.1 年终奖", heading_path="薪酬福利 > 2.1 年终奖",
    ),
    RetrievedChunk(
        chunk_id="c4", content="迟到 30 分钟以内按旷工半天处理。",
        section_title="1.2 迟到", heading_path="考勤制度 > 1.2 迟到",
    ),
]

scorer = ContentMatchScorer()


def test_exact_match():
    """content_contains 精确匹配时应命中。"""
    expect = Expect(content_contains="年假10天")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert result.hit_at_3, f"Expected hit, got {result}"
    assert result.mrr > 0


def test_case_insensitive():
    """大小写不敏感。"""
    expect = Expect(content_contains="年假10天")
    chunks_upper = [
        RetrievedChunk(chunk_id="c1", content="员工年满一年后可享受年假10天。".upper())
    ]
    result = scorer.score_retrieval("", chunks_upper, expect)
    assert result.hit_at_1, "Case insensitive match failed"


def test_no_match():
    """完全不匹配。"""
    expect = Expect(content_contains="不存在的内容")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert not result.hit_at_1
    assert result.mrr == 0.0


def test_empty_chunks():
    """空结果。"""
    expect = Expect(content_contains="年假10天")
    result = scorer.score_retrieval("", [], expect)
    assert not result.hit_at_1
    assert result.mrr == 0.0


def test_section_title_match():
    """section_title 精确匹配。"""
    expect = Expect(section_title="1.1 年假")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert result.hit_at_1, f"Section title match failed: {result}"


def test_heading_path_contains():
    """heading_path 子串匹配。"""
    expect = Expect(heading_path_contains="考勤制度")
    result = scorer.score_retrieval("", CHUNKS, expect)
    # c1 和 c4 都匹配考勤制度
    assert result.hit_at_1, f"Heading path match failed: {result}"
    assert result.hit_at_3  # 至少 2 个匹配


def test_combined_match():
    """content_contains + section_title 联合匹配。"""
    expect = Expect(content_contains="年假10天", section_title="1.1 年假")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert result.hit_at_1, "Combined match failed"


def test_combined_no_match_wrong_section():
    """content_contains 匹配但 section_title 不匹配。"""
    expect = Expect(content_contains="年假10天", section_title="3.1 加班")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert not result.hit_at_1, "Should not match wrong section"


def test_correct_rejection():
    """拒答：没有任何 chunk 匹配。"""
    expect = Expect(content_contains="完全不存在")
    # 模拟设置 expect_rejection（通过 RetrievalScore 的 correct_rejection 字段）
    result = scorer.score_retrieval("", CHUNKS, expect)
    # 手动设置 correct_rejection
    class RejectionExpect:
        content_contains = "完全不存在"
        section_title = ""
        heading_path_contains = ""
        page_number = None
        answer = ""
        expect_rejection = True
    rej_expect = RejectionExpect()
    result_w_rej = scorer.score_retrieval("", CHUNKS, rej_expect)
    assert not result_w_rej.hit_at_1
    assert result_w_rej.correct_rejection, "Should be correct rejection"


def test_mrr_rank1():
    """MRR 计算：第一个 chunk 命中。"""
    expect = Expect(content_contains="年假10天")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert result.mrr == 1.0, f"MRR should be 1.0 for rank 1, got {result.mrr}"


def test_mrr_rank2():
    """MRR 计算：第二个 chunk 命中。"""
    expect = Expect(content_contains="1.5 倍")
    result = scorer.score_retrieval("", CHUNKS, expect)
    assert result.mrr == 0.5, f"MRR should be 0.5 for rank 2, got {result.mrr}"


def test_ndcg():
    """NDCG 计算。"""
    ndcg = ndcg_at_k([0], 3)
    assert ndcg == 1.0, f"NDCG for rank 1 should be 1.0, got {ndcg}"
    ndcg2 = ndcg_at_k([1], 3)
    assert abs(ndcg2 - 0.6309) < 0.001, f"NDCG for rank 2 should be ~0.6309, got {ndcg2}"


def test_answer_match_scorer():
    """AnswerMatchScorer 基本功能。"""
    from tests.benchmark.scorers.answer_match import AnswerMatchScorer
    ascorer = AnswerMatchScorer()
    expect = Expect(answer="年假10天")
    result = ascorer.score_retrieval("", CHUNKS, expect)
    assert result.hit_at_1, f"Answer match should hit: {result}"
    assert result.mrr == 1.0


def test_retrieved_chunk_from_orm():
    """RetrievedChunk.from_raw 兼容 ORM 对象。"""
    class FakeChunk:
        chunk_id = "c1"
        content = "test content"
        section_title = "1.1"
        heading_path = "path"
        page_number = 2
        similarity = 0.95

    rc = RetrievedChunk.from_raw(FakeChunk())
    assert rc.chunk_id == "c1"
    assert rc.content == "test content"
    assert rc.section_title == "1.1"


def test_retrieved_chunk_from_dict():
    """RetrievedChunk.from_raw 兼容 dict。"""
    rc = RetrievedChunk.from_raw({
        "chunk_id": "c1", "content": "test",
        "similarity": 0.9
    })
    assert rc.chunk_id == "c1"
    assert rc.similarity == 0.9


if __name__ == "__main__":
    tests = [
        ("exact_match", test_exact_match),
        ("case_insensitive", test_case_insensitive),
        ("no_match", test_no_match),
        ("empty_chunks", test_empty_chunks),
        ("section_title_match", test_section_title_match),
        ("heading_path_contains", test_heading_path_contains),
        ("combined_match", test_combined_match),
        ("combined_no_match_wrong_section", test_combined_no_match_wrong_section),
        ("correct_rejection", test_correct_rejection),
        ("mrr_rank1", test_mrr_rank1),
        ("mrr_rank2", test_mrr_rank2),
        ("ndcg", test_ndcg),
        ("answer_match", test_answer_match_scorer),
        ("from_orm", test_retrieved_chunk_from_orm),
        ("from_dict", test_retrieved_chunk_from_dict),
    ]
    passed = 0
    failed = []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed.append((name, str(e)))
            print(f"  ❌ {name}: {e}")
    
    total = len(tests)
    print(f"\n{passed}/{total} passed")
    if failed:
        print("Failures:")
        for n, e in failed:
            print(f"  {n}: {e}")
        sys.exit(1)

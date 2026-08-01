"""G2 评测数据可信化回归测试（N14/N15 修复 + GQ-4/41/67/99 零分根因）。

覆盖：
1. N14 — golden_qa.json 声明条数 == 实际条数（109，GQ-9 与 GQ-1 重复故删除）
2. GQ-4 — query 语言与 expect 对齐（原英文 query 中文 expect 题缺陷）
3. GQ-41/67/99 — 零分题断言与 golden_handbook.md 实际内容一致（断言本身正确，
   零分根因是 SHA 伪随机 mock 嵌入导致向量召回失效，非断言错误）
4. N15 — mock 嵌入单一来源：embedder._mock_vector 为词袋 SSOT，测试文件
   不再自带变体实现；词袋语义（相似文本高余弦）锁死，防止退回 SHA 伪随机
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from app.services.ingestion.embedder import _mock_vector
from tests.golden_qa_loader import GOLDEN_QA_CASES, GOLDEN_QA_JSON

# 与 GQ-1 完全重复（query="年假有多少天？"，expect 相同），honesty-review-plan 删除
DROPPED_GQ9 = True

# 曾零分题：断言必须与 handbook 实际内容一致（此处验证断言本身）
ZERO_SCORE_CASES = {
    "GQ-4": {"content_contains": "年假10天", "heading": "考勤制度"},
    "GQ-41": {"content_contains": "年满一年", "heading": "考勤制度"},
    "GQ-67": {"content_contains": "500 元", "heading": "福利制度"},
    "GQ-99": {"content_contains": "警告", "heading": "信息安全"},
}

# 涉及 mock 嵌入实现的测试文件（不应再定义本地变体实现）
MOCK_EMBED_TEST_FILES = (
    "test_retrieval_golden.py",
    "test_retrieval_golden_fast.py",
    "test_retrieval_golden_full.py",
    "test_agent_golden.py",
)


# ═══════════════════════════════════════════════════════════════
# 1. N14 — 声明与条数一致
# ═══════════════════════════════════════════════════════════════


def test_fixture_declared_count_matches_actual():
    """fixture 声明（description 中的 109）与 cases 实际条数一致。"""
    data = json.loads(GOLDEN_QA_JSON.read_text(encoding="utf-8"))
    assert "109" in data["description"], f"description 应声明 109：{data['description']}"
    assert len(data["cases"]) == 109
    assert len(GOLDEN_QA_CASES) == 109


def test_gq9_dropped_by_design_no_hole_in_ids():
    """GQ-9 与 GQ-1 重复故删除；其余 GQ-1..GQ-110 编号连续无洞。"""
    ids = [c.case_id for c in GOLDEN_QA_CASES]
    nums = sorted(int(re.match(r"GQ-(\d+)", i).group(1)) for i in ids)
    assert nums[0] == 1 and nums[-1] == 110
    missing = [n for n in range(1, 111) if n not in set(nums)]
    assert missing == [9], f"仅允许缺 GQ-9（与 GQ-1 重复），实际缺失: {missing}"


def test_benchmark_loader_meta_total_matches():
    """benchmark loader 的 meta.total_questions 与 fixture 实际条数一致。"""
    from tests.benchmark.loaders.golden_qa import GoldenQADataset

    assert GoldenQADataset().meta.total_questions == 109


# ═══════════════════════════════════════════════════════════════
# 2. GQ-4 — query 与 expect 语言对齐
# ═══════════════════════════════════════════════════════════════


def test_gq4_query_language_aligned_with_expect():
    """GQ-4 query 应为中文且与 expect 关键词一致（修复前英文 query 中文 expect）。"""
    case = next(c for c in GOLDEN_QA_CASES if c.case_id == "GQ-4")
    assert re.search(r"[\u4e00-\u9fff]", case.query), "GQ-4 query 应为中文"
    assert "english" not in case.tags, "GQ-4 tags 不应含 english（已转中文题）"
    # expect 的中文关键词应出现在 query 中（词面对齐）
    assert "年假" in case.query and "10天" in case.query


# ═══════════════════════════════════════════════════════════════
# 3. GQ-41/67/99 — 断言与 handbook 实际内容一致（零分根因不是断言）
# ═══════════════════════════════════════════════════════════════


def test_zero_score_case_expects_exist_in_handbook():
    """GQ-4/41/67/99 的 content_contains/heading 均在 golden_handbook.md 中，
    证明零分根因在检索（mock 嵌入失效）而非 fixture 断言错误。"""
    from tests.golden_qa_loader import GOLDEN_MD

    md = GOLDEN_MD.read_text(encoding="utf-8")
    for cid, wants in ZERO_SCORE_CASES.items():
        assert wants["content_contains"] in md, (
            f"{cid}: content_contains={wants['content_contains']!r} 不在 handbook 中"
        )
        assert wants["heading"] in md, (
            f"{cid}: heading={wants['heading']!r} 不在 handbook 中"
        )


def test_zero_score_cases_not_rejection():
    """GQ-4/41/67/99 都是普通命中题（非拒答），零分=检索 miss，必须可命中。"""
    for cid in ZERO_SCORE_CASES:
        case = next(c for c in GOLDEN_QA_CASES if c.case_id == cid)
        assert case.expect_rejection is False, f"{cid} 不应是拒答题"


# ═══════════════════════════════════════════════════════════════
# 4. N15 — mock 嵌入单一来源（词袋 SSOT）
# ═══════════════════════════════════════════════════════════════


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def test_mock_vector_has_lexical_semantics():
    """词袋语义：共享 n-gram 的文本余弦高（SHA 伪随机会接近 0，此测试锁死实现）。"""
    v_annual = _mock_vector("年假10天")
    v_same = _mock_vector("年假10天")
    v_similar = _mock_vector("员工年满一年后可享受年假10天")
    v_unrelated = _mock_vector("春节中秋端午各发放节日礼金500元")

    assert _cosine(v_annual, v_same) == pytest.approx(1.0)
    assert _cosine(v_annual, v_similar) > 0.3, (
        "共享 n-gram（年假/10天）的文本余弦应显著 >0；若≈0 说明退回 SHA 伪随机"
    )
    assert _cosine(v_annual, v_unrelated) < _cosine(v_annual, v_similar), (
        "相关文本相似度应高于无关文本"
    )


def test_mock_vector_dim_and_norm():
    """mock 向量维度与 settings 一致且已归一化。"""
    from app.core.config import settings

    vec = _mock_vector("年假有多少天？")
    assert len(vec) == settings.embedding_dim
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_mock_embedding_single_source_in_test_files():
    """golden 测试文件不再自带 mock 变体实现，统一引用 embedder._mock_vector。

    test_agent_golden.py 依赖 conftest 的 provider=mock（embed_texts →
    _mock_vector），无显式引用，故只做「无本地实现」检查。
    """
    from tests.golden_qa_loader import FIXTURES

    for fname in MOCK_EMBED_TEST_FILES:
        src = (FIXTURES.parent / fname).read_text(encoding="utf-8")
        assert "def _lexical_mock_vector" not in src, (
            f"{fname} 仍定义本地 _lexical_mock_vector，应删除并引用 embedder._mock_vector"
        )
    # 显式引用检查仅适用于四个 monkeypatch embed_texts 的文件（agent golden 走 conftest）
    for fname in ("test_retrieval_golden.py", "test_retrieval_golden_fast.py", "test_retrieval_golden_full.py"):
        src = (FIXTURES.parent / fname).read_text(encoding="utf-8")
        assert "embedder._mock_vector" in src, (
            f"{fname} 未显式引用 embedder._mock_vector 统一入口"
        )
    # agent golden：不应残留本地变体或 embedder 直接引用（由 conftest provider=mock 接管）
    agent_src = (FIXTURES.parent / "test_agent_golden.py").read_text(encoding="utf-8")
    assert "_mock_vector" not in agent_src, (
        "test_agent_golden.py 不应再引用 _mock_vector（conftest 已接管 mock 嵌入）"
    )


def test_mock_vector_no_sha_pseudorandom():
    """embedder._mock_vector 源码不再使用 SHA-256 伪随机逐块填充。"""
    import inspect

    src = inspect.getsource(_mock_vector)
    assert "sha256" not in src.lower(), "embedder._mock_vector 不应含 SHA-256 伪随机逻辑"
    assert "md5" in src.lower(), "词袋实现应按 n-gram 哈希（md5）"

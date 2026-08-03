"""A2 RAGAS 数据集适配器测试。

覆盖：
1. 数据加载：三数据集加载 + 注册表校验
2. 数据提取：ground_truth / query 提取逻辑
3. 适配器初始化与 mock 模式
4. RAGAS Dataset 格式完整性（skip_llm=True）
"""

from __future__ import annotations

import json

import pytest

from tests.benchmark.loaders.ragas_adapter import (
    DATASETS,
    FIXTURE_DIR,
    RagasAdapter,
    _get_ground_truth,
)


# ── fixture 常量 ──

FIXTURE_EXPECTED_SIZES: dict[str, int] = {
    "golden_qa": 109,
    "enterprise_qa": 108,
    "advanced_qa": 20,
}


# ═══════════════════════════════════════════════════════════════
# A2-1: 数据加载与注册表
# ═══════════════════════════════════════════════════════════════

class TestDataLoading:
    """验证三数据集 fixture 文件存在、可加载、题量准确。"""

    @pytest.mark.parametrize("name, expected_count", list(FIXTURE_EXPECTED_SIZES.items()))
    def test_fixture_exists_and_count(self, name: str, expected_count: int) -> None:
        """每个注册的数据集文件存在且题量正确。"""
        filename = DATASETS.get(name)
        assert filename is not None, f"数据集 '{name}' 未注册"

        fpath = FIXTURE_DIR / filename
        assert fpath.exists(), f"fixture 文件不存在: {fpath}"

        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        cases = data.get("cases", [])
        assert len(cases) == expected_count, (
            f"{name}: 期望 {expected_count} 题，实际 {len(cases)}"
        )

    def test_all_registered_datasets_have_files(self) -> None:
        """所有注册的数据集都有对应的 fixture 文件。"""
        for name, filename in DATASETS.items():
            fpath = FIXTURE_DIR / filename
            assert fpath.exists(), f"注册了但文件不存在: {name} -> {fpath}"

    def test_each_case_has_query(self) -> None:
        """每道题都有非空 query。"""
        for name, filename in DATASETS.items():
            fpath = FIXTURE_DIR / filename
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            for case in data.get("cases", []):
                query = case.get("query", "")
                assert query, f"{name} case {case.get('case_id')} query 为空"


# ═══════════════════════════════════════════════════════════════
# A2-2: ground_truth 提取
# ═══════════════════════════════════════════════════════════════

class TestGroundTruthExtraction:
    """验证 _get_ground_truth() 能正确从各类 fixture 结构中提取真值。"""

    def test_extract_from_content_contains(self) -> None:
        """Golden QA 风格：从 expect.content_contains 提取。"""
        case = {"expect": {"content_contains": "休假10天"}}
        assert _get_ground_truth(case) == "休假10天"

    def test_extract_from_expected_chunk(self) -> None:
        """Agent Golden 风格：从 expected_chunk 提取（兜底）。"""
        case = {"expected_chunk": "populate the .gitignore"}
        assert _get_ground_truth(case) == "populate the .gitignore"

    def test_content_contains_preferred(self) -> None:
        """expect.content_contains 优先于 expected_chunk。"""
        case = {
            "expect": {"content_contains": "优先文本"},
            "expected_chunk": "兜底文本",
        }
        assert _get_ground_truth(case) == "优先文本"

    def test_empty_when_no_ground_truth(self) -> None:
        """两者都不存在时返回空字符串。"""
        assert _get_ground_truth({}) == ""
        assert _get_ground_truth({"expect": {}}) == ""
        assert _get_ground_truth({"query": "test"}) == ""

    @pytest.mark.parametrize("name", list(FIXTURE_EXPECTED_SIZES.keys()))
    def test_all_cases_have_ground_truth(self, name: str) -> None:
        """非拒答类 case 都有非空 ground_truth。

        拒答（expect_rejection=true）case 天然没有 ground_truth，跳过不检。
        """
        filename = DATASETS[name]
        fpath = FIXTURE_DIR / filename
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        empty_cases = []
        for case in data.get("cases", []):
            # 跳过拒答类 case
            if case.get("expect_rejection"):
                continue
            gt = _get_ground_truth(case)
            if not gt:
                empty_cases.append(case.get("case_id", "?"))

        assert not empty_cases, (
            f"{name}: 以下非拒答 case 缺少 ground_truth: {empty_cases[:5]}"
        )

    def test_extract_from_expects_list(self) -> None:
        """复数 expects（list）中的 content_contains 拼接提取。"""
        case = {
            "expects": [
                {"content_contains": "休假10天"},
                {"content_contains": "1.5倍"},
            ]
        }
        result = _get_ground_truth(case)
        assert "休假10天" in result
        assert "1.5倍" in result
        assert " | " in result

    def test_expects_empty_list_returns_empty(self) -> None:
        """空的 expects 列表返回空字符串。"""
        assert _get_ground_truth({"expects": []}) == ""

    def test_expect_dict_preferred_over_expects_list(self) -> None:
        """expect（单数 dict）优先于 expects（复数 list）。"""
        case = {
            "expect": {"content_contains": "优先文本"},
            "expects": [{"content_contains": "次要文本"}],
        }
        assert _get_ground_truth(case) == "优先文本"


# ═══════════════════════════════════════════════════════════════
# A2-3: 适配器初始化和 mock 模式
# ═══════════════════════════════════════════════════════════════

class TestRagasAdapterInit:
    """验证适配器初始化与 mock 模式输出格式。"""

    def test_init_with_skip_llm(self) -> None:
        """skip_llm=True 时不报错，能成功加载 fixture。"""
        adapter = RagasAdapter(db=None, kb_id=None, skip_llm=True)
        assert adapter._skip_llm is True
        assert adapter._retrieval is not None
        assert adapter._generation is not None

    def test_init_default_skip_llm_false(self) -> None:
        """默认不跳过 LLM。"""
        adapter = RagasAdapter(db=None, kb_id=None)
        assert adapter._skip_llm is False

    def test_unknown_dataset_raises(self) -> None:
        """未注册的数据集名抛出 ValueError。"""
        adapter = RagasAdapter(db=None, kb_id=None, skip_llm=True)
        with pytest.raises(ValueError, match="未知数据集"):
            import asyncio
            asyncio.run(adapter.to_ragas_dataset("nonexistent"))

    @pytest.mark.parametrize("name", list(FIXTURE_EXPECTED_SIZES.keys()))
    @pytest.mark.asyncio
    async def test_to_ragas_dataset_skip_llm_format(self, name: str) -> None:
        """skip_llm=True 时，to_ragas_dataset() 输出格式正确。

        验证：
        - question / answer / contexts / ground_truth 四个 key 齐全
        - 各 list 长度一致
        - sample 参数生效
        """
        adapter = RagasAdapter(db=None, kb_id=None, skip_llm=True)
        dataset = await adapter.to_ragas_dataset(name, sample=3)

        expected_keys = {"question", "answer", "contexts", "ground_truth"}
        assert set(dataset.keys()) == expected_keys, (
            f"{name}: key 不匹配: {set(dataset.keys())}"
        )

        n = 3
        assert len(dataset["question"]) == n
        assert len(dataset["answer"]) == n
        assert len(dataset["contexts"]) == n
        assert len(dataset["ground_truth"]) == n

        # question 非空
        for q in dataset["question"]:
            assert q, f"{name}: question 为空"

        # 非拒答类 case 的 ground_truth 非空
        # （拒答类 case 可能 ground_truth 为空，跳过不检）

    @pytest.mark.parametrize("name", list(FIXTURE_EXPECTED_SIZES.keys()))
    @pytest.mark.asyncio
    async def test_to_ragas_retrieval_dataset_format(self, name: str) -> None:
        """检索模式输出格式正确（无 answer 字段）。"""
        adapter = RagasAdapter(db=None, kb_id=None, skip_llm=True)
        dataset = await adapter.to_ragas_retrieval_dataset(name, sample=2)

        # 检索模式不需要 answer
        assert "question" in dataset
        assert "contexts" in dataset
        assert "ground_truth" in dataset
        assert len(dataset["question"]) == 2
        assert len(dataset["contexts"]) == 2
        assert len(dataset["ground_truth"]) == 2

    @pytest.mark.asyncio
    async def test_sample_limits_correctly(self) -> None:
        """sample 参数正确限制处理题数。"""
        adapter = RagasAdapter(db=None, kb_id=None, skip_llm=True)

        full = await adapter.to_ragas_dataset("golden_qa")
        assert len(full["question"]) == FIXTURE_EXPECTED_SIZES["golden_qa"]

        sampled = await adapter.to_ragas_dataset("golden_qa", sample=5)
        assert len(sampled["question"]) == 5

        sampled2 = await adapter.to_ragas_dataset("golden_qa", sample=0)
        assert len(sampled2["question"]) == FIXTURE_EXPECTED_SIZES["golden_qa"]

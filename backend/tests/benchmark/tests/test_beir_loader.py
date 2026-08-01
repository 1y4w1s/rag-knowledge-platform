"""BEIR 公开数据集加载器单元测试。

使用内置 mock 语料库（不依赖网络），验证：
1. 加载器注册
2. BM25 检索正确性
3. RAGAS scorer 集成路径
4. 空 qrels / 缺失文件 的优雅降级
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from tests.benchmark.run_benchmark import _BeirChunk


# ── Mock 语料库 ──

MOCK_CORPUS = [
    {"_id": "d1", "title": "Python Programming", "text": "Python is a high-level programming language."},
    {"_id": "d2", "title": "Machine Learning", "text": "Machine learning uses algorithms to learn from data."},
    {"_id": "d3", "title": "Deep Learning", "text": "Deep learning is a subset of machine learning using neural networks."},
    {"_id": "d4", "title": "Data Science", "text": "Data science combines statistics and computing to analyze data."},
    {"_id": "d5", "title": "Rust Systems", "text": "Rust is a systems programming language focused on safety."},
]

MOCK_QUERIES = [
    {"_id": "q1", "text": "What is Python used for?"},
    {"_id": "q2", "text": "How does machine learning work?"},
    {"_id": "q3", "text": "What is data science?"},
]

MOCK_QRELS = [
    ("q1", "d1", 1),
    ("q2", "d2", 1),
    ("q2", "d3", 1),
    ("q3", "d4", 1),
]


def _write_mock_beir(tmpdir: Path) -> None:
    """写入 mock BEIR 数据集到临时目录。"""
    (tmpdir / "qrels").mkdir(parents=True, exist_ok=True)

    with open(tmpdir / "corpus.jsonl", "w", encoding="utf-8") as f:
        for item in MOCK_CORPUS:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(tmpdir / "queries.jsonl", "w", encoding="utf-8") as f:
        for item in MOCK_QUERIES:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(tmpdir / "qrels" / "test.tsv", "w", encoding="utf-8") as f:
        f.write("query-id\tcorpus-id\tscore\n")
        for qid, did, score in MOCK_QRELS:
            f.write(f"{qid}\t{did}\t{score}\n")


# ── Fixtures ──


@pytest.fixture
def mock_beir_loader():
    """创建一个指向临时 mock 数据集的 BEIR 加载器。"""
    from tests.benchmark.loaders.beir import BEIRNFCorpus

    loader = BEIRNFCorpus()
    # 将 DATA_DIR 重定向到临时目录
    tmpdir = Path(tempfile.mkdtemp())
    _write_mock_beir(tmpdir / "beir" / "nfcorpus")

    with patch.object(loader.__class__, "DATA_DIR", tmpdir):
        yield loader


# ── 加载器测试 ──


@pytest.mark.asyncio
async def test_beir_loader_loads_queries(mock_beir_loader):
    """加载器应返回正确的查询数量。"""
    queries = await mock_beir_loader.load()
    assert len(queries) == 3
    assert queries[0].case_id == "q1"
    assert queries[1].case_id == "q2"
    assert queries[2].case_id == "q3"


@pytest.mark.asyncio
async def test_beir_loader_ground_truth(mock_beir_loader):
    """每个查询的 ground truth answer 和 expects 应正确映射 qrels。"""
    queries = await mock_beir_loader.load()
    q_map = {q.case_id: q for q in queries}

    # q1 → d1
    q1 = q_map["q1"]
    assert q1.answer is not None
    assert "Python is a high-level" in q1.answer
    assert len(q1.expects) == 1
    assert q1.metadata["qrel_doc_ids"] == ["d1"]

    # q2 → d2, d3
    q2 = q_map["q2"]
    assert q2.answer is not None
    assert "Machine learning uses" in q2.answer
    assert "Deep learning" in q2.answer
    assert len(q2.expects) == 2
    assert q2.metadata["qrel_doc_ids"] == ["d2", "d3"]

    # q3 → d4
    q3 = q_map["q3"]
    assert q3.answer is not None
    assert "Data science" in q3.answer
    assert len(q3.expects) == 1


@pytest.mark.asyncio
async def test_beir_loader_meta(mock_beir_loader):
    """元信息应正确返回。"""
    meta = mock_beir_loader.meta
    assert meta.name == "beir/nfcorpus"
    assert "retrieval" in meta.supported_modes
    assert "generation" not in meta.supported_modes


@pytest.mark.asyncio
async def test_beir_loader_register(mock_beir_loader):
    """加载器应可通过注册表发现。"""
    from tests.benchmark.loaders import list_datasets, get_loader

    all_ds = list_datasets()
    assert "beir/nfcorpus" in all_ds
    assert "beir/fiqa" in all_ds
    assert "beir/msmarco" in all_ds

    loader = get_loader("beir/nfcorpus")
    assert loader.meta.name == "beir/nfcorpus"


# ── BM25 检索测试 ──


@pytest.mark.asyncio
async def test_bm25_search_finds_relevant(mock_beir_loader):
    """BM25 应返回与 query 相关的文档。"""
    await mock_beir_loader.load()
    results = mock_beir_loader.search("Python programming language", top_k=3)
    assert len(results) == 3
    # 最相关的结果应该包含 Python
    assert results[0]["doc_id"] == "d1"
    assert "Python" in results[0]["content"]


@pytest.mark.asyncio
async def test_bm25_search_index_cached(mock_beir_loader):
    """BM25 索引应在多次调用间缓存（不重复构建）。"""
    await mock_beir_loader.load()
    # 第一次调用构建索引
    r1 = mock_beir_loader.search("Python", top_k=2)
    # 第二次应使用缓存（不重新加载语料库）
    r2 = mock_beir_loader.search("machine learning", top_k=2)
    assert len(r1) == 2
    assert len(r2) == 2
    # 验证缓存生效
    assert mock_beir_loader._bm25_cache is not None


# ── RAGAS 集成测试 ──


@pytest.mark.asyncio
async def test_beir_chunk_wrapping(mock_beir_loader):
    """BM25 结果应可通过 _BeirChunk 包装为 runner 兼容格式。"""
    await mock_beir_loader.load()
    results = mock_beir_loader.search("Machine learning", top_k=3)

    chunks = [
        _BeirChunk(chunk_id=r["doc_id"], content=r["content"], similarity=r["score"])
        for r in results
    ]
    assert len(chunks) == 3
    assert chunks[0].chunk_id == "d2"  # 最相关
    assert chunks[0].similarity > 0


# ── 边界情况测试 ──


@pytest.mark.asyncio
async def test_beir_empty_qrels():
    """当 qrels 文件缺失时，应优雅降级（返回空相关列表）。"""
    from tests.benchmark.loaders.beir import BEIRNFCorpus

    loader = BEIRNFCorpus()
    tmpdir = Path(tempfile.mkdtemp())
    beir_dir = tmpdir / "beir" / "nfcorpus"
    beir_dir.mkdir(parents=True, exist_ok=True)
    (beir_dir / "qrels").mkdir()

    # 只写 corpus 和 queries，不写 qrels
    with open(beir_dir / "corpus.jsonl", "w", encoding="utf-8") as f:
        for item in MOCK_CORPUS:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with open(beir_dir / "queries.jsonl", "w", encoding="utf-8") as f:
        for item in MOCK_QUERIES:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    # 写空 qrels
    with open(beir_dir / "qrels" / "test.tsv", "w", encoding="utf-8") as f:
        f.write("query-id\tcorpus-id\tscore\n")

    with patch.object(loader.__class__, "DATA_DIR", tmpdir):
        queries = await loader.load()
        assert len(queries) == 3
        for q in queries:
            assert q.answer is None  # 无相关文档
            assert len(q.expects) == 0


@pytest.mark.asyncio
async def test_beir_missing_corpus_file():
    """corpus.jsonl 缺失时应抛出 FileNotFoundError。"""
    from tests.benchmark.loaders.beir import BEIRNFCorpus

    loader = BEIRNFCorpus()
    tmpdir = Path(tempfile.mkdtemp())
    beir_dir = tmpdir / "beir" / "nfcorpus"
    beir_dir.mkdir(parents=True, exist_ok=True)
    (beir_dir / "qrels").mkdir()

    # 写入 queries 但不写 corpus，让 _load_corpus() 抛出 FileNotFoundError
    with open(beir_dir / "queries.jsonl", "w", encoding="utf-8") as f:
        for item in MOCK_QUERIES:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with open(beir_dir / "qrels" / "test.tsv", "w", encoding="utf-8") as f:
        f.write("query-id\tcorpus-id\tscore\n")

    with patch.object(loader.__class__, "DATA_DIR", tmpdir):
        # 先调用 download_if_needed 但不触发网络（本地已有部分文件但不全）
        # 跳过网络下载：直接 mock download_if_needed 返回 success
        with patch.object(loader, "download_if_needed") as mock_dl:
            mock_dl.return_value = beir_dir
            with pytest.raises(FileNotFoundError):
                await loader.load()

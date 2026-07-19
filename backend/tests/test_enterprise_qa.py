"""Enterprise QA 检索评测（v1.0 · 6 份模拟企业文档 · L1-L4 分层）。

使用 real embedding（BGE）验证跨文档检索能力。
按难度分层报告通过率。
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb
from tests.golden_qa_loader import chunk_matches, hit_at_k

FIXTURES = Path("/app/tests/fixtures")
QA_PATH = FIXTURES / "enterprise_qa.json"

# 难度门禁
THRESHOLDS = {
    "L1": 0.90,
    "L2": 0.80,
    "L3": 0.65,
    "L4": 0.50,
}

HIT_K = 3


def load_enterprise_cases():
    """加载 enterprise_qa.json。"""
    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    hit_k = data.get("hit_k", HIT_K)
    return cases, hit_k


async def _ingest_doc(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    upload_dir: Path,
) -> Document:
    """入库一份文档到指定 KB。"""
    source = FIXTURES / filename
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / filename
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=filename,
            file_type="md", file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None, f"Ingestion failed: {filename}"
        return row


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_enterprise_qa_retrieval(
    client,
    register_and_login,
    upload_dir,
) -> None:
    """全量 Enterprise QA 检索评测，按 L1-L4 分层报告。"""
    headers, user = await register_and_login(prefix="ent-qa")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    # 入库全部 6 份文档
    doc_files = sorted(FIXTURES.glob("acme_*.md"))
    for f in doc_files:
        await _ingest_doc(
            kb_id=kb_id, user_id=uuid.UUID(user["id"]),
            filename=f.name, upload_dir=upload_dir,
        )

    cases, hit_k = load_enterprise_cases()

    # 按题检索
    by_level: dict[str, dict] = {}
    results = []

    async with SessionLocal() as db:
        for case in cases:
            level = case.get("difficulty", "L1")
            if level not in by_level:
                by_level[level] = {"total": 0, "hit": 0}

            # 构建一个简单的 GoldenQACase-like object 用于 hit_at_k
            class FakeCase:
                pass
            fake = FakeCase()
            fake.content_contains = case.get("expect", {}).get("content_contains", "")
            fake.section_title = case.get("expect", {}).get("section_title")
            fake.heading_path_contains = case.get("expect", {}).get("heading_path_contains")
            fake.page_number = case.get("expect", {}).get("page_number")
            fake.expects = ()
            fake.min_match = 1
            fake.expect_rejection = False

            chunks = await retrieve_chunks(
                db, kb_id=kb_id, query=case["query"], top_k=hit_k,
            )

            by_level[level]["total"] += 1
            if chunks:
                passed = hit_at_k(chunks, fake, k=hit_k)
                if passed:
                    by_level[level]["hit"] += 1

            results.append({
                "case_id": case["case_id"],
                "level": level,
                "query": case["query"][:40],
                "hit": bool(chunks and hit_at_k(chunks, fake, k=hit_k)),
            })

    # 打印详细报告
    print(f"\n{'='*60}")
    print(f"Enterprise QA 检索评测 ({len(cases)} 题)")
    print(f"{'='*60}")

    all_pass = True
    for level in ["L1", "L2", "L3", "L4"]:
        stats = by_level.get(level, {"total": 0, "hit": 0})
        rate = stats["hit"] / max(1, stats["total"])
        threshold = THRESHOLDS.get(level, 0.5)
        ok = rate >= threshold
        status = "✅" if ok else "❌"
        print(f"  {level}: {stats['hit']}/{stats['total']} = {rate:.0%} (门禁 ≥{threshold:.0%}) {status}")
        if not ok:
            all_pass = False

    total_hits = sum(1 for r in results if r["hit"])
    print(f"  总体: {total_hits}/{len(results)} = {total_hits/max(1,len(results)):.0%}")
    print(f"  Hit@{hit_k}")

    # 打印失败 case 详情
    failures = [r for r in results if not r["hit"]]
    if failures:
        print(f"\n  失败详情 ({len(failures)} 题):")
        for r in failures:
            print(f"    [{r['level']}] {r['case_id']}: {r['query']}")

    assert all_pass, "Enterprise QA 检索门禁未通过"

    # 保存结果
    summary = {
        "dataset": "enterprise_qa",
        "total": len(results),
        "hit_k": hit_k,
        "by_level": {l: {"total": s["total"], "hit": s["hit"], "rate": s["hit"]/max(1,s["total"])} for l, s in by_level.items()},
        "overall_hit_rate": total_hits / max(1, len(results)),
    }
    import os, json as _json
    os.makedirs("/app/benchmark_results", exist_ok=True)
    Path("/app/benchmark_results/enterprise_qa.json").write_text(
        _json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n结果已保存: /app/benchmark_results/enterprise_qa.json")

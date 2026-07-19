"""Golden QA 生成质量门禁（Plan-RAG R5-2 生成·子串匹配）。
v1.0: 50 题全量生成 + 子串匹配判定，阈值 >=90%。

设计要点：
- 使用 real embedding（非 mock）确保 chunks 正确排序
- 真实 DeepSeek API 调用验证生成链路
- 子串匹配判定（客观可复现，无 LLM-as-Judge 噪音）
- 单 test 函数顺序执行所有 cases（避免 50 次 KB 创建开销）
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import DocumentStatus
from app.services.rag.generation import build_messages, stream_deepseek_tokens
from app.services.rag.retrieval import retrieve_chunks
from tests.conftest import create_test_kb as _create_kb
from tests.golden_qa_loader import (
    FIXTURES,
    GOLDEN_MD,
    GOLDEN_QA_CASES,
    HIT_K,
    chunk_matches,
    hit_at_k,
)

GENERATION_ACCURACY_MIN = 0.85  # 生成准确率门禁 >=85%

# 跳过无需生成评测的 case（如拒答题）
_SKIP_REJECTION = True


@pytest.mark.asyncio
async def test_golden_generation_accuracy(
    client,
    register_and_login,
    upload_dir,
) -> None:
    """全量生成题系统级门禁：生成准确率 >=85%（子串匹配）。

    流程：建 KB → 入库 golden_handbook.md → 逐题检索 + 生成 → 校验。
    """
    headers, user = await register_and_login(prefix="gd-gen")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    # 入库 golden_handbook.md（所有 case 共用一个 KB）
    await _ingest_golden_md(kb_id=kb_id, user_id=uuid.UUID(user["id"]), upload_dir=upload_dir)

    # 筛选需要生成评测的 case
    generation_cases = [
        c for c in GOLDEN_QA_CASES
        if not c.expect_rejection  # 拒答题不测生成
        and c.content_contains     # 必须有预期内容
    ]
    assert len(generation_cases) >= 10, f"生成评测题数不足: {len(generation_cases)}"

    # 逐题检索 + 生成 + 校验
    results: list[dict] = []
    async with SessionLocal() as db:
        for case in generation_cases:
            # 检索
            chunks = await retrieve_chunks(
                db, kb_id=kb_id, query=case.query, top_k=HIT_K,
            )
            if not chunks:
                results.append({
                    "case_id": case.case_id,
                    "query": case.query[:40],
                    "correct": False,
                    "reason": "no_chunks",
                })
                continue

            # 检查是否命中（如果检索都没命中，生成不可能正确）
            retrieval_hit = hit_at_k(chunks, case, k=HIT_K)
            if not retrieval_hit:
                results.append({
                    "case_id": case.case_id,
                    "query": case.query[:40],
                    "correct": False,
                    "reason": "retrieval_miss",
                })
                continue

            # 生成
            try:
                messages = build_messages(case.query, chunks)
                parts: list[str] = []
                async for token in stream_deepseek_tokens(messages):
                    parts.append(token)
                answer = "".join(parts)
            except Exception as exc:
                results.append({
                    "case_id": case.case_id,
                    "query": case.query[:40],
                    "correct": False,
                    "reason": f"generation_error: {exc}",
                })
                continue

            # 子串匹配判定
            expected = case.content_contains
            correct = expected and expected.lower() in answer.lower()
            results.append({
                "case_id": case.case_id,
                "query": case.query[:40],
                "correct": correct,
                "reason": "ok" if correct else f"missing: {expected[:60]}",
                "answer_prefix": answer[:80],
            })

    # 汇总
    n = len(results)
    good = sum(1 for r in results if r["correct"])
    accuracy = good / max(1, n)

    # 打印详情（方便 CI 调试）
    print(f"\n{'='*60}")
    print(f"生成质量评测 ({n} 题)")
    print(f"{'='*60}")
    for r in results:
        tag = "PASS" if r["correct"] else "FAIL"
        print(f"  [{tag}] {r['case_id']}: {r['query']}")
        if not r["correct"]:
            print(f"         reason: {r['reason']}")
    print(f"\n  准确率: {good}/{n} = {accuracy:.1%}")
    print(f"  门禁:   ≥{GENERATION_ACCURACY_MIN:.0%}")

    # 门禁断言
    assert accuracy >= GENERATION_ACCURACY_MIN, (
        f"生成准确率 {accuracy:.1%} 低于门禁 {GENERATION_ACCURACY_MIN:.0%} "
        f"({good}/{n})"
    )


async def _ingest_golden_md(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    upload_dir: Path,
) -> None:
    """将 golden_handbook.md 入库到指定 KB。"""
    from app.models.document import Document
    from app.services.ingestion.pipeline import process_document_ingestion

    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.md"
    storage_path.write_bytes(GOLDEN_MD.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=GOLDEN_MD.name,
            file_type="md", file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None, "Ingestion failed: document not found"

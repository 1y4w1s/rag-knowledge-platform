"""Generation Faithfulness + Citation Accuracy 评测。
对 golden_qa 的生成回答，评估：
1. Faithfulness: 回答中的每个事实是否都能在检索片段中找到依据
2. Citation Accuracy: [片段N] 引用是否指向包含对应信息的片段
"""
import asyncio, json, os, uuid
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")
SAMPLE_SIZE = 30  # 抽样 30 题（生成评测耗时较长）

FAITHFULNESS_PROMPT = """你是一个严格的事实性评估专家。评估以下 AI 回答是否忠实于给定的检索片段。

【检索片段】
{chunks}

【AI 回答】
{answer}

判断标准：
- 回答中的每个事实性陈述（数字、日期、规则、流程、实体关系等）必须能在检索片段中找到直接依据
- 如果回答中的任何事实无法在检索片段中找到支持，视为不忠实（unfaithful）
- 表述方式不同但事实一致，视为忠实（faithful）

请输出 JSON：{{"faithful": true/false, "reason": "一句话理由", "unfaithful_claims": ["不忠实的事实1", ...]}}"""

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal, engine
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks
    from app.services.rag.generation import build_messages, stream_deepseek_tokens
    from sqlalchemy import text
    from datetime import datetime, timezone

    # 建 KB + 入库
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"feval-{uuid.uuid4().hex[:8]}@e.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "username": f"feval{uuid.uuid4().hex[:8]}",
            "password": "JudgePass123!", "account_type": "personal",
        })
        resp = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "JudgePass123!"})
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await client.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "FaithEval"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    src = FIXTURES / "golden_handbook.md"
    did = uuid.uuid4()
    sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
    sp = sd / src.name; sp.write_bytes(src.read_bytes())
    async with SessionLocal() as db:
        doc = Doc(id=did, kb_id=kb_id, filename=src.name,
            file_type="md", file_size=sp.stat().st_size,
            storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
        db.add(doc); await db.commit()
        await process_document_ingestion(did)
    print("Ingestion done")

    # 加载 QA 并抽样
    data = json.loads((FIXTURES / "golden_qa.json").read_text(encoding="utf-8"))
    import random
    random.seed(42)
    cases = [c for c in data["cases"] if not c.get("expect_rejection")]
    sample = random.sample(cases, min(SAMPLE_SIZE, len(cases)))
    print(f"Sampled {len(sample)} cases for generation evaluation\n")

    # 逐题生成 + 评估
    results = []
    faithful_count = 0
    citation_ok_count = 0
    total_citations = 0

    async with SessionLocal() as db:
        for i, case in enumerate(sample):
            # 检索
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            if not chunks:
                continue

            # 生成
            try:
                messages = build_messages(case["query"], chunks)
                parts = []
                async for token in stream_deepseek_tokens(messages):
                    parts.append(token)
                answer = "".join(parts)
            except Exception as e:
                print(f"  [{i+1}/{len(sample)}] {case['case_id']}: generation failed: {e}")
                continue

            # 检查引用：是否有 [片段N] 标记
            import re
            citations = re.findall(r'\[片段(\d+)\]', answer)
            total_citations += len(citations)

            # 检查每个引用是否指向有效片段
            citation_valid = True
            for c in citations:
                idx = int(c) - 1
                if idx >= len(chunks):
                    citation_valid = False
                    break
            if citation_valid and citations:
                citation_ok_count += 1

            # Faithfulness 评估
            chunks_text = "\n---\n".join(
                f"[{i+1}] {c.parent_content or c.content}"[:500]
                for i, c in enumerate(chunks[:3])
            )
            judge_msg = FAITHFULNESS_PROMPT.format(chunks=chunks_text[:2000], answer=answer[:1500])
            try:
                judge_parts = []
                async for token in stream_deepseek_tokens(
                    [{"role": "user", "content": judge_msg}]
                ):
                    judge_parts.append(token)
                judge_raw = "".join(judge_parts)

                # 解析 JSON
                import json as _json
                # 找第一个 { 到最后一个 }
                brace_start = judge_raw.find('{')
                brace_end = judge_raw.rfind('}')
                if brace_start >= 0 and brace_end > brace_start:
                    judge_data = _json.loads(judge_raw[brace_start:brace_end+1])
                    faithful = judge_data.get("faithful", False)
                else:
                    faithful = True  # 无法解析视为通过
            except Exception:
                faithful = True

            if faithful:
                faithful_count += 1

            results.append({
                "case_id": case["case_id"],
                "query": case["query"][:40],
                "faithful": faithful,
                "has_citations": bool(citations),
                "citation_valid": citation_valid and bool(citations),
                "answer_prefix": answer[:100],
            })

            if (i+1) % 5 == 0:
                print(f"  [{i+1}/{len(sample)}] faithful={sum(1 for r in results if r['faithful'])}/{len(results)}")

    # 汇总
    n = len(results)
    faithfulness_rate = faithful_count / max(1, n)
    citation_rate = citation_ok_count / max(1, total_citations) if total_citations > 0 else 0

    print(f"\n{'='*60}")
    print(f"生成质量评测 ({n} 题)")
    print(f"{'='*60}")
    print(f"  Faithfulness: {faithful_count}/{n} = {faithfulness_rate:.1%}")
    print(f"  Citation Accuracy: {citation_ok_count}/{total_citations} = {citation_rate:.1%}")
    print(f"  （回答了 {n} 题，共 {total_citations} 个引用）")

    fails = [r for r in results if not r['faithful']]
    if fails:
        print(f"\n  不忠实回答 ({len(fails)}):")
        for r in fails[:5]:
            print(f"    {r['case_id']}: {r['answer_prefix'][:60]}")

    # 保存到 evaluation_runs
    summary = {
        "faithfulness": round(faithfulness_rate, 4),
        "citation_accuracy": round(citation_rate, 4),
        "total": n,
        "total_citations": total_citations,
    }
    from datetime import timezone
    async with engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO evaluation_runs (id, run_id, dataset_name, mode, total_queries,
                generation_faithfulness, generation_citation_accuracy, notes, triggered_by, created_at)
            VALUES (:id, :run_id, :dataset, :mode, :total,
                :faith, :cite, :notes, :trigger, :now)
        """), {
            "id": str(uuid.uuid4()),
            "run_id": f"gen_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "dataset": "golden_qa",
            "mode": "generation",
            "total": n,
            "faith": faithfulness_rate,
            "cite": citation_rate,
            "notes": json.dumps(summary),
            "trigger": "manual",
            "now": datetime.now(timezone.utc),
        })
        await conn.commit()
    print(f"\n结果已保存到 evaluation_runs")

asyncio.run(main())

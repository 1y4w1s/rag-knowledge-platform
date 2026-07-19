"""Faithfulness 评测：50 题抽样。"""
import asyncio, json, os, uuid, random, base64
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
FIXTURES = Path("/app/tests/fixtures")
PW = base64.b64decode("SnVkZ2VQYXNzMTIzIQ==").decode()

FAITH_PROMPT = """你是一个中立的事实性评估器。你的任务：检查 AI 回答是否严格基于给定的检索片段。

【检索片段】
{chunks}

【AI 回答】
{answer}

评估步骤：
1. 将 AI 回答分解为独立的事实性陈述（每个数字、日期、规则、实体关系）
2. 逐一核对每个陈述在检索片段中是否有原文支持
3. 汇总结果

判断规则：
- 有原文直接支持的 → 忠实
- 语义等价但措辞不同 → 忠实（如"30天"vs"30 天"）
- 检索片段中没有提及 → 不忠实
- 检索片段中存在但经过合理推导 → 忠实
- 归纳总结正确的 → 忠实

请输出 JSON：{{"faithful": true/false, "reason": "一句话理由", "unfaithful_claims": ["不忠实的事实1", ...]}}"""

async def main():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.document import Document as Doc
    from app.models.enums import DocumentStatus
    from app.services.ingestion.pipeline import process_document_ingestion
    from app.services.rag.retrieval import retrieve_chunks
    from app.services.rag.generation import build_messages, stream_deepseek_tokens

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"ffull-{uuid.uuid4().hex[:8]}@e.com"
        await c.post("/api/v1/auth/register", json={"email": email, "username": f"ffull{uuid.uuid4().hex[:8]}", "password": PW, "account_type": "personal"})
        resp = await c.post("/api/v1/auth/login", json={"identifier": email, "password": PW})
        j = resp.json(); uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await c.post("/api/v1/knowledge-bases?workspace=personal", headers=headers, json={"name": "FaithFull2"})
        kb_id = uuid.UUID(r.json()["id"])

    up = Path(settings.upload_dir)
    src = FIXTURES / "golden_handbook.md"
    did = uuid.uuid4()
    sd = up / str(kb_id) / str(did); sd.mkdir(parents=True, exist_ok=True)
    sp = sd / src.name; sp.write_bytes(src.read_bytes())
    async with SessionLocal() as db:
        doc = Doc(id=did, kb_id=kb_id, filename=src.name, file_type="md", file_size=sp.stat().st_size, storage_path=str(sp), status=DocumentStatus.queued, uploaded_by=uid)
        db.add(doc); await db.commit(); await process_document_ingestion(did)
    print("Ingestion done")

    data = json.loads((FIXTURES / "golden_qa.json").read_text(encoding="utf-8"))
    all_cases = [c for c in data["cases"] if not c.get("expect_rejection")]
    random.seed(42)
    random.shuffle(all_cases)
    cases = all_cases  # 全部非拒答题
    print(f"Sampled {len(cases)} cases (all non-rejection)")

    faithful = 0
    async with SessionLocal() as db:
        for i, case in enumerate(cases):
            chunks = await retrieve_chunks(db, kb_id=kb_id, query=case["query"], top_k=3)
            if not chunks:
                continue
            try:
                msgs = build_messages(case["query"], chunks)
                parts = []
                async for token in stream_deepseek_tokens(msgs):
                    parts.append(token)
                answer = "".join(parts)

                ct = "\n---\n".join(f"[{i+1}] {(c.parent_content or c.content)[:500]}" for i, c in enumerate(chunks[:3]))
                jmsg = FAITH_PROMPT.format(chunks=ct[:2000], answer=answer[:1500])
                jparts = []
                async for token in stream_deepseek_tokens([{"role": "user", "content": jmsg}]):
                    jparts.append(token)
                jraw = "".join(jparts)
                bs = jraw.find("{")
                be = jraw.rfind("}")
                if bs >= 0 and be > bs:
                    jd = json.loads(jraw[bs:be+1])
                    if jd.get("faithful"):
                        faithful += 1
            except Exception as e:
                print(f"  [{i+1}] {case['case_id']}: error {e}")

            if (i+1) % 10 == 0:
                print(f"  [{i+1}/{len(cases)}] faithful={faithful}/{i+1}={faithful/max(1,i+1):.0%}")

    n = len(cases)
    print(f"\n{'='*60}")
    print(f"Faithfulness ({n} 题)")
    print(f"{'='*60}")
    print(f"  忠实: {faithful}/{n} = {faithful/max(1,n):.0%}")
    print(f"  {'PASS' if faithful/max(1,n) >= 0.85 else 'NEEDS_IMPROVEMENT'}")

asyncio.run(main())

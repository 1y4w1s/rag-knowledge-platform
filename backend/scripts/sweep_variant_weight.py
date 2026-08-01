"""Sweep query_rewrite_variant_weight using cached LLM variants."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import embedder as embedder_mod
from app.services.ingestion import pipeline as ingestion_pipeline
from app.services.rag.executor import load_parent_contents
from app.services.rag.multi_query import multi_query_kb_recall
from app.services.rag.retrieval import FTS_RECALL, VECTOR_RECALL

FIXTURES = Path("/app/tests/fixtures")


def classify(rank: int | None) -> str:
    if rank is None:
        return "MISS_POOL"
    if rank <= 3:
        return "HIT_AT_3"
    if rank <= 20:
        return "RANK_4_20"
    return "MISS_POOL"


async def ingest(kb_id: uuid.UUID, user_id: uuid.UUID) -> None:
    real = embedder_mod.embed_texts

    async def skip_en(texts, provider=None):
        if (provider or "").lower() == "bge_en":
            raise RuntimeError("skip")
        return await real(texts, provider=provider)

    embedder_mod.embed_texts = skip_en  # type: ignore[assignment]
    ingestion_pipeline.embed_texts = skip_en  # type: ignore[assignment]
    try:
        for f in sorted(FIXTURES.glob("acme_*.md")):
            doc_id = uuid.uuid4()
            d = Path(settings.upload_dir) / str(kb_id) / str(doc_id)
            d.mkdir(parents=True, exist_ok=True)
            p = d / f.name
            p.write_bytes(f.read_bytes())
            async with SessionLocal() as db:
                db.add(
                    Document(
                        id=doc_id,
                        kb_id=kb_id,
                        filename=f.name,
                        file_type="md",
                        file_size=p.stat().st_size,
                        storage_path=str(p),
                        status=DocumentStatus.queued,
                        uploaded_by=user_id,
                    )
                )
                await db.commit()
            await ingestion_pipeline.process_document_ingestion(doc_id)
    finally:
        embedder_mod.embed_texts = real  # type: ignore[assignment]
        ingestion_pipeline.embed_texts = real  # type: ignore[assignment]


async def main() -> None:
    mq = json.loads(Path("/tmp/diag_mq_llm92.json").read_text(encoding="utf-8"))
    qa = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    needles = {
        c["case_id"]: (c.get("expect") or {}).get("content_contains") or ""
        for c in qa["cases"]
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"t{uuid.uuid4().hex[:8]}@e.com"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"u{uuid.uuid4().hex[:8]}",
                "password": "TestPass123!",
                "account_type": "personal",
            },
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": "TestPass123!"},
        )
        token = r.json()["access_token"]
        uid = uuid.UUID(r.json()["user"]["id"])
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            headers=headers,
            json={"name": "weight-sweep"},
        )
        kb_id = uuid.UUID(r.json()["id"])

    await ingest(kb_id, uid)

    for weight in (0.7, 0.4, 0.25):
        settings.query_rewrite_variant_weight = weight
        counts: Counter[str] = Counter()
        async with SessionLocal() as db:
            for row in mq["rows"]:
                case_id = row["case_id"]
                query = row["query"]
                needle = needles.get(case_id, "")
                variants = row.get("variants") or [query]
                fused, merged, _ = await multi_query_kb_recall(
                    db,
                    kb_id=kb_id,
                    query=query,
                    vector_limit=VECTOR_RECALL,
                    fts_limit=FTS_RECALL,
                    top_n=20,
                    injected_variants=variants[1:],
                )
                parents = await load_parent_contents(
                    db, [r.chunk for r in merged.values()]
                )
                rank = None
                for i, (chid, _) in enumerate(fused, start=1):
                    rec = merged[chid]
                    body = (
                        parents.get(rec.chunk.parent_chunk_id)
                        if rec.chunk.parent_chunk_id
                        else None
                    ) or rec.chunk.content or ""
                    if needle.lower() in body.lower() or needle.lower() in (
                        rec.chunk.content or ""
                    ).lower():
                        rank = i
                        break
                counts[classify(rank)] += 1
        n = max(1, sum(counts.values()))
        print(
            f"weight={weight} miss={counts['MISS_POOL']/n:.1%} "
            f"hit3={counts['HIT_AT_3']/n:.1%} "
            f"r420={counts['RANK_4_20']/n:.1%} raw={dict(counts)}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())

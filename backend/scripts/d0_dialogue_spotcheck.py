#!/usr/bin/env python3
"""D0：企业难池 + Golden 库内 fast 对话抽测（只读测量，不改检索默认）。

对每题：retrieve Top-3 针命中 + ChatEngine.stream 全量（citation/token/done）。
另跑 1 组同 thread 换题。skip_save 单轮；换题轮落库以便载历史。

用法（api 容器）：
  docker cp backend/scripts/d0_dialogue_spotcheck.py ruige-api:/tmp/d0_dialogue_spotcheck.py
  docker compose exec -T api env PYTHONPATH=/app RAG_RATE_LIMIT_MODE=bypass \\
    python /tmp/d0_dialogue_spotcheck.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

os.environ.setdefault("RAG_RATE_LIMIT_MODE", "bypass")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document as Doc
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.cache import set_query_cache_enabled
from app.services.rag.confidence_reply import (
    AnswerConfidence,
    classify_answer_confidence,
    partial_answer_disclaimer_for,
)
from app.services.rag.engine import ChatEngine
from app.services.rag.multi_turn import is_topic_shift
from app.services.rag.retrieval import retrieve_chunks
from app.services.rag.generation import no_context_reply_for

_FIXTURES_CANDIDATES = [
    Path("/app/tests/fixtures"),
    Path(__file__).resolve().parent.parent / "tests" / "fixtures",
]
FIXTURES = next((p for p in _FIXTURES_CANDIDATES if p.exists()), _FIXTURES_CANDIDATES[0])

# 企业难池抽样（含 1 拒答题）
ENT_IDS = [
    "ENT-002",  # 基础版月价
    "ENT-007",  # 集群最少节点
    "ENT-015",  # 服务期限
    "ENT-016",  # 保密期限
    "ENT-042",  # 上班时间
    "ENT-003",  # expect_rejection
    "ENT-077",  # 年付省多少（算）
    "ENT-104",  # Q1 人数
]

# Golden 抽样
GQ_IDS = [
    "GQ-1",  # 年假
    "GQ-2",  # 迟到
    "GQ-3",  # 年终奖
    "GQ-5",  # （读 fixture 确认）
    "GQ-8",
]

HIT_K = 3


def _load_cases(qa_file: str, ids: list[str]) -> list[dict]:
    data = json.loads((FIXTURES / qa_file).read_text(encoding="utf-8"))
    by_id = {c["case_id"]: c for c in data["cases"]}
    out = []
    for cid in ids:
        if cid not in by_id:
            print(f"WARN missing case {cid}", flush=True)
            continue
        out.append(by_id[cid])
    return out


def _needle_hit(chunks: list, case: dict) -> bool:
    if case.get("expect_rejection"):
        return False
    expect = case.get("expect") or {}
    cc = (expect.get("content_contains") or "").lower()
    sp = (expect.get("section_title") or "").lower()
    hp = (expect.get("heading_path_contains") or "").lower()
    if not cc and not sp and not hp:
        return False
    for ck in chunks[:HIT_K]:
        content = (ck.content or "").lower()
        st = (ck.heading_path or ck.section_title or "").lower()
        ok = True
        if cc and cc not in content:
            ok = False
        if sp and sp not in st:
            ok = False
        if hp and hp not in st:
            ok = False
        if ok:
            return True
    return False


def _needle_preview(case: dict, n: int = 80) -> str:
    if case.get("expect_rejection"):
        return "<expect_rejection>"
    cc = (case.get("expect") or {}).get("content_contains") or ""
    return cc.replace("\n", " ")[:n]


async def _pick_existing_kb(*, filename_like: str) -> tuple[uuid.UUID, uuid.UUID, str] | None:
    """复用已有 completed 库，避免本窗重嵌 OOM。"""
    async with SessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT kb.id AS kb_id,
                           COALESCE(kb.owner_user_id, (
                               SELECT u.id FROM users u ORDER BY u.created_at LIMIT 1
                           )) AS user_id,
                           kb.name AS kb_name,
                           COUNT(d.id) AS ndocs
                    FROM knowledge_bases kb
                    JOIN documents d ON d.kb_id = kb.id
                      AND d.deleted_at IS NULL AND d.status = 'completed'
                    WHERE d.filename ILIKE :pat
                    GROUP BY kb.id, kb.owner_user_id, kb.name
                    HAVING COUNT(d.id) >= :min_docs
                    ORDER BY COUNT(d.id) DESC, kb.created_at DESC
                    LIMIT 1
                    """
                ),
                {"pat": filename_like, "min_docs": 1 if "golden" in filename_like.lower() else 6},
            )
        ).one_or_none()
        if not row:
            return None
        return row.kb_id, row.user_id, row.kb_name


async def _register_kb(name: str) -> tuple[uuid.UUID, uuid.UUID]:
    """仅在无现成库时建库（会 import app.main，内存较重）。"""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"d0-{uuid.uuid4().hex[:8]}@e.com"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"d0{uuid.uuid4().hex[:8]}",
                "password": "JudgePass123!",
                "account_type": "personal",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": "JudgePass123!"},
        )
        j = resp.json()
        uid = uuid.UUID(j["user"]["id"])
        headers = {"Authorization": f"Bearer {j['access_token']}"}
        r = await client.post(
            "/api/v1/knowledge-bases?workspace=personal",
            headers=headers,
            json={"name": name},
        )
        kb_id = uuid.UUID(r.json()["id"])
    return kb_id, uid


async def _ingest(kb_id: uuid.UUID, uid: uuid.UUID, doc_names: list[str]) -> None:
    up = Path(settings.upload_dir)
    for doc_name in doc_names:
        src = FIXTURES / doc_name
        if not src.exists():
            print(f"WARN missing doc {doc_name}", flush=True)
            continue
        did = uuid.uuid4()
        sd = up / str(kb_id) / str(did)
        sd.mkdir(parents=True, exist_ok=True)
        sp = sd / src.name
        sp.write_bytes(src.read_bytes())
        async with SessionLocal() as db:
            doc = Doc(
                id=did,
                kb_id=kb_id,
                filename=src.name,
                file_type="md",
                file_size=sp.stat().st_size,
                storage_path=str(sp),
                status=DocumentStatus.queued,
                uploaded_by=uid,
            )
            db.add(doc)
            await db.commit()
            await process_document_ingestion(did)


async def _resolve_pool(
    *,
    env_kb: str,
    env_user: str,
    reuse_pat: str,
    create_name: str,
    docs: list[str],
) -> tuple[uuid.UUID, uuid.UUID, str]:
    raw_kb = os.environ.get(env_kb, "").strip()
    raw_user = os.environ.get(env_user, "").strip()
    if raw_kb:
        kb_id = uuid.UUID(raw_kb)
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT kb.name,
                               COALESCE(kb.owner_user_id, (
                                   SELECT u.id FROM users u ORDER BY u.created_at LIMIT 1
                               )) AS user_id
                        FROM knowledge_bases kb WHERE kb.id = :kb_id
                        """
                    ),
                    {"kb_id": kb_id},
                )
            ).one()
            uid = uuid.UUID(raw_user) if raw_user else row.user_id
            return kb_id, uid, f"env:{row.name}"

    picked = await _pick_existing_kb(filename_like=reuse_pat)
    if picked:
        kb_id, uid, name = picked
        return kb_id, uid, f"reuse:{name}"

    kb_id, uid = await _register_kb(create_name)
    print(f"ingest new kb={kb_id} docs={docs}", flush=True)
    await _ingest(kb_id, uid, docs)
    return kb_id, uid, f"new:{create_name}"


async def _run_one(
    *,
    kb_id: uuid.UUID,
    uid: uuid.UUID,
    case: dict,
    pool: str,
    skip_save: bool = True,
    thread_id: uuid.UUID | None = None,
) -> dict:
    query = case["query"]
    async with SessionLocal() as db:
        chunks = await retrieve_chunks(db, kb_id=kb_id, query=query, top_k=HIT_K)
        top3_hit = _needle_hit(chunks, case)
        conf = classify_answer_confidence(chunks, query)

        engine = ChatEngine(
            db,
            user_id=uid,
            message=query,
            kb_id=kb_id,
            skip_save=skip_save,
            thread_id=thread_id,
        )
        stream_cites: list[dict] = []
        tokens: list[str] = []
        done_cites: list[dict] = []
        correction = None
        err = None
        async for ev in engine.stream():
            et = ev.get("event")
            data = ev.get("data") or {}
            if et == "citation":
                stream_cites.append(data)
            elif et == "token":
                tokens.append(data.get("text") or "")
            elif et == "correction":
                correction = data.get("text") or ""
            elif et == "done":
                done_cites = list(data.get("citations") or [])
            elif et == "error":
                err = data.get("detail")

        answer = "".join(tokens)
        if correction:
            answer = correction
        refuse_text = no_context_reply_for(query)
        is_refuse = conf is AnswerConfidence.refuse or answer.strip().startswith(
            refuse_text[:12]
        )
        partial_prefix = partial_answer_disclaimer_for(query)
        is_partial = (not is_refuse) and (
            conf is AnswerConfidence.low or answer.startswith(partial_prefix[:12])
        )
        cite_marks = re.findall(r"\[片段\d+\]", answer)
        # 针短片段是否出现在回答（粗判贴段；拒答题跳过）
        needle = (case.get("expect") or {}).get("content_contains") or ""
        answer_has_needle_hint = False
        if needle and not case.get("expect_rejection"):
            hints = [
                m.group(0).replace(" ", "")
                for m in re.finditer(
                    r"[¥$]\s*[\d,]+|\d+\s*天|\d+\s*个月|\d+:\d+|99\.99%|\d+\s*人",
                    needle,
                )
            ]
            ans_compact = answer.replace(" ", "")
            for h in hints[:4]:
                if h and h in ans_compact:
                    answer_has_needle_hint = True
                    break
            compact = re.sub(r"\s+", "", needle)[:20]
            if compact and compact in re.sub(r"\s+", "", answer):
                answer_has_needle_hint = True

        row = {
            "pool": pool,
            "case_id": case["case_id"],
            "query": query,
            "expect_rejection": bool(case.get("expect_rejection")),
            "top3_hit": top3_hit,
            "confidence": conf.value,
            "is_refuse": is_refuse,
            "is_partial": is_partial,
            "n_stream_citations": len(stream_cites),
            "n_done_citations": len(done_cites),
            "cite_marks_in_answer": cite_marks,
            "answer_has_needle_hint": answer_has_needle_hint,
            "retrieval_query": engine.retrieval_query,
            "history_len": len(engine.history or []),
            "needle_preview": _needle_preview(case),
            "answer_preview": answer.replace("\n", " ")[:280],
            "error": err,
            "top3_docs": [
                {
                    "doc": getattr(c, "filename", None),
                    "sim": round(c.similarity, 4) if c.similarity else None,
                    "excerpt": (c.content or "").replace("\n", " ")[:60],
                }
                for c in chunks[:HIT_K]
            ],
        }
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return row


async def _create_thread(kb_id: uuid.UUID, uid: uuid.UUID) -> uuid.UUID:
    """直接插 chat_threads（避免再绕权限）。"""
    tid = uuid.uuid4()
    async with SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO chat_threads (
                    id, thread_kind, kb_id, user_id, title, status, created_at, updated_at
                )
                VALUES (
                    :id, 'knowledge_base', :kb_id, :user_id, :title, 'active', NOW(), NOW()
                )
                """
            ),
            {
                "id": str(tid),
                "kb_id": str(kb_id),
                "user_id": str(uid),
                "title": "D0 topic-shift",
            },
        )
        await db.commit()
    return tid


async def _topic_shift_pair(kb_id: uuid.UUID, uid: uuid.UUID, ent_cases: list[dict]) -> list[dict]:
    """同 thread：先问价格，再问无关长问（合同保密）。"""
    by_id = {c["case_id"]: c for c in ent_cases}
    # 用 ENT-002 作首轮；换题用 ENT-016 问句（够长且无关）
    c1 = by_id.get("ENT-002") or ent_cases[0]
    c2 = by_id.get("ENT-016")
    if not c2:
        c2 = {
            "case_id": "TOPIC-SHIFT",
            "query": "框架合同里的保密期限是多少年？",
            "expect": {"content_contains": "3 年"},
        }
    tid = await _create_thread(kb_id, uid)
    print(
        json.dumps(
            {
                "pool": "enterprise_topic_shift",
                "phase": "meta",
                "thread_id": str(tid),
                "turn1": c1["case_id"],
                "turn2": c2["case_id"],
                "is_topic_shift_gate": is_topic_shift(
                    c2["query"],
                    [
                        {"role": "user", "content": c1["query"]},
                        {"role": "assistant", "content": "（占位）基础版价格……"},
                    ],
                ),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    r1 = await _run_one(
        kb_id=kb_id, uid=uid, case=c1, pool="enterprise_topic_shift_t1", skip_save=False, thread_id=tid
    )
    r2 = await _run_one(
        kb_id=kb_id, uid=uid, case=c2, pool="enterprise_topic_shift_t2", skip_save=False, thread_id=tid
    )
    # 换题干净：history_len==0 且 retrieval_query==原文，答不含首轮主题「基础版」价表串扰过多
    clean = (
        r2.get("history_len", -1) == 0
        and r2.get("retrieval_query") == c2["query"]
        and "1,200" not in (r2.get("answer_preview") or "")
        and "基础版每月" not in (r2.get("answer_preview") or "")
    )
    print(
        json.dumps(
            {
                "pool": "enterprise_topic_shift",
                "phase": "verdict",
                "topic_shift_clean": clean,
                "t2_history_len": r2.get("history_len"),
                "t2_retrieval_query": r2.get("retrieval_query"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return [r1, r2]


async def main() -> None:
    set_query_cache_enabled(False)
    print(
        f"D0 start fixtures={FIXTURES} chat_provider={settings.chat_provider!r} "
        f"rerank_policy={getattr(settings, 'rerank_policy', None)!r} "
        f"query_rewrite_policy={getattr(settings, 'query_rewrite_policy', None)!r}",
        flush=True,
    )

    ent_cases = _load_cases("enterprise_qa.json", ENT_IDS)
    gq_cases = _load_cases("golden_qa.json", GQ_IDS)

    ent_docs = sorted(p.name for p in FIXTURES.glob("acme_*.md"))
    kb_ent, uid_ent, how_ent = await _resolve_pool(
        env_kb="D0_ENT_KB_ID",
        env_user="D0_ENT_USER_ID",
        reuse_pat="acme_%",
        create_name="D0-Enterprise",
        docs=ent_docs,
    )
    print(f"enterprise kb={kb_ent} user={uid_ent} via={how_ent}", flush=True)

    rows: list[dict] = []
    for case in ent_cases:
        rows.append(await _run_one(kb_id=kb_ent, uid=uid_ent, case=case, pool="enterprise"))

    await _topic_shift_pair(kb_ent, uid_ent, ent_cases)

    kb_gq, uid_gq, how_gq = await _resolve_pool(
        env_kb="D0_GQ_KB_ID",
        env_user="D0_GQ_USER_ID",
        reuse_pat="golden_%",
        create_name="D0-Golden",
        docs=["golden_handbook.md"],
    )
    print(f"golden kb={kb_gq} user={uid_gq} via={how_gq}", flush=True)
    for case in gq_cases:
        rows.append(await _run_one(kb_id=kb_gq, uid=uid_gq, case=case, pool="golden"))

    # Summary counts for纪要
    actionable = [r for r in rows if not r.get("expect_rejection")]
    top3_ok = [r for r in actionable if r.get("top3_hit")]
    top3_ok_bad_ans = []
    for r in top3_ok:
        # 粗筛：Top-3 已对但拒答 / 无引用标 / 无针 hint
        bad = False
        reasons = []
        if r["is_refuse"]:
            bad = True
            reasons.append("false_refuse")
        if not r["cite_marks_in_answer"] and r["n_done_citations"] == 0:
            bad = True
            reasons.append("no_citation")
        if not r["answer_has_needle_hint"] and not r["is_partial"]:
            # partial 允许弱答；normal 却无 hint → 可疑
            if r["confidence"] == "normal":
                bad = True
                reasons.append("weak_answer_hint")
        if bad:
            top3_ok_bad_ans.append({**r, "bad_reasons": reasons})

    print(
        json.dumps(
            {
                "phase": "summary",
                "n_enterprise": sum(1 for r in rows if r["pool"] == "enterprise"),
                "n_golden": sum(1 for r in rows if r["pool"] == "golden"),
                "n_actionable": len(actionable),
                "n_top3_hit": len(top3_ok),
                "n_top3_hit_suspect_answer": len(top3_ok_bad_ans),
                "suspect_ids": [r["case_id"] for r in top3_ok_bad_ans],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    out_path = os.environ.get("D0_OUT", "").strip()
    if out_path:
        # 容器内落盘，避免宿主 Tee 弄坏 UTF-8
        class _Tee:
            def __init__(self, *streams):
                self._streams = streams

            def write(self, data):
                for s in self._streams:
                    s.write(data)
                    s.flush()

            def flush(self):
                for s in self._streams:
                    s.flush()

        _f = open(out_path, "w", encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, _f)
        sys.stderr = _Tee(sys.__stderr__, _f)
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr, flush=True)
        raise
    finally:
        if out_path:
            try:
                _f.close()
            except Exception:
                pass
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
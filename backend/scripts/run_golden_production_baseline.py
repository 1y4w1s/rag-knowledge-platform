"""EW-C2：通义嵌入 golden Hit@3 手跑基线（不走 pytest mock）。

用法（项目根目录，需 PostgreSQL + TONGYI_API_KEY）：

  cd backend
  $env:EMBEDDING_PROVIDER='tongyi'
  py -3.11 scripts/run_golden_production_baseline.py

输出 Markdown 结果表，写入 stdout；可加 ``--json`` 导出明细。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

# 确保 backend 在 pythonpath
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import CurrentUser
from app.models.enums import AccountType
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.auth.service import register_user
from app.services.knowledge_base.crud import create_knowledge_base
from app.services.rag.retrieval import retrieve_chunks
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.golden_qa_loader import (  # noqa: E402
    FIXTURES,
    GOLDEN_MD,
    GOLDEN_QA_CASES,
    GoldenQACase,
    HIT_K,
)
from tests.test_retrieval_golden import (  # noqa: E402
    _ingest_fixture,
    _make_golden_docx,
    _make_golden_pdf,
    hit_at_k,
)


@dataclass
class CaseResult:
    case_id: str
    query: str
    hit: bool
    top3: list[dict]


def _resolve_source(case: GoldenQACase, tmp_dir: Path) -> tuple[Path, str]:
    if case.source == "md":
        return GOLDEN_MD, "md"
    if case.source == "docx":
        docx_path = FIXTURES / "golden_handbook.docx"
        if not docx_path.exists():
            _make_golden_docx(docx_path)
        return docx_path, "docx"
    pdf_path = tmp_dir / "golden_handbook.pdf"
    _make_golden_pdf(pdf_path)
    return pdf_path, "pdf"


async def _run_case(
    case: GoldenQACase,
    upload_dir: Path,
    tmp_dir: Path,
) -> CaseResult:
    prefix = f"bl_{case.case_id.lower().replace('-', '_')}"
    async with SessionLocal() as db:
        reg = await register_user(
            db,
            email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
            username=f"{prefix}{uuid.uuid4().hex[:6]}"[:32],
            nickname=None,
            password="password123",
            account_type=AccountType.personal,
            org_name=None,
            invite_code=None,
        )
        current_user = CurrentUser(**reg.user.model_dump())
        scope = WorkspaceScope(
            kind=WorkspaceKind.personal,
            user_id=current_user.id,
            org_id=None,
        )
        kb = await create_knowledge_base(
            db,
            current_user,
            KnowledgeBaseCreate(name=f"Baseline {case.case_id}"),
            scope,
        )
        kb_id = kb.id
        user_id = current_user.id

    source, file_type = _resolve_source(case, tmp_dir)
    await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=source,
        file_type=file_type,
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_id,
            query=case.query,
            top_k=HIT_K,
        )

    top3 = [
        {
            "section_title": c.section_title,
            "heading_path": c.heading_path,
            "page_number": c.page_number,
            "content_preview": c.content[:80],
        }
        for c in chunks[:HIT_K]
    ]
    return CaseResult(
        case_id=case.case_id,
        query=case.query,
        hit=hit_at_k(chunks, case, k=HIT_K),
        top3=top3,
    )


def _markdown_table(results: list[CaseResult]) -> str:
    passed = sum(1 for r in results if r.hit)
    total = len(results)
    lines = [
        f"# RAG 生产嵌入基线抽测 · {date.today().isoformat()}",
        "",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 嵌入 | 通义 text-embedding-v2 |",
        f"| EMBEDDING_PROVIDER | `{settings.embedding_provider}` |",
        f"| Hit@3 | **{passed}/{total}** |",
        "",
        "| ID | 问题 | Hit@3 | Top-1 section | Top-1 page |",
        "|----|------|-------|---------------|------------|",
    ]
    for r in results:
        top1 = r.top3[0] if r.top3 else {}
        mark = "✅" if r.hit else "❌"
        lines.append(
            f"| {r.case_id} | {r.query[:24]} | {mark} | "
            f"{top1.get('section_title') or '—'} | {top1.get('page_number') or '—'} |"
        )
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="通义嵌入 golden Hit@3 手跑基线")
    parser.add_argument("--json", action="store_true", help="输出 JSON 明细")
    args = parser.parse_args()

    settings.embedding_provider = "tongyi"
    if not settings.tongyi_api_key:
        print(
            "错误：未配置 TONGYI_API_KEY。"
            "请在项目根 .env 填入通义 Key 后再跑。",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        upload_dir = Path(tmp) / "uploads"
        upload_dir.mkdir()
        settings.upload_dir = str(upload_dir)
        tmp_dir = Path(tmp)

        results: list[CaseResult] = []
        for case in GOLDEN_QA_CASES:
            print(f"运行 {case.case_id}…", file=sys.stderr)
            results.append(await _run_case(case, upload_dir, tmp_dir))

    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        print(_markdown_table(results))

    passed = sum(1 for r in results if r.hit)
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Eval-Ops 测试数据种子（S/M/L 档 · 元数据 · 不调嵌入 API）。

前置：先跑 ``seed_enterprise_demo.py`` 创建「知岸演示公司」与 demo_admin。

用法（项目根目录）：
  docker cp backend/scripts/seed_volume_data.py zhiku-api:/tmp/seed_volume_data.py
  docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --tier S --workspace team
  docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --tier M --workspace team
  docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --purge-eval-ops --tier L --workspace team
"""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services.org.units import create_org_root_unit, create_org_unit, get_org_root_unit

ORG_NAME = "知岸演示公司"
ADMIN_EMAIL = "demo-admin@example.com"
DEFAULT_DEPARTMENT = "研发部"
EVAL_OPS_MARKER = "eval-ops:"

S_TIER_MARKER = "eval-ops:s-tier"
S_TIER_STORAGE = "seed/volume/s-tier"
S_TIER_DOCS_PER_KB = 5

M_TIER_MARKER = "eval-ops:m-tier"
M_TIER_STORAGE = "seed/volume/m-tier"
M_TIER_KB_COUNT = 220
M_TIER_DOCS_PER_KB = 2

L_TIER_MARKER = "eval-ops:l-tier"
L_TIER_STORAGE = "seed/volume/l-tier"
L_TIER_KB_COUNT = 6000
L_TIER_DOCS_PER_KB = 1


@dataclass(frozen=True)
class KbSpec:
    name: str
    description: str


@dataclass(frozen=True)
class TierConfig:
    label: str
    marker: str
    storage_prefix: str
    docs_per_kb: int
    kb_count: int
    name_prefix: str
    index_width: int
    fixed_specs: tuple[KbSpec, ...] = ()


S_TIER_KBS: tuple[KbSpec, ...] = (
    KbSpec("产品需求规范库", f"{S_TIER_MARKER} · 产品侧 PRD 与需求追踪"),
    KbSpec("产品发布清单", f"{S_TIER_MARKER} · 版本发布与变更记录"),
    KbSpec("市场调研报告库", f"{S_TIER_MARKER} · 竞品与市场洞察"),
    KbSpec("市场营销素材库", f"{S_TIER_MARKER} · 活动文案与渠道素材"),
    KbSpec("研发技术 Wiki", f"{S_TIER_MARKER} · 架构说明与开发规范"),
    KbSpec("人力资源制度", f"{S_TIER_MARKER} · 入职、考勤与福利"),
    KbSpec("财务报销指引", f"{S_TIER_MARKER} · 费用类型与审批流程"),
    KbSpec("客户服务话术", f"{S_TIER_MARKER} · 常见问题应答模板"),
    KbSpec("项目管理模板", f"{S_TIER_MARKER} · 里程碑、风险与复盘"),
    KbSpec("企业培训课件", f"{S_TIER_MARKER} · 内训讲义与测验"),
)


def _bulk_kb_spec(
    index: int,
    *,
    marker: str,
    name_prefix: str,
    index_width: int,
) -> KbSpec:
    idx = f"{index:0{index_width}d}"
    if index % 17 == 0:
        name = f"产品模拟库-{idx}"
    elif index % 23 == 0:
        name = f"市场模拟库-{idx}"
    else:
        name = f"{name_prefix}-{idx}"
    return KbSpec(name, f"{marker} · 高负载占位 #{idx}")


def _iter_tier_specs(tier: TierConfig) -> Iterator[KbSpec]:
    if tier.fixed_specs:
        yield from tier.fixed_specs
        return
    for index in range(1, tier.kb_count + 1):
        yield _bulk_kb_spec(
            index,
            marker=tier.marker,
            name_prefix=tier.name_prefix,
            index_width=tier.index_width,
        )


def _doc_filenames(kb_name: str, *, count: int) -> list[str]:
    short = kb_name.replace(" ", "")[:12]
    templates = [
        f"{short}-总览.md",
        f"{short}-细则-v1.txt",
        f"{short}-FAQ.md",
        f"{short}-附录-2026.pdf",
        f"{short}-归档.docx",
    ]
    return templates[:count]


def _tier_config(tier: str) -> TierConfig:
    if tier == "S":
        return TierConfig(
            label="S",
            marker=S_TIER_MARKER,
            storage_prefix=S_TIER_STORAGE,
            docs_per_kb=S_TIER_DOCS_PER_KB,
            kb_count=len(S_TIER_KBS),
            name_prefix="",
            index_width=0,
            fixed_specs=S_TIER_KBS,
        )
    if tier == "M":
        return TierConfig(
            label="M",
            marker=M_TIER_MARKER,
            storage_prefix=M_TIER_STORAGE,
            docs_per_kb=M_TIER_DOCS_PER_KB,
            kb_count=M_TIER_KB_COUNT,
            name_prefix="模拟资料库",
            index_width=4,
        )
    if tier == "L":
        return TierConfig(
            label="L",
            marker=L_TIER_MARKER,
            storage_prefix=L_TIER_STORAGE,
            docs_per_kb=L_TIER_DOCS_PER_KB,
            kb_count=L_TIER_KB_COUNT,
            name_prefix="高负载模拟库",
            index_width=6,
        )
    raise SystemExit(f"未知档位: {tier}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eval-Ops 测试数据种子")
    parser.add_argument(
        "--tier",
        default="S",
        choices=["S", "M", "L"],
        help="S=10×5 · M=220×2 · L=6000×1（高负载分页压测）",
    )
    parser.add_argument(
        "--workspace",
        default="team",
        choices=["team"],
        help="工作区：team=演示公司组织空间",
    )
    parser.add_argument(
        "--department",
        default=DEFAULT_DEPARTMENT,
        help=f"资料库归属部门（默认：{DEFAULT_DEPARTMENT}）",
    )
    parser.add_argument(
        "--purge-eval-ops",
        action="store_true",
        help="先删除演示公司内所有 eval-ops 标记的库/文档，再写入本档",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="每处理多少库提交一次（默认 200；L 档建议保持 ≥100）",
    )
    return parser.parse_args()


async def _get_demo_org_and_admin(db) -> tuple[Organization, User]:
    org = await db.scalar(select(Organization).where(Organization.name == ORG_NAME))
    if org is None:
        raise SystemExit(
            f"未找到组织「{ORG_NAME}」。请先运行 seed_enterprise_demo.py。"
        )

    admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if admin is None:
        raise SystemExit(
            f"未找到管理员 {ADMIN_EMAIL}。请先运行 seed_enterprise_demo.py。"
        )
    return org, admin


async def _ensure_department(db, org: Organization, department_name: str) -> OrgUnit:
    root = await get_org_root_unit(db, org.id)
    if root is None:
        root = await create_org_root_unit(db, org_id=org.id, name="总部")
        print(f"Created org root: {root.name}")

    dept = await db.scalar(
        select(OrgUnit).where(
            OrgUnit.org_id == org.id,
            func.lower(func.btrim(OrgUnit.name)) == department_name.lower(),
        )
    )
    if dept is not None:
        return dept

    dept = await create_org_unit(
        db, org_id=org.id, name=department_name, parent=root
    )
    print(f"Created department: {department_name}")
    return dept


async def _purge_eval_ops_data(db, org_id: uuid.UUID) -> tuple[int, int]:
    kb_ids_stmt = select(KnowledgeBase.id).where(
        KnowledgeBase.owner_org_id == org_id,
        KnowledgeBase.description.like(f"%{EVAL_OPS_MARKER}%"),
    )
    doc_result = await db.execute(
        delete(Document).where(Document.kb_id.in_(kb_ids_stmt))
    )
    kb_result = await db.execute(
        delete(KnowledgeBase).where(
            KnowledgeBase.owner_org_id == org_id,
            KnowledgeBase.description.like(f"%{EVAL_OPS_MARKER}%"),
        )
    )
    await db.commit()
    return int(doc_result.rowcount or 0), int(kb_result.rowcount or 0)


async def _get_or_create_kb(
    db,
    *,
    org_id: uuid.UUID,
    org_unit_id: uuid.UUID,
    spec: KbSpec,
) -> tuple[KnowledgeBase, str]:
    existing = await db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.owner_org_id == org_id,
            func.lower(func.btrim(KnowledgeBase.name)) == spec.name.lower(),
        )
    )
    if existing is not None:
        changed = False
        if existing.org_unit_id != org_unit_id:
            existing.org_unit_id = org_unit_id
            changed = True
        if existing.description != spec.description:
            existing.description = spec.description
            changed = True
        return existing, "updated" if changed else "unchanged"

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name=spec.name,
        description=spec.description,
        owner_org_id=org_id,
        owner_user_id=None,
        org_unit_id=org_unit_id,
    )
    db.add(kb)
    await db.flush()
    return kb, "created"


async def _get_or_create_document(
    db,
    *,
    kb_id: uuid.UUID,
    filename: str,
    uploaded_by: uuid.UUID,
    storage_prefix: str,
) -> str:
    existing = await db.scalar(
        select(Document).where(
            Document.kb_id == kb_id,
            Document.filename == filename,
        )
    )
    if existing is not None:
        changed = False
        if existing.status != DocumentStatus.completed:
            existing.status = DocumentStatus.completed
            changed = True
        if existing.chunk_count is not None:
            existing.chunk_count = None
            changed = True
        if existing.error_message is not None:
            existing.error_message = None
            changed = True
        return "updated" if changed else "unchanged"

    ext = filename.rsplit(".", 1)[-1].lower()
    file_type = ext if ext in {"md", "txt", "pdf", "docx"} else "txt"
    doc_id = uuid.uuid4()
    now = datetime.now(UTC)
    doc = Document(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        file_type=file_type,
        file_size=1024,
        content_sha256=None,
        storage_path=f"{storage_prefix}/{kb_id}/{doc_id}/{filename}",
        status=DocumentStatus.completed,
        error_message=None,
        chunk_count=None,
        processing_started_at=now,
        processing_completed_at=now,
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    return "created"


def _print_monitor(
    *,
    index: int,
    total: int,
    started_at: float,
    kb_created: int,
    doc_created: int,
) -> None:
    elapsed = time.perf_counter() - started_at
    rate = index / elapsed if elapsed > 0 else 0.0
    remaining = total - index
    eta = remaining / rate if rate > 0 else 0.0
    print(
        f"[monitor] {index}/{total} 库 | {rate:.1f} 库/秒 | "
        f"已用 {elapsed:.0f}s | 预计剩余 {eta:.0f}s | "
        f"新增库 {kb_created} · 新增文档 {doc_created}"
    )


async def _fetch_org_counts(db, org_id: uuid.UUID, *, tier_marker: str) -> dict[str, int]:
    kb_total = int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.owner_org_id == org_id)
        )
        or 0
    )
    tier_kb_total = int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(
                KnowledgeBase.owner_org_id == org_id,
                KnowledgeBase.description.like(f"%{tier_marker}%"),
            )
        )
        or 0
    )
    doc_total = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(KnowledgeBase.owner_org_id == org_id)
        )
        or 0
    )
    tier_doc_total = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.owner_org_id == org_id,
                KnowledgeBase.description.like(f"%{tier_marker}%"),
            )
        )
        or 0
    )
    return {
        "kb_total": kb_total,
        "tier_kb_total": tier_kb_total,
        "doc_total": doc_total,
        "tier_doc_total": tier_doc_total,
    }


async def _seed_tier(
    *,
    tier: TierConfig,
    department_name: str,
    batch_size: int,
    purge_eval_ops: bool,
) -> None:
    kb_created = 0
    kb_updated = 0
    doc_created = 0
    doc_updated = 0
    total = tier.kb_count
    started_at = time.perf_counter()
    monitor_every = max(50, batch_size)

    async with SessionLocal() as db:
        org, admin = await _get_demo_org_and_admin(db)
        dept = await _ensure_department(db, org, department_name)

        if purge_eval_ops:
            print("=== 清空 eval-ops 测试数据 ===")
            docs_deleted, kbs_deleted = await _purge_eval_ops_data(db, org.id)
            print(f"已删除文档 {docs_deleted} · 资料库 {kbs_deleted}")
            print()

        for index, spec in enumerate(_iter_tier_specs(tier), start=1):
            kb, kb_status = await _get_or_create_kb(
                db,
                org_id=org.id,
                org_unit_id=dept.id,
                spec=spec,
            )
            if kb_status == "created":
                kb_created += 1
            elif kb_status == "updated":
                kb_updated += 1

            for filename in _doc_filenames(spec.name, count=tier.docs_per_kb):
                doc_status = await _get_or_create_document(
                    db,
                    kb_id=kb.id,
                    filename=filename,
                    uploaded_by=admin.id,
                    storage_prefix=tier.storage_prefix,
                )
                if doc_status == "created":
                    doc_created += 1
                elif doc_status == "updated":
                    doc_updated += 1

            if index % batch_size == 0:
                await db.commit()
                _print_monitor(
                    index=index,
                    total=total,
                    started_at=started_at,
                    kb_created=kb_created,
                    doc_created=doc_created,
                )

            elif total >= monitor_every and index % monitor_every == 0:
                _print_monitor(
                    index=index,
                    total=total,
                    started_at=started_at,
                    kb_created=kb_created,
                    doc_created=doc_created,
                )

        await db.commit()
        counts = await _fetch_org_counts(db, org.id, tier_marker=tier.marker)

    elapsed = time.perf_counter() - started_at
    print()
    print(f"=== Eval-Ops {tier.label} 档测试数据 ===")
    print(f"组织: {ORG_NAME}")
    print(f"部门: {department_name}")
    print(f"资料库: 本批 {total} 个（本档合计 {counts['tier_kb_total']} · 组织内 {counts['kb_total']}）")
    print(
        f"文档: 本批目标 {total * tier.docs_per_kb} 个"
        f"（本档合计 {counts['tier_doc_total']} · 组织内 {counts['doc_total']}）"
    )
    print(f"新增库 {kb_created} · 更新库 {kb_updated}")
    print(f"新增文档 {doc_created} · 更新文档 {doc_updated}")
    print(f"总耗时 {elapsed:.1f}s · 平均 {total / elapsed if elapsed > 0 else 0:.1f} 库/秒")
    print()
    print("说明: 仅写入元数据，不调用通义 embedding，不上传真实文件。")
    if tier.label == "L":
        print("验收: demo_admin 团队空间 · 部门「全公司」→ 列表 total ≥6000 · 每页 24 卡")
        print("      试 ?q=产品 / ?q=高负载 / ?page=2 保留 sort&q")
    elif tier.label == "M":
        print("验收: 团队空间 → 资料库列表应 200+ 库 · 体验滚动/搜索/加载")
        print("      建议部门切「全公司」；?q=产品 / ?q=模拟 可缩小范围")
    else:
        print("验收: demo_admin 团队空间 → 列表 ≥10 库 · ?q=产品 有结果")
    print(f"登录: {ADMIN_EMAIL} / password123")


async def main() -> None:
    args = _parse_args()
    if args.workspace != "team":
        raise SystemExit("当前仅支持 --workspace team")
    if args.batch_size < 1:
        raise SystemExit("--batch-size 必须 ≥1")
    tier = _tier_config(args.tier)
    await _seed_tier(
        tier=tier,
        department_name=args.department.strip(),
        batch_size=args.batch_size,
        purge_eval_ops=args.purge_eval_ops,
    )


if __name__ == "__main__":
    asyncio.run(main())

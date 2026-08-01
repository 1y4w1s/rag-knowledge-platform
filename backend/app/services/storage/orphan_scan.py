"""orphan 磁盘对账扫描（地图 H2 · 事后补 Plan-3E-4 漏网）。"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.knowledge_base import KnowledgeBase
from app.services.audit.log import write_audit_log
from app.services.storage.cleaner import remove_document_tree, remove_kb_tree, unlink_file

logger = logging.getLogger(__name__)

OrphanKind = Literal["O1", "O2", "O3"]


@dataclass(frozen=True)
class OwnerIndex:
    """DB 侧「有主」集合；软删文档仍算有主。"""

    kb_ids: frozenset[uuid.UUID]
    doc_ids: frozenset[uuid.UUID]
    owned_paths: frozenset[Path]


@dataclass(frozen=True)
class OrphanItem:
    kind: OrphanKind
    path: Path
    relpath: str
    size_bytes: int
    mtime: float
    kb_id: uuid.UUID | None = None
    doc_id: uuid.UUID | None = None


@dataclass
class OrphanReport:
    items: list[OrphanItem] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    skipped_grace: int = 0


@dataclass
class ApplyResult:
    deleted: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run: bool = True


def upload_root() -> Path:
    return Path(settings.upload_dir).resolve()


def is_under_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _parse_uuid(name: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(name)
    except ValueError:
        return None


def _stat_size_mtime(path: Path) -> tuple[int, float]:
    try:
        st = path.stat()
        size = st.st_size if path.is_file() else 0
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    try:
                        size += child.stat().st_size
                    except OSError:
                        pass
        return size, st.st_mtime
    except OSError:
        return 0, 0.0


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


async def load_owner_index(db: AsyncSession) -> OwnerIndex:
    kb_ids = frozenset(
        (await db.scalars(select(KnowledgeBase.id))).all()
    )
    docs = (await db.scalars(select(Document))).all()
    doc_ids = frozenset(d.id for d in docs)
    paths: set[Path] = set()
    for d in docs:
        if d.storage_path:
            paths.add(Path(d.storage_path).resolve())
    versions = (await db.scalars(select(DocumentVersion))).all()
    for v in versions:
        if v.storage_path:
            paths.add(Path(v.storage_path).resolve())
    return OwnerIndex(kb_ids=kb_ids, doc_ids=doc_ids, owned_paths=frozenset(paths))


def scan_orphans(
    *,
    owners: OwnerIndex,
    upload_dir: Path | None = None,
    grace_hours: float | None = None,
    now: datetime | None = None,
) -> OrphanReport:
    """枚举盘上 O1/O2/O3；宽限期内的项计入 skipped_grace 且不进 items。"""
    root = (upload_dir or Path(settings.upload_dir)).resolve()
    grace = (
        settings.orphan_grace_hours if grace_hours is None else grace_hours
    )
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    grace_sec = max(0.0, float(grace)) * 3600.0
    report = OrphanReport()

    if not root.is_dir():
        return report

    for kb_entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not kb_entry.is_dir():
            if kb_entry.is_file():
                report.anomalies.append(_rel(root, kb_entry))
            continue
        kb_id = _parse_uuid(kb_entry.name)
        if kb_id is None:
            report.anomalies.append(_rel(root, kb_entry))
            continue

        if kb_id not in owners.kb_ids:
            size, mtime = _stat_size_mtime(kb_entry)
            if now_ts - mtime < grace_sec:
                report.skipped_grace += 1
                continue
            report.items.append(
                OrphanItem(
                    kind="O1",
                    path=kb_entry.resolve(),
                    relpath=_rel(root, kb_entry),
                    size_bytes=size,
                    mtime=mtime,
                    kb_id=kb_id,
                )
            )
            continue

        for doc_entry in sorted(kb_entry.iterdir(), key=lambda p: p.name):
            if not doc_entry.is_dir():
                if doc_entry.is_file():
                    report.anomalies.append(_rel(root, doc_entry))
                continue
            doc_id = _parse_uuid(doc_entry.name)
            if doc_id is None:
                report.anomalies.append(_rel(root, doc_entry))
                continue

            if doc_id not in owners.doc_ids:
                size, mtime = _stat_size_mtime(doc_entry)
                if now_ts - mtime < grace_sec:
                    report.skipped_grace += 1
                    continue
                report.items.append(
                    OrphanItem(
                        kind="O2",
                        path=doc_entry.resolve(),
                        relpath=_rel(root, doc_entry),
                        size_bytes=size,
                        mtime=mtime,
                        kb_id=kb_id,
                        doc_id=doc_id,
                    )
                )
                continue

            for file_entry in sorted(doc_entry.iterdir(), key=lambda p: p.name):
                if not file_entry.is_file():
                    continue
                resolved = file_entry.resolve()
                if not is_under_root(root, resolved):
                    report.anomalies.append(_rel(root, file_entry))
                    continue
                if resolved in owners.owned_paths:
                    continue
                size, mtime = _stat_size_mtime(file_entry)
                if now_ts - mtime < grace_sec:
                    report.skipped_grace += 1
                    continue
                report.items.append(
                    OrphanItem(
                        kind="O3",
                        path=resolved,
                        relpath=_rel(root, file_entry),
                        size_bytes=size,
                        mtime=mtime,
                        kb_id=kb_id,
                        doc_id=doc_id,
                    )
                )

    return report


async def apply_orphans(
    db: AsyncSession,
    report: OrphanReport,
    *,
    dry_run: bool = True,
    max_delete: int | None = None,
    upload_dir: Path | None = None,
) -> ApplyResult:
    """干跑默认；真删复用 cleaner，受 max_delete 限制。"""
    root = (upload_dir or Path(settings.upload_dir)).resolve()
    limit = (
        settings.orphan_max_delete if max_delete is None else max_delete
    )
    result = ApplyResult(dry_run=dry_run)
    deleted_meta: list[dict] = []

    for item in report.items:
        if result.deleted >= limit:
            result.skipped += 1
            continue
        if not is_under_root(root, item.path):
            logger.warning("orphan apply skip escaped path %s", item.path)
            result.errors += 1
            continue
        if dry_run:
            result.skipped += 1
            continue

        try:
            if item.kind == "O1" and item.kb_id is not None:
                cleanup = remove_kb_tree(item.kb_id)
                if cleanup.tree_errors:
                    result.errors += 1
                    continue
            elif item.kind == "O2" and item.kb_id and item.doc_id:
                cleanup = remove_document_tree(
                    kb_id=item.kb_id, doc_id=item.doc_id
                )
                if cleanup.file_errors + cleanup.tree_errors:
                    result.errors += 1
                    continue
            elif item.kind == "O3":
                cleanup = unlink_file(item.path, root=root)
                if cleanup.file_errors:
                    result.errors += 1
                    continue
            else:
                result.errors += 1
                continue
        except OSError:
            logger.warning("orphan apply failed %s", item.path, exc_info=True)
            result.errors += 1
            continue

        result.deleted += 1
        deleted_meta.append(
            {
                "kind": item.kind,
                "relpath": item.relpath,
                "bytes": item.size_bytes,
            }
        )
        await write_audit_log(
            db,
            action="storage.orphan_deleted",
            actor_user_id=None,
            resource_type="storage",
            resource_id=item.doc_id or item.kb_id,
            kb_id=item.kb_id,
            metadata={
                "kind": item.kind,
                "relpath": item.relpath,
                "bytes": item.size_bytes,
            },
        )

    await write_audit_log(
        db,
        action="storage.orphan_scan",
        actor_user_id=None,
        resource_type="storage",
        metadata={
            "found": len(report.items),
            "anomalies": len(report.anomalies),
            "skipped_grace": report.skipped_grace,
            "deleted": result.deleted,
            "skipped": result.skipped,
            "errors": result.errors,
            "dry_run": dry_run,
        },
    )
    await db.commit()
    return result


def report_to_dict(report: OrphanReport) -> dict:
    return {
        "found": len(report.items),
        "skipped_grace": report.skipped_grace,
        "anomalies": list(report.anomalies),
        "items": [
            {
                "kind": i.kind,
                "relpath": i.relpath,
                "bytes": i.size_bytes,
                "mtime": i.mtime,
                "kb_id": str(i.kb_id) if i.kb_id else None,
                "doc_id": str(i.doc_id) if i.doc_id else None,
            }
            for i in report.items
        ],
    }

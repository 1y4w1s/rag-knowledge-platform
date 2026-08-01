"""H2：orphan 扫描（无主文件可报告 / 干跑默认 / 真删闸）。"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from app.services.storage.orphan_scan import (
    OwnerIndex,
    apply_orphans,
    is_under_root,
    scan_orphans,
)


def _owners(
    *,
    kb_ids: set[uuid.UUID] | None = None,
    doc_ids: set[uuid.UUID] | None = None,
    owned_paths: set[Path] | None = None,
) -> OwnerIndex:
    return OwnerIndex(
        kb_ids=frozenset(kb_ids or ()),
        doc_ids=frozenset(doc_ids or ()),
        owned_paths=frozenset(p.resolve() for p in (owned_paths or ())),
    )


def _touch(path: Path, content: bytes = b"x", *, age_hours: float = 48.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    past = time.time() - age_hours * 3600
    os.utime(path, (past, past))
    if path.parent.is_dir():
        os.utime(path.parent, (past, past))
    return path


@pytest.fixture
def upload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "orphan_grace_hours", 24.0)
    monkeypatch.setattr(settings, "orphan_max_delete", 100)
    return tmp_path


def test_o1_orphan_kb_tree_detected_and_apply_removes(
    upload_root: Path,
) -> None:
    kb_id = uuid.uuid4()
    junk = upload_root / str(kb_id) / str(uuid.uuid4()) / "a.txt"
    _touch(junk, age_hours=48)
    os.utime(upload_root / str(kb_id), (time.time() - 48 * 3600,) * 2)

    report = scan_orphans(owners=_owners(), grace_hours=24)
    assert len(report.items) == 1
    assert report.items[0].kind == "O1"
    assert report.items[0].kb_id == kb_id

    # dry_run：目录仍在
    assert (upload_root / str(kb_id)).is_dir()


@pytest.mark.asyncio
async def test_o1_apply_deletes(upload_root: Path) -> None:
    from app.core.database import SessionLocal

    kb_id = uuid.uuid4()
    junk = upload_root / str(kb_id) / str(uuid.uuid4()) / "a.txt"
    _touch(junk, age_hours=48)
    os.utime(upload_root / str(kb_id), (time.time() - 48 * 3600,) * 2)

    report = scan_orphans(owners=_owners(), grace_hours=24)
    async with SessionLocal() as db:
        result = await apply_orphans(db, report, dry_run=False, max_delete=10)
    assert result.deleted == 1
    assert not (upload_root / str(kb_id)).exists()


def test_o2_orphan_doc_tree(upload_root: Path) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    _touch(upload_root / str(kb_id) / str(doc_id) / "x.txt", age_hours=48)
    os.utime(upload_root / str(kb_id) / str(doc_id), (time.time() - 48 * 3600,) * 2)

    report = scan_orphans(
        owners=_owners(kb_ids={kb_id}),
        grace_hours=24,
    )
    assert len(report.items) == 1
    assert report.items[0].kind == "O2"
    assert report.items[0].doc_id == doc_id


@pytest.mark.asyncio
async def test_o2_apply_deletes(upload_root: Path) -> None:
    from app.core.database import SessionLocal

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc_dir = upload_root / str(kb_id) / str(doc_id)
    _touch(doc_dir / "x.txt", age_hours=48)
    os.utime(doc_dir, (time.time() - 48 * 3600,) * 2)

    report = scan_orphans(owners=_owners(kb_ids={kb_id}), grace_hours=24)
    async with SessionLocal() as db:
        result = await apply_orphans(db, report, dry_run=False)
    assert result.deleted == 1
    assert not doc_dir.exists()


def test_o3_unowned_file_owned_kept(upload_root: Path) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    owned = upload_root / str(kb_id) / str(doc_id) / "keep.bin"
    orphan = upload_root / str(kb_id) / str(doc_id) / "junk.bin"
    _touch(owned, b"keep", age_hours=48)
    _touch(orphan, b"junk", age_hours=48)

    report = scan_orphans(
        owners=_owners(
            kb_ids={kb_id},
            doc_ids={doc_id},
            owned_paths={owned},
        ),
        grace_hours=24,
    )
    assert len(report.items) == 1
    assert report.items[0].kind == "O3"
    assert report.items[0].path == orphan.resolve()
    assert owned.is_file()


def test_version_path_not_orphan(upload_root: Path) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    current = upload_root / str(kb_id) / str(doc_id) / "v2.bin"
    old = upload_root / str(kb_id) / str(doc_id) / "v1.bin"
    _touch(current, age_hours=48)
    _touch(old, age_hours=48)

    report = scan_orphans(
        owners=_owners(
            kb_ids={kb_id},
            doc_ids={doc_id},
            owned_paths={current, old},
        ),
        grace_hours=24,
    )
    assert report.items == []


def test_soft_deleted_doc_still_owner(upload_root: Path) -> None:
    """软删行仍在 doc_ids + owned_paths → 不算 orphan。"""
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    blob = upload_root / str(kb_id) / str(doc_id) / "soft.bin"
    _touch(blob, age_hours=48)

    report = scan_orphans(
        owners=_owners(
            kb_ids={kb_id},
            doc_ids={doc_id},
            owned_paths={blob},
        ),
        grace_hours=24,
    )
    assert report.items == []


def test_grace_skips_fresh_orphan(upload_root: Path) -> None:
    kb_id = uuid.uuid4()
    junk = upload_root / str(kb_id) / str(uuid.uuid4()) / "a.txt"
    _touch(junk, age_hours=1)  # within 24h
    os.utime(upload_root / str(kb_id), (time.time() - 1 * 3600,) * 2)

    report = scan_orphans(owners=_owners(), grace_hours=24)
    assert report.items == []
    assert report.skipped_grace >= 1


def test_owned_only_empty_report(upload_root: Path) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    blob = upload_root / str(kb_id) / str(doc_id) / "only.bin"
    _touch(blob, age_hours=48)

    report = scan_orphans(
        owners=_owners(
            kb_ids={kb_id},
            doc_ids={doc_id},
            owned_paths={blob},
        ),
        grace_hours=24,
    )
    assert report.items == []


def test_path_escape_rejected(upload_root: Path) -> None:
    outside = Path(upload_root).parent / f"escape-{uuid.uuid4().hex}.txt"
    outside.write_bytes(b"nope")
    assert not is_under_root(upload_root, outside)
    outside.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_dry_run_does_not_delete(upload_root: Path) -> None:
    from app.core.database import SessionLocal

    kb_id = uuid.uuid4()
    junk = upload_root / str(kb_id) / "x.txt"
    # O1 needs a dir named uuid
    junk = upload_root / str(kb_id) / str(uuid.uuid4()) / "x.txt"
    _touch(junk, age_hours=48)
    os.utime(upload_root / str(kb_id), (time.time() - 48 * 3600,) * 2)

    report = scan_orphans(owners=_owners(), grace_hours=24)
    assert report.items
    async with SessionLocal() as db:
        result = await apply_orphans(db, report, dry_run=True)
    assert result.dry_run is True
    assert result.deleted == 0
    assert (upload_root / str(kb_id)).is_dir()


@pytest.mark.asyncio
async def test_o3_apply_unlinks_only_orphan(upload_root: Path) -> None:
    from app.core.database import SessionLocal

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    owned = upload_root / str(kb_id) / str(doc_id) / "keep.bin"
    orphan = upload_root / str(kb_id) / str(doc_id) / "junk.bin"
    _touch(owned, b"keep", age_hours=48)
    _touch(orphan, b"junk", age_hours=48)

    report = scan_orphans(
        owners=_owners(
            kb_ids={kb_id},
            doc_ids={doc_id},
            owned_paths={owned},
        ),
        grace_hours=24,
    )
    async with SessionLocal() as db:
        result = await apply_orphans(db, report, dry_run=False)
    assert result.deleted == 1
    assert owned.is_file()
    assert not orphan.exists()


def test_non_uuid_anomaly(upload_root: Path) -> None:
    weird = upload_root / "not-a-uuid"
    weird.mkdir()
    report = scan_orphans(owners=_owners(), grace_hours=0)
    assert "not-a-uuid" in report.anomalies
    assert report.items == []

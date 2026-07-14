"""磁盘清盘服务（Plan-3E-4 / EW-A1 · Plan-3E-6a 失败计数）。"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.documents.upload import _storage_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupResult:
    """磁盘清盘结果；OSError 累加计数，不抛错（Plan-3E-6a）。"""

    file_errors: int = 0
    tree_errors: int = 0


def _kb_root(kb_id: uuid.UUID) -> Path:
    return Path(settings.upload_dir) / str(kb_id)


def remove_document_tree(
    *,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    storage_path: str | None = None,
) -> CleanupResult:
    """删磁盘文件与文档目录；失败只打日志，不抛错（Plan-3A / 3E-4 / 3E-6a）。"""
    file_errors = 0
    tree_errors = 0

    if storage_path:
        path = Path(storage_path)
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            file_errors += 1
            logger.warning(
                "delete document: failed to unlink file %s",
                storage_path,
                exc_info=True,
            )

    doc_dir = _storage_dir(kb_id, doc_id)
    try:
        if doc_dir.is_dir():
            shutil.rmtree(doc_dir)
    except OSError:
        tree_errors += 1
        logger.warning("delete document: failed to rmtree %s", doc_dir, exc_info=True)

    return CleanupResult(file_errors=file_errors, tree_errors=tree_errors)


def remove_kb_tree(kb_id: uuid.UUID) -> CleanupResult:
    """删资料库整棵 upload 目录树；失败只打日志，不阻塞 DB 删除（Plan-3E-4 / 3E-6a）。"""
    tree_errors = 0
    kb_dir = _kb_root(kb_id)
    try:
        if kb_dir.is_dir():
            shutil.rmtree(kb_dir)
    except OSError:
        tree_errors += 1
        logger.warning("delete kb: failed to rmtree %s", kb_dir, exc_info=True)

    return CleanupResult(tree_errors=tree_errors)

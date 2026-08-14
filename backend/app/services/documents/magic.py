"""NW-45 · 上传落盘前 magic bytes 双检（≠ ClamAV · ≠ parse 入库魔数）。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationError

# 二进制类型：扩展名 → 期望文件头前缀
_BINARY_MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK",
    "xlsx": b"PK",
    "pptx": b"PK",
    "png": b"\x89PNG",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
}

# 纯文本不得冒充的二进制头（含常见可执行）
_TEXT_FORBIDDEN_PREFIXES: tuple[bytes, ...] = (
    b"%PDF",
    b"PK",
    b"\x89PNG",
    b"\xff\xd8\xff",
    b"MZ",
)

_TEXT_TYPES = frozenset({"txt", "md"})

ZIP_BOMB_ERROR_CODE = "zip_bomb_detected"
ZIP_CONTAINER_TYPES = frozenset({"docx", "xlsx", "pptx"})


def _mismatch_detail(file_type: str) -> str:
    return (
        f"文件内容与扩展名 .{file_type} 不符（疑似伪装扩展名），"
        "请确认文件类型后重新上传"
    )


def _format_bytes(n: int) -> str:
    if n >= 1024**3:
        return f"{n / (1024**3):.2f} GiB"
    if n >= 1024**2:
        return f"{n / (1024**2):.2f} MiB"
    if n >= 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n} B"


def assert_zip_archive_safe(source: Path | bytes) -> None:
    """docx/xlsx/pptx 解压前压缩炸弹防护：只读 central directory，不抽取内容。"""
    if isinstance(source, Path):
        target: Path | io.BytesIO = source
    else:
        target = io.BytesIO(source)
    try:
        with zipfile.ZipFile(target) as zf:
            total_uncompressed = 0
            total_compressed = 0
            for info in zf.infolist():
                total_uncompressed += int(info.file_size)
                total_compressed += int(info.compress_size)
    except zipfile.BadZipFile:
        return

    ratio = total_uncompressed / total_compressed if total_compressed else 0.0
    limit_bytes = settings.zip_max_uncompressed_bytes
    limit_ratio = settings.zip_max_compression_ratio

    if limit_bytes > 0 and total_uncompressed > limit_bytes:
        raise ValidationError(
            detail=(
                "文件解压后内容体积超过安全上限"
                f"（当前约 {_format_bytes(total_uncompressed)} / "
                f"上限 {_format_bytes(limit_bytes)}），"
                "请拆分文档或降低内容量后重新上传"
            ),
            extra={
                "error_code": ZIP_BOMB_ERROR_CODE,
                "reason": "uncompressed_size",
                "uncompressed_bytes": total_uncompressed,
                "compressed_bytes": total_compressed,
                "ratio": round(ratio, 2),
                "limit_bytes": limit_bytes,
                "limit_ratio": limit_ratio,
            },
        )

    if limit_ratio > 0 and ratio > limit_ratio:
        raise ValidationError(
            detail=(
                "文件压缩比异常"
                f"（当前约 {ratio:.1f} 倍 / 上限 {limit_ratio:g} 倍），"
                "疑似压缩炸弹，请拆分文档或降低内容量后重新上传"
            ),
            extra={
                "error_code": ZIP_BOMB_ERROR_CODE,
                "reason": "compression_ratio",
                "uncompressed_bytes": total_uncompressed,
                "compressed_bytes": total_compressed,
                "ratio": round(ratio, 2),
                "limit_bytes": limit_bytes,
                "limit_ratio": limit_ratio,
            },
        )


def assert_content_matches_extension(file_type: str, content: bytes) -> None:
    """按扩展名校验内容头；失败抛 ValidationError（→ 422）。

    空文件由调用方先拦。未知类型（不在白名单）本函数不处理。
    """
    ext = file_type.lower().lstrip(".")
    if not content:
        return

    expected = _BINARY_MAGIC.get(ext)
    if expected is not None:
        if not content.startswith(expected):
            raise ValidationError(detail=_mismatch_detail(ext))
        if ext in ZIP_CONTAINER_TYPES:
            assert_zip_archive_safe(content)
        return

    if ext in _TEXT_TYPES:
        for prefix in _TEXT_FORBIDDEN_PREFIXES:
            if content.startswith(prefix):
                raise ValidationError(detail=_mismatch_detail(ext))
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(
                detail=(
                    f"文件内容与扩展名 .{ext} 不符（须为 UTF-8 文本），"
                    "请确认文件类型后重新上传"
                ),
            ) from exc

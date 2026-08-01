"""NW-45 · 上传落盘前 magic bytes 双检（≠ ClamAV · ≠ parse 入库魔数）。"""

from __future__ import annotations

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


def _mismatch_detail(file_type: str) -> str:
    return (
        f"文件内容与扩展名 .{file_type} 不符（疑似伪装扩展名），"
        "请确认文件类型后重新上传"
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

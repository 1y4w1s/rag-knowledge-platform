"""扫描 PDF OCR（Format-F4）；PaddleOCR + pdf2image，可选依赖。

Heavy 依赖仅在首次 OCR 调用时加载；``OCR_ENABLED=0`` 时不 import Paddle。
失败统一走 ``ocr_errors`` 原因码（B3）。
"""

from __future__ import annotations

import importlib.util
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from app.core.config import settings
from app.services.ingestion.ocr_errors import (
    OCR_CORRUPT,
    OCR_DEPS_MISSING,
    OCR_DISABLED,
    OCR_PAGE_LIMIT,
    OCR_POPPLER_MISSING,
    OCR_RUNTIME_ERROR,
    looks_like_poppler_missing,
    raise_ocr,
)

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

OcrPageResult = tuple[int, str]

_paddle_ocr: object | None = None


def is_ocr_enabled() -> bool:
    """环境开关 ``OCR_ENABLED``（默认开启）。"""
    return settings.ocr_enabled


def has_ocr_python_deps() -> bool:
    """PaddleOCR / pdf2image 是否已安装（不加载模型、不看开关）。"""
    return (
        importlib.util.find_spec("paddleocr") is not None
        and importlib.util.find_spec("pdf2image") is not None
    )


def is_ocr_runtime_available() -> bool:
    """开关开启且 Python OCR 依赖已安装（不加载模型）。"""
    return is_ocr_enabled() and has_ocr_python_deps()


def is_poppler_on_path() -> bool:
    """系统 PATH 是否有 poppler 工具（轻量，无子进程）。"""
    return shutil.which("pdftoppm") is not None or shutil.which("pdfinfo") is not None


def _require_ocr_enabled() -> None:
    if not settings.ocr_enabled:
        raise_ocr(OCR_DISABLED)


def _get_paddle_ocr():
    global _paddle_ocr
    _require_ocr_enabled()
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise_ocr(OCR_DEPS_MISSING, cause=exc)
        try:
            _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        except Exception as exc:
            raise_ocr(OCR_RUNTIME_ERROR, cause=exc)
    return _paddle_ocr


def _extract_text_from_paddle_result(raw) -> str:
    if not raw or raw[0] is None:
        return ""
    lines: list[str] = []
    for line in raw[0]:
        if not line or len(line) < 2:
            continue
        payload = line[1]
        text = payload[0] if isinstance(payload, (list, tuple)) else str(payload)
        if text:
            lines.append(str(text))
    return "\n".join(lines).strip()


def _run_ocr_on_image(image: Image.Image) -> str:
    import numpy as np

    ocr = _get_paddle_ocr()
    img_array = np.array(image.convert("RGB"))
    raw = ocr.ocr(img_array, cls=True)
    return _extract_text_from_paddle_result(raw)


def ocr_image(image: Image.Image, *, page_number: int = 1) -> OcrPageResult:
    """对单张 PIL 图像 OCR，返回 ``(页码, 文本)``。"""
    _require_ocr_enabled()
    try:
        text = _run_ocr_on_image(image)
    except Exception as exc:
        from app.services.ingestion.ocr_errors import OcrFailure

        if isinstance(exc, OcrFailure):
            raise
        raise_ocr(OCR_RUNTIME_ERROR, cause=exc)
    return (page_number, text)


def ocr_image_path(path: Path | str, *, page_number: int = 1) -> OcrPageResult:
    """对本地图片文件 OCR。"""
    from PIL import Image

    with Image.open(path) as image:
        return ocr_image(image, page_number=page_number)


def ocr_pdf_pages(
    pdf_path: Path | str,
    *,
    max_pages: int | None = None,
    on_page: Callable[[int, int], None] | None = None,
) -> list[OcrPageResult]:
    """将 PDF 每页渲染为图后 OCR，返回 ``[(页码, 文本), ...]``。

    ``on_page(n, m)``：可选同步回调（当前页 / 总页），供 NW-4 进度回写。
    """
    _require_ocr_enabled()
    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
    except ImportError as exc:
        raise_ocr(OCR_DEPS_MISSING, cause=exc)

    limit = max_pages if max_pages is not None else settings.ocr_max_pages
    pdf_path = Path(pdf_path)
    try:
        info = pdfinfo_from_path(str(pdf_path))
    except Exception as exc:
        if looks_like_poppler_missing(exc):
            raise_ocr(OCR_POPPLER_MISSING, cause=exc)
        raise_ocr(OCR_CORRUPT, cause=exc)

    page_count = int(info.get("Pages", 0))

    if page_count > limit:
        raise_ocr(
            OCR_PAGE_LIMIT,
            message=f"扫描页数超过上限（{limit} 页），请拆分后上传",
        )
    if page_count == 0:
        return []

    try:
        images = convert_from_path(str(pdf_path), first_page=1, last_page=page_count)
    except Exception as exc:
        if looks_like_poppler_missing(exc):
            raise_ocr(OCR_POPPLER_MISSING, cause=exc)
        raise_ocr(OCR_RUNTIME_ERROR, cause=exc)

    results: list[OcrPageResult] = []
    for page_number, image in enumerate(images, start=1):
        if on_page is not None:
            on_page(page_number, page_count)
        text = _run_ocr_on_image(image)
        results.append((page_number, text))
    return results

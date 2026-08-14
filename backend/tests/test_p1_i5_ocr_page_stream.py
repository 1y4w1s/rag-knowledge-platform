"""P1-I5 · OCR 逐页渲染识别（防 OOM）：逐页 convert、用完即弃、异常映射与源码哨兵。

测试全部 mock pdfinfo_from_path / convert_from_path / _run_ocr_on_image，
不依赖 poppler / PaddleOCR 环境；用带 close spy 的 FakeImage 验证位图释放。
"""

from __future__ import annotations

import ast
import logging
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from app.core.config import settings
from app.services.ingestion.ocr import ocr_pdf_pages
from app.services.ingestion.ocr_errors import (
    OCR_DISABLED,
    OCR_PAGE_LIMIT,
    OCR_POPPLER_MISSING,
    OCR_RUNTIME_ERROR,
    OcrFailure,
)

OCR_MODULE = "app.services.ingestion.ocr"


class FakeImage:
    """带 close spy 的假 PIL 位图。"""

    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


def _fake_images(count: int) -> list[FakeImage]:
    return [FakeImage() for _ in range(count)]


@contextmanager
def _fake_pdf2image(
    *,
    pages: int,
    per_page: list[list[FakeImage]] | None = None,
    convert_error: BaseException | None = None,
) -> Iterator[types.ModuleType]:
    """把假 pdf2image 注入 sys.modules，隔离可选依赖 poppler。"""
    module = types.ModuleType("pdf2image")
    if convert_error is not None:
        module.convert_from_path = Mock(side_effect=convert_error)
    elif per_page is not None:
        module.convert_from_path = Mock(side_effect=per_page)
    else:
        module.convert_from_path = Mock()
    module.pdfinfo_from_path = Mock(return_value={"Pages": pages})
    with patch.dict(sys.modules, {"pdf2image": module}):
        yield module


@pytest.fixture(autouse=True)
def _ocr_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)


def test_ocr_max_pages_default_is_30() -> None:
    assert settings.ocr_max_pages == 30


def test_convert_called_once_per_page_with_explicit_single_page_range(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=3, per_page=[[image] for image in _fake_images(3)]) as fake:
        with patch(f"{OCR_MODULE}._run_ocr_on_image", side_effect=["页 1", "页 2", "页 3"]):
            ocr_pdf_pages(pdf)

    assert fake.convert_from_path.call_count == 3
    assert fake.convert_from_path.call_args_list == [
        call(str(pdf), first_page=1, last_page=1),
        call(str(pdf), first_page=2, last_page=2),
        call(str(pdf), first_page=3, last_page=3),
    ]


def test_results_preserve_page_order_and_content(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    pages = [[FakeImage()] for _ in range(3)]

    with _fake_pdf2image(pages=3, per_page=pages):
        with patch(
            f"{OCR_MODULE}._run_ocr_on_image",
            side_effect=["第一页", "第二页", "第三页"],
        ):
            results = ocr_pdf_pages(pdf)

    assert results == [(1, "第一页"), (2, "第二页"), (3, "第三页")]


def test_each_page_image_closed_exactly_once_and_render_is_single_page(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "scan.pdf"
    images = _fake_images(3)

    with _fake_pdf2image(pages=3, per_page=[[image] for image in images]) as fake:
        with patch(f"{OCR_MODULE}._run_ocr_on_image", return_value="文本"):
            ocr_pdf_pages(pdf)

    for image in images:
        assert image.close_count == 1
    for current_call in fake.convert_from_path.call_args_list:
        assert current_call.kwargs["last_page"] == current_call.kwargs["first_page"]


def test_on_page_reports_each_page_before_ocr(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    events: list[str] = []

    def on_page(page_number: int, total: int) -> None:
        events.append(f"on_page:{page_number}/{total}")

    def run_ocr(_image: FakeImage) -> str:
        events.append("ocr")
        return "文本"

    with _fake_pdf2image(pages=3, per_page=[[FakeImage()] for _ in range(3)]):
        with patch(f"{OCR_MODULE}._run_ocr_on_image", side_effect=run_ocr):
            ocr_pdf_pages(pdf, on_page=on_page)

    assert events == [
        "on_page:1/3",
        "ocr",
        "on_page:2/3",
        "ocr",
        "on_page:3/3",
        "ocr",
    ]


def test_pdfinfo_called_only_once(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=3, per_page=[[FakeImage()] for _ in range(3)]) as fake:
        with patch(f"{OCR_MODULE}._run_ocr_on_image", return_value="文本"):
            ocr_pdf_pages(pdf)

    assert fake.pdfinfo_from_path.call_count == 1


def test_ocr_disabled_short_circuits_before_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "scan.pdf"
    monkeypatch.setattr(settings, "ocr_enabled", False)

    with _fake_pdf2image(pages=3) as fake:
        with pytest.raises(OcrFailure) as exc_info:
            ocr_pdf_pages(pdf)

    assert exc_info.value.reason == OCR_DISABLED
    fake.pdfinfo_from_path.assert_not_called()
    fake.convert_from_path.assert_not_called()


def test_page_limit_still_guards_before_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "scan.pdf"
    monkeypatch.setattr(settings, "ocr_max_pages", 2)

    with _fake_pdf2image(pages=3) as fake:
        with pytest.raises(OcrFailure) as exc_info:
            ocr_pdf_pages(pdf)

    assert exc_info.value.reason == OCR_PAGE_LIMIT
    assert "扫描页数超过上限" in str(exc_info.value)
    fake.convert_from_path.assert_not_called()


def test_max_pages_argument_still_guards_before_render(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=3) as fake:
        with pytest.raises(OcrFailure) as exc_info:
            ocr_pdf_pages(pdf, max_pages=2)

    assert exc_info.value.reason == OCR_PAGE_LIMIT
    fake.convert_from_path.assert_not_called()


def test_zero_page_pdf_returns_empty_without_render(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=0) as fake:
        results = ocr_pdf_pages(pdf)

    assert results == []
    fake.convert_from_path.assert_not_called()


def test_render_poppler_missing_maps_to_poppler_reason(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(
        pages=1, convert_error=RuntimeError("pdftoppm 未安装或不在 PATH")
    ):
        with pytest.raises(OcrFailure) as exc_info:
            ocr_pdf_pages(pdf)

    assert exc_info.value.reason == OCR_POPPLER_MISSING


def test_render_generic_error_maps_to_runtime_reason(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=1, convert_error=RuntimeError("render boom")):
        with pytest.raises(OcrFailure) as exc_info:
            ocr_pdf_pages(pdf)

    assert exc_info.value.reason == OCR_RUNTIME_ERROR


def test_empty_single_page_render_fails_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pdf = tmp_path / "scan.pdf"

    with _fake_pdf2image(pages=2, per_page=[[FakeImage()], []]):
        with patch(f"{OCR_MODULE}._run_ocr_on_image", return_value="第一页文本"):
            with caplog.at_level(logging.WARNING, logger=OCR_MODULE):
                with pytest.raises(OcrFailure) as exc_info:
                    ocr_pdf_pages(pdf)

    assert exc_info.value.reason == OCR_RUNTIME_ERROR
    assert "page=2" in caplog.text


def test_ocr_exception_still_closes_page_image(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    image = FakeImage()

    with _fake_pdf2image(pages=1, per_page=[[image]]):
        with patch(
            f"{OCR_MODULE}._run_ocr_on_image", side_effect=RuntimeError("paddle boom")
        ):
            with pytest.raises(RuntimeError, match="paddle boom"):
                ocr_pdf_pages(pdf)

    assert image.close_count == 1


def _top_level_imports(source: str) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(source)
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.append(("import", tuple(alias.name for alias in node.names)))
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                (node.module or "", tuple(alias.name for alias in node.names))
            )
    return imports


def test_source_no_longer_renders_whole_book_and_closes_images() -> None:
    source_path = Path(__file__).resolve().parent.parent / "app/services/ingestion/ocr.py"
    source = source_path.read_text(encoding="utf-8")

    assert "first_page=1, last_page=page_count" not in source
    assert "first_page=page_number, last_page=page_number" in source
    assert "image.close()" in source

    expected_imports: list[tuple[str, tuple[str, ...]]] = [
        ("__future__", ("annotations",)),
        ("import", ("importlib.util",)),
        ("import", ("logging",)),
        ("import", ("shutil",)),
        ("pathlib", ("Path",)),
        ("typing", ("TYPE_CHECKING", "Callable")),
        ("app.core.config", ("settings",)),
        (
            "app.services.ingestion.ocr_errors",
            (
                "OCR_CORRUPT",
                "OCR_DEPS_MISSING",
                "OCR_DISABLED",
                "OCR_PAGE_LIMIT",
                "OCR_POPPLER_MISSING",
                "OCR_RUNTIME_ERROR",
                "looks_like_poppler_missing",
                "raise_ocr",
            ),
        ),
    ]
    assert _top_level_imports(source) == expected_imports

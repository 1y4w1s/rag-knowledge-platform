"""OCR 失败原因码与用户可见文案（B3）。

原因进日志 ``reason=``；``error_message`` 用人话。禁止把「未安装」写成「未启用」。
"""

from __future__ import annotations

from typing import NoReturn

# --- reason codes ---
OCR_DISABLED = "ocr_disabled"
OCR_DEPS_MISSING = "ocr_deps_missing"
OCR_POPPLER_MISSING = "ocr_poppler_missing"
OCR_PAGE_LIMIT = "ocr_page_limit"
OCR_EMPTY = "ocr_empty"
OCR_CORRUPT = "ocr_corrupt"
OCR_RUNTIME_ERROR = "ocr_runtime_error"

OCR_USER_MESSAGES: dict[str, str] = {
    OCR_DISABLED: (
        "扫描件 OCR 未开启（OCR_ENABLED=0），请联系管理员或上传带文字层的 PDF"
    ),
    OCR_DEPS_MISSING: "OCR 引擎未安装（需 PaddleOCR），当前环境无法识别扫描件",
    OCR_POPPLER_MISSING: "OCR 渲染组件缺失（poppler），无法将 PDF 转为图片识别",
    OCR_PAGE_LIMIT: "扫描页数超过上限，请拆分后上传",
    OCR_EMPTY: "OCR 未识别到文字",
    OCR_CORRUPT: "PDF 加密或损坏，无法进行 OCR 识别",
    OCR_RUNTIME_ERROR: (
        "OCR 处理失败，请稍后重试；若反复失败请联系管理员查看服务日志"
    ),
}

# 历史短句 → reason（兼容旧 raise / 测试迁移期）
_LEGACY_MESSAGE_TO_REASON: dict[str, str] = {
    "不支持扫描件": OCR_DISABLED,
    "OCR 未启用": OCR_DISABLED,
    "OCR 服务未启用": OCR_DEPS_MISSING,
    "OCR 服务未安装": OCR_DEPS_MISSING,
    "OCR 未识别到文字": OCR_EMPTY,
    "PDF 加密或损坏，无法进行 OCR 识别": OCR_CORRUPT,
}


class OcrFailure(ValueError):
    """携带 ``reason`` 的 OCR 失败；``str(exc)`` 即为用户文案。"""

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message if message is not None else message_for(reason))


def message_for(reason: str) -> str:
    return OCR_USER_MESSAGES.get(reason, OCR_USER_MESSAGES[OCR_RUNTIME_ERROR])


def raise_ocr(
    reason: str,
    *,
    message: str | None = None,
    cause: BaseException | None = None,
) -> NoReturn:
    err = OcrFailure(reason, message=message)
    if cause is not None:
        raise err from cause
    raise err


def reason_from_exception(exc: BaseException) -> str | None:
    if isinstance(exc, OcrFailure):
        return exc.reason
    if isinstance(exc, (ValueError, RuntimeError)):
        text = str(exc).strip()
        if text in _LEGACY_MESSAGE_TO_REASON:
            return _LEGACY_MESSAGE_TO_REASON[text]
        if text.startswith("扫描页数超过上限"):
            return OCR_PAGE_LIMIT
    return None


def looks_like_poppler_missing(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__} {exc}".lower()
    needles = (
        "poppler",
        "pdftoppm",
        "pdfinfo",
        "unable to get page count",
        "pdfinfonotinstalled",
    )
    return any(n in msg for n in needles)

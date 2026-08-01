"""PII 脱敏（NW-27 回显 · NW-34 送模 scrub · SEC-5）。

- mask_pii：规则集（手机号/证件/邮箱 → 占位）
- citation 回显：executor.excerpt 调 mask（CITATION_REDACT_*）
- 送模片段：scrub_llm_context（LLM_CONTEXT_REDACT_*，默认关；仍算出境 ≠ NW-33）
不 scrub 入库 / 预览 / 问句 / 历史。
"""

from __future__ import annotations

import re

# 连续 11 位大陆手机；前后非数字，减少订单号误伤
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# 18 位身份证（末位可 X）；不做校验位
_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
# 简单邮箱子集（非完整 RFC）
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])",
)

_PHONE_PLACEHOLDER = "【手机号】"
_ID_PLACEHOLDER = "【证件号】"
_EMAIL_PLACEHOLDER = "【邮箱】"


def mask_pii(text: str) -> str:
    """对约定敏感模式做字符串替换；永不记录匹配捕获组。"""
    if not text:
        return text
    out = _PHONE_RE.sub(_PHONE_PLACEHOLDER, text)
    out = _ID_RE.sub(_ID_PLACEHOLDER, out)
    out = _EMAIL_RE.sub(_EMAIL_PLACEHOLDER, out)
    return out


def scrub_llm_context(text: str) -> str:
    """送模【检索片段】正文：开 LLM_CONTEXT_REDACT 则 mask_pii，否则原样。"""
    if not text:
        return text
    from app.core.config import settings

    if not settings.llm_context_redact_enabled:
        return text
    return mask_pii(text)

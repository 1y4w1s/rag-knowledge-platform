"""P2-R16：送大模型前正文 PII 脱敏默认开启（LLM_CONTEXT_REDACT_ENABLED=true）。"""

from __future__ import annotations

import pytest

from app.core.config import Settings, settings
from app.services.rag.redact import scrub_llm_context

_PHONE = "13812345678"
_ID = "110101199001011234"
_EMAIL = "alice@example.com"
_PII_BODY = f"联系人手机 {_PHONE}，身份证 {_ID}，邮箱 {_EMAIL}。"


def _default_redact_enabled() -> bool:
    return Settings.model_fields["llm_context_redact_enabled"].default


def test_config_default_is_on() -> None:
    """P2-R16：送模 scrub 的代码默认值必须为开，防止回退到明文出境。"""
    assert _default_redact_enabled() is True


def test_scrub_default_masks_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认值下 scrub_llm_context 不再原样放行手机号/证件/邮箱。"""
    monkeypatch.setattr(settings, "llm_context_redact_enabled", _default_redact_enabled())
    out = scrub_llm_context(_PII_BODY)

    assert _PHONE not in out
    assert _ID not in out
    assert _EMAIL not in out
    assert "【手机号】" in out
    assert "【证件号】" in out
    assert "【邮箱】" in out

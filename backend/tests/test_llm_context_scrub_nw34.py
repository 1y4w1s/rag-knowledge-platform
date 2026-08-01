"""NW-34：送模【检索片段】scrub（独立开关 · 复用 mask_pii）。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.rag.generation import build_messages
from app.services.rag.redact import scrub_llm_context
from app.services.rag.types import RetrievedChunk

_PHONE = "13812345678"
_ID = "110101199001011234"
_EMAIL = "alice@example.com"
_PII_BODY = f"联系人手机 {_PHONE}，身份证 {_ID}，邮箱 {_EMAIL}。"


def _chunk(content: str, *, parent: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="pii_sample.md",
        content=content,
        parent_content=parent,
        page_number=1,
        section_title="联系方式",
        heading_path="手册>联系",
        similarity=0.9,
    )


def _context_blob(messages: list[dict[str, str]]) -> str:
    return "\n".join(m["content"] for m in messages if "【检索片段】" in m.get("content", ""))


def test_scrub_off_keeps_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", False)
    assert scrub_llm_context(_PII_BODY) == _PII_BODY
    assert _PHONE in scrub_llm_context(_PII_BODY)


def test_scrub_on_masks_three_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    out = scrub_llm_context(_PII_BODY)
    assert _PHONE not in out
    assert _ID not in out
    assert _EMAIL not in out
    assert "【手机号】" in out
    assert "【证件号】" in out
    assert "【邮箱】" in out


def test_build_messages_on_no_raw_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    messages = build_messages("联系方式是什么？", [_chunk(_PII_BODY)])
    blob = _context_blob(messages)
    assert blob
    assert _PHONE not in blob
    assert _ID not in blob
    assert _EMAIL not in blob
    assert "【手机号】" in blob
    # 问句不洗
    assert any("【用户问题】" in m["content"] and "联系方式是什么？" in m["content"] for m in messages)


def test_build_messages_off_keeps_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", False)
    messages = build_messages("联系方式是什么？", [_chunk(_PII_BODY)])
    blob = _context_blob(messages)
    assert _PHONE in blob
    assert _EMAIL in blob


def test_build_messages_prefers_scrubbed_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    leaf = "leaf 无号"
    parent = f"parent 含 {_PHONE}"
    messages = build_messages("问", [_chunk(leaf, parent=parent)])
    blob = _context_blob(messages)
    assert _PHONE not in blob
    assert "【手机号】" in blob
    assert "leaf 无号" not in blob


@pytest.mark.asyncio
async def test_verify_answer_scrubs_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    captured: list[str] = []

    async def _fake_stream(messages: list[dict[str, str]], **_kw):
        captured.append(messages[0]["content"])
        yield '{"verified": true}'

    monkeypatch.setattr(
        "app.services.rag.generation.stream_deepseek_tokens",
        _fake_stream,
    )
    from app.services.rag.generation import verify_answer

    ok, _ = await verify_answer("任意答", [_chunk(_PII_BODY)], "联系方式？")
    assert ok is True
    assert captured
    assert _PHONE not in captured[0]
    assert "【手机号】" in captured[0]


def test_decoupled_from_citation_redact(monkeypatch: pytest.MonkeyPatch) -> None:
    """关回显仍可开送模；开回显关送模 → prompt 仍原文。"""
    monkeypatch.setattr(settings, "citation_redact_enabled", False)
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    blob = _context_blob(build_messages("q", [_chunk(_PII_BODY)]))
    assert _PHONE not in blob

    monkeypatch.setattr(settings, "citation_redact_enabled", True)
    monkeypatch.setattr(settings, "llm_context_redact_enabled", False)
    blob2 = _context_blob(build_messages("q", [_chunk(_PII_BODY)]))
    assert _PHONE in blob2

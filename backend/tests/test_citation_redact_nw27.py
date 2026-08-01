"""NW-27：citation excerpt 脱敏（先 mask 后截断）。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.rag.executor import excerpt
from app.services.rag.redact import mask_pii
from app.services.rag.retrieval import chunk_to_citation
from app.services.rag.types import RetrievedChunk


def _chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="pii_sample.md",
        content=content,
        page_number=1,
        section_title="联系方式",
        heading_path="手册>联系",
        similarity=0.9,
    )


def test_mask_phone_id_email() -> None:
    text = (
        "联系人手机 13812345678，"
        "身份证 110101199001011234，"
        "邮箱 alice@example.com。"
    )
    out = mask_pii(text)
    assert "13812345678" not in out
    assert "110101199001011234" not in out
    assert "alice@example.com" not in out
    assert "【手机号】" in out
    assert "【证件号】" in out
    assert "【邮箱】" in out


def test_mask_phone_requires_non_digit_boundary() -> None:
    # 前后仍是数字 → 不当手机号（订单号防误伤）
    assert mask_pii("13812345678901") == "13812345678901"
    assert "【手机号】" in mask_pii("联系 13812345678 结束")
    assert "13812345678" not in mask_pii("联系 13812345678 结束")


def test_mask_id_allows_trailing_x() -> None:
    assert "【证件号】" in mask_pii("证号 11010119900101123X")
    assert "11010119900101123X" not in mask_pii("证号 11010119900101123X")


def test_excerpt_mask_then_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    """半截号在截断边界：须先 mask，否则前缀泄漏。"""
    monkeypatch.setattr(settings, "citation_redact_enabled", True)
    # 195 字填充 + 完整手机 → 若先截到 200，只剩前几位数字
    filler = "字" * 195
    phone = "13812345678"
    out = excerpt(filler + phone)
    assert "【手机号】" in out
    assert phone not in out
    assert "1381234" not in out
    assert len(out) <= 200


def test_excerpt_off_keeps_raw_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "citation_redact_enabled", False)
    text = "手机 13812345678 备用"
    assert excerpt(text) == text
    assert "【手机号】" not in excerpt(text)


def test_chunk_to_citation_redacts_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "citation_redact_enabled", True)
    citation = chunk_to_citation(_chunk("紧急联系人电话：13900001111。"))
    assert "【手机号】" in citation["excerpt"]
    assert "13900001111" not in citation["excerpt"]

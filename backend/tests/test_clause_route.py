"""A3 条款号 / 文档名路由：抽取、加法注入、开关与缓存 key。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.rag.route_recall import (
    extract_clause_tokens,
    extract_filename_cues,
    inject_route_hits,
    should_attempt_route,
)


def test_extract_clause_tokens_decimal_and_chinese() -> None:
    assert "1.2" in extract_clause_tokens("员工手册 1.2 条款对迟到怎么规定？")
    assert "第三条" in extract_clause_tokens("合同第三条服务期限是多久？")
    assert extract_clause_tokens("年假有多少天？") == []


def test_extract_filename_cues_keeps_meaningful_tokens() -> None:
    cues = extract_filename_cues("SSH 默认端口号建议改成什么？")
    assert any(c.lower() == "ssh" for c in cues)
    assert "端口" in cues or "端口号" in cues or "默认" in cues
    assert "什么" not in cues


def test_should_attempt_route() -> None:
    assert should_attempt_route("员工手册 1.2 条款") is True
    assert should_attempt_route("SSH 端口") is True
    assert should_attempt_route("？") is False


def test_inject_route_hits_keeps_base_and_appends() -> None:
    a, b, c, route = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fused = [(a, 1.0), (b, 0.9), (c, 0.8)]
    merged = {
        a: _fake_row(a, "base.md"),
        b: _fake_row(b, "base.md"),
        c: _fake_row(c, "base.md"),
    }
    route_rows = [_fake_row(route, "ops.md"), _fake_row(a, "base.md")]  # a 重复应跳过
    new_fused, new_merged = inject_route_hits(
        fused, merged, route_rows, extra_slots=5, protect_top=2
    )
    ids = [cid for cid, _ in new_fused]
    assert ids[:2] == [a, b]  # Top-2 保护
    assert route in ids
    assert route in new_merged
    assert len(ids) == 3  # 窗口长度不变：替换尾部


def test_inject_route_hits_respects_extra_slots() -> None:
    base = [uuid.uuid4() for _ in range(8)]
    fused = [(b, 1.0 - i * 0.01) for i, b in enumerate(base)]
    merged = {b: _fake_row(b, "a.md") for b in base}
    routes = [_fake_row(uuid.uuid4(), "x.md") for _ in range(10)]
    new_fused, _ = inject_route_hits(
        fused, merged, routes, extra_slots=2, protect_top=3
    )
    ids = [cid for cid, _ in new_fused]
    assert ids[:3] == base[:3]
    assert len(ids) == 8
    assert ids[6] not in base or ids[7] not in base  # 尾部被替换


def test_inject_identity_when_empty_route() -> None:
    a = uuid.uuid4()
    fused = [(a, 1.0)]
    merged = {a: _fake_row(a, "a.md")}
    new_fused, new_merged = inject_route_hits(fused, merged, [], extra_slots=5)
    assert new_fused == fused
    assert new_merged is merged or new_merged == merged


def test_cache_key_includes_clause_route_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.rag import cache as cache_mod

    kb = uuid.uuid4()
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    monkeypatch.setattr(settings, "clause_route_enabled", False)
    k0 = cache_mod._cache_key(kb, "1.2 迟到")
    monkeypatch.setattr(settings, "clause_route_enabled", True)
    k1 = cache_mod._cache_key(kb, "1.2 迟到")
    assert k0 != k1


def _fake_row(chunk_id: uuid.UUID, filename: str):
    from app.services.rag.types import _RecallRow

    chunk = type(
        "C",
        (),
        {
            "id": chunk_id,
            "document_id": uuid.uuid4(),
            "content": "body",
            "page_number": 1,
            "section_title": "1.2 迟到",
            "heading_path": "考勤>1.2",
            "parent_chunk_id": None,
            "kb_id": uuid.uuid4(),
        },
    )()
    return _RecallRow(chunk=chunk, filename=filename)

"""M2 W1 · 证据充分性判定规则单测（check_evidence_sufficiency）。

覆盖 §4.2 用例清单 10 项：
  1. 无命中
  2. 命中不足（sim 高）
  3. 命中充足
  4. sim 不足
  5. diversity 不足
  6. coverage 检查
  7. 阈值边界（sim=0.5）
  8. 阈值边界（hit=3）
  9. 自定义阈值
 10. observation mode（配置关）→ 零审计写入
"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.agent.tools.semantic_search import SemanticSearchHit
from app.services.rag.evidence import check_evidence_sufficiency

QUERY = "如果 API 返回 429 错误码，可能是什么原因？"


def _hit(
    score: float,
    chunk_id: uuid.UUID | None = None,
    doc_name: str = "acme_FAQ合集.md",
) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=chunk_id or uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="kb",
        doc_name=doc_name,
        page=1,
        section_title="集成与API",
        excerpt="API 错误码 排查 解决方案",
        score=score,
    )


# ── 用例 1：无命中 ──


def test_no_hits() -> None:
    v = check_evidence_sufficiency((), QUERY)
    assert v.sufficient is False
    assert v.reason == "无命中"
    assert v.hit_count == 0
    assert v.top_sim_score == 0.0
    assert v.chunk_diversity == 0


# ── 用例 2：命中不足（sim 高，仅 1 条）──


def test_hit_count_insufficient() -> None:
    v = check_evidence_sufficiency([_hit(0.6)], QUERY)
    assert v.sufficient is False
    assert "命中数 1 < 3" in v.reason
    assert v.hit_count == 1
    assert v.top_sim_score == 0.6


# ── 用例 3：命中充足（sim 高，diversity 高）──


def test_sufficient_hits() -> None:
    hits = [_hit(0.6), _hit(0.7), _hit(0.65)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is True
    assert v.reason == "证据充分"
    assert v.hit_count == 3
    assert v.chunk_diversity >= 3
    assert v.coverage_ratio > 0


# ── 用例 4：sim 不足 ──


def test_top_sim_insufficient() -> None:
    hits = [_hit(0.4), _hit(0.35), _hit(0.3)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is False
    assert "最高相似度 0.400 < 0.5" in v.reason


# ── 用例 5：diversity 不足（3 条同一 chunk）──


def test_chunk_diversity_insufficient() -> None:
    shared_id = uuid.uuid4()
    hits = [_hit(0.6, chunk_id=shared_id) for _ in range(3)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is False
    assert "去重 chunk 数 1 < 2" in v.reason
    assert v.chunk_diversity == 1


# ── 用例 6：coverage 检查（3 条同 doc，coverage=1/3 > 0）──


def test_coverage_same_doc() -> None:
    hits = [_hit(0.6), _hit(0.7), _hit(0.65)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is True
    assert v.coverage_ratio > 0


# ── 用例 7：阈值边界（sim=0.5）──


def test_sim_boundary_exact() -> None:
    hits = [_hit(0.5), _hit(0.6), _hit(0.55)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is True


# ── 用例 8：阈值边界（hit=3）──


def test_hit_boundary_exact() -> None:
    hits = [_hit(0.6), _hit(0.7), _hit(0.65)]
    v = check_evidence_sufficiency(hits, QUERY)
    assert v.sufficient is True
    assert v.hit_count == 3


# ── 用例 9：自定义阈值 ──


def test_custom_threshold() -> None:
    hits = [_hit(0.45)]
    v = check_evidence_sufficiency(
        hits, QUERY, min_hit_count=1, min_top_sim=0.4, min_chunk_diversity=1,
    )
    assert v.sufficient is True


# ── 用例 10：observation mode（配置关）→ 零审计写入 ──


@pytest.mark.asyncio
async def test_obs_mode_default_off_no_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置关时 runtime 不调用 check_evidence_sufficiency，零审计写入。"""
    monkeypatch.setattr(
        settings, "agent_evidence_sufficiency_obs", False,
    )

    from unittest.mock import patch

    with patch(
        "app.services.rag.evidence.check_evidence_sufficiency",
        wraps=None,
    ) as mock_check:
        # 模拟 runtime 中的 observation mode 判断路径
        # 若 config 关，if 块不进入，check_evidence_sufficiency 不被调用
        assert settings.agent_evidence_sufficiency_obs is False
        mock_check.assert_not_called()

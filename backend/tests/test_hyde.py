"""HyDE 单元测试（完全独立，无需项目 conftest）。

测试策略：
- mock complete_chat 避免真实 LLM 调用
- 测试：正常生成、降级（失败返回 None）、空 query、环境变量开关
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.services.rag.hyde import (
    generate_hypothetical_document,
    is_hyde_enabled,
)


# ── Fixtures ──


@pytest.fixture(autouse=True)
def reset_hyde_cache():
    """每次测试前重置 HyDE 环境变量缓存。"""
    # 直接修改模块内部缓存
    import app.services.rag.hyde as hyde_mod
    hyde_mod._HYDE_ENABLED = None
    yield
    hyde_mod._HYDE_ENABLED = None


# ═══════════════════════════════════════════════════════════════
# is_hyde_enabled
# ═══════════════════════════════════════════════════════════════


class TestIsHydeEnabled:
    """验证环境变量闸门。"""

    def test_default_disabled(self):
        """未设置 HYDE_ENABLED 时返回 False。"""
        os.environ.pop("HYDE_ENABLED", None)
        assert is_hyde_enabled() is False

    def test_explicit_true(self):
        """HYDE_ENABLED=true 时返回 True。"""
        os.environ["HYDE_ENABLED"] = "true"
        assert is_hyde_enabled() is True

    def test_explicit_false(self):
        """HYDE_ENABLED=false 时返回 False。"""
        os.environ["HYDE_ENABLED"] = "false"
        assert is_hyde_enabled() is False

    def test_numeric_true(self):
        """HYDE_ENABLED=1 时返回 True。"""
        os.environ["HYDE_ENABLED"] = "1"
        assert is_hyde_enabled() is True

    def test_cache_not_re_read(self):
        """验证缓存：第二次调用不走 os.environ。"""
        os.environ["HYDE_ENABLED"] = "true"
        assert is_hyde_enabled() is True
        os.environ["HYDE_ENABLED"] = "false"
        # 缓存 hit，仍为 True
        assert is_hyde_enabled() is True


# ═══════════════════════════════════════════════════════════════
# generate_hypothetical_document
# ═══════════════════════════════════════════════════════════════


class TestGenerateHypotheticalDocument:
    """验证假设文档生成。"""

    @pytest.fixture(autouse=True)
    def enable_hyde(self):
        os.environ["HYDE_ENABLED"] = "true"
        import app.services.rag.hyde as hyde_mod
        hyde_mod._HYDE_ENABLED = None
        yield

    @patch("app.services.rag.hyde.complete_chat", new_callable=AsyncMock)
    async def test_normal_generation(self, mock_complete):
        """正常调用 complete_chat 返回假设文档。"""
        from app.core.config import settings

        mock_complete.return_value = "索隐是一款企业级知识库管理平台，支持文档管理、智能问答和引用溯源。"
        with patch.object(settings, "deepseek_api_key", "sk-test"):
            result = await generate_hypothetical_document("索隐是什么？")
        assert result is not None
        assert "索隐" in result
        assert len(result) > 10

    @patch("app.services.rag.hyde.complete_chat", new_callable=AsyncMock)
    async def test_empty_result_fallback(self, mock_complete):
        """complete_chat 返回空字符串时降级返回 None。"""
        mock_complete.return_value = "   "
        result = await generate_hypothetical_document("测试查询")
        assert result is None

    @patch("app.services.rag.hyde.complete_chat", new_callable=AsyncMock)
    async def test_exception_fallback(self, mock_complete):
        """complete_chat 抛异常时降级返回 None，不传播异常。"""
        mock_complete.side_effect = RuntimeError("API 不可达")
        result = await generate_hypothetical_document("测试查询")
        assert result is None

    async def test_empty_query(self):
        """空 query 时直接返回 None，不调 complete_chat。"""
        result = await generate_hypothetical_document("")
        assert result is None

    async def test_whitespace_query(self):
        """仅空格的 query 直接返回 None。"""
        result = await generate_hypothetical_document("   ")
        assert result is None

    @patch("app.services.rag.hyde.complete_chat", new_callable=AsyncMock)
    async def test_hyde_disabled_returns_none(self, mock_complete):
        """HYDE_ENABLED=false 时直接返回 None，不调 LLM。"""
        os.environ["HYDE_ENABLED"] = "false"
        import app.services.rag.hyde as hyde_mod
        hyde_mod._HYDE_ENABLED = None
        result = await generate_hypothetical_document("测试查询")
        assert result is None
        mock_complete.assert_not_called()

    @patch("app.services.rag.hyde.complete_chat", new_callable=AsyncMock)
    async def test_no_api_key_returns_none(self, mock_complete):
        """P2-R9：无 LLM key 时直接返回 None，不把兜底文案当真假设文档。"""
        from app.core.config import settings

        with patch.object(settings, "deepseek_api_key", ""), patch.object(
            settings, "tongyi_api_key", ""
        ):
            result = await generate_hypothetical_document("索隐是什么？")
        assert result is None
        mock_complete.assert_not_called()

"""D1 GraphRAG — Query NER 单元测试。

覆盖 query_ner_sync 函数 + graph_entity_recall 兜底逻辑分支。
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.rag.query_ner import (
    _build_prompt,
    _try_parse_name_list,
    query_ner_sync,
)


class TestTryParseNameList:
    """_try_parse_name_list 解析测试"""

    def test_normal_json(self) -> None:
        raw = '{"entities": ["华为技术有限公司", "张三"]}'
        result = _try_parse_name_list(raw)
        assert result == ["华为技术有限公司", "张三"]

    def test_empty_entities(self) -> None:
        raw = '{"entities": []}'
        result = _try_parse_name_list(raw)
        assert result == []

    def test_malformed_fallback(self) -> None:
        raw = 'some text\n{"entities": ["华为"]}\nmore text'
        result = _try_parse_name_list(raw)
        assert result == ["华为"]

    def test_completely_garbage(self) -> None:
        raw = "not json at all!!!"
        result = _try_parse_name_list(raw)
        assert result == []

    def test_empty_string(self) -> None:
        result = _try_parse_name_list("")
        assert result == []

    def test_entities_not_list(self) -> None:
        raw = '{"entities": "华为"}'
        result = _try_parse_name_list(raw)
        assert result == []


class TestBuildPrompt:
    """_build_prompt 构造测试"""

    def test_no_context(self) -> None:
        prompt = _build_prompt("华为的项目", None)
        assert "华为的项目" in prompt
        # _CONTEXT_HINT 块（"对话历史：\n"）不应出现在无 context 的 prompt 中
        assert "对话历史：\n" not in prompt

    def test_with_context(self) -> None:
        context = [
            {"role": "user", "content": "华为进展如何"},
            {"role": "assistant", "content": "正在推进"},
        ]
        prompt = _build_prompt("他们的项目", context)
        assert "他们的项目" in prompt
        assert "对话历史" in prompt
        assert "user: 华为进展如何" in prompt
        assert "assistant: 正在推进" in prompt

    def test_context_truncated(self) -> None:
        """超过 4 条时只取最近 4 条"""
        context = [{"role": "user", "content": f"msg{i}"} for i in range(6)]
        prompt = _build_prompt("test", context)
        # 应只含最近的 4 条：msg2, msg3, msg4, msg5
        assert "msg0" not in prompt
        assert "msg1" not in prompt
        assert "msg2" in prompt
        assert "msg5" in prompt

    def test_context_safe_get(self) -> None:
        """缺失 role/content 字段时不抛异常"""
        context = [{"role": "user"}, {"content": "仅content"}]
        prompt = _build_prompt("test", context)
        assert "unknown" in prompt  # role 缺省时回退 "unknown"
        assert "仅content" in prompt


class TestQueryNerSync:
    """query_ner_sync 同步函数测试"""

    FAKE_VALID_RESPONSE = {
        "choices": [
            {
                "message": {
                    "content": '{"entities": ["华为技术有限公司", "张三"]}',
                }
            }
        ]
    }

    FAKE_EMPTY_RESPONSE = {
        "choices": [{"message": {"content": '{"entities": []}'}}]
    }

    FAKE_MALFORMED_RESPONSE = {
        "choices": [{"message": {"content": "```json\n{\"entities\": [\"华为\"]}\n```"}}]
    }

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_basic(self, mock_client: MagicMock) -> None:
        """正常返回实体名列表"""
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_VALID_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync("华为的项目")
        assert result == ["华为技术有限公司", "张三"]

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_empty(self, mock_client: MagicMock) -> None:
        """返回空实体列表"""
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_EMPTY_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync("你好")
        assert result == []

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_malformed_fallback(self, mock_client: MagicMock) -> None:
        """畸形 JSON 触发兜底解析"""
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_MALFORMED_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync("test")
        assert result == ["华为"]

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_timeout(self, mock_client: MagicMock) -> None:
        """超时降级返回 []"""
        mock_instance = MagicMock()
        mock_instance.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync("华为的项目")
        assert result == []

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_http_error(self, mock_client: MagicMock) -> None:
        """HTTP 错误降级返回 []"""
        mock_instance = MagicMock()
        mock_instance.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync("华为的项目")
        assert result == []

    def test_no_api_key(self) -> None:
        """无 API key 时返回 [] 不抛异常"""
        with patch("app.services.rag.query_ner.settings") as mock_settings:
            mock_settings.deepseek_api_key = ""
            result = query_ner_sync("华为的项目")
            assert result == []

    @patch("app.services.rag.query_ner.httpx.Client")
    @patch("app.services.rag.query_ner.settings.deepseek_api_key", "test-key")
    def test_with_context(self, mock_client: MagicMock) -> None:
        """传递 context 时 prompt 含对话历史"""
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_VALID_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = query_ner_sync(
            "他们的项目",
            context=[{"role": "user", "content": "华为进展如何"}],
        )
        assert result == ["华为技术有限公司", "张三"]
        # 验证实际调用的 payload 含 context
        call_kwargs = mock_instance.post.call_args[1]
        messages = call_kwargs["json"]["messages"]
        prompt_text = messages[0]["content"]
        assert "华为进展如何" in prompt_text
        assert "user" in prompt_text


class TestGraphEntityRecallNERFallback:
    """graph_entity_recall 的 NER 兜底逻辑（通过 import 进 retrieval.py）"""

    @pytest.mark.asyncio
    async def test_fallback_trigger_on_empty_tokens(self) -> None:
        """空 token（纯标点）时 NER 兜底被调用"""
        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.query_ner_sync", return_value=["华为"]),
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()
            mock_result = []

            # 所有 execute 统一返回空结果
            mock_execute = MagicMock()
            mock_execute.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_execute)

            result = await graph_entity_recall(mock_db, ANY, "？？", mock_result)
            assert result == []

    @pytest.mark.asyncio
    async def test_fallback_on_empty_tokens_with_ner_match(self) -> None:
        """空 token（纯标点）时 NER 兜底命中 entity"""
        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.query_ner_sync", return_value=["华为技术有限公司"]),
        ):
            from app.services.rag.retrieval import graph_entity_recall
            from uuid import UUID

            mock_db = AsyncMock()
            mock_result = []

            mock_entity = MagicMock()
            mock_entity.id = UUID("00000000-0000-0000-0000-000000000001")

            # 所有 execute 返回统一结果：NER ILIKE 返回实体、mention 返回空
            mock_execute_all = MagicMock()
            mock_execute_all.scalars.return_value.all.return_value = [mock_entity]
            mock_db.execute = AsyncMock(return_value=mock_execute_all)

            result = await graph_entity_recall(mock_db, ANY, "？？", mock_result)
            assert result == []

    @pytest.mark.asyncio
    async def test_graph_recall_disabled(self) -> None:
        """graph_recall_enabled=False 时 NER 不被调用"""
        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", False),
            patch("app.services.rag.retrieval.query_ner_sync") as mock_ner,
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()
            result = await graph_entity_recall(mock_db, ANY, "华为", [])
            mock_ner.assert_not_called()

    @pytest.mark.asyncio
    async def test_lexical_match_skips_ner(self) -> None:
        """词法匹配命中实体时 NER 不被调用"""
        with (
            patch("app.services.rag.retrieval.settings.graph_recall_enabled", True),
            patch("app.services.rag.retrieval.query_ner_sync") as mock_ner,
        ):
            from app.services.rag.retrieval import graph_entity_recall

            mock_db = AsyncMock()

            mock_entity = MagicMock()
            mock_entity.id = "some-id"

            # 所有 execute 返回统一结果：词法 ILIKE 返回实体、mention 返回空
            mock_execute_all = MagicMock()
            mock_execute_all.scalars.return_value.all.return_value = [mock_entity]
            mock_db.execute = AsyncMock(return_value=mock_execute_all)

            result = await graph_entity_recall(mock_db, ANY, "华为", [])

            mock_ner.assert_not_called()

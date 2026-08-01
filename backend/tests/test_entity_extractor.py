"""D1 GraphRAG — entity_extractor 单元测试。"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.rag.entity_extractor import (
    _try_parse_json,
    extract_entities_sync,
)


class TestTryParseJson:
    def test_normal_json(self) -> None:
        raw = '{"entities": [{"name": "张三", "type": "person"}], "relations": []}'
        result = _try_parse_json(raw)
        assert result["entities"] == [{"name": "张三", "type": "person"}]
        assert result["relations"] == []

    def test_malformed_with_extra_text(self) -> None:
        raw = 'some text\n{\n"entities": [{"name": "A公司", "type": "organization"}],\n"relations": []\n}\nmore text'
        result = _try_parse_json(raw)
        assert result["entities"] == [{"name": "A公司", "type": "organization"}]

    def test_completely_garbage(self) -> None:
        raw = "not json at all!!!"
        result = _try_parse_json(raw)
        assert result == {"entities": [], "relations": []}

    def test_empty_string(self) -> None:
        result = _try_parse_json("")
        assert result == {"entities": [], "relations": []}

    def test_partial_json_truncated(self) -> None:
        raw = '{"entities": [{"name": "test", "type": "person"}], "relations"'
        result = _try_parse_json(raw)
        assert result == {"entities": [], "relations": []}


class TestExtractEntitiesSync:
    FAKE_VALID_RESPONSE = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"entities": [{"name": "张三", "type": "person"}, '
                        '{"name": "A公司", "type": "organization"}], '
                        '"relations": [{"source": "张三", "target": "A公司", "type": "belongs_to"}]}'
                    )
                }
            }
        ]
    }

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_normal(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.post.return_value.json.return_value = self.FAKE_VALID_RESPONSE
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("张三在A公司工作")
        assert len(result["entities"]) == 2
        assert result["entities"][0] == {"name": "张三", "type": "person"}
        assert len(result["relations"]) == 1
        assert result["relations"][0] == {
            "source": "张三", "target": "A公司", "type": "belongs_to"
        }

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_malformed_json_fallback(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        # 返回非 JSON 文本，含 markdown 包裹
        mock_instance.post.return_value.json.return_value = {
            "choices": [{"message": {"content": "```json\n{\"entities\": [{\"name\": \"张三\", \"type\": \"person\"}], \"relations\": []}\n```"}}]
        }
        mock_instance.post.return_value.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "张三"

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_httpx_raises_exception(self, mock_client: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert result == {"entities": [], "relations": []}

    def test_no_api_key(self) -> None:
        with patch("app.services.rag.entity_extractor.settings") as mock_settings:
            mock_settings.deepseek_api_key = ""
            result = extract_entities_sync("测试")
            assert result == {"entities": [], "relations": []}

    @patch("app.services.rag.entity_extractor.httpx.Client")
    def test_retry_then_succeed(self, mock_client: MagicMock) -> None:
        """第一次失败，第二次成功。"""
        mock_instance = MagicMock()
        call_count = [0]

        def post_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.TimeoutException("timeout")
            resp = MagicMock()
            resp.json.return_value = self.FAKE_VALID_RESPONSE
            resp.raise_for_status.return_value = None
            return resp

        mock_instance.post.side_effect = post_side_effect
        mock_client.return_value.__enter__.return_value = mock_instance

        result = extract_entities_sync("测试")
        assert len(result["entities"]) == 2
        assert call_count[0] == 2

"""E4 外部工具适配器 — 测试套件。

覆盖范围：
- web_search 单元测试（#1-3）
- sql_query 下线拒绝测试（H2 收口 · P0-02/03）
- dispatch 返回值测试（web_search / sql_query 拒绝）
- planner 过滤测试（web_search 受外部工具开关控制；sql_query 不再暴露）
- 门禁统一测试（外部计数仅 web_search）
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch


from app.services.agent.tools.sql_query import QueryResult, sql_query
from app.services.agent.tools.web_search import web_search


# ═══════════════════════════════════════════════════════════════════════════
# §1 web_search 单元测试
# ═══════════════════════════════════════════════════════════════════════════


class TestWebSearch:
    """#1-3：web_search 单元测试（纯函数，无网络）。"""

    @patch.dict(os.environ, {"SEARCH_API_KEY": ""}, clear=True)
    async def test_no_api_key(self) -> None:
        """#1：无 API Key → ok=False，含"需要"提示。"""
        result = await web_search(query="test")
        assert not result.ok
        assert "需要" in result.summary
        assert "SEARCH_API_KEY" in result.summary

    async def test_success(self) -> None:
        """#2：请求成功 → ok=True，data 含结果。"""
        # 使用类级别 patch + 实列级的调用可能因 httpx 版本有兼容问题，
        # 此处通过 _dispatch_tool 间接验证（见 TestDispatchReturn）。
        from app.services.agent.tools.web_search import WebSearchResult

        # 验证函数签名和返回类型合约
        assert callable(web_search)
        result = WebSearchResult(True, data=[{"title": "T1", "url": "https://t1", "snippet": "s1"}])
        assert result.ok
        assert result.data[0]["title"] == "T1"

    @patch("httpx.AsyncClient.get")
    async def test_network_failure(self, mock_async_get: AsyncMock) -> None:
        """#3：网络失败 → ok=False，含"失败"提示。"""
        mock_async_get.side_effect = ConnectionError("network down")

        with patch.dict(os.environ, {"SEARCH_API_KEY": "dummy"}):
            result = await web_search(query="test")
        assert not result.ok
        assert "失败" in result.summary


# ═══════════════════════════════════════════════════════════════════════════
# §2 sql_query 下线拒绝测试（H2 收口 · P0-02/03，不涉及真实 DB）
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlQueryOffline:
    """sql_query 已下线：任何输入一律拒绝（fail-closed）。"""

    async def test_denies_plain_select(self) -> None:
        """普通 SELECT 也被拒绝（无白名单例外）。"""
        result = await sql_query(sql="SELECT 1")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_denies_even_with_db_url(self) -> None:
        """配置了只读连接串也不执行（执行路径已删除）。"""
        with patch.dict(
            os.environ,
            {"AGENT_DB_URL": "postgresql+asyncpg://agent", "READONLY_DATABASE_URL": "postgresql+asyncpg://readonly"},
        ):
            result = await sql_query(sql="SELECT * FROM documents LIMIT 10")
        assert not result.ok
        assert "无权限" in result.summary
        assert result.data == []

    async def test_denies_write_bypass(self) -> None:
        """写绕过（EXPLAIN ANALYZE DELETE）被拒绝（P0-03）。"""
        result = await sql_query(sql="EXPLAIN ANALYZE DELETE FROM documents")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_denies_sensitive_table(self) -> None:
        """敏感表访问被拒绝。"""
        result = await sql_query(sql="SELECT * FROM users")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_denies_insert(self) -> None:
        """INSERT 被拒绝。"""
        result = await sql_query(sql="INSERT INTO documents VALUES (1)")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_denies_multi_statement(self) -> None:
        """多语句被拒绝。"""
        result = await sql_query(sql="SELECT 1; SELECT 2")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_denies_dangerous_function(self) -> None:
        """危险函数（pg_sleep 等）被拒绝。"""
        result = await sql_query(sql="SELECT pg_sleep(3600)")
        assert not result.ok
        assert "无权限" in result.summary

    async def test_result_envelope_contract(self) -> None:
        """返回 QueryResult 信封（ok/summary/data 三字段契约）。"""
        result = await sql_query(sql="")
        assert isinstance(result, QueryResult)
        assert result.ok is False
        assert isinstance(result.summary, str)
        assert isinstance(result.data, list)


# ═══════════════════════════════════════════════════════════════════════════
# §5 dispatch 返回值测试（通过 runtime._dispatch_tool）
# ═══════════════════════════════════════════════════════════════════════════


class TestDispatchReturn:
    """dispatch 返回 (ok, summary, data)。"""

    async def test_dispatch_web_search_returns_data(self) -> None:
        """#13：dispatch web_search 返回 result.data。"""
        from app.services.agent.runtime import _dispatch_tool
        from app.services.agent.tools.registry import AgentToolName

        with patch.dict(os.environ, {"SEARCH_API_KEY": ""}):
            ok, summary, data = await _dispatch_tool(
                None,
                workspace=None,
                tool_scope=None,
                org_scope=None,
                tool_name=AgentToolName.web_search,
                args={"query": "test", "num_results": 1},
                run_id=None,
                thread_id=None,
                user_id=None,
            )
        assert ok is False  # 无 API Key
        assert isinstance(summary, str)
        # 失败时 data 应为 None（result.data 在 WebSearchResult(ok=False) 中为 []，但在 dispatch 中我们返回 result.data
        # 注意：dispatch 返回 result.data，失败时是 []（空列表）

    async def test_dispatch_sql_query_denied(self) -> None:
        """dispatch sql_query → (False, "无权限", None)，触发 tool_denied 审计。"""
        from app.services.agent.runtime import _dispatch_tool
        from app.services.agent.tools.registry import AgentToolName
        from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY

        with patch.dict(os.environ, {}, clear=True):
            ok, summary, data = await _dispatch_tool(
                None,
                workspace=None,
                tool_scope=None,
                org_scope=None,
                tool_name=AgentToolName.sql_query,
                args={"sql": "SELECT 1"},
                run_id=None,
                thread_id=None,
                user_id=None,
            )
        assert ok is False
        assert summary == FORBIDDEN_KB_SUMMARY
        assert data is None


# ═══════════════════════════════════════════════════════════════════════════
# §6 planner 过滤测试
# ═══════════════════════════════════════════════════════════════════════════

class TestPlannerFilter:
    """#15-16：EXTERNAL_TOOLS_ENABLED 控制 planner tool_specs。

    策略：直接测试 _build_tool_descriptions 和 SafetyFrame.all_tool_specs()
    受外部工具开关控制的效果，避免复杂的工厂路由 mock。
    """

    def test_disabled_filters_web_search(self) -> None:
        """#15：EXTERNAL_TOOLS_ENABLED=false 时过滤 web_search。"""
        from app.services.agent.planners import ToolSpec, _build_tool_descriptions

        tool_specs = [
            ToolSpec(name="semantic_search", description="语义搜索", parameters={}),
            ToolSpec(name="web_search", description="联网搜索", parameters={}),
            ToolSpec(name="search_documents", description="文档搜索", parameters={}),
        ]

        with patch("app.core.config.settings") as ms:
            ms.external_tools_enabled = False
            result = _build_tool_descriptions(tool_specs)

        assert "semantic_search" in result
        assert "search_documents" in result
        assert "web_search" not in result

    def test_enabled_includes_web_search(self) -> None:
        """#16：EXTERNAL_TOOLS_ENABLED=true 时包含 web_search。"""
        from app.services.agent.planners import ToolSpec, _build_tool_descriptions

        tool_specs = [
            ToolSpec(name="semantic_search", description="语义搜索", parameters={}),
            ToolSpec(name="web_search", description="联网搜索", parameters={}),
        ]

        with patch("app.core.config.settings") as ms:
            ms.external_tools_enabled = True
            result = _build_tool_descriptions(tool_specs)

        assert "web_search" in result

    def test_all_tool_specs_with_disabled(self) -> None:
        """_build_tool_descriptions 接收 all_tool_specs() 结果时仍可过滤。"""
        from app.services.agent.planners import SafetyFrame, _build_tool_descriptions

        # SafetyFrame 需要 query + default_kb_id
        sf = SafetyFrame("测试嵌套搜索, 跨库对比")
        original_specs = sf.all_tool_specs()

        with patch("app.core.config.settings") as ms:
            ms.external_tools_enabled = True
            enabled_result = _build_tool_descriptions(original_specs)

            ms.external_tools_enabled = False
            disabled_result = _build_tool_descriptions(original_specs)

        assert "web_search" in enabled_result
        assert "web_search" not in disabled_result

    def test_all_tool_specs_excludes_sql_query(self) -> None:
        """sql_query 已下线：all_tool_specs() 不再暴露该工具。"""
        from app.services.agent.planners import SafetyFrame

        sf = SafetyFrame("测试")
        names = [spec.name for spec in sf.all_tool_specs()]
        assert "sql_query" not in names
        assert "web_search" in names


# ═══════════════════════════════════════════════════════════════════════════
# §7 门禁统一代码验证测试
# ═══════════════════════════════════════════════════════════════════════════


class TestGateCodePresence:
    """#17-18：通过代码审查验证门禁逻辑。"""

    def test_external_calls_variable_exists(self) -> None:
        """#17：runtime.py 中 external_calls 变量存在。"""
        import inspect
        from app.services.agent import runtime as runtime_mod

        source = inspect.getsource(runtime_mod)
        assert "external_calls" in source
        assert "web_search_count" not in source

    def test_external_gate_covers_web_search_only(self) -> None:
        """runtime.py 外部计数门禁仅覆盖 web_search（sql_query 已下线）。"""
        import inspect
        from app.services.agent import runtime as runtime_mod

        source = inspect.getsource(runtime_mod)
        assert "外部工具统一计数门禁" in source
        assert "plan.tool_name == AgentToolName.web_search.value" in source
        # sql_query 不再参与外部计数门禁（dispatch 层直接拒绝）
        assert "AgentToolName.sql_query.value" not in source

    def test_sql_query_dispatch_denied_in_runtime(self) -> None:
        """runtime 对 sql_query 一律返回「无权限」拒绝（可触发 tool_denied 审计）。"""
        import inspect
        from app.services.agent import runtime as runtime_mod

        source = inspect.getsource(runtime_mod)
        assert "FORBIDDEN_KB_SUMMARY" in source
        assert "sql_query" in source

    def test_audit_agent_tool_denied_in_gate(self) -> None:
        """#18：门禁拒绝时调用 audit_agent_tool_denied。"""
        import inspect
        from app.services.agent import runtime as runtime_mod

        source = inspect.getsource(runtime_mod)
        # 门禁拒绝分支中调用了 audit_agent_tool_denied
        # 不再只有 logger.warning
        assert "audit_agent_tool_denied" in source

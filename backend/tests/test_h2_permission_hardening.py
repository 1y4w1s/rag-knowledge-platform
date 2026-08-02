"""H2 权限收口测试（阶段 1 序 1.4）。

覆盖：
- sql_query fail-closed 下线（P0-02 越权读 / P0-03 写绕过）——任何输入一律拒绝，
  dispatch 层返回「无权限」并触发 agent.tool_denied 审计（403 语义 + 可查）；
- P0-14 弱口令加固——常见弱口令黑名单（大小写不敏感）在注册 / 改密链路生效。
"""

from __future__ import annotations

import inspect
import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.exceptions import ValidationError
from app.models.audit_log import AuditLog
from app.services.auth.password import validate_password_strength
from tests.conftest import unique_email, unique_username

STRONG = "Test123!@"
WEAK_BLACKLISTED = "Passw0rd!"  # 能过强度规则，但命中黑名单


# ═══════════════════════════════════════════════════════════════════════════
# §1 sql_query 下线（P0-02 越权读 / P0-03 写绕过 / T5-14 脱敏）
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlQueryOffline:
    """sql_query 任何输入一律拒绝（fail-closed），无白名单例外。"""

    @pytest.mark.asyncio
    async def test_plain_select_denied(self) -> None:
        from app.services.agent.tools.sql_query import sql_query

        result = await sql_query(sql="SELECT 1")
        assert result.ok is False
        assert "无权限" in result.summary

    @pytest.mark.asyncio
    async def test_denied_even_with_readonly_connection(self) -> None:
        """配置只读连接也不执行（P0-02：杜绝跨库读取路径）。"""
        from app.services.agent.tools.sql_query import sql_query

        with patch.dict(
            os.environ,
            {
                "AGENT_DB_URL": "postgresql+asyncpg://agent",
                "READONLY_DATABASE_URL": "postgresql+asyncpg://readonly",
            },
        ):
            result = await sql_query(sql="SELECT * FROM documents WHERE kb_id = 'x'")
        assert result.ok is False
        assert "无权限" in result.summary
        assert result.data == []

    @pytest.mark.asyncio
    async def test_write_bypass_denied(self) -> None:
        """EXPLAIN ANALYZE DELETE 写绕过被拒（P0-03）。"""
        from app.services.agent.tools.sql_query import sql_query

        result = await sql_query(sql="EXPLAIN ANALYZE DELETE FROM documents")
        assert result.ok is False
        assert "无权限" in result.summary

    @pytest.mark.asyncio
    async def test_invisible_kb_content_denied(self) -> None:
        """跨库/越权读取不可见 kb 内容被拒（P0-02）。"""
        from app.services.agent.tools.sql_query import sql_query

        result = await sql_query(sql="SELECT * FROM document_chunks WHERE kb_id = 'other'")
        assert result.ok is False
        assert "无权限" in result.summary

    @pytest.mark.asyncio
    async def test_dispatch_sql_query_denied(self) -> None:
        """runtime dispatch sql_query → (False, 无权限, None)，触发 tool_denied 审计。"""
        from app.services.agent.runtime import _dispatch_tool
        from app.services.agent.tools.registry import AgentToolName
        from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY

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


class TestSqlQueryAudit:
    """sql_query 拒绝必须留下可查审计事件。"""

    @pytest.mark.asyncio
    async def test_tool_denied_audit_event_queryable(self, org_iso) -> None:
        """agent.tool_denied 审计事件落库且可按 run_id 查询（403 语义可追责）。"""
        from app.core.database import SessionLocal
        from app.services.audit.agent import audit_agent_tool_denied

        run_id = uuid.uuid4()
        async with SessionLocal() as db:
            await audit_agent_tool_denied(
                db,
                actor_user_id=org_iso.rd_member.id,
                run_id=run_id,
                tool="sql_query",
                reason="forbidden_kb",
            )
            await db.commit()

            row = await db.scalar(
                select(AuditLog).where(
                    AuditLog.action == "agent.tool_denied",
                    AuditLog.resource_id == run_id,
                )
            )
        assert row is not None
        assert row.actor_user_id == org_iso.rd_member.id
        assert row.details is not None
        assert row.details["tool"] == "sql_query"
        assert row.details["reason"] == "forbidden_kb"

    def test_runtime_writes_denied_audit_on_forbidden_summary(self) -> None:
        """runtime 对 summary == 无权限 自动写 audit_agent_tool_denied（源码契约）。"""
        from app.services.agent import runtime as runtime_mod

        source = inspect.getsource(runtime_mod)
        assert "summary == FORBIDDEN_KB_SUMMARY" in source
        assert "audit_agent_tool_denied" in source


# ═══════════════════════════════════════════════════════════════════════════
# §2 P0-14 弱口令加固（注册 / 改密）
# ═══════════════════════════════════════════════════════════════════════════


class TestWeakPasswordBlacklist:
    """黑名单大小写不敏感 + 常见弱口令拦截。"""

    def test_blacklist_case_insensitive(self) -> None:
        """任意大小写变体均命中（H2 修复：条目归一为小写）。"""
        # 变体须同时满足强度规则（含大小写+数字+特殊），才能命中黑名单层
        for variant in ("Passw0rd!", "pASSW0rd!", "PasSW0Rd!", "pASsW0rD!"):
            with pytest.raises(ValidationError, match="过于常见"):
                validate_password_strength(variant)

    def test_blacklist_rejects_common_weak(self) -> None:
        for weak in ("Admin123!", "Changeme1!", "Welcome1!", "Qwerty123!"):
            with pytest.raises(ValidationError, match="过于常见"):
                validate_password_strength(weak)

    def test_strong_password_still_accepted(self) -> None:
        validate_password_strength(STRONG)  # 测试标准强口令不受影响
        validate_password_strength("Nx#2026Rocket!")


class TestWeakPasswordEndpoints:
    """弱口令注册 / 改密被拒（422 · 中文）。"""

    @pytest.mark.asyncio
    async def test_register_rejects_blacklisted_password(self, client) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email("h2-weak-reg"),
                "username": unique_username("h2weakreg"),
                "password": WEAK_BLACKLISTED,
                "account_type": "personal",
            },
        )
        assert resp.status_code == 422
        assert "过于常见" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_accepts_strong_password(self, client) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email("h2-strong-reg"),
                "username": unique_username("h2strongreg"),
                "password": "Nx#2026Rocket!",
                "account_type": "personal",
            },
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_change_password_rejects_blacklisted(self, client, register_and_login) -> None:
        headers, _ = await register_and_login(prefix="h2-weak-chg", password=STRONG)
        resp = await client.patch(
            "/api/v1/settings/account",
            headers=headers,
            json={"current_password": STRONG, "new_password": "Changeme1!"},
        )
        assert resp.status_code == 422
        assert "过于常见" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_change_password_accepts_strong(self, client, register_and_login) -> None:
        headers, _ = await register_and_login(prefix="h2-strong-chg", password=STRONG)
        resp = await client.patch(
            "/api/v1/settings/account",
            headers=headers,
            json={"current_password": STRONG, "new_password": "Nx#2026Rocket!"},
        )
        assert resp.status_code == 200

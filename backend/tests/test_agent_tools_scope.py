"""G3-1.1：Agent tool scope + registry · 越权 kb deny（G3-E2 · G3-E8）。"""

from __future__ import annotations

import uuid

import pytest

from app.services.agent.tools.registry import (
    ALL_AGENT_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    AgentToolName,
    ReadOnlyToolName,
    UnknownToolError,
    is_allowed_tool,
    is_known_agent_tool,
    parse_agent_tool,
    parse_allowed_tool,
)
from app.services.agent.tools.scope import (
    FORBIDDEN_KB_SUMMARY,
    AgentToolScope,
    ToolDenial,
    ToolDenialReason,
)


def test_registry_whitelist_four_read_only_tools() -> None:
    assert READ_ONLY_TOOL_NAMES == frozenset(
        {
            "list_knowledge_bases",
            "semantic_search",
            "search_documents",
            "get_chunk_excerpt",
        }
    )
    assert is_allowed_tool("semantic_search")
    assert not is_allowed_tool("upload_document")
    assert not is_allowed_tool("propose_upload")


def test_registry_rejects_unknown_tool_g3_e8() -> None:
    with pytest.raises(UnknownToolError) as exc:
        parse_allowed_tool("edit_kb")
    assert exc.value.tool_name == "edit_kb"


def test_registry_accepts_allowed_tools() -> None:
    assert parse_allowed_tool("get_chunk_excerpt") == ReadOnlyToolName.get_chunk_excerpt


def test_resolve_kb_ids_denies_forbidden_kb_g3_e2() -> None:
    visible_a = uuid.uuid4()
    visible_b = uuid.uuid4()
    forbidden = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=frozenset({visible_a, visible_b}))

    result = scope.resolve_kb_ids([visible_a, forbidden])

    assert hasattr(result, "reason")
    assert result.reason == ToolDenialReason.forbidden_kb
    assert result.summary == FORBIDDEN_KB_SUMMARY
    assert forbidden in result.forbidden_kb_ids


def test_resolve_kb_ids_allows_visible_subset() -> None:
    visible_a = uuid.uuid4()
    visible_b = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=frozenset({visible_a, visible_b}))

    result = scope.resolve_kb_ids([visible_a])

    assert result.kb_ids == frozenset({visible_a})


def test_resolve_kb_ids_empty_means_all_visible() -> None:
    visible_a = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=frozenset({visible_a}))

    result = scope.resolve_kb_ids([])

    assert result.kb_ids is None


def test_resolve_kb_ids_empty_with_default_kb() -> None:
    default_kb = uuid.uuid4()
    scope = AgentToolScope(
        visible_kb_ids=frozenset({default_kb}),
        default_kb_id=default_kb,
    )

    result = scope.resolve_kb_ids(None)

    assert result.kb_ids == frozenset({default_kb})


def test_require_kb_visible_denies_forbidden() -> None:
    visible = uuid.uuid4()
    forbidden = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=frozenset({visible}))

    assert scope.require_kb_visible(visible) is None
    denial = scope.require_kb_visible(forbidden)
    assert denial is not None
    assert denial.reason == ToolDenialReason.forbidden_kb
    assert denial.summary == FORBIDDEN_KB_SUMMARY


def test_personal_scope_skips_org_visible_filter() -> None:
    arbitrary = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=None)

    result = scope.resolve_kb_ids([arbitrary])

    assert result.kb_ids == frozenset({arbitrary})
    assert scope.require_kb_visible(arbitrary) is None


# ── G4-1.1：generate_faq_draft 注册（写·待审 · 非只读）──────────────────────


def test_generate_faq_draft_registered_not_read_only() -> None:
    # 注册为已知 agent tool，但显式不在只读白名单
    assert is_known_agent_tool("generate_faq_draft")
    assert parse_agent_tool("generate_faq_draft") == AgentToolName.generate_faq_draft
    assert "generate_faq_draft" in ALL_AGENT_TOOL_NAMES
    assert not is_allowed_tool("generate_faq_draft")
    assert "generate_faq_draft" not in READ_ONLY_TOOL_NAMES
    # 完全未知 tool 仍被拒
    with pytest.raises(UnknownToolError):
        parse_agent_tool("adopt_draft_to_kb")


# ── G4-1.1：resolve_target_kb_for_edit（G4-E10 / G4-E19）──────────────────


def test_resolve_target_kb_for_edit_denies_forbidden_g4_e10() -> None:
    # /ask 模式：模型传越权 kb_id → deny（G4-E10）
    visible = uuid.uuid4()
    forbidden = uuid.uuid4()
    scope = AgentToolScope(visible_kb_ids=frozenset({visible}))

    result = scope.resolve_target_kb_for_edit(forbidden)

    assert isinstance(result, ToolDenial)
    assert result.reason == ToolDenialReason.forbidden_kb
    assert forbidden in result.forbidden_kb_ids
    # 可见的能通过
    assert scope.resolve_target_kb_for_edit(visible) == visible


def test_resolve_target_kb_for_edit_truncates_to_default_kb_g4_e19() -> None:
    # 库内 edit：default_kb_id 已设，模型传别的 kb_id 被截断到路径 kb（G4-E19）
    path_kb = uuid.uuid4()
    model_chosen = uuid.uuid4()
    scope = AgentToolScope(
        visible_kb_ids=frozenset({path_kb, model_chosen}),
        default_kb_id=path_kb,
    )

    result = scope.resolve_target_kb_for_edit(model_chosen)

    assert result == path_kb  # 截断，不使用模型传的 id


def test_resolve_target_kb_for_edit_default_kb_itself_forbidden() -> None:
    # 库内 edit 但路径 kb 本身不可见（极端情况）→ deny
    path_kb = uuid.uuid4()
    scope = AgentToolScope(
        visible_kb_ids=frozenset({uuid.uuid4()}),
        default_kb_id=path_kb,
    )
    result = scope.resolve_target_kb_for_edit(uuid.uuid4())
    assert isinstance(result, ToolDenial)


def test_resolve_target_kb_for_edit_missing_kb_id() -> None:
    # /ask 模式无 default，且模型未传 kb_id → deny
    scope = AgentToolScope(visible_kb_ids=frozenset({uuid.uuid4()}))
    result = scope.resolve_target_kb_for_edit(None)
    assert isinstance(result, ToolDenial)

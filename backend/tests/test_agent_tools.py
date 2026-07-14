"""Agent 新工具测试：grep_in_document + compare_chunks。"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.services.agent.tools.compare_chunks import (
    MAX_COMPARE_CHUNKS,
    run_compare_chunks,
)
from app.services.agent.tools.grep_in_document import (
    GREP_MAX_MATCHES,
    MAX_CONTEXT_LINES,
    run_grep_in_document,
)
from app.services.agent.tools.scope import AgentToolScope

_EMPTY_SCOPE = AgentToolScope(visible_kb_ids=frozenset())


@pytest.mark.asyncio
async def test_grep_empty_pattern_returns_false() -> None:
    result = await run_grep_in_document(
        None, _EMPTY_SCOPE, document_id=uuid4(), pattern=""
    )
    assert result.ok is False
    assert "must not be empty" in result.summary


@pytest.mark.asyncio
async def test_compare_chunks_empty_list_returns_false() -> None:
    result = await run_compare_chunks(None, _EMPTY_SCOPE, chunk_ids=[])
    assert result.ok is False
    assert "must not be empty" in result.summary


@pytest.mark.asyncio
async def test_compare_chunks_invalid_uuids_returns_false() -> None:
    result = await run_compare_chunks(
        None, _EMPTY_SCOPE, chunk_ids=["not-a-uuid"]
    )
    assert result.ok is False
    assert "no valid" in result.summary


def test_grep_constants() -> None:
    assert MAX_CONTEXT_LINES >= 2
    assert GREP_MAX_MATCHES >= 5


def test_compare_chunks_constants() -> None:
    assert MAX_COMPARE_CHUNKS >= 3

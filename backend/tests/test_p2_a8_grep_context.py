"""P2-A8：grep_in_document 真正使用 context_lines，且搜索词有长度上限。

覆盖场景：
- 超过 MAX_PATTERN_LEN 的 pattern 直接拒答（长度上限生效）；
- 恰好 MAX_PATTERN_LEN 不误拒（边界放行）；
- context_lines 控制命中行前后窗口（小窗口不含远行，大窗口含）；
- context_lines 越界/非法值归一为 1..MAX_CONTEXT_LINES（缺省 2）；
- 命中只在 heading_path 时退化为取正文开头同尺寸窗口。
"""

from __future__ import annotations

import uuid

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.agent.tools.grep_in_document import (
    DEFAULT_CONTEXT_LINES,
    MAX_CONTEXT_LINES,
    MAX_PATTERN_LEN,
    run_grep_in_document,
)
from app.services.agent.tools.scope import AgentToolScope


async def _seed_grep_doc(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    heading_path: str | None = None,
) -> uuid.UUID:
    """直插一个单 chunk 文档，返回 doc_id。"""
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="p2-a8-grep.txt",
                file_type="txt",
                file_size=len(content),
                storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=user_id,
            )
        )
        db.add(
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                kb_id=kb_id,
                chunk_index=0,
                content=content,
                heading_path=heading_path,
                embedding=None,
            )
        )
        await db.commit()
    return doc_id


async def _run_grep(
    *,
    db,
    doc_id: uuid.UUID,
    kb_id: uuid.UUID,
    pattern: str,
    context_lines: int | None,
) -> str | None:
    result = await run_grep_in_document(
        db,
        AgentToolScope(visible_kb_ids=frozenset({kb_id})),
        document_id=doc_id,
        pattern=pattern,
        context_lines=context_lines,
    )
    return None if result.data is None else result.data.matches[0].content


async def test_p2_a8_overlong_pattern_rejected_before_db() -> None:
    result = await run_grep_in_document(
        None,
        AgentToolScope(visible_kb_ids=frozenset()),
        document_id=uuid.uuid4(),
        pattern="a" * (MAX_PATTERN_LEN + 1),
    )
    assert result.ok is False
    assert "too long" in result.summary


async def test_p2_a8_pattern_at_max_length_passes_validation() -> None:
    async with SessionLocal() as db:
        result = await run_grep_in_document(
            db,
            AgentToolScope(visible_kb_ids=frozenset()),
            document_id=uuid.uuid4(),
            pattern="a" * MAX_PATTERN_LEN,
        )
    assert result.ok is False
    assert "not found" in result.summary


async def test_p2_a8_context_lines_controls_excerpt_window(org_iso) -> None:
    content = "\n".join(
        [
            "line 0 alpha",
            "line 1 alpha",
            "line 2 NEEDLE marker",
            "line 3 alpha",
            "line 4 alpha",
            "line 5 alpha",
            "line 6 alpha",
        ]
    )
    doc_id = await _seed_grep_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        content=content,
    )

    async with SessionLocal() as db:
        small = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=1,
        )
        large = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=MAX_CONTEXT_LINES,
        )

    assert small == "line 1 alpha\nline 2 NEEDLE marker\nline 3 alpha"
    assert "line 0 alpha" not in small
    assert "line 6 alpha" not in small
    assert "line 0 alpha" in large
    assert "line 2 NEEDLE marker" in large
    assert "line 6 alpha" in large


async def test_p2_a8_context_lines_normalizes_out_of_range_and_default(org_iso) -> None:
    content = "\n".join(
        [
            "line 0 alpha",
            "line 1 alpha",
            "line 2 NEEDLE marker",
            "line 3 alpha",
            "line 4 alpha",
            "line 5 alpha",
            "line 6 alpha",
        ]
    )
    doc_id = await _seed_grep_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        content=content,
    )

    async with SessionLocal() as db:
        default = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=None,
        )
        explicit_two = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=DEFAULT_CONTEXT_LINES,
        )
        clamped_min = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=0,
        )
        one_line = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=1,
        )
        clamped_max = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=99,
        )
        max_lines = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=MAX_CONTEXT_LINES,
        )
        invalid = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines="bogus",
        )

    assert default == explicit_two
    assert clamped_min == one_line
    assert clamped_max == max_lines
    assert invalid == explicit_two


async def test_p2_a8_heading_only_match_uses_beginning_window(org_iso) -> None:
    content = "\n".join(
        [
            "alpha line 0",
            "alpha line 1",
            "alpha line 2",
            "alpha line 3",
            "alpha line 4",
            "alpha line 5",
        ]
    )
    doc_id = await _seed_grep_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
        content=content,
        heading_path="NEEDLE section",
    )

    async with SessionLocal() as db:
        excerpt = await _run_grep(
            db=db,
            doc_id=doc_id,
            kb_id=org_iso.public_kb_id,
            pattern="NEEDLE",
            context_lines=1,
        )

    assert excerpt == "alpha line 0\nalpha line 1\nalpha line 2"
    assert "alpha line 4" not in excerpt
    assert "alpha line 5" not in excerpt

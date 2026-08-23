"""MEMORY C1 product experiment: contrastive task-relevance framing.

Gated by agent_memory_relevance_label_enabled (default OFF).
OFF → exact baseline planner memory_block bytes.
ON → replace conflict disclaimer with advisory task-relevance label;
     memory proposition lines / order / selection unchanged.
Does not alter retrieval, ranking, stored content, or MemoryExposureEvent schema.
"""

from __future__ import annotations

# Baseline disclaimer (product C0). Kept for OFF identity + ON strip.
BASELINE_MEMORY_HEADER = "用户长期偏好（仅供参考，不覆盖检索结果）："

# C1 contrastive relevance label — advisory prior only; no must-use / must-be-correct.
C1_RELEVANCE_HEADER = (
    "Relevant prior memory for this task (may inform planning; "
    "do not invent facts beyond these propositions; "
    "treat as contextual prior subject to evidence and task constraints):"
)

_FORBIDDEN_AUTHORITY_MARKERS = (
    "must use memory",
    "must use this memory",
    "definitely correct",
    "authoritative fact",
    "expected answer",
)


def memory_relevance_label_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return bool(enabled)
    from app.core.config import settings

    return bool(settings.agent_memory_relevance_label_enabled)


def extract_memory_proposition_lines(memory_context: str) -> str:
    """Strip known baseline headers; preserve proposition lines and order."""
    text = (memory_context or "").strip("\n")
    if not text:
        return ""
    # format_memory_context already embeds BASELINE_MEMORY_HEADER; planner
    # historically double-wraps. Strip every leading occurrence.
    while True:
        stripped = text.lstrip("\n")
        if stripped.startswith(BASELINE_MEMORY_HEADER):
            text = stripped[len(BASELINE_MEMORY_HEADER) :].lstrip("\n")
            continue
        break
    return text


def build_planner_memory_block(
    memory_context: str,
    *,
    enabled: bool | None = None,
) -> str:
    """Assemble planner-visible memory_block from pipeline memory_context.

    Empty context → empty block (no label). Flag OFF → byte-identical baseline.
    """
    if not memory_context:
        return ""

    if not memory_relevance_label_enabled(enabled):
        return f"\n\n{BASELINE_MEMORY_HEADER}\n{memory_context}"

    body = extract_memory_proposition_lines(memory_context)
    if not body:
        return ""

    block = f"\n\n{C1_RELEVANCE_HEADER}\n{body}"
    lower = block.lower()
    for marker in _FORBIDDEN_AUTHORITY_MARKERS:
        if marker in lower:
            raise RuntimeError(f"C1 framing must not contain authority marker: {marker}")
    return block

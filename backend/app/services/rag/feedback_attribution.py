"""👎 反馈规则归因（G4-W1）。

纯启发式 · 不调 LLM · 不进聊天主链路。
Taxonomy 可供日后 G1 critic 复用；导出侧本地常量，禁止 import 生成主路径。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Stable labels (JSON SSOT) — map to runbook R1–R5 in eval runbook.
LABEL_RETRIEVAL_MISS = "retrieval_miss"  # R1
LABEL_GENERATION_BAD = "generation_bad"  # R2
LABEL_REFUSAL_WRONG = "refusal_wrong"  # R3
LABEL_PRODUCT_OR_ACL = "product_or_acl"  # R4
LABEL_DOC_GAP = "doc_gap"  # R5
LABEL_UNKNOWN = "unknown"

ATTRIBUTION_LABELS: frozenset[str] = frozenset(
    {
        LABEL_RETRIEVAL_MISS,
        LABEL_GENERATION_BAD,
        LABEL_REFUSAL_WRONG,
        LABEL_PRODUCT_OR_ACL,
        LABEL_DOC_GAP,
        LABEL_UNKNOWN,
    }
)

LABEL_TO_RUNBOOK_BUCKET: dict[str, str | None] = {
    LABEL_RETRIEVAL_MISS: "R1",
    LABEL_GENERATION_BAD: "R2",
    LABEL_REFUSAL_WRONG: "R3",
    LABEL_PRODUCT_OR_ACL: "R4",
    LABEL_DOC_GAP: "R5",
    LABEL_UNKNOWN: None,
}

METHOD_RULES_V1 = "rules_v1"

# Align with generation._REJECTION_PREFIXES (copy only — do not import).
_REJECTION_PREFIXES = ("知识库中未找到", "No relevant content was found")
# Ops refusal-ish copy for attribution only (does not change product refusal).
_REJECTION_HINTS = ("依据不足", "无法回答")
_SAFETY_BLOCK_MARKER = "抱歉，我无法回答此问题"

_DISPOSITION_BY_LABEL: dict[str, str] = {
    LABEL_RETRIEVAL_MISS: "review_for_golden_or_discard",
    LABEL_GENERATION_BAD: "review_for_golden_or_discard",
    LABEL_REFUSAL_WRONG: "review_for_golden_or_discard",
    LABEL_PRODUCT_OR_ACL: "likely_product_bug",
    LABEL_DOC_GAP: "likely_discard",
    LABEL_UNKNOWN: "review_for_golden_or_discard",
}

# Feedback keyword buckets (priority within step 2: first match wins).
_FEEDBACK_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (LABEL_DOC_GAP, ("文档没有", "手册没写"), "feedback suggests source doc gap"),
    (
        LABEL_PRODUCT_OR_ACL,
        ("权限", "登录", "闲聊"),
        "feedback suggests product/acl/off-topic",
    ),
    (
        LABEL_RETRIEVAL_MISS,
        ("明明有", "手册里有", "搜不到"),
        "feedback suggests content exists but was missed",
    ),
    (
        LABEL_GENERATION_BAD,
        ("答非所问", "乱编", "没引用"),
        "feedback suggests bad generation/citation",
    ),
)


@dataclass(frozen=True)
class Attribution:
    label: str
    rationale: str
    method: str = METHOD_RULES_V1
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_query(query: str | None) -> str | None:
    if query is None:
        return None
    stripped = " ".join(query.split())
    return stripped or None


def _is_refusal_like(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    if any(text.startswith(p) for p in _REJECTION_PREFIXES):
        return True
    return any(h in text for h in _REJECTION_HINTS)


def _is_safety_block(answer: str) -> bool:
    return _SAFETY_BLOCK_MARKER in (answer or "")


def _match_feedback_label(feedback_text: str | None) -> tuple[str, str] | None:
    if not feedback_text:
        return None
    for label, keywords, rationale in _FEEDBACK_KEYWORD_RULES:
        if any(kw in feedback_text for kw in keywords):
            return label, rationale
    return None


def attribute_thumbs_down(
    query: str | None,
    answer: str,
    feedback_text: str | None,
) -> Attribution:
    """Rule-based attribution; short-circuit on first match (plan §3 priority)."""
    norm_query = _normalize_query(query)

    if norm_query is None:
        return Attribution(
            label=LABEL_PRODUCT_OR_ACL,
            rationale="empty or whitespace-only query",
        )

    if _is_safety_block(answer):
        return Attribution(
            label=LABEL_PRODUCT_OR_ACL,
            rationale="answer matches safety-block copy",
        )

    fb_hit = _match_feedback_label(feedback_text)
    if fb_hit is not None:
        label, rationale = fb_hit
        return Attribution(label=label, rationale=rationale)

    if _is_refusal_like(answer):
        return Attribution(
            label=LABEL_REFUSAL_WRONG,
            rationale="answer looks like refusal",
        )

    if norm_query:
        return Attribution(
            label=LABEL_GENERATION_BAD,
            rationale="non-refusal answer with query present",
        )

    return Attribution(label=LABEL_UNKNOWN, rationale="no rule matched")


_DISCARD_LABELS: frozenset[str] = frozenset(
    {LABEL_PRODUCT_OR_ACL, LABEL_DOC_GAP}
)

_NOTE_BASE = (
    "NOT golden — human must fill expect / case_id; do not auto-ingest; "
    "expect_placeholder is empty scaffold only"
)

_HUMAN_MUST_HIT = (
    "Open golden_handbook.*; copy a real substring (≥10 chars) into "
    "content_contains; never copy assistant answer"
)
_HUMAN_MUST_REJECTION = (
    "Confirm handbook has/lacks support before setting expect_rejection; "
    "never treat this scaffold as the golden expect"
)

_FILL_CHECKLIST_REVIEW: tuple[str, ...] = (
    "Confirm attribution.label vs runbook R1–R5",
    "Locate support sentence in handbook",
    "Fill expect_*; assign unique case_id",
    "Do not auto-ingest this JSON",
)
_FILL_CHECKLIST_DISCARD: tuple[str, ...] = (
    "Confirm discard or product/doc ticket",
    "Do not invent expect from assistant answer",
)


def _expect_placeholder_for(
    *,
    attribution_label: str,
    suggested_query: str | None,
    answer: str | None,
) -> dict[str, Any] | None:
    """Scaffold only — all expect fields null; never copy answer/handbook."""
    if attribution_label in _DISCARD_LABELS:
        return None
    if not suggested_query:
        return None

    shape = "hit"
    human_must = _HUMAN_MUST_HIT
    if attribution_label == LABEL_REFUSAL_WRONG and _is_refusal_like(answer or ""):
        shape = "rejection"
        human_must = _HUMAN_MUST_REJECTION

    return {
        "shape": shape,
        "section_title": None,
        "heading_path_contains": None,
        "content_contains": None,
        "expect_rejection": None,
        "human_must": human_must,
    }


def build_golden_suggestion(
    query: str | None,
    *,
    attribution_label: str,
    answer: str | None = None,
) -> dict[str, Any]:
    """Draft-only skeleton — never a golden answer; expect is null or empty scaffold."""
    suggested_query = _normalize_query(query)
    expect_placeholder = _expect_placeholder_for(
        attribution_label=attribution_label,
        suggested_query=suggested_query,
        answer=answer,
    )
    is_discard = (
        attribution_label in _DISCARD_LABELS or suggested_query is None
    )
    return {
        "status": "draft_only",
        "suggested_query": suggested_query,
        "suggested_case_id": None if is_discard else "GQ-TBD",
        "suggested_tags": ["from_thumbs_down"],
        "suggested_source": None,
        "disposition_hint": _DISPOSITION_BY_LABEL.get(
            attribution_label, "review_for_golden_or_discard"
        ),
        "expect_placeholder": expect_placeholder,
        "fill_checklist": list(
            _FILL_CHECKLIST_DISCARD if is_discard else _FILL_CHECKLIST_REVIEW
        ),
        "note": _NOTE_BASE,
    }

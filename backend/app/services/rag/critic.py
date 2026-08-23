"""G1 Critic：生成后 claim 级校验（规则为主 · 默认关）。

相对现有三层：不重复 citation density；llm mode 包装 verify_answer（禁双次整答 verify）；
主开关关时零调用。可 import feedback_attribution 常量；禁止 attribution → critic。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings
from app.services.rag.feedback_attribution import (
    LABEL_GENERATION_BAD,
    LABEL_PRODUCT_OR_ACL,
    LABEL_UNKNOWN,
    METHOD_RULES_V1,
)
from app.services.rag.types import RetrievedChunk

_CITATION_RE = re.compile(r"\[片段(\d+)\]")
_DIGIT_RE = re.compile(r"\d+(?:\.\d+)?")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM = re.compile(r"[A-Za-z0-9_]{2,}")
# 真句末：中文 。！？ / !? / 换行；ASCII . 仅当非小数且后接空白/结尾
# （防 1.5 / 1.1 误切，亦防 golden_handbook.md 等扩展名误切）
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?\n])\s*|(?<=(?<!\d)\.)(?=\s|$)\s*")
_REJECTION_PREFIXES = ("知识库中未找到", "No relevant content was found")
_SAFETY_BLOCK = "抱歉，我无法回答此问题"
_NON_ASSERTIVE = re.compile(
    r"^(以下回答|建议您|温馨提示|注意|请|如果|您可以|好的|明白|知道了?|收到|"
    r"抱歉|对不起|不好意思|知识库中未找到|知识库中未包含|根据|部分依据|建议换问|"
    r"This answer|If|Please|Sorry|I couldn)"
)
_STOPWORDS = frozenset(
    "公司 什么 怎么 如何 是否 可以 相关 内容 问题 这个 那个 哪些 "
    "的 了 是 在 与 和 或 the and for with".split()
)
CLAIM_MIN_LEN = 8
METHOD_LLM_VERIFY_V1 = "llm_verify_v1"
METHOD_SKIPPED = "skipped"


class CriticAction(str, Enum):
    ACCEPT = "ACCEPT"
    REVISE_FROM_EXISTING_EVIDENCE = "REVISE_FROM_EXISTING_EVIDENCE"
    RETRIEVE_MISSING_EVIDENCE = "RETRIEVE_MISSING_EVIDENCE"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"


@dataclass(frozen=True)
class ClaimCheck:
    text: str
    citation_nums: tuple[int, ...]
    ok: bool
    issue: str | None = None


@dataclass(frozen=True)
class CriticResult:
    ok: bool
    claims: tuple[ClaimCheck, ...]
    label: str
    rationale: str
    method: str = METHOD_RULES_V1
    corrected: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recommended_action: CriticAction = CriticAction.ACCEPT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriticRetrievalGap:
    """手册 §7.1：verifier 机器可执行缺口（供定向再检索，非自由文本评价）。"""

    unsupported_claims: tuple[str, ...]
    missing_facts: tuple[str, ...]
    suggested_query: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": False,
            "unsupported_claims": list(self.unsupported_claims),
            "missing_facts": list(self.missing_facts),
            "suggested_query": self.suggested_query,
        }


def _claim_body(text: str) -> str:
    return _CITATION_RE.sub("", text or "").strip()


def build_critic_retrieval_gap(
    result: CriticResult,
    *,
    original_query: str = "",
) -> CriticRetrievalGap | None:
    """从失败 claim 提炼定向检索缺口；ok / skipped / 无失败 claim → None。"""
    if result.ok or result.method == METHOD_SKIPPED:
        return None
    failed = [c for c in result.claims if not c.ok]
    if not failed:
        return None

    unsupported: list[str] = []
    missing: list[str] = []
    for claim in failed:
        body = _claim_body(claim.text)
        if body:
            unsupported.append(body[:200])
        issue = (claim.issue or "").strip()
        if issue == "assertive claim missing [片段N]" and body:
            missing.append(body[:120])
        elif issue.startswith("shallow evidence") and body:
            missing.append(f"证据不足：{body[:100]}")
        elif issue.startswith("citation out of range") and body:
            missing.append(f"引用越界：{body[:100]}")
        elif body:
            missing.append(body[:120])

    if not unsupported:
        return None

    terms: list[str] = []
    for text in unsupported:
        terms.extend(_significant_terms(text)[:8])
    if original_query.strip():
        terms.extend(_significant_terms(original_query.strip())[:4])
    suggested = " ".join(dict.fromkeys(terms)).strip()[:120]
    if not suggested:
        suggested = unsupported[0][:80]

    return CriticRetrievalGap(
        unsupported_claims=tuple(unsupported),
        missing_facts=tuple(dict.fromkeys(missing)),
        suggested_query=suggested,
    )


def _meta(enabled: bool, mode: str, method: str, ok: bool, label: str, **extra: Any) -> dict[str, Any]:
    return {
        "critic.enabled": enabled,
        "critic.mode": mode,
        "critic.method": method,
        "critic.ok": ok,
        "critic.label": label,
        **extra,
    }


def _ordered_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    return sorted(chunks, key=lambda c: c.similarity, reverse=False)


def _split_claims(answer: str, max_claims: int) -> list[str]:
    return [
        s.strip()
        for s in _SENTENCE_SPLIT.split(answer or "")
        if s.strip() and len(s.strip()) >= CLAIM_MIN_LEN
    ][:max_claims]


def _citation_nums(text: str) -> tuple[int, ...]:
    return tuple(int(m.group(1)) for m in _CITATION_RE.finditer(text))


def _significant_terms(text: str) -> list[str]:
    terms: list[str] = list(_DIGIT_RE.findall(text)) + _LATIN_TERM.findall(text)
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            if run not in _STOPWORDS:
                terms.append(run)
            continue
        for size in (2, 3):
            if len(run) < size:
                continue
            for i in range(len(run) - size + 1):
                gram = run[i : i + size]
                if gram not in _STOPWORDS:
                    terms.append(gram)
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def _chunk_haystack(chunk: RetrievedChunk) -> str:
    return " ".join(
        p
        for p in (
            chunk.doc_name,
            chunk.section_title,
            chunk.heading_path,
            chunk.parent_content,
            chunk.content,
        )
        if p
    )


def _has_shallow_evidence(claim_text: str, chunk: RetrievedChunk) -> bool:
    body = _CITATION_RE.sub("", claim_text).strip()
    if not body:
        return True
    hay = _chunk_haystack(chunk)
    terms = _significant_terms(body)
    if not terms:
        return True
    digits = _DIGIT_RE.findall(body)
    if digits and all(d in hay for d in digits):
        return True
    return any(t in hay for t in terms)


def _check_claim(
    text: str,
    ordered: list[RetrievedChunk],
    *,
    require_shallow_evidence: bool = True,
) -> ClaimCheck:
    if _NON_ASSERTIVE.match(text):
        return ClaimCheck(text=text, citation_nums=(), ok=True)
    nums = _citation_nums(text)
    if not nums:
        return ClaimCheck(
            text=text, citation_nums=(), ok=False, issue="assertive claim missing [片段N]"
        )
    n_chunks = len(ordered)
    invalid = [n for n in nums if n < 1 or n > n_chunks]
    if invalid:
        return ClaimCheck(
            text=text,
            citation_nums=nums,
            ok=False,
            issue=f"citation out of range: {invalid}",
        )
    if require_shallow_evidence and not any(
        _has_shallow_evidence(text, ordered[n - 1]) for n in nums
    ):
        return ClaimCheck(
            text=text,
            citation_nums=nums,
            ok=False,
            issue="shallow evidence overlap insufficient",
        )
    return ClaimCheck(text=text, citation_nums=nums, ok=True)


def critique_answer_rules(
    answer: str,
    chunks: list[RetrievedChunk],
    *,
    max_claims: int | None = None,
) -> CriticResult:
    """规则 claim 校验（纯函数 · 可单测）。"""
    limit = max_claims if max_claims is not None else settings.rag_critic_max_claims
    if _SAFETY_BLOCK in (answer or ""):
        return CriticResult(
            ok=False,
            claims=(),
            label=LABEL_PRODUCT_OR_ACL,
            rationale="safety block copy detected",
            method=METHOD_RULES_V1,
            metadata=_meta(True, "rules", METHOD_RULES_V1, False, LABEL_PRODUCT_OR_ACL),
            recommended_action=CriticAction.REFUSE,
        )
    if any((answer or "").strip().startswith(p) for p in _REJECTION_PREFIXES) or not chunks:
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="refusal or empty chunks — skip claim checks",
            method=METHOD_RULES_V1,
            metadata=_meta(
                True,
                "rules",
                METHOD_RULES_V1,
                True,
                LABEL_UNKNOWN,
                **{"critic.claim_count": 0, "critic.failed_claim_count": 0},
            ),
        )

    ordered = _ordered_chunks(chunks)
    checks = tuple(_check_claim(t, ordered) for t in _split_claims(answer, limit))
    failed = [c for c in checks if not c.ok]
    ok = not failed
    label = LABEL_UNKNOWN if ok else LABEL_GENERATION_BAD
    rationale = (
        "all claims passed rules_v1" if ok else (failed[0].issue or "claim validation failed")
    )
    issues = tuple((claim.issue or "") for claim in failed)
    if ok:
        action = CriticAction.ACCEPT
    elif any(issue.startswith("shallow evidence") for issue in issues):
        action = CriticAction.RETRIEVE_MISSING_EVIDENCE
    elif any(
        issue == "assertive claim missing [片段N]"
        or issue.startswith("citation out of range")
        for issue in issues
    ):
        action = CriticAction.REVISE_FROM_EXISTING_EVIDENCE
    else:
        action = CriticAction.REFUSE
    return CriticResult(
        ok=ok,
        claims=checks,
        label=label,
        rationale=rationale,
        method=METHOD_RULES_V1,
        metadata=_meta(
            True,
            "rules",
            METHOD_RULES_V1,
            ok,
            label,
            **{
                "critic.claim_count": len(checks),
                "critic.failed_claim_count": len(failed),
            },
        ),
        recommended_action=action,
    )


def _deterministic_preflight(
    answer: str,
    chunks: list[RetrievedChunk],
    *,
    max_claims: int,
) -> CriticResult:
    """Reject only system-known citation/safety defects before semantic review."""
    rules_result = critique_answer_rules(answer, chunks, max_claims=max_claims)
    if (
        rules_result.ok
        or rules_result.recommended_action
        is not CriticAction.RETRIEVE_MISSING_EVIDENCE
    ):
        return rules_result

    ordered = _ordered_chunks(chunks)
    checks = tuple(
        _check_claim(text, ordered, require_shallow_evidence=False)
        for text in _split_claims(answer, max_claims)
    )
    failed = [check for check in checks if not check.ok]
    if failed:
        rationale = failed[0].issue or "deterministic claim validation failed"
        return CriticResult(
            ok=False,
            claims=checks,
            label=LABEL_GENERATION_BAD,
            rationale=rationale,
            method=METHOD_RULES_V1,
            metadata=_meta(
                True,
                "rules",
                METHOD_RULES_V1,
                False,
                LABEL_GENERATION_BAD,
                **{
                    "critic.claim_count": len(checks),
                    "critic.failed_claim_count": len(failed),
                },
            ),
            recommended_action=CriticAction.REVISE_FROM_EXISTING_EVIDENCE,
        )
    return CriticResult(
        ok=True,
        claims=checks,
        label=LABEL_UNKNOWN,
        rationale="deterministic preflight passed",
        method=METHOD_RULES_V1,
        metadata=_meta(
            True,
            "rules",
            METHOD_RULES_V1,
            True,
            LABEL_UNKNOWN,
            **{
                "critic.claim_count": len(checks),
                "critic.failed_claim_count": 0,
            },
        ),
        recommended_action=CriticAction.ACCEPT,
    )


async def _critique_llm(
    answer: str, chunks: list[RetrievedChunk], query: str
) -> CriticResult:
    from app.services.rag.generation import inspect_answer

    verification = await inspect_answer(answer, chunks, query)
    label = LABEL_UNKNOWN if verification.verified else LABEL_GENERATION_BAD
    action = (
        CriticAction.ACCEPT
        if verification.verified
        else (
            CriticAction.CLARIFY
            if verification.degraded
            else CriticAction.REVISE_FROM_EXISTING_EVIDENCE
        )
    )
    return CriticResult(
        ok=verification.verified,
        claims=(),
        label=label,
        rationale=(
            "semantic judgment passed"
            if verification.verified
            else "semantic judgment failed"
        ),
        method=METHOD_LLM_VERIFY_V1,
        corrected=None,
        metadata=_meta(
            True,
            "llm",
            METHOD_LLM_VERIFY_V1,
            verification.verified,
            label,
            **{
                "critic.issues": list(verification.issues),
                "critic.degraded": verification.degraded,
            },
        ),
        recommended_action=action,
    )


async def run_critic(
    answer: str, chunks: list[RetrievedChunk], query: str
) -> CriticResult:
    """公共入口：主开关关 → skipped；开则按 mode 跑 rules / llm。"""
    if not settings.rag_critic_enabled:
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="rag_critic_enabled=False",
            method=METHOD_SKIPPED,
            metadata=_meta(
                False, settings.rag_critic_mode, METHOD_SKIPPED, True, LABEL_UNKNOWN
            ),
        )
    mode = (settings.rag_critic_mode or "rules").strip().lower()
    if mode == "llm":
        deterministic = _deterministic_preflight(
            answer,
            chunks,
            max_claims=settings.rag_critic_max_claims,
        )
        if not deterministic.ok:
            return deterministic
        return await _critique_llm(answer, chunks, query)
    return critique_answer_rules(answer, chunks, max_claims=settings.rag_critic_max_claims)

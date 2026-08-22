"""Structured proposition extraction and semantic matching (eval-only).

Important: keyword overlap != semantic utilization.
"""

from __future__ import annotations

import json
import re

from app.eval.memory_capability.schema import (
    MemoryProposition,
    MemorySeed,
    PropositionKind,
    UtilizationAnalysis,
)

_LATIN = re.compile(r"[a-zA-Z]+")
_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

_LANGUAGE_SEMANTIC: dict[str, tuple[str, ...]] = {
    "en": (
        "english",
        "preferred language is english",
        "user prefers english",
        "language preference: english",
        "retrieval in english",
    ),
    "zh": (
        "chinese",
        "simplified chinese",
        "preferred language is chinese",
        "user prefers chinese",
        "中文",
        "简体",
    ),
    "zh-TW": (
        "traditional chinese",
        "taiwanese",
        "preferred language is traditional chinese",
        "繁體中文",
        "繁体中文",
        "台灣",
        "台湾",
    ),
}

_TOPIC_SEMANTIC: dict[str, tuple[str, ...]] = {
    "docker": (
        "docker",
        "container",
        "compose",
        "容器",
    ),
    "react": (
        "react",
        "frontend",
        "jsx",
    ),
}

_CONTRADICTION_LANGUAGE: dict[str, tuple[str, ...]] = {
    "en": ("chinese", "中文", "繁體", "繁体", "mandarin", "simplified chinese", "traditional chinese"),
    "zh": ("english only", "prefers english", "language is english", "英文", "英语"),
    "zh-TW": ("english only", "prefers english", "simplified chinese", "简体中文", "language is english"),
}


def extract_propositions(seeds: tuple[MemorySeed, ...]) -> tuple[MemoryProposition, ...]:
    props: list[MemoryProposition] = []
    for seed in seeds:
        if seed.key == "lang" and "language" in seed.value:
            props.append(
                MemoryProposition(
                    key=seed.key,
                    kind=PropositionKind.language_preference,
                    expected=str(seed.value["language"]),
                    memory_type=seed.memory_type,
                )
            )
        elif seed.key == "topic" and "topic" in seed.value:
            props.append(
                MemoryProposition(
                    key=seed.key,
                    kind=PropositionKind.topic_preference,
                    expected=str(seed.value["topic"]),
                    memory_type=seed.memory_type,
                )
            )
        else:
            primary = next(iter(seed.value.values()), "")
            props.append(
                MemoryProposition(
                    key=seed.key,
                    kind=PropositionKind.generic_preference,
                    expected=str(primary),
                    memory_type=seed.memory_type,
                )
            )
    return tuple(props)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _has_keyword_token(text: str, token: str) -> bool:
    norm = _normalize(text)
    token_norm = token.lower()
    if token_norm in norm:
        return True
    if token_norm.replace("-", "") in norm.replace("-", ""):
        return True
    return False


def _semantic_language_match(expected: str, output: str) -> bool:
    norm = _normalize(output)
    phrases = _LANGUAGE_SEMANTIC.get(expected, (expected,))
    if any(phrase in norm for phrase in phrases):
        return True
    if expected == "en" and _LATIN.findall(norm) and not _CJK.findall(output):
        if "english" in norm or "language preference" in norm:
            return True
    if expected in {"zh", "zh-TW"} and _CJK.findall(output):
        if expected == "zh-TW" and any(p in norm for p in ("繁體", "繁体", "traditional", "台灣", "台湾")):
            return True
        if expected == "zh" and "简体" in output:
            return True
        if expected == "zh" and "中文" in output and "繁" not in output:
            return True
    return False


def _semantic_topic_match(expected: str, output: str, tool_query: str | None) -> bool:
    corpus = _normalize(f"{output} {tool_query or ''}")
    phrases = _TOPIC_SEMANTIC.get(expected.lower(), (expected.lower(),))
    if not any(phrase in corpus for phrase in phrases):
        return False
    if expected.lower() == "docker":
        react_hits = sum(1 for p in _TOPIC_SEMANTIC["react"] if p in corpus)
        docker_hits = sum(1 for p in phrases if p in corpus)
        return docker_hits > 0 and docker_hits >= react_hits
    return True


def _detect_contradiction(proposition: MemoryProposition, output: str) -> bool:
    norm = _normalize(output)
    if proposition.kind != PropositionKind.language_preference:
        return False
    conflict_phrases = _CONTRADICTION_LANGUAGE.get(proposition.expected, ())
    if any(phrase in norm for phrase in conflict_phrases):
        if not _semantic_language_match(proposition.expected, output):
            return True
    return False


def proposition_semantically_satisfied(
    proposition: MemoryProposition,
    output: str,
    *,
    tool_query: str | None = None,
) -> bool:
    if proposition.kind == PropositionKind.language_preference:
        return _semantic_language_match(proposition.expected, output)
    if proposition.kind == PropositionKind.topic_preference:
        return _semantic_topic_match(proposition.expected, output, tool_query)
    return _normalize(proposition.expected) in _normalize(output)


def has_keyword_overlap_only(
    proposition: MemoryProposition,
    output: str,
) -> bool:
    """True when raw token appears but semantic contract is not satisfied."""
    if proposition_semantically_satisfied(proposition, output):
        return False
    token = proposition.expected
    if proposition.kind == PropositionKind.language_preference:
        return _has_keyword_token(output, token)
    if proposition.kind == PropositionKind.topic_preference:
        return _has_keyword_token(output, token)
    return _has_keyword_token(output, token)


def memory_exposed_in_context(exposed_context: str, seeds: tuple[MemorySeed, ...]) -> bool:
    if not seeds:
        return exposed_context == ""
    if not exposed_context.strip():
        return False
    for seed in seeds:
        payload = json.dumps(seed.value, ensure_ascii=False, sort_keys=True)
        if seed.key not in exposed_context and payload not in exposed_context:
            return False
    return True


def analyze_utilization(
    seeds: tuple[MemorySeed, ...],
    output: str,
    *,
    tool_query: str | None = None,
) -> UtilizationAnalysis:
    if not seeds:
        return UtilizationAnalysis(
            semantic_utilized=False,
            keyword_overlap_only=False,
            contradicted=False,
            reason="no seeded propositions",
        )

    propositions = extract_propositions(seeds)
    matched: list[str] = []
    keyword_only = False
    contradicted = False

    for prop in propositions:
        if _detect_contradiction(prop, output):
            contradicted = True
        if proposition_semantically_satisfied(prop, output, tool_query=tool_query):
            matched.append(f"{prop.key}={prop.expected}")
        elif has_keyword_overlap_only(prop, output):
            keyword_only = True

    all_semantic = len(matched) == len(propositions) and not contradicted
    return UtilizationAnalysis(
        semantic_utilized=all_semantic,
        keyword_overlap_only=keyword_only and not all_semantic,
        contradicted=contradicted,
        matched_propositions=tuple(matched),
        reason="" if all_semantic else "proposition contract not fully satisfied",
    )


def seeds_equivalent(a: tuple[MemorySeed, ...], b: tuple[MemorySeed, ...]) -> bool:
    if len(a) != len(b):
        return False
    a_keys = {(s.key, s.memory_type, json.dumps(s.value, sort_keys=True)) for s in a}
    b_keys = {(s.key, s.memory_type, json.dumps(s.value, sort_keys=True)) for s in b}
    return a_keys == b_keys

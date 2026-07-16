"""内容安全过滤层：在生成前后检查输入/输出内容。

架构：
- input_safety_check(): 用户输入检查（拒绝有害/违规查询）
- output_safety_check(): LLM 输出检查（过滤幻觉/有害内容）
- 两级模式：block（拒绝）或 flag（标记 + 放行）
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── 敏感词列表（第一版：基础关键字匹配，后续可升级为模型分类）──

# 输入侧：拒绝回答的违规查询关键词
_BLOCKED_INPUT_PATTERNS: list[re.Pattern] = [
    re.compile(r"如何制作(炸弹|违禁药|毒品|枪支|爆炸物)", re.IGNORECASE),
    re.compile(r"(赌博|赌场)网站", re.IGNORECASE),
    re.compile(r"破解(密码|系统|软件|账号)", re.IGNORECASE),
    re.compile(r"出售(个人信息|隐私数据|银行卡)", re.IGNORECASE),
    re.compile(r"(黑客|攻击)方法", re.IGNORECASE),
    re.compile(r"儿童(色情|性)", re.IGNORECASE),
]

# 输出侧：应被拦截的重度有害内容关键词
_BLOCKED_OUTPUT_PATTERNS: list[re.Pattern] = [
    re.compile(r"(制作|配方|步骤).*(炸弹|冰毒|海洛因)", re.IGNORECASE),
    re.compile(r"具体(攻击|入侵).*步骤", re.IGNORECASE),
]

# 输出侧：应被屏蔽的敏感信息泄露模式
_LEAKAGE_OUTPUT_PATTERNS: list[re.Pattern] = [
    re.compile(r"(sk-[a-zA-Z0-9_\-]{20,}|deepseek-[a-zA-Z0-9_\-]{10,})", re.IGNORECASE),  # API Key
    re.compile(r"eyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}"),  # JWT
    re.compile(r"(?:system|assistant)\s*(?:prompt|message|instruction)", re.IGNORECASE),  # 疑似 system prompt
]

# 输出侧：应被标记（flag）的中度敏感内容
_FLAGGED_OUTPUT_PATTERNS: list[re.Pattern] = [
    re.compile(r"歧视(女性|种族|宗教|年龄|性取向)", re.IGNORECASE),
    re.compile(r"暴力\s*(解决|手段|方法)", re.IGNORECASE),
    re.compile(r"(政治|宗教)敏感话题", re.IGNORECASE),
]

SAFETY_BLOCK_REPLY = "抱歉，我无法回答此问题。请提出与知识库相关的问题。"
SAFETY_BLOCK_REPLY_EN = "Sorry, I cannot answer this question. Please ask questions related to the knowledge base."


def input_safety_check(text: str) -> tuple[bool, str | None]:
    """检查用户输入是否违规。

    Returns:
        (is_safe, block_reply_or_None)
    """
    for pattern in _BLOCKED_INPUT_PATTERNS:
        if pattern.search(text):
            logger.warning("输入安全拦截: pattern=%s, text=%s", pattern.pattern, text[:80])
            return False, SAFETY_BLOCK_REPLY
    return True, None


def output_safety_check(text: str) -> tuple[bool, list[str]]:
    """检查 LLM 输出是否包含不安全内容。

    Returns:
        (is_safe, flagged_reasons)

    返回 False 当：
    - 包含重度有害内容（block）
    - 泄露 API Key / JWT / System Prompt
    """
    blocked = [p.pattern for p in _BLOCKED_OUTPUT_PATTERNS if p.search(text)]
    if blocked:
        logger.warning("输出安全拦截: %s", blocked)
        return False, blocked

    leaked = [p.pattern for p in _LEAKAGE_OUTPUT_PATTERNS if p.search(text)]
    if leaked:
        logger.warning("输出泄露拦截: %s", leaked)
        return False, leaked

    flagged = [p.pattern for p in _FLAGGED_OUTPUT_PATTERNS if p.search(text)]
    if flagged:
        logger.info("输出安全标记: %s", flagged)

    return True, flagged

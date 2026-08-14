"""T6 长期记忆分层 · W2 滑动窗口（工作记忆）服务。

消息数 / token 双预算裁剪，溢出内容转为摘要占位；确定性纯函数、零 LLM、零 DB。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkingMessage:
    role: str            # "user" | "assistant"
    content: str


@dataclass(frozen=True, slots=True)
class SummaryPlaceholder:
    key: str             # f"{agent_memory_window_summary_prefix}:{n}"
    collapsed_indexes: list[int]   # 被折叠消息在原列表中的下标（升序）
    preview: str         # 固定占位文案（不含用户/助手原文）


@dataclass(frozen=True, slots=True)
class SlidingWindowResult:
    retained: list[WorkingMessage]
    placeholders: list[SummaryPlaceholder]


def estimate_token_count(text: str) -> int:
    """与 generation.estimate_token_count 同口径的本地实现（中文 ×1.5 + 英文词 ×1.3）。"""
    cjk = sum(
        1
        for c in text
        if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f"
    )
    ascii_words = len(text.split())
    return int(cjk * 1.5 + ascii_words * 1.3)


def _split_collapsed(
    collapsed: list[tuple[int, WorkingMessage]],
    summary_prefix: str,
    summary_max: int,
) -> list[SummaryPlaceholder]:
    """按原顺序把被折叠消息切分为至多 summary_max 段，每段产出一条占位记录。"""
    if not collapsed or summary_max <= 0:
        return []
    if len(collapsed) <= summary_max:
        segments = [collapsed]
    else:
        chunk_size = (len(collapsed) + summary_max - 1) // summary_max
        segments = [
            collapsed[i : i + chunk_size]
            for i in range(0, len(collapsed), chunk_size)
        ]
    return [
        SummaryPlaceholder(
            key=f"{summary_prefix}:{index}",
            collapsed_indexes=[orig_index for orig_index, _ in segment],
            preview=f"已折叠 {len(segment)} 条较早消息，摘要待生成",
        )
        for index, segment in enumerate(segments, start=1)
    ]


def trim_sliding_window(
    history: list[WorkingMessage],
    *,
    max_messages: int = 12,
    token_budget: int = 22400,
    min_keep: int = 2,
    summary_prefix: str = "wm_summary",
    summary_max: int = 3,
) -> SlidingWindowResult:
    """消息数 / token 双预算滑动窗口裁剪。确定性、纯函数、零 LLM。

    双预算均禁用（max_messages <= 0 且 token_budget <= 0）时返回全部历史且占位为空；
    单个预算为 0 表示该维度关闭。min_keep > 0 时即使超预算也强制保留最新 min_keep 条。
    """
    if not history or (max_messages <= 0 and token_budget <= 0):
        return SlidingWindowResult(retained=list(history), placeholders=[])

    retained: list[WorkingMessage] = []
    token_total = 0
    for msg in reversed(history):
        if max_messages > 0 and len(retained) + 1 > max_messages:
            break
        msg_tokens = estimate_token_count(msg.content)
        if token_budget > 0 and token_total + msg_tokens > token_budget:
            break
        retained.append(msg)
        token_total += msg_tokens
    retained.reverse()

    if min_keep > 0 and len(retained) < min_keep:
        retained = list(history[-min_keep:])

    retained_ids = {id(msg) for msg in retained}
    collapsed = [
        (index, msg)
        for index, msg in enumerate(history)
        if id(msg) not in retained_ids
    ]
    placeholders = _split_collapsed(collapsed, summary_prefix, summary_max)
    return SlidingWindowResult(retained=retained, placeholders=placeholders)


def build_collapsed_summary(
    history: list[WorkingMessage],
    placeholder: SummaryPlaceholder,
) -> str:
    """对折叠消息段生成确定性结构化摘要（零 LLM、不含原文）。

    只输出角色 / 数量 / token / 长度等元数据，不输出任何消息内容；
    与记忆行 summary（canonical JSON 字段压缩）不同源、不同格式。
    """
    messages = [history[index] for index in placeholder.collapsed_indexes]
    user_count = sum(1 for message in messages if message.role == "user")
    assistant_count = sum(
        1 for message in messages if message.role == "assistant"
    )
    tokens = sum(estimate_token_count(message.content) for message in messages)
    lengths = [len(message.content) for message in messages]
    min_chars = min(lengths) if lengths else 0
    max_chars = max(lengths) if lengths else 0
    return (
        f"[会话折叠摘要] 较早消息 {len(messages)} 条："
        f"user {user_count} / assistant {assistant_count}，"
        f"约 {tokens} token，长度 {min_chars}~{max_chars} 字"
    )


def apply_placeholder_summaries(
    history: list[WorkingMessage],
    placeholders: list[SummaryPlaceholder],
) -> list[SummaryPlaceholder]:
    """把每个占位的 preview 替换为折叠段结构化摘要（确定性、幂等）。"""
    return [
        SummaryPlaceholder(
            key=placeholder.key,
            collapsed_indexes=list(placeholder.collapsed_indexes),
            preview=build_collapsed_summary(history, placeholder),
        )
        for placeholder in placeholders
    ]


def trim_sliding_window_with_summary(
    history: list[WorkingMessage],
    *,
    max_messages: int = 12,
    token_budget: int = 22400,
    min_keep: int = 2,
    summary_prefix: str = "wm_summary",
    summary_max: int = 3,
) -> SlidingWindowResult:
    """滑动窗口裁剪后直接把占位替换为结构化摘要（组合入口）。"""
    result = trim_sliding_window(
        history,
        max_messages=max_messages,
        token_budget=token_budget,
        min_keep=min_keep,
        summary_prefix=summary_prefix,
        summary_max=summary_max,
    )
    return SlidingWindowResult(
        retained=result.retained,
        placeholders=apply_placeholder_summaries(history, result.placeholders),
    )


@dataclass(frozen=True, slots=True)
class WindowedPromptHistory:
    history: list[dict[str, str]]             # prompt 就绪历史（含折叠摘要 system 消息；无折叠 = 原历史浅拷贝）
    folded: bool                              # 是否发生折叠
    placeholders: list[SummaryPlaceholder]    # 折叠段结构化摘要（测试/审计用；不进 prompt）


def build_windowed_prompt_history(
    history: list[dict[str, str]],
    *,
    max_messages: int = 12,
    token_budget: int = 22400,
    min_keep: int = 2,
    summary_prefix: str = "wm_summary",
    summary_max: int = 3,
) -> WindowedPromptHistory:
    """零 LLM 会话历史窗口化：role/content dict → prompt 就绪历史。

    - 空 history → history=[] / folded=False / placeholders=[]；
    - 无折叠（未超消息数 / token 预算）→ history 与输入逐字相等（浅拷贝），folded=False；
    - 有折叠 → retained 转回 role/content dict（不含被折叠原文），最前插入
      {"role": "system", "content": "【对话摘要】\\n" + "\\n".join(ph.preview ...)}；
    - 确定性纯函数：同输入必同输出；被折叠消息原文永远不进入返回结果。
    """
    if not history:
        return WindowedPromptHistory(history=[], folded=False, placeholders=[])

    messages = [
        WorkingMessage(role=msg["role"], content=msg["content"])
        for msg in history
    ]
    result = trim_sliding_window_with_summary(
        messages,
        max_messages=max_messages,
        token_budget=token_budget,
        min_keep=min_keep,
        summary_prefix=summary_prefix,
        summary_max=summary_max,
    )
    if not result.placeholders:
        return WindowedPromptHistory(
            history=list(history), folded=False, placeholders=[]
        )

    retained = [
        {"role": message.role, "content": message.content}
        for message in result.retained
    ]
    summary_content = "【对话摘要】\n" + "\n".join(
        placeholder.preview for placeholder in result.placeholders
    )
    return WindowedPromptHistory(
        history=[{"role": "system", "content": summary_content}, *retained],
        folded=True,
        placeholders=list(result.placeholders),
    )

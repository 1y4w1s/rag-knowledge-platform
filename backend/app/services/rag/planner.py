"""检索策略决策（Phase 1 从 retrieval.py 拆分）。

职责：
- 是否跳过 Rerank 的置信度评估（always 路径）
- 条件精排：是否因排序歧义才跑 Rerank
- 条件多查询：短问 / 池空洞才扩
- 自适应 Top-K 数量
- Query Understanding 相关辅助函数

纯函数——不依赖 DB 连接。
"""

from __future__ import annotations

import re
from uuid import UUID

from app.core.config import settings
from app.services.rag.types import RetrievedChunk

import enum


class RetrievalStrategy(enum.Enum):
    """自适应检索策略等级。

    simple  → 单路向量（最快），适合短关键词查询
    medium  → 混合检索 + RRF（当前默认），适合常规查询
    complex → 多查询 + HyDE + Rerank，适合长描述/多意图查询
    """
    simple = "simple"
    medium = "medium"
    complex = "complex"


def select_strategy(query: str) -> RetrievalStrategy:
    """根据 query 复杂度选择检索策略。

    维度：
    - 超短问（去标点 < 4 字）→ simple（如"年假"）
    - 实体数 ≥ 2 或多意图 → complex（优先于长度判断）
    - 长问（> 20 字）→ complex（如"……和……有什么区别"）
    - 其余 → medium
    """
    core = (query or "").translate(_PUNCT_STRIP).strip()
    core_len = len(core)

    if 0 < core_len < _SHORT_QUERY_LEN:
        return RetrievalStrategy.simple

    # 实体数 + 多意图检测（独立于长度）
    if _count_named_entities(query) >= 2 or _has_multi_intent(query):
        return RetrievalStrategy.complex

    if core_len > _LONG_QUERY_LEN:
        return RetrievalStrategy.complex

    return RetrievalStrategy.medium

# 条件精排阈值（偏保守 · 少触发）
_RRF_REL_GAP = 0.08
_CHANNEL_JACCARD_MAX = 0.34
_HIGH_SIM = 0.85

# 条件多查询阈值（偏保守 · 少触发）
# 短问：去标点后 len < 4（如「年假」）；完整短句如「年假有多少天」不直扩
_SHORT_QUERY_LEN = 4
# 长问：去标点后 len > 20 触发 complex 策略
_LONG_QUERY_LEN = 20
# 绝对 max_sim 门槛依赖真 BGE 量纲；mock 词表向量 cos≈0.02，本叶不用绝对 sim 判 miss
_PUNCT_STRIP = str.maketrans("", "", "？?。.!！，,、；;：:…—-·\t\n\r ")


# ── 命名实体检测（B3 自适应策略用）──

# 书名号 / 引号包裹的命名实体（≥2 字符非空白）
_ENTITY_QUOTE_PATTERN = re.compile(
    r'[《「【"][^《》「」【】"]{2,}[》」】"]'
)
# 组织名：英文前缀 or 2-8 中文 + 后缀
_ORG_NAME_PATTERN = re.compile(
    r'(?:[A-Z][a-z]+|[\u4e00-\u9fff]{3,8})'  # 前缀：英文前缀 or 3-8 中文（最小 3 防"介绍公司"误匹配）
    r'(?:公司|集团|银行|保险|科技|有限|股份|组织|局|处|中心|院|所|委员会|大学|学院)'  # 后缀
)
# 多意图关键词
_MULTI_INTENT_PATTERN = re.compile(
    r'(?:和|与|及|比较|对比|区别|分别|以及|或者|还是|同时)'
)

# 复合题判定（实验 M）：条件句中的关联词 / 连接词堆叠
_COMPOSITE_COND_WORD = re.compile(r'(和|且|又|但|还|需要|同时|也|或)')
# 并列/对比标记：答案通常在同一 chunk（对比表/并列问答），拆分反而拆散检索
_COMPARE_MARKERS = ("分别", "区别", "对比", "比较")


def is_composite_query(query: str) -> bool:
    """复合题判定：多问号 / 条件组合 / 连接词堆叠（排除并列对比）。

    复合题 = 需跨知识点或跨条件筛选取证的查询
    （如"1000用户+SSO+审计+预算3万"、"能退款吗？能退多少？"）。
    仅对命中者启用子查询拆分（实验 M），避免实验 J 全量 multi-query 的噪音。
    并列/对比题（含"分别/区别/对比/比较"）答案通常在同一 chunk，拆分
    会引入噪音（实测 ENT-059/072 回归），一律不判复合。

    Returns:
        True → 判定为复合题（后续走 decompose 子查询拆分路径）
    """
    if not query:
        return False
    q = query.replace("（", "(").replace("）", ")")
    # 信号 1：双问号（"能退款吗？能退多少？"）
    if q.count("？") >= 2 or q.count("?") >= 2:
        return True
    # 信号 2：条件句（如果/若）+ 条件词（和/且/又/但/需要…），且句长足够
    if ("如果" in q or "若" in q) and _COMPOSITE_COND_WORD.search(q) and len(q) >= 12:
        return True
    # 信号 3：多意图连接词堆叠（"全量备份和增量备份分别…"）——但排除并列/对比
    if any(m in q for m in _COMPARE_MARKERS):
        return False
    conns = _MULTI_INTENT_PATTERN.findall(q)
    if len(conns) >= 2 and len(q) >= 15:
        return True
    return False


def _count_named_entities(query: str) -> int:
    """统计 query 中的命名实体数（书名号/引号包裹 + 组织名）。"""
    if not query:
        return 0
    count = 0
    count += len(_ENTITY_QUOTE_PATTERN.findall(query))
    count += len(_ORG_NAME_PATTERN.findall(query))
    return count


def _has_multi_intent(query: str) -> bool:
    """检测 query 是否包含多意图（对比/并列关键词）。"""
    if not query:
        return False
    return bool(_MULTI_INTENT_PATTERN.search(query))


def effective_rerank_policy() -> str:
    """解析有效精排策略：off | always | conditional。

    RERANK_POLICY 优先；未设/off 时若 RERANK_ENABLED=true 则桥接为 always。
    """
    policy = (settings.rerank_policy or "off").strip().lower()
    if policy in ("always", "conditional"):
        return policy
    if settings.rerank_enabled:
        return "always"
    return "off"


def effective_query_rewrite_policy() -> str:
    """解析有效多查询策略：off | always | conditional。

    QUERY_REWRITE_POLICY 优先；未设/off 时若 QUERY_REWRITE_ENABLED=true 则桥接 always。
    """
    policy = (settings.query_rewrite_policy or "off").strip().lower()
    if policy in ("always", "conditional"):
        return policy
    if settings.query_rewrite_enabled:
        return "always"
    return "off"


def is_short_query_for_rewrite(query: str) -> bool:
    """超短问直扩：去标点空白后 len < 4。"""
    core = (query or "").translate(_PUNCT_STRIP).strip()
    return 0 < len(core) < _SHORT_QUERY_LEN


def should_expand_queries(
    query: str,
    candidates: list[RetrievedChunk],
    *,
    has_effective_fts: bool = False,
) -> bool:
    """条件多查询：默认不扩；仅首轮结构空洞时 True。

    短问由 is_short_query_for_rewrite 在检索前直扩。
    miss 代理（本叶）：空池 / ≤1 候选 /（无有效 FTS 且候选 ≤2）。
    不用绝对 max_sim（mock 与真 BGE 量纲不可比）。
    """
    _ = query
    if not candidates:
        return True
    if len(candidates) <= 1:
        return True
    if not has_effective_fts and len(candidates) <= 2:
        return True
    return False


def should_skip_rerank(
    candidates: list[RetrievedChunk],
    fts_rows: list,
    query: str,
) -> bool:
    """4 信号置信度评估：是否跳过 Rerank（always 路径）。

    Returns:
        True → 跳过 Rerank（RRF 顺序直接返回）
        False → 保留 Rerank
    """
    if not candidates:
        return True

    max_sim = max(c.similarity for c in candidates)
    query_len = len(query)
    fts_high = fts_rows and fts_rows[0].fts_rank is not None and fts_rows[0].fts_rank > 0.1
    only_one = len(candidates) <= 1

    if only_one:
        return True
    if max_sim > 0.85:
        return True
    if max_sim > 0.70 and fts_high:
        return True
    if fts_high and query_len < 10:
        return True
    return False


def should_run_rerank(
    candidates: list[RetrievedChunk],
    *,
    vector_top_ids: list[UUID] | None = None,
    fts_top_ids: list[UUID] | None = None,
) -> bool:
    """条件精排：默认不跑；仅排序歧义时为 True。

    硬排除（False）：≤1 候选、极高向量置信、RRF 分差已拉开。
    介入（True）：RRF 过平，或向量/FTS Top-3 Jaccard 低（且未硬排除）。
    """
    if len(candidates) <= 1:
        return False

    max_sim = max(c.similarity for c in candidates)
    if max_sim > _HIGH_SIM:
        return False

    rel_gap = _rrf_relative_gap(candidates)
    if rel_gap is not None and rel_gap >= _RRF_REL_GAP:
        return False

    # A：RRF 过平
    if (
        len(candidates) >= 3
        and candidates[0].rrf_score is not None
        and candidates[2].rrf_score is not None
        and rel_gap is not None
        and rel_gap < _RRF_REL_GAP
    ):
        return True

    # B：两路 Top-3 分歧
    if vector_top_ids is not None and fts_top_ids is not None:
        v = set(vector_top_ids[:3])
        f = set(fts_top_ids[:3])
        if v and f and _jaccard(v, f) < _CHANNEL_JACCARD_MAX:
            return True

    return False


def _rrf_relative_gap(candidates: list[RetrievedChunk]) -> float | None:
    """(s1 - s_ref) / s1；s_ref=rank3（不足 3 条用最后一条）。无分则 None。"""
    if not candidates or candidates[0].rrf_score is None:
        return None
    ref_idx = min(2, len(candidates) - 1)
    if candidates[ref_idx].rrf_score is None:
        return None
    s1 = float(candidates[0].rrf_score)
    s_ref = float(candidates[ref_idx].rrf_score)
    return (s1 - s_ref) / max(s1, 1e-9)


def _jaccard(a: set[UUID], b: set[UUID]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def adaptive_top_k(candidates: list[RetrievedChunk], query: str) -> int:
    """根据置信度自适应调整送入 LLM 的 chunk 数量。"""
    if not candidates:
        return 0

    max_sim = max(c.similarity for c in candidates)
    query_len = len(query)

    if max_sim > 0.85:
        return 2
    elif max_sim > 0.70 or query_len > 20:
        return 3
    else:
        return min(len(candidates), 5)


def effective_rerank_for_strategy(
    strategy: RetrievalStrategy, base_policy: str
) -> str:
    """返回实际生效的精排策略：透传 base_policy（实验 N 收紧）。

    B3 曾让 complex 强制 always，不受 RERANK_POLICY 影响。实验 N 诊断实锤：
    bge-reranker 对 FAQ 段落型答案负排序——complex 非 composite 题 Hit@3
    84%→68%（19 题中 5 题负排序、仅 2 题救回，净 -16pp）。且生产
    rerank_policy=off 时该强制在 rerank_chunks 内部被短路成 no-op。
    故回落：complex 与 medium/simple 一样透传 base_policy，全局由
    RERANK_POLICY 控制（composite 题仍由 retrieval 侧 rerank_strategy=None 跳过）。

    Args:
        strategy: 自适应检索策略等级。
        base_policy: effective_rerank_policy() 返回的基础策略（off/always/conditional）。

    Returns:
        实际生效的精排策略。
    """
    _ = strategy
    return base_policy

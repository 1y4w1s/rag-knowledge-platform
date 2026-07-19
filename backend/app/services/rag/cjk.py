"""CJK 文本分词辅助（FTS 兼容）。

策略（双路径）：
1. jieba 词级分词 → 精确匹配"年假""员工"等完整词汇
2. 逐字拆分 fallback → 容忍单字搜索（"假"也能命中"年假"）

入库时用 to_tsvector('simple', segment_cjk(content))。
检索时用 plainto_tsquery('simple', segment_cjk(query))。
两者用同一分词函数，保证索引和查询一致。
"""

import re
import jieba

# 单个 CJK 字符正则
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")

# jieba 初始化（首次调用加载词典）
_jieba_initialized = False


def _ensure_jieba() -> None:
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.initialize()
        _jieba_initialized = True


def segment_cjk(text: str) -> str:
    """对文本做 CJK 友好分词，供 PostgreSQL simple 配置索引和查询。

    双路径策略：
    - jieba 词级：'员工年假' → '员工 年假'
    - 单字 fallback：同时保留逐字拆分，用 OR 语义兼容单字搜索

    返回空格分隔的 token 字符串。
    """
    _ensure_jieba()

    words = jieba.lcut(text)
    tokens: list[str] = []

    for w in words:
        # 纯 CJK 词：添加词本身 + 单个字符
        if _CJK_CHAR.fullmatch(w) is not None:
            # 单字：只加一次
            tokens.append(w)
        elif _CJK_CHAR.search(w):
            # 混合词（如 "Python3 年假"）：加原词 + 逐字拆分
            tokens.append(w)
            # 把 CJK 部分逐字拆开
            chars = _CJK_CHAR.findall(w)
            tokens.extend(chars)
        else:
            # 非 CJK（英文/数字）：原样保留
            tokens.append(w)

    result = " ".join(tokens)
    return result


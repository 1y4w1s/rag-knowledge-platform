"""CJK 文本分词辅助（FTS 兼容）。
PostgreSQL simple 配置按空格分词，中文无空格则整个短语当一个 token。
此模块在文档入库和检索查询时在中文/日文/韩文字符间插入空格，
使 simple 配置能正确索引和匹配每个字符。"""

import re

# CJK 统一表意文字 + 扩展A/B + 注音 + 平假名/片假名 + 谚文
_CJK_RE = re.compile(r"([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af])")


def segment_cjk(text: str) -> str:
    """在 CJK 字符间插入空格，供 PostgreSQL simple 配置分词。

    >>> segment_cjk("人工智能工程师")
    '人 工 智 能 工 程 师'
    >>> segment_cjk("machine learning 人工智能")
    'machine learning 人 工 智 能'
    >>> segment_cjk("hello world")
    'hello world'
    """
    return _CJK_RE.sub(r" \1 ", text).strip()

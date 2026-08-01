"""G5-B · 写意图检测（detect_write_intent）单元测试（情景 4-7 · 纯逻辑）。

覆盖：
- 删除意图命中（含文档名）
- 恢复意图命中（回收站文档）
- 创建意图命中（新建 + 文档名词）
- 疑问句拦截（吗/怎么/？ → None）
- 无具体文档名（「把这个删了」）→ None
- 普通问答 → None
- 创建动词但无文档名词（「新建一个任务」）→ None
"""

import pytest

from app.services.agent.planners import detect_write_intent


def test_detect_delete_with_name() -> None:
    intent = detect_write_intent("帮我把旧版年假制度.docx 删掉")
    assert intent is not None
    assert intent.operation == "delete"


def test_detect_restore_with_name() -> None:
    intent = detect_write_intent("把回收站里的旧版年假制度.docx 恢复")
    assert intent is not None
    assert intent.operation == "restore"


def test_detect_create_with_doc_noun() -> None:
    intent = detect_write_intent("帮我新建一份《报销制度》文档草稿")
    assert intent is not None
    assert intent.operation == "create"


def test_create_verb_without_doc_noun_is_none() -> None:
    # 「新建一个任务」无文档名词 → 不触发（避免误触 edit 流）
    assert detect_write_intent("帮我新建一个任务") is None


def test_question_interception_delete() -> None:
    # 疑问句 → 不触发（情景 6 · 避免误删）
    assert detect_write_intent("年假文档能删吗？") is None
    assert detect_write_intent("怎么删掉旧版年假？") is None


def test_question_interception_restore() -> None:
    assert detect_write_intent("这个文档可以恢复吗？") is None


def test_vague_delete_without_name_is_none() -> None:
    # 无具体文档名（纯语气代词）→ 不触发
    assert detect_write_intent("把这个删了") is None
    assert detect_write_intent("我要删除它") is None


def test_plain_chat_is_none() -> None:
    assert detect_write_intent("今天天气怎么样") is None
    assert detect_write_intent("帮我总结一下这份会议纪要") is None


def test_empty_message_is_none() -> None:
    assert detect_write_intent("") is None
    assert detect_write_intent("   ") is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("删除 员工手册 v3.pdf", "delete"),
        ("恢复 员工手册 v2", "restore"),
        ("创建 产品白皮书 文档", "create"),
        ("把年假制度.docx 移除", "delete"),
        ("找回 回收站里的合同模板", "restore"),
    ],
)
def test_parametrized_intents(text: str, expected: str) -> None:
    intent = detect_write_intent(text)
    assert intent is not None
    assert intent.operation == expected

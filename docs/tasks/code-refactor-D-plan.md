# code-refactor-D · Plan

> **父 SPEC**：`docs/tasks/code-refactor-spec.md`  
> **风险**：低（纯提取 + 替换，不改变返回结构）  
> **预计改动**：5 个文件（4 API 文件修改 + 1 新建共享文件），约 +180 / -160 行  
> **基线**：frontend `npm run build` ✅ · Docker 3 services up · pytest 需用 Docker 容器内环境运行（因 Python 3.9 本机不支持 `X | None` 语法）

---

## §0 做什么 / 不做什么

### 做
1. 在 `backend/app/services/rag/message_builder.py` 新建共享函数 `build_chat_message_list`
2. 从 4 个 API handler 中删除内联的引用富化循环，替换为调用上述函数
3. 将 4 个文件中重复的 SSE 标头字典提取为模块级常量 (`SSE_HEADERS`) 统一导出

### 不做
- 不改业务逻辑（引用回填、403/404 行为、ChatMessageResponse 字段）
- 不改 `ask.py` / `ask_threads.py` 缺少 `approval_id/approval_status` 的现状（行为不变）
- 不改任何 DB migration
- 不改测试文件
- 不改 `citations.py` / `ask_common.py` 中的函数签名
- 不新增其他功能

---

## §1 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/app/services/rag/message_builder.py` | **create** | 新建文件：`build_chat_message_list()` + `SSE_HEADERS` 常量 |
| `backend/app/api/chat.py` | modify | 删除 L117–149 循环，调用 `build_chat_message_list`；删除内联 SSE headers |
| `backend/app/api/kb_threads.py` | modify | 删除 L359–391 循环，调用 `build_chat_message_list`；删除内联 SSE headers |
| `backend/app/api/ask.py` | modify | 删除 L96–133 循环，调用 `build_chat_message_list`；删除内联 SSE headers |
| `backend/app/api/ask_threads.py` | modify | 删除 L347–386 循环，调用 `build_chat_message_list`；删除内联 SSE headers |

---

## §2 函数设计

### `build_chat_message_list(db, rows, *, current_user, kb_visible_fn, department_id=None, include_approval=False) -> list[ChatMessageResponse]`

**参数说明：**

| 参数 | 类型 | 来源 |
|------|------|------|
| `db` | `AsyncSession` | 所有 4 个 handler |
| `rows` | `list[ChatMessage]` | 所有 4 个 handler |
| `current_user` | `CurrentUser` | 所有 4 个 handler |
| `kb_visible_fn` | `Callable[[Any], Awaitable[bool]]` | KB 变体传 `is_kb_visible_in_org_scope` 的闭包；Workspace 变体传 `citation_visible_in_scope` 的判断闭包 |
| `department_id` | `str \| None` | 所有 handler |
| `include_approval` | `bool` | `True` → KB 变体（含 `approval_id`/`approval_status`）；`False` → Workspace 变体 |

**行为：**
```
for each row in rows:
  citations = None
  if row.citations is not None:
    citations = []
    for raw in row.citations:
      payload = HistoryCitationPayload.model_validate(raw)
      visible = await kb_visible_fn(payload, raw)
      if not visible:
        payload = payload.model_copy(update={source_status: source_inaccessible})
      elif payload.kb_id is not None:
        payload = await enrich_history_citation_payload(db, current_user, payload, kb_id=payload.kb_id, department_id=department_id)
      citations.append(payload)
  messages.append(ChatMessageResponse(...))
return messages
```

**关键设计决策：**
- `kb_visible_fn` 抽象了 KB vs Workspace 的可见性判断差异：  
  KB 变体直接返回 `kb_visible` 布尔值（忽略 `payload.kb_id`），Workspace 变体用 `citation_visible_in_scope` 判断
- `payload.kb_id is not None` 检查仅在 Workspace 变体中有意义（KB 变体 `kb_visible` 为 True 时一定有 kb_id）
- SSE headers 从各文件删除，改为 `from app.services.rag.message_builder import SSE_HEADERS`

---

## §3 变更步骤（按序执行）

### Step 1：新建 `message_builder.py`

```python
"""引用富化共享函数（code-refactor-D）：从历史消息 rows 构建 ChatMessageResponse 列表。"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.schemas.chat import ChatMessageResponse, HistoryCitationPayload
from app.schemas.citation import CitationSourceStatus
from app.services.rag.citations import enrich_history_citation_payload

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def build_chat_message_list(
    db: AsyncSession,
    rows: list[Any],
    *,
    current_user: CurrentUser,
    kb_visible_fn: Callable[[HistoryCitationPayload, dict], Awaitable[bool]],
    department_id: str | None = None,
    include_approval: bool = False,
) -> list[ChatMessageResponse]:
    """从 DB rows 构建 ChatMessageResponse 列表，逐条回填引用可见性/富化。"""
    messages: list[ChatMessageResponse] = []
    for row in rows:
        citations: list[HistoryCitationPayload] | None = None
        if row.citations is not None:
            citations = []
            for raw in row.citations:
                payload = HistoryCitationPayload.model_validate(raw)
                visible = await kb_visible_fn(payload, raw)
                if not visible:
                    payload = payload.model_copy(
                        update={
                            "source_status": CitationSourceStatus.source_inaccessible
                        }
                    )
                elif payload.kb_id is not None:
                    payload = await enrich_history_citation_payload(
                        db,
                        current_user,
                        payload,
                        kb_id=payload.kb_id,
                        department_id=department_id,
                    )
                citations.append(payload)
        kwargs: dict[str, Any] = {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "citations": citations,
            "created_at": row.created_at,
        }
        if include_approval:
            kwargs["approval_id"] = row.approval_id
            kwargs["approval_status"] = row.approval_status
        messages.append(ChatMessageResponse(**kwargs))
    return messages
```

### Step 2：修改 `chat.py`
- 文件顶部 import 增加：`from app.services.rag.message_builder import SSE_HEADERS, build_chat_message_list`
- 删除 L117–149 的引用富化循环
- 删除 L67–68 和 L77–80 的内联 SSE headers 定义
- `post_chat` 的 SSE headers 改为使用 `SSE_HEADERS`
- `get_chat_messages` 函数体替换为：

```python
    kb_visible = await is_kb_visible_in_org_scope(...)
    
    async def _kb_visible(_payload: HistoryCitationPayload, _raw: dict) -> bool:
        return kb_visible

    messages = await build_chat_message_list(
        db, rows,
        current_user=current_user,
        kb_visible_fn=_kb_visible,
        department_id=department_id,
        include_approval=True,
    )
    return ChatMessagesListResponse(messages=messages)
```

### Step 3：修改 `kb_threads.py`
- 同上，增加 import，删除循环和内联 SSE headers，调用 `build_chat_message_list`

### Step 4：修改 `ask.py`
- 增加 import，删除循环和内联 SSE headers
- Workspace 变体使用 `citation_visible_in_scope` 作为 `kb_visible_fn`：

```python
    async def _citation_visible(payload: HistoryCitationPayload, raw: dict) -> bool:
        return await citation_visible_in_scope(
            db, current_user, raw, scope=scope, department_id=department_id
        )

    messages = await build_chat_message_list(
        db, rows,
        current_user=current_user,
        kb_visible_fn=_citation_visible,
        department_id=department_id,
        include_approval=False,
    )
```

### Step 5：修改 `ask_threads.py`
- 与 Step 4 相同模式

### Step 6：验收
- 运行 `pytest tests/test_chat.py tests/test_kb_threads.py tests/test_ask_chat.py tests/test_ask_threads.py -q`
- 验证 API 行为不变（同一请求前后响应一致）

---

## §4 边界 & 异常

| 边界 | 处理 |
|------|------|
| `rows` 为空 | 返回空列表 |
| `row.citations` 为 None | citations 保持 None |
| `kb_visible_fn` 返回 False | 对应 payload 标记 `source_inaccessible` |
| `payload.kb_id` 为 None | 跳过 `enrich_history_citation_payload` 调用（Workspace 场景） |
| `enrich_history_citation_payload` 抛异常 | 透传给调用方，不捕获 |
| `kb_visible_fn` 抛异常 | 向上传播，不吞没 |

---

## §5 验收门禁（本窗专用）

```
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — D                    │
│            ┃   ┃                                     │
│            ┗━━━┛                                     │
│                                                       │
│  📍 对话标记：{日期} · code-refactor-D · I 窗         │
│                                                       │
│  ▢ 仅改 SPEC 约定的 5 个文件                          │
│  ▢ `pytest tests/test_chat.py tests/test_kb_threads.py tests/test_ask_chat.py tests/test_ask_threads.py -q` 全绿 │
│  ▢ 不改业务行为（4 个 GET /messages 接口返回 JSON 结构不变）│
│  ▢ 不改 DB schema / migration                         │
│  ▢ 不改公共 API 签名（请求/响应字段不变）               │
│  ▢ SSE headers 4 文件一致（均为 `SSE_HEADERS`）        │
│                                                       │
│  回退方案：git checkout -- backend/app/api/{chat,kb_threads,ask,ask_threads}.py backend/app/services/rag/message_builder.py │
│                                                       │
│  ── 验收人签名：___________  日期：___________  ──    │
└─────────────────────────────────────────────────────┘
```

---

## §6 回退指令

```powershell
# 回退所有改动
git checkout -- backend/app/api/chat.py backend/app/api/kb_threads.py backend/app/api/ask.py backend/app/api/ask_threads.py backend/app/services/rag/message_builder.py
```

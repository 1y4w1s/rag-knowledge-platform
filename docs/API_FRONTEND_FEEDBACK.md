# 睿阁 — 对话反馈（👍/👎）API 对接文档

> 后端已就绪，前端只需在对话页面加两个按钮。

---

## 1. 获取 `message_id`

每次 SSE `done` 事件会返回：

```json
event: done
data: {"message_id": "uuid-string", "citations": [...]}
```

前端**必须记录**每条消息的 `message_id`，提交反馈时需要它。

---

## 2. 提交反馈

```http
POST /api/v1/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 1,
  "feedback_text": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message_id` | UUID | 是 | 从 SSE `done` 事件获取 |
| `rating` | int | 是 | `1` = 点赞, `0` = 点踩 |
| `feedback_text` | string | 否 | 可选评论文本，最长 2000 字 |

**响应：** `201 Created`

```json
{
  "id": "uuid",
  "message_id": "uuid",
  "rating": 1,
  "feedback_text": null,
  "created_at": "2026-07-17T12:00:00Z"
}
```

**注意：** 同一用户对同一消息多次提交会更新（upsert），不会报错。

---

## 3. 撤回反馈

```http
DELETE /api/v1/feedback/{feedback_id}
Authorization: Bearer <token>
```

**响应：** `204 No Content`

---

## 4. 查询当前用户对某消息的反馈

```http
GET /api/v1/feedback/messages/{message_id}
Authorization: Bearer <token>
```

**响应：** `200 OK`

```json
{
  "id": "uuid",
  "rating": 1,
  "created_at": "2026-07-17T12:00:00Z"
}
```

如果未反馈过，返回 `null`。

---

## 5. 获取反馈统计

```http
GET /api/v1/feedback/stats?kb_id=<kb_id>
Authorization: Bearer <token>
```

**响应：** `200 OK`

```json
{
  "total": 100,
  "thumbs_up": 85,
  "thumbs_down": 15,
  "approval_rate": 0.85
}
```

---

## 6. 前端交互示例

```typescript
// 收到 SSE done 事件后
const messageId = doneEvent.message_id;

// 用户点击 👍
await fetch("/api/v1/feedback", {
  method: "POST",
  headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  body: JSON.stringify({ message_id: messageId, rating: 1 }),
});

// 用户点击 👎
await fetch("/api/v1/feedback", {
  method: "POST",
  headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  body: JSON.stringify({ message_id: messageId, rating: 0 }),
});
```

---

## 7. 后端状态确认

| 组件 | 状态 |
|------|------|
| `chat_feedback` 表 | ✅ 已建（message_id, user_id, rating, feedback_text） |
| `POST /api/v1/feedback` | ✅ 已注册 |
| `GET /api/v1/feedback/stats` | ✅ 已注册 |
| `GET /api/v1/feedback/history` | ✅ 已注册 |
| `DELETE /api/v1/feedback/{id}` | ✅ 已注册 |
| SSE `done` 事件中的 `message_id` | ✅ 已提供 |

**前端同学只需：** 在对话气泡底部加 👍/👎 两个按钮，调用 `POST /api/v1/feedback` 即可。

# 睿阁 API · 前端对接参考

> 版本: 0.12.0 · 基准 URL: `http://<host>:8000/api/v1`
> 认证: Bearer JWT（`POST /auth/login` → `access_token`）

---

## 一、认证（Auth）

### POST /auth/register

注册。`account_type` 决定个人版/企业版。

**Request:**
```json
{
  "email": "user@example.com",
  "username": "zhangsan",        // 3-32 位字母数字下划线
  "nickname": "张三",             // 可选
  "password": "Pass1234",         // ≥8 位，需含大小写+数字
  "account_type": "personal",     // "personal" | "enterprise"
  "org_name": null,               // enterprise 时必填
  "invite_code": null             // enterprise 时可选
}
```

**Response (201):**
```json
{ "user": { "id": "uuid", "email": "...", "username": "zhangsan", "account_type": "personal", ... } }
```

---

### POST /auth/login

**Request:**
```json
{ "identifier": "zhangsan", "password": "Pass1234" }
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "uuid", "email": "...", "username": "zhangsan", "nickname": "张三", "account_type": "personal", "org_id": null, "org_role": null, "is_owner": false, "primary_unit_id": null, "unit_ids": [], "unit_admin_unit_ids": [] }
}
```

> `org_role`: "admin" | "member" | null · `account_type`: "personal" | "enterprise"

---

### GET /auth/me

**Headers:** `Authorization: Bearer <token>`

**Response:** 同 `/login` 的 `user` 对象。

---

### POST /auth/forgot-password

**Request:**
```json
{ "identifier": "user@example.com" }
```
**Response:** `{ "message": "..." }` — 发重置邮件（需 Resend 配置）。

### POST /auth/reset-password

**Request:**
```json
{ "token": "jwt...", "new_password": "NewPass1234" }
```
**Response:** `{ "message": "..." }`

---

### POST /auth/invites/validate

**Request:** `{ "code": "INVITE-CODE" }`
**Response:** `{ "org_id": "uuid", "org_name": "公司名" }`

---

## 二、知识库（Knowledge Bases）

### GET /knowledge-bases?workspace=personal&limit=20&offset=0

列出当前用户的资料库。

**Query 参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace` | `"personal"` \| `<组织 UUID>` | 工作区类型；`personal` 或组织 ID 字符串（**非** `team`/`company`） |
| `department_id` | `string?` | 部门过滤（企业版） |
| `limit` / `offset` | `int` | 分页 |

**Response:**
```json
{
  "items": [{
    "id": "uuid",
    "name": "员工手册",
    "description": null,
    "owner_user_id": "uuid",
    "owner_org_id": null,
    "org_unit_id": null,
    "created_at": "2026-01-01T00:00:00",
    "document_count": 5,
    "processing_count": 0,
    "failed_count": 0
  }],
  "total": 1, "limit": 20, "offset": 0
}
```

### POST /knowledge-bases?workspace=personal

```json
{ "name": "新资料库", "description": "可选", "org_unit_id": null }
```
**Response (201):** `KnowledgeBaseResponse`

### GET /knowledge-bases/{kb_id}
### PATCH /knowledge-bases/{kb_id}
```json
{ "name": "新名称", "description": "新描述" }
```
### DELETE /knowledge-bases/{kb_id}
**Response (204):** 无 body

---

## 三、文档（Documents）

所有路径在 `/knowledge-bases/{kb_id}/documents` 下。

### GET /knowledge-bases/{kb_id}/documents?status=completed&limit=20&offset=0

列出资料库中的文档。

**Query 参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | `"all" \| "queued" \| "processing" \| "completed" \| "failed"` | 过滤状态 |
| `limit` / `offset` | `int` | 分页 |

**Response:**
```json
{
  "items": [{ "id": "uuid", "filename": "手册.pdf", "file_type": "pdf", "file_size": 102400, "status": "completed", "uploaded_by": "uuid", "created_at": "...", "updated_at": "...", "visibility": "everyone" }],
  "total": 1, "limit": 20, "offset": 0
}
```

### POST /knowledge-bases/{kb_id}/documents

上传文档。**multipart/form-data**.

| 字段 | 类型 | 说明 |
|------|------|------|
| `files` | `File[]` | 可传多个。白名单: pdf, docx, md, txt, xlsx, pptx |
| `visibility` | `query: "everyone" \| "admin_only"` | 可选，文档级可见性；缺省由后端决定（通常 `everyone`） |

**Response (201):** `DocumentUploadResponse`
```json
{ "documents": [{ "id": "uuid", "filename": "手册.pdf", "status": "queued", "visibility": "everyone", ... }] }
```
> 响应顶层键为 `documents`（**非** `items`）；**无 `failed` 字段**。单个文件失败由后端内部处理，不在响应体暴露。

### GET /knowledge-bases/{kb_id}/documents/{doc_id}
### GET /knowledge-bases/{kb_id}/documents/{doc_id}/preview

返回文档预览内容（文本 / 图片 base64）。

### DELETE /knowledge-bases/{kb_id}/documents/{doc_id}
软删 → 进回收站。**Response (204)**

### POST /knowledge-bases/{kb_id}/documents/{doc_id}/restore
从回收站恢复。**Response (200)**

### DELETE /knowledge-bases/{kb_id}/documents/{doc_id}/permanent
永久删除。**Response (204)**

### GET /knowledge-bases/{kb_id}/documents/trash
列出回收站文档（同上 `DocumentListResponse`）。

### POST /knowledge-bases/{kb_id}/documents/{doc_id}/retry
重试失败的文档入库。**Response (200)**

### PATCH /knowledge-bases/{kb_id}/documents/{doc_id}/visibility
```json
{ "visibility": "everyone" | "admin_only" }
```

---

## 四、对话（Chat）— SSE 流式

### POST /knowledge-bases/{kb_id}/chat

**Request:**
```json
{
  "message": "年假有多少天？",
  "thread_id": null           // 可选，续传历史对话
}
```

**Response: `text/event-stream`**

SSE 事件流，按顺序接收：

```
# 1-N 个 citation（检索片段）
event: citation
data: {"chunk_id":"uuid","document_id":"uuid","doc_name":"员工手册.md","page":1,"section_title":"1.1 年假","excerpt":"员工年满一年后可享受年假10天..."}

# 0-N 个 token（LLM 流式输出）
event: token
data: {"text":"员"}

# 最终 done
event: done
data: {"message_id":"uuid","citations":[{"chunk_id":"...",...}]}
```

**前端对接:**
```
const source = new EventSource(...) // 或用 fetch + ReadableStream
source.addEventListener('citation', e => addCitation(JSON.parse(e.data)))
source.addEventListener('token', e => appendText(JSON.parse(e.data).text))
source.addEventListener('done', e => {
  const { message_id, citations } = JSON.parse(e.data)
  // message_id 是点赞/点踩的唯一键
  feedbackMessageId = message_id
})
```

### POST /knowledge-bases/{kb_id}/threads

创建对话线程（支持多轮对话）。

```json
{ "title": "" }
```
**Response (201):** `{ "id": "uuid", "title": "", "status": "active", ... }`

### POST /knowledge-bases/{kb_id}/threads/{thread_id}/chat

**Request:** 同 `/chat`，但不需要 `thread_id` 字段（路径决定）。

```json
{ "message": "年假需要提前多久申请？" }
```

**SSE 响应：** 同 `/chat`

### GET /knowledge-bases/{kb_id}/threads?limit=20&offset=0
列出线程。**Response:** `{ "threads": [{ "id": "uuid", "title": "...", "last_message_at": "...", ...}] }`

### PATCH /knowledge-bases/{kb_id}/threads/{thread_id}
```json
{ "title": "新标题", "status": "archived" }
```

### DELETE /knowledge-bases/{kb_id}/threads/{thread_id}

### GET /knowledge-bases/{kb_id}/threads/{thread_id}/messages

返回历史消息列表。
```json
[
  { "id": "uuid", "role": "user", "content": "年假有多少天？", "created_at": "..." },
  { "id": "uuid", "role": "assistant", "content": "根据员工手册，员工满一年后可享受年假10天。", "citations": [...], "retrieval_duration_ms": 580, "created_at": "..." }
]
```

---

## 五、工作区对话（Workspace · 跨库）

### POST /ask/chat

**Request:** 同 `/kb/{id}/chat` 但不传 kb_id。

```json
{ "message": "...", "department_id": null, "thread_id": null }
```

**SSE 响应:** 同上。`citation` 多一个 `kb_name` 字段。

### POST /ask/threads（创建线程）
### POST /ask/threads/{id}/chat（线程内对话）
### GET /ask/threads（列表）
### PATCH /ask/threads/{id}（修改标题等）
### DELETE /ask/threads/{id}
### GET /ask/threads/{id}/messages（消息列表）
### GET /ask/messages（无 thread 的历史消息）
### GET /ask/search?q=关键词（搜索历史对话）

---

## 六、点赞/点踩（Feedback）

所有路径在 `/feedback` 下。

### POST /feedback

```json
{
  "message_id": "uuid（来自 SSE done 事件）",
  "rating": 1,          // 1=thumbs up, 0=thumbs down
  "feedback_text": null  // 可选评论
}
```
**Response (201):**
```json
{ "id": "uuid", "message_id": "uuid", "rating": 1, "feedback_text": null, "created_at": "...", "updated_at": null }
```

> **幂等：** 同 `message_id` + `user_id` 第二次提交会更新 rating。

### GET /feedback/messages/{message_id}

查看当前用户对某条消息的反馈。无反馈时返回 `null`。

### GET /feedback/stats?kb_id=uuid（可选）

```json
{ "total": 10, "thumbs_up": 8, "thumbs_down": 2, "approval_rate": 0.8 }
```

### GET /feedback/history?limit=20&offset=0

```json
{ "items": [{ "id": "uuid", "message_id": "uuid", "rating": 1, ... }], "total": 10 }
```

### DELETE /feedback/{feedback_id}
撤回反馈。**Response (204)**

---

## 七、跨库搜索（Search）

### GET /search/documents?q=关键词&mode=filename&workspace=personal&limit=20

| 参数 | 说明 |
|------|------|
| `q` | 搜索关键词（必填） |
| `mode` | `"filename"` 按文件名 / `"content"` 按正文 |
| `workspace` | 必填，`"personal"` 或组织 UUID，限定检索范围 |
| `department_id` | 可选，部门过滤 |
| `limit` | `int` 1–50，默认 20（**无 `offset`**） |

**Response:**
```json
{
  "items": [{
    "doc_id": "uuid", "filename": "手册.pdf", "file_type": "pdf",
    "status": "completed", "kb_id": "uuid", "kb_name": "员工手册",
    "created_at": "...", "snippet": "...,", "page_number": 2
  }],
  "query": "关键词", "total": 1, "mode": "filename"
}
```

---

## 八、统计面板（Dashboard）

### GET /dashboard/stats

**Response:** `DashboardStatsResponse`（看板正在重做，前端须以本结构为准）
```json
{
  "scope": "personal",
  "knowledge_base_count": 3,
  "document_count": 15,
  "documents_by_status": { "queued": 0, "processing": 2, "completed": 12, "failed": 1 },
  "total_chunk_count": 480,
  "avg_processing_duration_seconds": 12.5,
  "ingestion_success_rate": 93.3,
  "chat_message_count": 42,
  "member_count": 5,
  "recent_kb_id": "uuid",
  "recent_kb_name": "员工手册",
  "recent_activities": [{ "type": "document_uploaded", "title": "上传了手册.pdf", "kb_id": "uuid", "doc_id": "uuid", "created_at": "..." }],
  "question_trend": [{ "date": "2026-07-01", "count": 10 }, ...],
  "format_distribution": [{ "format": "pdf", "count": 5 }, ...],
  "recent_threads": [{ "id": "uuid", "title": "...", "last_message_at": "..." }],
  "golden_hit_rate_percent": 81.2
}
```
> 字段名变更提醒：原 `kb_count`→`knowledge_base_count`；`chat_count`→`chat_message_count`；`document_statuses`→`documents_by_status`（含 `queued`）；`format_share`→`format_distribution`；`trend`→`question_trend`（字段为 `date`+`count`，**非** `chats`/`documents`）；`recent_activity`→`recent_activities`（字段 `type`/`title`/`kb_id`/`doc_id`）。

---

## 九、审计日志（Audit）

### GET /admin/audit-logs?limit=20&offset=0&action=kb.created&kb_id=uuid

需组织 Admin 角色。

**Response:**
```json
{
  "items": [{ "id": "uuid", "actor_user_id": "uuid", "action": "kb.created", "resource_type": "knowledge_base", "resource_id": "uuid", "details": { "name": "新库" }, "created_at": "..." }],
  "total": 1, "limit": 20, "offset": 0
}
```

---

## 十、组织（Organization）

### GET/PATCH /organization/settings
### GET /organization/members
### POST /organization/members（添加成员，需邮箱）
### DELETE /organization/members/{user_id}
### PATCH /organization/members/{user_id}（改角色）
```json
{ "role": "admin" | "member" }
```
### POST /organization/invites（生成邀请码）
**Response:** `{ "code": "INVITE-XXX", "org_id": "uuid", "expires_at": "...", "created_at": "..." }`
### POST /organization/transfer-ownership（转让所有者）
```json
{ "target_user_id": "uuid" }
```

---

## 十一、部门（Org Units）

### GET /org-units/picker?org_id=uuid（下拉选择用）
**Response:** `{ "user_units": [{...}], "org_units": [{...}], "all_units": [{...}] }`

### GET /org-units?org_id=uuid
### POST /org-units
```json
{ "name": "技术部", "parent_id": "uuid" }
```
### PATCH /org-units/{id}
```json
{ "name": "新名称" }
```
### DELETE /org-units/{id}

### GET /org-units/{unit_id}/members
### POST /org-units/{unit_id}/members
```json
{ "user_id": "uuid", "role": "unit_member", "is_primary": false }
```
### PATCH /org-units/{unit_id}/members/{user_id}
```json
{ "role": "unit_admin", "is_primary": true }
```
### DELETE /org-units/{unit_id}/members/{user_id}

---

## 十二、知识库授权（KB Grants）

### GET /knowledge-bases/{kb_id}/grants
### POST /knowledge-bases/{kb_id}/grants
```json
{ "grantee_type": "org_unit", "grantee_id": "uuid", "permission": "read" }
```
### DELETE /knowledge-bases/{kb_id}/grants/{grant_id}

---

## 十三、账号设置（Settings）

### GET /settings/account
```json
{ "id": "uuid", "email": "...", "username": "...", "nickname": "张三", "account_type": "enterprise", "org_id": "uuid", "org_role": "admin", "org_name": "某某公司" }
```

### PATCH /settings/account（改密码）
```json
{ "current_password": "Old1234", "new_password": "New12345" }
```

### PATCH /settings/profile（改昵称/用户名）
```json
{ "nickname": "新昵称", "username": "new_name" }
```

### POST /settings/account/join-team
```json
{ "invite_code": "INVITE-XXX" }
```
### POST /settings/account/leave-team

---

## 十四、API Keys

### POST /api-keys
### GET /api-keys
### DELETE /api-keys/{key_id}

---

## 十四（续）、Agent 写库审批（G4-3）

Agent 生成草稿后，落库需人工审批。

### POST /agent/approvals/{approval_id}/resolve

**Request:**
```json
{ "action": "adopt" | "cancel" }
```

- `action=adopt` → 写库 + 异步入库，返回 `AdoptApprovalResponse`
- `action=cancel` → 仅翻转 `agent_approvals.status=cancelled`，**不写库**

**Response (200) — adopt:**
```json
{ "document_id": "uuid", "kb_id": "uuid", "filename": "草稿.md", "status": "processing" }
```

**Response (200) — cancel:**
```json
{ "ok": true }
```

> 红线：resolve 是独立 HTTP 端点，**不在 SSE 层写库**；cancel 绝不写库/改源文件。前端如需展示 Agent 待审批项列表，当前仅有 resolve 端点，列表查询端点若后续提供另行补充。

---

## 十五、关键数据流

### 对话完整生命周期

```
用户输入 → POST /chat
           ↓
SSE: citation × N  (检索片段)
SSE: token    × N  (LLM 逐字生成)
SSE: done { message_id, citations }
           ↓
用户看到完整回答（展示 citations 作为引用来源）
           ↓
用户点击 👍/👎 → POST /feedback { message_id, rating }
           ↓
GET /feedback/stats → 看板展示 approval_rate
```

### 多轮对话

```
POST /kb/{id}/threads → thread_id
POST /kb/{id}/threads/{thread_id}/chat → 自动加载历史 + contextualize_query
```

### 错误处理

| 状态码 | 说明 |
|--------|------|
| 200 | SSE 流正常结束（含 empty citations = 无依据拒答） |
| 401 | JWT 过期/无效 |
| 403 | 无权限（跨库、只读操作） |
| 404 | 资源不存在 |
| 429 | 限流（chat 30/h, upload 20/h） |
| 503 | DB 不可用 |

### 关键枚举值

- `account_type`: `"personal"` | `"enterprise"`
- `org_role`: `"admin"` | `"member"` | `null`
- `workspace`: `"personal"` | `<组织 UUID>`（个人版传 `personal`，企业版传组织 ID 字符串）
- `document_status`: `"queued"` | `"processing"` | `"completed"` | `"failed"`
- `visibility`: `"everyone"` | `"admin_only"`
- `rating`: `1` (thumbs up) | `0` (thumbs down)

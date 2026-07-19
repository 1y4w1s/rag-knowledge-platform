# 睿阁 — 前端路由 / 组件 / 数据流索引

> 交接对象：前端开发者
> 更新日期：2026-07-17

---

## 1. 路由一览

| 路径 | 页面组件 | 权限 | 说明 |
|------|---------|------|------|
| `/` | `Dashboard` | 已登录 | 仪表盘（文档统计、ingestion 状态）|
| `/ask` | `AskPage` | 已登录 | 跨库对话（Ask 模式）|
| `/chat/:kbId` | `ChatPage` | 已登录 + kb 权限 | 单库对话 |
| `/knowledge-bases` | `KBListPage` | 已登录 | 资料库列表 |
| `/knowledge-bases/:kbId` | `KBDetailPage` | 已登录 + kb 权限 | 资料库详情 + 文档列表 |
| `/account` | `AccountPage` | 已登录 | 账号设置 |
| `/admin/*` | `AdminPage` | 企业 Admin | 组织管理 |
| `/login` | `LoginPage` | 未登录 | |
| `/register` | `RegisterPage` | 未登录 | |
| `/invite` | `InvitePage` | 未登录 | 邀请码注册 |

---

## 2. Context 树

```
<AuthProvider>                    → lib/auth-context.tsx
  <WorkspaceProvider>             → lib/workspace-context.tsx
    <DepartmentProvider>          → lib/department-context.tsx
      <ThemeProvider>             → 组件库主题
        <Router>
          <Pages.../>
```

| Context | 存储内容 | 提供方式 |
|---------|---------|---------|
| AuthProvider | token, user, login/logout | `useAuth()` |
| WorkspaceProvider | workspace_id, workspace_type | `useWorkspace()` |
| DepartmentProvider | department_id, departments 树 | `useDepartment()` |

---

## 3. API 客户端层

| 文件 | 职责 |
|------|------|
| `lib/api-client.ts` | 封装 fetch，自动附加 Bearer token、trace_id header |
| `lib/api-knowledge-bases.ts` | KB CRUD API 调用 |
| `lib/api-documents.ts` | 文档上传/列表/删除 |
| `lib/api-chat.ts` | SSE 对话流 |
| `lib/api-auth.ts` | 注册/登录/密码重置 |
| `lib/api-feedback.ts` | 对话反馈 👍/👎 |

---

## 4. SSE 流处理

```
ChatPage / AskPage
    │
    ▼
useMessageStream()  →  lib/use-message-stream.ts
    │
    ├── POST /api/v1/knowledge-bases/{id}/chat
    ├── 读取 SSE 事件流：
    │       event: citation → data: {chunk_id, section_title, content}
    │       event: token    → data: {text: "部"}
    │       event: done     → data: {message_id, citations}
    │
    ├── citations 事件 → 显示引用面板
    ├── token 事件    → 追加到当前消息气泡
    └── done 事件     → 启用反馈按钮 👍/👎
```

**关键 Hook**:
```typescript
// use-message-stream.ts
function useMessageStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  
  const send = async (kbId: string, text: string) => {
    // POST → SSE → 逐 token 追加 → done 事件触发完成
  };
  
  return { messages, isStreaming, send };
}
```

---

## 5. 组件目录

| 目录 | 说明 |
|------|------|
| `components/auth/` | 登录/注册表单 |
| `components/chat/` | 对话气泡、输入框、引用面板 |
| `components/dashboard/` | 仪表盘统计卡片 |
| `components/kb/` | 资料库列表卡片、详情面板 |
| `components/settings/` | 账号/组织设置 |
| `components/ui/` | 基础 UI 组件（Button, Input, Modal 等）|
| `components/feedback/` | 👍/👎 按钮 |

---

## 6. 对话反馈接口

```typescript
// 获取 message_id（来自 SSE done 事件）
const messageId = doneEvent.message_id;

// 提交 👍
POST /api/v1/feedback
{ "message_id": messageId, "rating": 1 }

// 提交 👎
POST /api/v1/feedback
{ "message_id": messageId, "rating": 0 }

// 查询统计
GET /api/v1/feedback/stats
→ { total: 100, thumbs_up: 85, thumbs_down: 15, approval_rate: 0.85 }
```

完整对接文档见 `docs/API_FRONTEND_FEEDBACK.md`。

---

## 7. 前端重做参考

如需对现有页面进行视觉重做，参考 `docs/frontend-rework/` 目录：

| 文件 | 说明 |
|------|------|
| `04-frontend-rework-scope.md` | 重做范围清单（5 核心页）|
| `05-design-review-2026-07-15.md` | 设计评审记录 + Before/After |
| `INDEX.md` | 技术参考包索引 |

设计系统规范见 `docs/DESIGN.md`。

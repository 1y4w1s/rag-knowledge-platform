# code-refactor-K: chat-api.ts Zod 运行时校验

> **父级**：`docs/tasks/code-refactor-spec.md` §P2 K
> **状态**：📋 计划稿

## §0 · 做 & 不做

### 做

1. **安装 `zod`** 到 `frontend/package.json`（`dependencies`）
2. **创建 Zod schemas** 覆盖 `chat-api.ts` 中所有 `as` 强转的数据类型：
   - `Citation`、`CitationResolveResult`、`ChatDonePayload`
   - `ApprovalRequiredPayload`、`ApprovalState`
   - `ChatMessagesResponse`、`HistoryMessage`
3. **`dispatchChatSseBlock` 加 Zod 校验**：每个 SSE 事件分支用对应的 schema 做 `safeParse`，无效数据不传给 handler
4. **`resolveCitation` / `fetchChatMessages` 加 Zod 校验**：`res.json()` 后做 `parse` / `safeParse`
5. **导出 Zod schemas**（供 `ask-api.ts` 等外部复用）
6. **更新测试**：`chat-api.test.ts` 追加 Zod 校验覆盖率
7. **`npm run build` 绿**

### 不做

- 不改业务行为（handler 签名不变、返回值类型不变）
- **不碰 `ask-api.ts`**（属 Scope 外，待后续同模式跟进）
- 不改 SSE 解析流程逻辑
- 不改 API 路由或请求参数
- 不改其他文件除非 import 链必须

## §1 · 具体方案

### 1.1 Zod schema 设计

创建 `frontend/src/lib/chat-schemas.ts`（新文件，约 120 行），集中存放所有 schema：

```ts
import { z } from "zod";

export const CitationSourceStatusSchema = z.enum([
  "available", "document_deleted", "chunk_stale", "source_inaccessible",
]);

export const CitationSchema = z.object({
  chunk_id: z.string().min(1),
  document_id: z.string().min(1),
  doc_name: z.string().min(1),
  page: z.number().int().nullable(),
  section_title: z.string().nullable(),
  excerpt: z.string().min(1),
  kb_id: z.string().nullable().optional(),
  kb_name: z.string().nullable().optional(),
  source_status: CitationSourceStatusSchema.nullable().optional(),
});

export const ChatDonePayloadSchema = z.object({
  message_id: z.string().min(1),
  citations: z.array(CitationSchema),
  agent_run_id: z.string().nullable().optional(),
  approval_id: z.string().nullable().optional(),
  approval_status: z.string().nullable().optional(),
});

export const ApprovalRequiredPayloadSchema = z.object({
  approval_id: z.string().min(1),
  draft_type: z.string(),
  filename: z.string().min(1),
  kb_id: z.string().min(1),
  kb_name: z.string().min(1),
  draft_preview: z.string(),
  citations: z.array(CitationSchema),
  can_adopt: z.boolean(),
});

export const ApprovalStateSchema = z.object({
  approval_id: z.string().min(1),
  filename: z.string().min(1),
  kb_name: z.string().min(1),
  draft_preview: z.string(),
  citations: z.array(CitationSchema),
  can_adopt: z.boolean(),
  status: z.enum(["pending", "adopted", "cancelled"]),
});

export const HistoryMessageSchema = z.object({
  id: z.string().min(1),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  citations: z.array(CitationSchema).nullable(),
  approval_id: z.string().nullable().optional(),
  approval_status: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: z.string(),
});

export const ChatMessagesResponseSchema = z.object({
  messages: z.array(HistoryMessageSchema),
});

export const CitationResolveResultSchema = z.object({
  document_id: z.string().min(1),
  chunk_id: z.string().min(1),
  source_status: CitationSourceStatusSchema,
  doc_name: z.string().nullable(),
});
```

### 1.2 `chat-api.ts` 改造

在 `dispatchChatSseBlock` 中，每个 `as` 强转前加 Zod `safeParse`：

```
citation 事件: data → CitationSchema.safeParse → onCitation
done 事件: data → ChatDonePayloadSchema.safeParse → onDone
approval_required 事件: data → ApprovalRequiredPayloadSchema.safeParse → onApprovalRequired

tool_start / tool_result / agent_budget: 用内联 zod schema 或保留原逻辑（字段少，风险低）
```

在 `resolveCitation` 中：
```
const json = await res.json();
return CitationResolveResultSchema.parse(json);
```

在 `fetchChatMessages` 中：
```
const data = ChatMessagesResponseSchema.parse(await res.json());
return data.messages;
```

### 1.3 保留的 `as`（无需验证）

- `ChatStreamHandlers` — 纯类型定义，无运行时数据流
- `CitationLabelMode` — union type，编译期已足够
- 工具函数入参出参 — 纯计算，不解析外部数据

### 1.4 类型重用

- 保留现有 TS `interface` 和 `type` 导出（Zod 的 `z.infer<typeof X>` 可选迁移，不在本轮范围）
- Zod schema 和 TS type 双维护，不做 type 替换

## §2 · 变更文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/package.json` | ✅ 改 | 添加 `zod` dependency |
| `frontend/src/lib/chat-schemas.ts` | 🆕 新增 | Zod schema 定义（~120 行） |
| `frontend/src/lib/chat-api.ts` | ✅ 改 | 替换 7 个 `as` 强转为 Zod safeParse/parse |
| `frontend/src/lib/chat-api.test.ts` | ✅ 改 | 追加 Zod 校验测试（~80 行） |

## §3 · 验收门禁

1. **`npm run build` 绿** — tsc + vite build 无报错
2. **`npx vitest run src/lib/chat-api.test.ts` 绿** — 原有测试 + 新增测试全通过
3. **不改业务行为** — 函数签名、返回值类型、handler 触发时机均不变
4. **无效 SSE 数据自动丢弃** — safeParse 失败的 payload 不触发 handler（`console.warn` 记录）

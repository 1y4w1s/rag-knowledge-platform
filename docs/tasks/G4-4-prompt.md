【背景】G4-min P ✅ · V ✅ v4.2 V2 冻结 · R ✅ · L ✅ · H4-1～H4-6 已拍板
· G4-0.1～G4-1.1 ✅ · G4-1.2 ✅ · G4-1.3 ✅ · G4-2.1～G4-2.5 ✅
· G4-3.1 ✅ · G4-3.2 ✅ · G4-3.3 ✅（adopt/cancel 真实落地 · 全量 157 passed）
· G4-3.5 ✅（审计钩子：4 事件 + 独立会话 denied + metadata 无草稿全文）
· 后端 resolve/adopt/cancel/audit 全部固化且零回退 · 下一窗 **G4-4**（前端端到端 SSE 串验）· WIP=0

【要求】严格只做 plan §9 **G4-4.1 / G4-4.2 / G4-4.3**（前端），把编辑模式 SSE 的
`approval_required` 事件与 `POST /api/v1/agent/approvals/{id}/resolve` 接进 UI，**端到端串验**
整条链路。后端 **一律不动**（G4-3.1/3.2/3.3/3.5 零回退），fast/thorough SSE **零回归**。

== 后端既定语义（前端消费，勿改后端）==
- SSE 顺序（编辑模式）：`tool_*` → `citation` → `token` → **`approval_required`**（成功）/ `refusal`（拒答 G4-E11）→ `done`。
- `approval_required` 载荷（来自 `app/services/agent/stream.py` 行 387-399）：
  ```json
  {
    "approval_id": "uuid",
    "draft_type": "faq",
    "filename": "建议文件名.md",
    "kb_id": "uuid",
    "kb_name": "库名",
    "draft_preview": "截断后的草稿预览（后端已截断，非全文）",
    "citations": [ ... ],
    "can_adopt": true | false
  }
  ```
  - `can_adopt=false` ⇒ 当前用户对该 kb **无写权限**（典型 Member）→ 前端**不显示采纳钮**，仅展示说明文案。
- `done` 载荷含 `approval_id` + `approval_status:"pending"`（plan §5.3）。
- 采纳：`POST .../resolve` `{action:"adopt"}` → 200 `{document_id, kb_id, filename, status:"processing"}`（filename 为实际落库名，可能 `_v2`）。
- 取消：`POST .../resolve` `{action:"cancel"}` → 200 `{ok:true}`。
- 错误码：Member 撤他人 → 403（G4-E9）· 重复采纳/取消 → 409（G4-E3/E5）· 未知 action → 422 · approval 不存在 → 404（G4-E8）。

== 改动清单（前端 · 全部位于 frontend/）==

**1. 模式类型 + 切换器（G4-4.1）**
- `src/lib/agent-mode.ts`：
  `export type AgentMode = "fast" | "thorough"` → 扩展为 `"fast" | "thorough" | "edit"`；
  `agentModeLabel` 增加 `mode === "edit" ? "编辑"`。
- `src/components/chat/AgentModeSwitcher.tsx`：
  当前 `MODES`（行 12-15）仅 fast/thorough；新增 `{ value: "edit", label: "编辑" }`。
  当前行 48-57 的「编辑」是 `disabled` 灰钮占位（data-testid="agent-mode-edit"）→ 改为**可用**按钮，
  `onClick={() => onChange("edit")}`，**全员可切（含 Member）**，去掉 `disabled`/`aria-disabled`/G4 愿景 title。

**2. SSE 解析新增 approval_required（G4-4.3 前置）**
- `src/lib/chat-api.ts`：
  - `ChatStreamHandlers`（行 58-65）新增：
    `onApprovalRequired?: (payload: ApprovalRequiredPayload) => void;`
    并导出 `ApprovalRequiredPayload` 类型（字段同上方后端载荷：`approval_id, draft_type, filename, kb_id, kb_name, draft_preview, citations, can_adopt`）。
  - `dispatchChatSseBlock`（行 67-113）在 `else if` 链中新增：
    `else if (eventName === "approval_required") { handlers.onApprovalRequired?.(data as unknown as ApprovalRequiredPayload); }`
  - `src/lib/thread-api.ts` 的 `dispatchSseBlock`（行 85-87）已转发到 `dispatchChatSseBlock`，**无需改动**。

**3. 会话 Hook 接审批（G4-4.3）**
- `src/lib/use-thread-session.ts`（`useThreadSession`）：
  - 扩展 `ChatMessage` / `AssistantChatMessage` 类型（`src/components/chat/ChatMessageList.tsx` 导出）增加可选字段：
    `approval?: { approval_id, filename, kb_name, draft_preview, citations, can_adopt, status: "pending"|"adopted"|"cancelled" }`。
  - `sendMessage`（行 257）的 `streamThreadChat` handlers（行 303-356）新增 `onApprovalRequired`：
    把 payload 写进**当前最后一条 assistant message** 的 `approval` 字段（status 默认 `"pending"`）。
  - 新增并暴露两个异步方法（与现有 `archiveThread` 等同级）：
    - `resolveApproval(approvalId, action: "adopt"|"cancel")` → 调 `POST /api/v1/agent/approvals/${approvalId}/resolve`（在 `thread-api.ts` 新增 `resolveApproval` 函数，复用 `threadFetch` + Bearer；解析 200 出参；非 2xx 抛带 status 的错误）。
    - 采纳成功（200）：把对应 message.approval.status 置 `"adopted"`，并用响应 `filename` 覆盖显示（反映 `_v2`）。
    - 取消成功（200 `ok:true`）：status 置 `"cancelled"`。
    - 捕获 409/403：转为**友好提示**（toast/卡片内文案），**不抛 500、不崩**；保留卡片可重试或直接显示终态。
  - 确认 `abortForModeSwitch`（行 93-96）在编辑模式发送中切模式时也 Abort SSE（G4-E13）；`sendMessage` 已把 `mode` 透传 `streamThreadChat`（行 358），保留。

**4. ApprovalCard 组件（G4-4.2 · 新建）**
- 新建 `src/components/chat/ApprovalCard.tsx` + 内联 `DraftPreview`（可折叠预览，展示 `draft_preview`，不拉全文）：
  - props：`approval`（含 `can_adopt`）、`onAdopt()`、`onCancel()`、`resolving?`（按钮 loading 态）。
  - **Admin / 可写角色**（`can_adopt === true`）：渲染「采纳」「取消」双钮（采纳主钮、取消次钮）。
  - **Member / 不可写角色**（`can_adopt === false`）：**无采纳钮**，仅展示说明文案（如「你对该知识库无写入权限，需管理员采纳」）。
  - **终态渲染**：`status==="adopted"` → 灰显「已采纳 · 落库文件名.md」；`status==="cancelled"` → 灰显「已取消」。
  - 引用 chips：复用现有 `Citation` 渲染，展示 `approval.citations`。
  - 对齐 preview v4.2 采纳卡视觉（参考 `.mode-switcher` / 卡片样式体系）。

**5. 消息渲染接线（G4-4.2）**
- `src/components/chat/ChatMessageList.tsx`：渲染 assistant message 时，若 `message.approval` 存在，
  在其下方挂 `<ApprovalCard approval={message.approval} onAdopt={...} onCancel={...} />`；
  `onAdopt`/`onCancel` 由页面经 `useThreadSession` 暴露的 `resolveApproval` 绑定（需把 message 的 approval_id 传回）。
- **F5 刷新保留终态（G4-E18）**：`loadMessages`（行 133）经 `fetchThreadMessages` 拿历史，
  历史消息若带 `approval_id`/`approval_status`（`chat_messages` 附属字段，G4-0.4 已落库）则映射为
  `message.approval.status`，卡片直接渲染终态，无需重发 SSE。

**6. 页面接线（G4-4.1）**
- `src/pages/AskPage.tsx` 与 `src/pages/ChatPage.tsx`：将 `AgentModeSwitcher` 的 `onChange` 值
  经 `useThreadSession.sendMessage(message, mode)` 透传为 `mode`；确认当前 `sendMessage` 调用已传 `mode`
  （如未传，补上 `selectedMode` 状态）。保持 fast/thorough 现网路径不受影响。

== 红线 ==
- **只动前端**；后端 resolve/adopt/cancel/audit/stream 一律不碰（G4-3.x 零回退）。
- fast / thorough SSE 与渲染**零回归**（仅新增 approval_required 分支，不误伤既有事件）。
- Member **不暴露采纳钮**：靠 SSE `can_adopt=false` 隐藏，而非靠点下后吃 403；403 仅作兜底友好提示。
- `draft_preview` 仅展示后端已截断预览；前端**不另行拉草稿全文**，更不写进非必要状态。
- 审计钩子不动、出参零回退。
- 不动 G4-4 之外的任何窗口（G4-5 前端测试/A 层验收留待下一窗）。

== 测试约定（前端）==
- `npm run build` 必须绿（G4-4.1 验收硬指标）。
- 组件单测（vitest，沿用 `*.test.ts` 体系）新增 `src/components/chat/ApprovalCard.test.tsx`：
  - `can_adopt=true` 渲染双钮；点击采纳 → 调 `resolveApproval(adopt)` 且卡片转「已采纳」+ 显示 `_v2` 文件名。
  - `can_adopt=false` 无采纳钮 + 说明文案。
  - `status="adopted"/"cancelled"` 灰显终态。
  - 重复采纳（mock 409）→ 友好提示不崩；Member 撤他人（mock 403）→ 兜底提示。
- 后端基线**不动**：`tests/test_agent_*.py`（排除 golden）仍 157 passed + `test_agent_audit.py` 绿，作为回归护城河。

== 验收 ==
- `npm run build` 绿；`AgentModeSwitcher` 三档（快速/精准/编辑）可见，含 Member 可切编辑。
- 编辑模式 SSE 收到 `approval_required` → `ApprovalCard` 渲染草稿预览 + citation chips。
- Admin/可写：点采纳 → `resolveApproval(adopt)` → 卡片变「已采纳」且显示实际落库文件名（`_v2` 反映）；后端 200+`processing`（既有）。
- 点取消 → `resolveApproval(cancel)` → 卡片变「已取消」。
- Member/不可写：无采纳钮 + 说明文案（G4-E2）；万一越权点下 → 403 兜底友好提示。
- 重复采纳/取消 → 409 友好提示，不崩（G4-E3/E5）。
- 发送中切模式 → Abort SSE（G4-E13）。
- F5 刷新 → 卡片终态保留（G4-E18）。
- 无命中 → 无 `approval_required`，走 `refusal` 拒答（G4-E11）。
- fast / thorough SSE 语义零回归；后端 157 + audit 测试仍绿（零改动）。
- 计划文档 `discovery-agent-g4-write-plan.md` 顶部状态行 + §9 G4-4.1/G4-4.2/G4-4.3 行标 ✅，
  新增 §14.7 验证记录。下一窗 G4-4 完成 → 进入 **G4-5**（前端测试固化 + A 层验收）。

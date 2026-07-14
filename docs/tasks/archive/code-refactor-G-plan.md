# code-refactor-G · Plan — AskPage + ChatPage 提取共享组件

> **父 SPEC**：`docs/tasks/code-refactor-spec.md`  
> **风险**：中  
> **预计改动**：5 个文件（2 新建 + 3 修改），约 −100 行净缩减  
> **基线**：`npm run build` ✅（开工前确认）

---

## §0 · 做什么 / 不做什么

### 做

| # | 内容 |
|---|------|
| G-1 | 提取共享 hook `useChatPageHandlers.ts`：`AskPage`/`ChatPage` 中 7 组 **完全相同的 handler** 移入共享 hook |
| G-2 | 提取共享组件 `ChatPageShell.tsx`：`ThreadListPanel` + `AgentModeSwitcher`/`AgentBudgetChip` + `ChatMessageList` + `ChatInput` 的组装结构；以 `toolbar` slot 承载两页不同的顶栏 |
| G-3 | 改造 `AskPage.tsx`：删除 7 个 handler 的内联定义 + 提取出的 JSX 布局 → 使用 `useChatPageHandlers` + `ChatPageShell`，保留 `hasVisibleKbs` 守卫、`kbCheckError` 横幅、`UnassignedDepartmentBanner` 等 AskPage 独有内容 |
| G-4 | 改造 `ChatPage.tsx`：同上改造，保留 `ChatToolbar` 使用、`subtitle` 等 ChatPage 独有内容 |

### 不做

- ❌ 不改业务行为（handler 逻辑零修改）
- ❌ 不改 API / 路由 / `useThreadSession` 签名
- ❌ 不改 `ChatInput` / `ChatMessageList` / `AgentModeSwitcher` / `ThreadListPanel` 等子组件
- ❌ 不改 CSS 类名（`ask-chat-layout` / `ask-chat-main` / `ask-thread-panel` / `chat-thread-panel`）
- ❌ 不改 `ChatToolbar` 组件
- ❌ 不改变循环依赖 / import 链
- ❌ 不新增第三方依赖

---

## §1 · 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `frontend/src/lib/use-chat-page-handlers.ts` | **create** | 共享 hook：封装 7 个 handler + `scrollToBottom` + `threadPanelCollapsed` 状态 + Escape key useEffect |
| `frontend/src/components/chat/ChatPageShell.tsx` | **create** | 共享布局组件：`ask-chat-layout` 结构，含 ThreadListPanel + AgentModeBar + 内容区 + ChatInput |
| `frontend/src/pages/AskPage.tsx` | **modify** | 改用 `useChatPageHandlers` + `ChatPageShell`，保留 `hasVisibleKbs`/`kbCheckError`/`UnassignedDepartmentBanner` 独有逻辑 |
| `frontend/src/pages/ChatPage.tsx` | **modify** | 改用 `useChatPageHandlers` + `ChatPageShell`，保留 `ChatToolbar`/`subtitle`/KB loading 等独有逻辑 |
| `frontend/src/components/chat/ChatPageShellSkeleton.tsx` | **modify** | 可选：更新 docstring 注释（如果有引用旧说法） |

---

## §2 · 变更步骤（按序执行）

### Step 1 — 创建 `useChatPageHandlers.ts`

路径：`frontend/src/lib/use-chat-page-handlers.ts`

**输入**：从 `useThreadSession` 萃取以下回调 + 页面级守卫参数

```typescript
interface UseChatPageHandlersProps {
  // From useThreadSession
  abortStreaming: () => string | null;
  abortForModeSwitch: () => string | null;
  createNewThread: () => Promise<ChatThread>;
  selectThread: (id: string) => void;
  archiveThread: (id: string) => Promise<void>;
  sendMessage: (msg: string, mode: AgentMode) => Promise<void>;
  resolveApproval: (id: string, action: "adopt" | "cancel") => Promise<void>;

  // Page-specific guards
  canSend?: boolean;           // ChatPage: teamBusinessAllowed; AskPage: teamBusinessAllowed && hasVisibleKbs
  agentMode: AgentMode;
  setAgentMode: (mode: AgentMode) => void;
  isMobile: boolean;
}
```

**输出返回**：

```typescript
{
  // States
  threadPanelCollapsed: boolean;
  setThreadPanelCollapsed: (v: boolean) => void;
  creatingThread: boolean;
  archivingThreadId: string | null;
  draftRestore: ChatInputDraftRestore | undefined;

  // Scroll ref
  scrollRef: RefObject<HTMLDivElement>;
  scrollToBottom: () => void;

  // Handlers
  handleAgentModeChange: (mode: AgentMode) => void;
  handleCreateThread: () => Promise<void>;
  handleNewChat: () => void;
  handleSelectThread: (threadId: string) => void;
  handleArchiveThread: (threadId: string) => Promise<void>;
  handleSend: (message: string) => void;
  handleAdoptApproval: (messageIndex: number, approvalId: string) => void;
  handleCancelApproval: (messageIndex: number, approvalId: string) => void;
  handleDismissThreadPanel: () => void;
}
```

**内联 useEffects**：
- `useEffect` 初始化 `threadPanelCollapsed = isMobile`
- `useEffect` Escape key → collapse 面板
- `useEffect` cleanup 无（caller 自己管理 `abortStreaming`）

**`handleSend` 逻辑**：
- 如果 `canSend === false` → 直接 return
- 否则 `abortStreaming(); sendMessage(message, agentMode);`

### Step 2 — 创建 `ChatPageShell.tsx`

路径：`frontend/src/components/chat/ChatPageShell.tsx`

**Props**：

```typescript
interface ChatPageShellProps {
  // Thread panel
  threadPanelCollapsed: boolean;
  threadPanelClassName: string;              // "ask-thread-panel" | "chat-thread-panel"
  threadPanelSubtitle?: string;
  onDismissThreadPanel: () => void;

  // ThreadListPanel data
  threads: ChatThread[];
  activeThreadId: string | null;
  threadsLoading: boolean;
  threadsError: string | null;
  creatingThread: boolean;
  archivingThreadId: string | null;
  onSelectThread: (id: string) => void;
  onCreateThread: () => void;
  onArchiveThread: (id: string) => void;
  onRetryThreads: () => void;

  // Toolbar slot (the main difference between AskPage and ChatPage)
  toolbar: ReactNode;

  // Agent mode
  agentMode: AgentMode;
  agentBudget: AgentBudgetState | null;
  onAgentModeChange: (mode: AgentMode) => void;

  // Chat content
  messages: ChatMessage[];
  historyLoading: boolean;
  historyError: string | null;
  streamError: string | null;
  streaming: boolean;
  toolSteps: ToolTimelineStep[];
  activeThreadId: string | null;

  // ChatMessageList
  chatMessageListKbId: string;
  citationMode?: CitationLabelMode;
  onToggleCitation: (msgIdx: number, citIdx: number) => void;
  onAdoptApproval?: (msgIdx: number, approvalId: string) => void;
  onCancelApproval?: (msgIdx: number, approvalId: string) => void;
  resolvingApprovalId: string | null;
  approvalError: string | null;

  // ChatInput
  chatInputDisabled: boolean;
  chatInputPlaceholder?: string;
  draftRestore: ChatInputDraftRestore | undefined;
  onSendMessage: (msg: string) => void;

  // Scroll ref
  scrollRef: RefObject<HTMLDivElement>;

  // Optional extra banner after toolbar
  children?: ReactNode;  // For AskPage's UnassignedDepartmentBanner + kbCheckError
}
```

**内部结构**（将当前 AskPage/ChatPage 共享的 JSX 结构移入）：

```tsx
<div className="-m-6 flex h-[calc(100vh-3.25rem)] flex-col overflow-hidden">
  <div className="ask-chat-layout">
    {/* Backdrop */}
    <div className={cn("thread-list-drawer-backdrop", !threadPanelCollapsed && "open")} .../>
    
    {/* Thread panel */}
    <ThreadListPanel className={cn("thread-list-panel", threadPanelClassName, ...)} .../>
    
    {/* Main area */}
    <div className="ask-chat-main">
      {/* Toolbar slot */}
      {toolbar}
      
      {/* Agent mode bar */}
      <div className="agent-mode-bar">
        <AgentModeSwitcher .../>
        <AgentBudgetChip .../>
      </div>
      
      {/* Extra children (banners, etc.) */}
      {children}
      
      {/* Chat content */}
      <div ref={scrollRef} className="chat-scroll">
        <div className="chat-inner">
          {/* History error */}
          {/* Stream error */}
          {/* Loading / ChatMessageList + ToolTimeline */}
        </div>
      </div>
      
      {/* Chat input */}
      <ChatInput .../>
    </div>
  </div>
</div>
```

### Step 3 — 改造 `AskPage.tsx`

保留：
- `checkVisibleKbs` / `kbLoading` / `hasVisibleKbs` / `kbCheckError`
- `hasVisibleKbs` 守卫 → `EmptyStateV44`
- `kbCheckError` → `AlertBanner`
- `UnassignedDepartmentBanner`
- `useEffect` for quick question (`?q=`)
- `useEffect` for title + breadcrumb

删除并替换为 `useChatPageHandlers` + `ChatPageShell`：
- 7 个 handler 定义
- `scrollToBottom`
- `threadPanelCollapsed` 状态
- `creatingThread` / `archivingThreadId` / `draftRestore` 状态
- `scrollRef`
- `useEffect` for scrollToBottom / Escape key
- 整个 `<ThreadListPanel>` + `<AgentModeSwitcher>` + `<ChatMessageList>` + `<ChatInput>` 的 JSX 结构

`ChatPageShell` 的 `toolbar` slot 中传入 **内联 toolbar JSX**（当前 AskPage 行 287–327 的内容）。

`canSend` = `teamBusinessAllowed && hasVisibleKbs`

`chatMessageListKbId` = `""`, `citationMode` = `"workspace"`

### Step 4 — 改造 `ChatPage.tsx`

保留：
- `loadPage` / `kb` / `loading` / `error` 状态
- `<ChatToolbar>` 组件（传入 `toolbar` slot）
- `useEffect` for quick question
- `useEffect` for title + breadcrumb + cleanup
- `!id` / `loading` / `error` early return guards

删除并替换（同 Step 3）+ 传入：
- `threadPanelClassName` = `"chat-thread-panel"`
- `threadPanelSubtitle` = `"本资料库 · 仅自己可见"`
- `toolbar` = `<ChatToolbar .../>`
- `canSend` = `teamBusinessAllowed`
- `chatMessageListKbId` = `id`
- `citationMode` 不传（默认 `"kb"`）

---

## §3 · 边界 & 异常

| 场景 | 处理 |
|------|------|
| `canSend` 为 `false`（AskPage: 无可见 KB） | `handleSend` 直接 return；`ChatInput` 通过 `chatInputDisabled` + 占位符提示 |
| ChatPage `!id` | 仍由 `ChatPage` 自身处理（early return `AlertBanner`），不进入 `ChatPageShell` |
| ChatPage `loading` / `error` | 仍由 `ChatPage` 自身处理 skeleton/error，不进入 `ChatPageShell` |
| AskPage `kbLoading` | 仍由 `AskPage` 自身处理 skeleton，不进入 `ChatPageShell` |
| 空消息列表 | `ChatMessageList` 内部已有空态处理，不影响 |
| Module not found | 所有 import 使用 `@/` alias，与项目一致 |

**为什么保留早期 return guards 在 `AskPage`/`ChatPage` 中**：因为 skeleton 和 error 页不需要进入共享布局（它们本身就是全屏替代 UI），将条件外置保持 `ChatPageShell` 简单。

---

## §4 · 验收门禁（本窗专用）

```text
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — code-refactor-G      │
│            ┃   ┃                                    │
│            ┗━━━┛                                    │
│                                                     │
│  ▢ 仅改 SPEC 约定的 4–5 个文件                       │
│  ▢ npm run build 绿                                  │
│  ▢ 不改业务行为（比较 handler 逻辑前后一致）           │
│  ▢ 不改 API 签名                                     │
│  ▢ 不改 DB schema / migration                       │
│  ▢ 不改 AGENTS.md / PRD / TECH                      │
│  ▢ AskPage 和 ChatPage 对话流程正常                   │
│  ▢ 删除本 plan 文件                                   │
│                                                     │
│  回退：git checkout -- frontend/src/pages/AskPage.tsx │
│         frontend/src/pages/ChatPage.tsx              │
│         frontend/src/lib/use-chat-page-handlers.ts   │
│         frontend/src/components/chat/ChatPageShell.tsx│
│                                                     │
│  ── 验收人签名：___________  日期：___________  ──  │
└─────────────────────────────────────────────────────┘
```

---

## §5 · 回退指令

```powershell
git checkout -- `
  frontend/src/pages/AskPage.tsx `
  frontend/src/pages/ChatPage.tsx `
  frontend/src/lib/use-chat-page-handlers.ts `
  frontend/src/components/chat/ChatPageShell.tsx
```

删除多余文件：
```powershell
Remove-Item frontend/src/lib/use-chat-page-handlers.ts
Remove-Item frontend/src/components/chat/ChatPageShell.tsx
```

---

## §6 · 预估行数变化

| 文件 | 原行数 | 目标行数 | 变化 |
|------|--------|----------|------|
| `use-chat-page-handlers.ts` | 0 | ~90 | +90 (new) |
| `ChatPageShell.tsx` | 0 | ~180 | +180 (new) |
| `AskPage.tsx` | 450 | ~260 | −190 |
| `ChatPage.tsx` | 412 | ~230 | −182 |
| **合计** | **862** | **~760** | **−102** |

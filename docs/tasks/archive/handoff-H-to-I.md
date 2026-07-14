# 知岸 — 交接文档：Task H → Task I

> **生成时间**：2026-07-14  
> **当前任务**：`code-refactor-H` ✅ 已完成  
> **下一任务**：`code-refactor-I` — `use-ask-session` + `use-chat-session` 合并

---

## 项目概况

- **产品名**：知岸（企业级知识库 RAG）
- **技术栈**：FastAPI + PostgreSQL/pgvector（后端） · React + TypeScript + Vite（前端） · Docker Compose（部署）
- **前端重构总纲**：`docs/tasks/code-refactor-spec.md`
- **架构基线文档**：`docs/TECH.md` · `docs/PRD.md`
- **当前进展**：P2 前端舟山 — Task G ✅ → **Task H ✅ → Task I（进行中）** → J → K → L → M

## Task H 完成内容

将 `frontend/src/lib/use-thread-session.ts`（517 行）拆分为 4 个文件：

| 文件 | 行数 | 职责 |
|------|------|------|
| `use-thread-list.ts` | 107 | 线程 CRUD：`loadThreads`/`selectThread`/`resetActiveChat`/`createNewThread`/`renameThread`/`archiveThread` |
| `use-message-stream.ts` | 325 | 流式发送/接收：`sendMessage`/`loadMessages`/`abortStreaming`/`toggleCitation` + 所有 refs |
| `use-approval-resolver.ts` | 50 | 审核生命周期：`resolveApproval` |
| `use-thread-session.ts` | 93 | 合成面 facade：持有共享 state（activeThreadId/threads/messages），调用 3 子 hook，返回 25 字段 |

**关键架构决策**：

1. **合成面（facade）模式** — `use-thread-session.ts` 保留为导出入口，AskPage/ChatPage 的 `import { useThreadSession }` 不变
2. **共享状态上提** — `activeThreadId`、`threads`、`messages` 由合成面持有
3. **逐一传参** — 子 hook 不接受 `deps` 对象（避免 unstable reference 导致无限 re-render），而是接收单个稳定值（`useState` setter、`useCallback` 结果）
4. **布线顺序** — `useMessageStream` 先调用，因为 `useThreadList` 需要 `ms.abortStreaming`

## 坑区

1. **deps 对象导致无限 re-render**：`useMessageStream(context, { activeThreadId, ... })` 每次 render 创建新对象 → 子 hook 全部 useCallback 重创 → useEffect 重跑 → 死循环。**修复**：改为 `useMessageStream(context, setActiveThreadId, activeThreadIdRef, ...)` 逐一传参。
2. **npm run build 硬门禁**：任何前端改动后必须跑 `npm run build`（tsc + vite build），不能只看 tsc
3. **Docker web rebuild**：改前端文件后，`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d web` 才能生效（`docker compose build web` 后也必须 `up -d web`）

## 准备 Task I — use-ask-session + use-chat-session 合并

### 背景

- `use-ask-session.ts`（~198 行）和 `use-chat-session.ts`（~199 行）是两个 86% 相似的 hook
- 目前 AskPage 和 ChatPage 都直接使用 `use-thread-session`（Task H 产物），不再引用这两个 session hook？
- **需要先调研**：这两个文件是否仍被引用，还是 Task G/H 已经让它们成为 dead code

### 调研路线

```powershell
# 检查两个 session hook 的引用
Select-String "use-ask-session|use-chat-session" frontend/src/**/*.ts frontend/src/**/*.tsx

# 如果零引用 → 直接删除 + 清理 import
# 如果还有引用 → 提取共享基类 useSessionBase
```

### 判定逻辑

- 如果 Task H 完成后 `use-ask-session` 和 `use-chat-session` 不再被任何文件引用 → **直接删除**，AskPage/ChatPage 统一用 `use-thread-session`
- 如果还有差异 → 提取共享基类 `useSessionBase`，两个 hook 继承它

### 验收标准

- `npm run build` 绿
- AskPage/ChatPage 对话框功能正常
- 不改业务行为

## 参考文档

| 文档 | 路径 |
|------|------|
| 前端重构总纲 | `docs/tasks/code-refactor-spec.md` |
| 交接上下文 | `docs/tasks/handoff-frontend-refactor.md` |
| 项目管理 | 根目录 `AGENTS.md` |
| 踩坑合集 | 根目录 `AGENTS.md` 踩坑区 |
| UI 设计 | `docs/DESIGN.md` |
| 产品需求 | `docs/PRD.md` |

---

*— handoff 完 —*

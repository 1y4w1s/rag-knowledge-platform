# 知岸代码质量修复 — SPEC 总纲

> **状态**：📋 计划稿（等待用户确认）  
> **来源**：`docs/tasks/code-refactor-spec.md` · 代码评审见 `AGENTS.md` 踩坑区 + 评审会话  
> **父级**：无（独立工程任务链）  
> **范围**：全栈代码重构（后端 API/Service/Test + 前端 Page/Hook/Component）  
> **工期**：原子任务一次一条，每条单开对话，不混窗

---

## §0 · 做 & 不做

### 做

| 域 | 内容 |
|----|------|
| 后端 | `retrieval.py` / `retrieval_workspace.py` 合并、`thread_persistence.py` KB/Workspace CRUD 合并、`persistence.py` 保存回合合并、API 层引用富化循环提取共享函数、服务层 `HTTPException` 替换为领域异常 |
| 前端 | `AskPage` + `ChatPage` 提取共享组件/hook、`use-thread-session.ts` 拆分、`use-ask-session` + `use-chat-session` 合并、**28-prop 钻取传对象 ✅**、`chat-api.ts` 加 Zod 运行时校验、`EmptyStateV44.tsx` 文件拆分、`scenes.tsx` 工厂化 |
| 测试 | `test_org_isolation.py` ✅ F1 / `test_organization_members.py` ✅ F2 / `test_audit_events.py` ✅ F3 按场景拆分文件、`conftest.py` 移除 test-file-as-plugin |
| 品质 | 每任务发布前跑 pytest A 层 + 对应 test_* 回归 + 前端 `npm run build` |

### 先修 BUG（P0 级，优先于所有重构）

| # | 问题 | 位置 | 修复方式 |
|---|------|------|----------|
| B1 | `KnowledgeBaseResponse` 有 `updated_at` 但 `KnowledgeBase` 模型无此列 | `schemas/knowledge_base.py:28` vs `models/knowledge_base.py:43-45` | 模型加列 + alembic migration 025 ✅ |
| B2 | `Document.uploaded_by` 类型 `Mapped[uuid.UUID]`（非可选）与 `nullable=True` 矛盾 | `models/document.py:43-47` | 已修复：`Mapped[uuid.UUID \| None]` ✅ |

### 不做（本轮）

- 不改 `ingestion/` 层（已经干净）
- 不改 `models/` 和 `core/`（无问题）
- 不改业务逻辑/行为/API 契约
- 不改数据库迁移（B1 的 migration 除外——如果选加列方案）
- 不改 Docker/npm 依赖
- 不改 AGENTS.md / PRD / TECH（除非接口签名变了——大概率不）
- 不新增/删除功能

### 核心原则

1. **纯重构**：每条原子任务不改变对外行为（API 响应、前端渲染、用户流程）
2. **一次一条**：每条任务必须开新对话；禁止在同一个对话里做两条
3. **先计划再动**：每条任务动工前，AI 输出 `docs/tasks/code-refactor-{序号}-plan.md`（本 SPEC 的子 plan），你审批通过后再开 I 窗
4. **验收强门禁**：见 §4

---

## §1 · 修复策略总览

```
P0 先修 BUG —— 最优先，改完才能动重构
  ├─ B1. ✅ KnowledgeBaseResponse.updated_at 模型无此列（模型加列 + alembic migration 025）
  └─ B2. ✅ Document.uploaded_by 类型标注与 nullable 矛盾（已修复：模型为 Mapped[uuid.UUID | None]）

P1 架构舟山 —— AI plan + implement，每条一窗
  ├─ A. ✅ retrieval.py + retrieval_workspace.py 合并（已完成）
  ├─ B. ✅ thread_persistence.py KB/Workspace CRUD 合并（已完成：6 组已合并 + 旧双份函数清除）
  ├─ C. ✅ persistence.py save_kb/workspace_chat_turn 合并（已完成：_save_turn 共享 helper）
  ├─ D. ✅ API 层引用富化循环 × 4 文件提取共享函数（已完成）
  ├─ E. ✅ 服务层 HTTPException → 领域异常（Phase 1 ✅ + Phase 2 ✅ + Phase 3 ✅）
  ├─ F1. ✅ test_org_isolation.py 拆分（已删除的文件，清理残留 import 断链）
  ├─ F2. ✅ test_organization_members.py 拆分（已完成：4 文件 + fixture）
  └─ F3. ✅ test_audit_events.py 拆分（已完成：4 文件 + fixture）

P2 前端舟山 —— 每条一窗
  ├─ G. ✅ AskPage + ChatPage 提取共享组件（已完成：useChatPageHandlers + ChatPageShell）
  ├─ H. ✅ use-thread-session.ts 拆分为 3 个子 hook（已完成：useThreadList + useMessageStream + useApprovalResolver + 合成面 facade）
  ├─ I. ✅ use-ask-session + use-chat-session 合并（已完成：直接删除，零引用 dead code）
  ├─ J. ✅ 28-prop 钻取 → 传对象（已完成：ChatPageShell 39 flat props → 5 分组对象 + 4 flat props）
  ├─ K. ✅ chat-api.ts Zod 运行时校验（已完成：chat-schemas.ts + safeParse/parse + 30 测试）
  ├─ L. ✅ EmptyStateV44.tsx 文件拆分
  └─ M. ✅ scenes.tsx 工厂化（已完成：createScene 工厂函数 + 移除 7 处重复 inviteRoles）

P3 清理 —— 可批量
  └─ N. ✅ 空行/导入风格/SSE 标头常量/docstring 统一（已完成：api-error.ts import 顺序 · 后端 docstring 已修复）
```

**建议开工顺序**：~~B1~~/~~B2~~（BUG 均已修复）→ ~~D~~ → ~~C~~ → ~~B~~ → ~~A~~ → ~~E-Phase1~~/~~E-Phase2~~/~~E-Phase3~~ → ~~F~~（G～M 前端重构）→ N

原因：B1/B2/A/B/C/D/E/F 已完成（F1/F2/F3 测试拆分均已完工）；**G～M 前端重构** 下一项。

---

## §2 · 原子任务 SPEC（输入 / 输出 / 边界 / 异常）

每条任务的 SPEC 格式固定如下节所示，**动工前 AI 必须写出该子 plan** 才能动代码。

---

### 任务 D · API 层引用富化循环合并

> **代号**：`code-refactor-D`  
> **依赖**：无  
> **风险**：低（纯提取+替换，不改变返回结构）  
> **改动文件**：4 个 API 文件 + 1 个新建共享文件

#### D-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `backend/app/api/chat.py` 行 117–149、`kb_threads.py` 行 359–391、`ask.py` 行 96–133、`ask_threads.py` 行 347–386 中分别内联的引用富化循环 |
| **输出** | 一个可复用的 `build_chat_message_list(db, rows, kb_visible_fn, ...) → list[ChatMessageResponse]` 函数，存放在 `backend/app/services/rag/message_builder.py` |
| **行为** | 从 4 个 API 文件中删除对应循环，替换为调用上述共享函数 |
| **边界条件** | ① `rows` 为空列表 → 返回空列表 ② `kb_visible_fn` 返回 False → 对应消息的 citations 设为空列表 ③ `citations` 为 None → 保留 None ④ SSE 标头（`Cache-Control` / `Connection` / `X-Accel-Buffering`）作为模块级常量统一导出 |
| **异常处理** | ① `EnrichError`（原 `enrich_history_citation_payload` 抛的异常）不捕获，透传给 caller ② `kb_visible_fn` 抛异常 → 向上传播，不吞没 ③ 不改变原有 404/403 行为 |
| **验证标准** | ① `pytest tests/test_chat.py tests/test_kb_threads.py tests/test_ask_chat.py tests/test_ask_threads.py -q` 全部通过 ② CI 不新增失败 ③ SSE 标头 4 文件一致 |
| **强门禁** | 验收通过后关窗；下一条必须 **新对话** |

---

### 任务 C · persistence.py 保存回合合并

> **代号**：`code-refactor-C`  
> **依赖**：无（可与 D 并行）  
> **风险**：低（内部重构，不改变 `save_chat_turn` / `save_kb_chat_turn` 签名）

#### C-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `backend/app/services/rag/persistence.py` `save_kb_chat_turn`（行 29–85）+ `save_workspace_chat_turn`（行 88–153）两段 86% 相同的代码 |
| **输出** | 一个 `_save_turn(db, *, thread, common, user_content, assistant_content, citations, assistant_id, retrieval_duration_ms)` 私有 helper；`save_kb_chat_turn` 和 `save_workspace_chat_turn` 分别构造 `common` dict 后调用它 |
| **行为** | 保存回合的逻辑只在一处，不再复制 |
| **边界条件** | ① `citations` 为空列表 → 正常保存 ② `assistant_message_id` 为 None → 内部用 `uuid.uuid4()` ③ `retrieval_duration_ms` 为 None → `ChatMessage.retrieval_duration_ms` 存 None |
| **异常处理** | 保持原有异常行为不变（`IntegrityError` 等由外层 commit 处理） |
| **验证标准** | ① `pytest tests/test_chat.py tests/test_chat_messages.py -q` 全绿 ② 发一条对话看数据库 `chat_messages` 表字段正确 |
| **强门禁** | 本条任务只改 `persistence.py` 一个文件 | **验证通过后关窗开新窗**

---

### 任务 B · thread_persistence.py CRUD 合并

> **代号**：`code-refactor-B`  
> **依赖**：无  
> **风险**：中（515 行文件，6 组 CRUD 对，引用方多）

#### B-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `backend/app/services/rag/thread_persistence.py` 中 6 组 KB/Workspace 双份 CRUD 函数 |
| **输出** | 用 `thread_kind` 参数化的单一 CRUD 函数代替每组双份 |
| **行为** | `get_or_create_active_thread`（合并 `get_or_create_active_kb_thread` + `get_or_create_active_workspace_thread`）接收 `thread_kind` + 可选参数；其他 5 组同类合并 |
| **边界条件** | ① `thread_kind=knowledge_base` 时 `kb_id` 必传 ② `thread_kind=workspace` 时 `workspace_kind`/`workspace_org_id`/`department_key` 必传组 ③ 参数不满足 → 函数签名的类型系统保证（**不在运行时加 assert**） |
| **异常处理** | 函数不自己 `raise`，让不合法参数经由 `Optional` → SQL 查询过滤自然返回空 |
| **验证标准** | ① `pytest tests/test_thread_persistence.py tests/test_kb_threads.py tests/test_ask_threads.py -q` 全绿 ② `pytest tests/test_chat.py tests/test_chat_messages.py` 全绿 |
| **强门禁** | 改动 1 个文件（`thread_persistence.py`）**禁止**顺手修其他问题 |

---

### 任务 A · retrieval.py / retrieval_workspace.py 合并

> **代号**：`code-refactor-A`  
> **依赖**：建议在 C/D 之后（先建立重构节奏）  
> **风险**：**高**（检索核心，改动触达 chat/search/agent 多个模块）

#### A-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `backend/app/services/rag/retrieval.py`（277行）+ `retrieval_workspace.py`（275行） |
| **输出** | 单一 `retrieval.py`，`retrieval_workspace.py` 删除（所有 import 切换到新 `retrieval.py`） |
| **行为** | 核心检索函数接受 `org_scope: OrgScope | None` 参数：`None`=单 KB 检索，`Some`=跨 KB 检索；`diversity` 和 `kb_name` 字段根据 scope 存在性动态选择 |
| **边界条件** | ① `org_scope` 为 None 且 `kb_id` 为 None → TypeError（参数不合法）② 工作区检索结果多 `kb_name` 字段 → 调用方不崩（`RetrievedChunk` 已有该字段）③ `apply_kb_diversity` 仅当 `org_scope` 非 None 时调用 |
| **异常处理** | 保持所有异常行为不变（嵌入失败 → 降级为纯 FTS、rerank 失败 → 返回未 rerank 结果） |
| **验证标准** | **强制性**：① `pytest tests/test_retrieval_golden.py -v` **12/12 Hit@3 gate**（见 AGENTS.md 验收口径 R5-2）② `pytest tests/test_retrieval_hybrid.py tests/test_retrieval_security.py tests/test_retrieval_workspace.py -q` 全绿 ③ 人工抽测 2～3 条检索题（R5-3） |
| **强门禁** | ❗ **本条是最高风险任务**—— `pytest` 全绿后**必须人工验收**（打开浏览器，在资料库内对话和在 workspace 对话各发一条，看检索结果是否正确）。验收后关窗开新窗。 |

---

### 任务 G · AskPage + ChatPage 提取共享组件

> **代号**：`code-refactor-G`  
> **依赖**：建议在 H/I 之前（先做好底层的 hook 才能让页面干净）  
> **风险**：中（涉及前端路由和页面结构）

#### G-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `frontend/src/pages/AskPage.tsx`（14.5K）+ `ChatPage.tsx`（12.9K）中 7 个重复的 handler 函数 + 约 70% 相同的 JSX 布局 |
| **输出** | 一个共享 hook `useChatPageHandlers.ts`（包含 7 个 handler）+ 一个共享组件 `ChatPageShell.tsx`（包含 ThreadListPanel + ChatMessageList + ChatInput + AgentModeSwitcher 的组装） |
| **行为** | `AskPage` 和 `ChatPage` 各约 40% 行数删减；两者行为完全不变 |
| **边界条件** | ① AskPage 多出的 `hasVisibleKbs` guard 保留在 AskPage 中传入 ② 两页的 breadcrumb 路径不同 → 通过 props 或 children 传入 ③ 两页的 agent mode 默认值不同 → 在 handler 中通过参数区分 |
| **异常处理** | 所有 handler 的错误处理逻辑（`try/catch`、`toast`）保持不变，仅移动到共享 hook 中 |
| **验证标准** | ① `npm run build` 绿 ✅ ② 在浏览器操作 AskPage 和 ChatPage 各 3 条对话（新建 → 发消息 → 删线程 → 切换模式），功能正常 |
| **强门禁** | 前端改动后 `npm run build` 必须绿，**docker compose build web** 也必须绿 |
| **状态** | ✅ 已完成（2026-07-13） |

---

### 任务 H · use-thread-session.ts 拆分 ✅ 已完成

> **代号**：`code-refactor-H`  
> **依赖**：无  
> **风险**：中（该 hook 被 AskPage 和 ChatPage 同时使用）
> **状态**：✅ 2026-07-14 完成

#### H-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `frontend/src/lib/use-thread-session.ts`（509行） |
| **输出** | 3 个 hook：`useThreadList`（线程 CRUD + 列表管理）、`useMessageStream`（流式发送/接收）、`useApprovalResolver`（审核生命周期）；`use-thread-session.ts` 保留为导出合成面（import 3 个子 hook 组合为与原签名一致的 hook） |
| **行为** | 对外接口（`{ threads, activeThreadId, sendMessage, ... }`）完全不变，调用方（`AskPage`、`ChatPage`）不需要改任何 import |
| **边界条件** | ① `sendMessage` 必须在 `useMessageStream` 中 ② 线程列表状态在 `useThreadList` 中 ③ 审核批准在 `useApprovalResolver` 中 ④ 三个 hook 通过参数共享 `activeThreadId`（由父级或 context 传递） |
| **异常处理** | 保持所有回滚逻辑（`rollbackInFlightMessages`）完整迁移 |
| **验证标准** | ① `npm run build` 绿 ✅ ② `AskPage` 和 `ChatPage` 各自的对话流程完整测试（新建→发消息→切换线程→中止→滚动→引用预览→审核操作）③ `pytest` 不相关 |
| **强门禁** | **不准**在拆分的同时修行为；拆分后文件总行数应约等于拆分前 509 行（+ 少量导入/导出胶水）|

#### H-2 · 事后修复

| 项 | 内容 |
|----|------|
| **R1** | 初期 `deps` 对象每次 render 新引用 → 子 hook 全部 `useCallback` 重创 → `useEffect` 无限重跑。修复：改为逐一传参，利用 React 的 `useState` setter 稳定引用特性 |
| **R2** | `useMessageStream` 签名去掉 `messages`/`activeThreadId` pass-through 参数，由合成面直接返回 |
| **验证** | `npm run build` ✅ · 用户确认对话框功能正常 |

---

### 任务 I · use-ask-session + use-chat-session 合并

> **代号**：`code-refactor-I`  
> **依赖**：建议在 H 之后  
> **风险**：低（两个 hook 结构相同，合并后不改变调用方）

#### I-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `frontend/src/lib/use-ask-session.ts`（~198行）+ `use-chat-session.ts`（~199行） |
| **输出** | `use-thread-session.ts` 已包含的能力...（如果 H 完成后发现这两个 session hook 是 H 的子集，则直接删除，改 AskPage/ChatPage 统一用 `use-thread-session`；如果还有差异，提取共享基类 `useSessionBase`） |
| **行为** | 两个 hook 统一为同一个实现 |
| **边界条件** | 略（动工时 AI 输出完整 SPEC） |
| **验证标准** | `npm run build` 绿 + AskPage/ChatPage 对话可用 |
| **强门禁** | I 和 G 可能相互依赖，AI 必须在 plan 中说明执行顺序 |

---

### 任务 E · 服务层 HTTPException → 领域异常

> **代号**：`code-refactor-E`  
> **依赖**：无  
> **风险**：高（24 个文件，约 113 处 raise）

#### E-1 · SPEC（阶段一：异常类 + 映射器） ✅ Phase 1 已完成

#### E-2 · SPEC（阶段二：services/organization/） ✅ Phase 2 已完成

| 项 | 内容 |
|----|------|
| **输入** | `backend/app/services/organization/invites.py`、`members.py`、`settings.py` |
| **输出** | 3 个文件已使用领域异常（暂未发现 HTTPException）；清理死导入 `from fastapi import status` |
| **行为** | 删除 3 个文件中残留的未使用 `from fastapi import status` |
| **边界条件** | `services/organization/` 已在 Phase 1 或前置工作中全部替换为领域异常 |
| **异常处理** | 不涉及业务逻辑改动 |
| **验证标准** | `pytest tests/test_organization.py tests/test_invite_codes.py tests/test_org_member_*.py -q` 37 passed（1 预存 NameError 失败）|

#### E-3 · SPEC（阶段三：services/ 残余 HTTPException） ✅ Phase 3 已完成

| 项 | 内容 |
|----|------|
| **输入** | `services/account/settings.py`（10处）、`services/audit/query.py`（1处）、`services/org/scope.py`（6处）、`services/org/unit_members.py`（7处）、`services/org/units.py`（8处） |
| **输出** | 5 个文件共 32 处 `raise HTTPException` 全部替换为领域异常；导入清理 |
| **行为** | `400→ValidationError`、`401→UnauthorizedError`、`403→ForbiddenError`、`404→NotFoundError`、`409→ConflictError`、`422→ValidationError` |
| **边界条件** | `services/` 目录零残留 `raise HTTPException` |
| **异常处理** | 不涉及业务逻辑改动 |
| **验证标准** | `pytest tests/test_org_*.py -q` 55 passed（1 预存 NameError 失败）；`services/` 零残留 |
| **强门禁** | ✅ Phase 3 关窗 · 任务 E 全部完成

---

### 任务 F · 测试巨型文件拆分

> **代号**：`code-refactor-F`  
> **依赖**：无  
> **风险**：中（不影响生产代码，但 fixture 引用复杂）

#### F-1 · SPEC（子任务 F1：`test_org_isolation.py`）

| 项 | 内容 |
|----|------|
| **输入** | `backend/tests/test_org_isolation.py`（36,984 行） |
| **输出** | 5～8 个按场景拆分的文件：`test_org_visibility.py`、`test_org_grants.py`、`test_org_search_scope.py`、`test_org_chat_scope.py`、`test_org_messages_scope.py` |
| **行为** | 共享 fixture `OrgIsolationFixture` 提取到 `tests/fixtures/org_isolation.py`；每个场景文件只导入自己需要的 fixture |
| **边界条件** | ① 所有测试必须仍然找到一个 `_build_org_isolation_fixture` 的单一来源 ② `kwargs` 传参保持兼容 ③ `pytest_plugins` 不再引用本文件 |
| **例外处理** | fixture 失败 → 测试 skip（而非 silent pass） |
| **验证标准** | `pytest tests/ -q -k "org"` 与原全量运行对比，测试数一致 |
| **强门禁** | ❗ **必须删除 `conftest.py` 第 9 行 `pytest_plugins = ("tests.test_org_isolation",)`** 否则循环依赖未修复 |

#### F-2 · SPEC（子任务 F2：`test_organization_members.py`）✅ 已完成，见 `code-refactor-F-plan.md`

#### F-3 · SPEC（子任务 F3：`test_audit_events.py`）✅ 已完成，见 `code-refactor-F-plan.md`

---

### 任务 L · EmptyStateV44.tsx 文件拆分 ✅

> **代号**：`code-refactor-L`  
> **依赖**：无  
> **风险**：低（纯拆分，不改变行为）  
> **状态**：✅ 2026-07-14 完成

#### L-1 · SPEC

| 项 | 内容 |
|----|------|
| **输入** | `frontend/src/components/ui/EmptyState/EmptyStateV44.tsx`（408 行，含 HeroArt + Icon + EmptyStateV44 + InviteDialogProps + InviteDialog） |
| **输出** | 3 个文件：`HeroArt.tsx`（SVG 插画）、`InviteDialog.tsx`（邀请弹窗 + props 接口）、`EmptyStateV44.tsx`（Icon + 主组件，~226 行） |
| **行为** | `EmptyStateV44` 导出名不变；`index.ts`/`scenes.tsx` re-export 不变；所有调用方 `import { EmptyStateV44 } from "@/components/ui/EmptyState"` 不受影响 |
| **边界条件** | ① `HeroArt` 无 props，纯 SVG ② `InviteDialog` 接口签名未变 ③ `DEFAULT_INVITE_ROLES` 在 EmptyStateV44.tsx 用于 fallback、在 InviteDialog.tsx 用于 role-grid 过滤，各自独立 import |
| **异常处理** | 不涉及 |
| **验证标准** | ① `npm run build` 绿 ② `npx vitest run src/components/ui/EmptyState/EmptyStateV44.test.tsx` 3/3 green |

### 任务 J～M · 前端清理

（AI 动工时各自输出完整 SPEC，结构参照 D-1 的 SPEC 格式）

#### 共同验证标准

- `npm run build` 绿
- `docker compose build web && docker compose up -d web` 绿
- 浏览器操作相关页面 1～2 条用户流程正常

---

## §3 · 重构前后流程规范

```
┌─────────────────────────────────────────────────────────────┐
│                    整条修复工程全流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ① 基线规约（你确认本 SPEC 后，每窗开工前必须做）                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ a. 跑 `pytest tests/ -q` → 记录当前通过数（如 347+） │    │
│  │ b. 跑 `npm run build` → 记录构建成功                 │    │
│  │ c. 记录当前 git commit hash                          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ② 每原子任务一次对话                                           │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Step 1: 你告诉我「开工 task D」                       │    │
│  │ Step 2: AI 读相关文件 → 输出原子 plan（子 plan）       │    │
│  │ Step 3: 你审 plan（scope/风险/DoD）→ 批准 或 退回     │    │
│  │ Step 4: AI implement（改代码 → 跑门禁 → 签名）        │    │
│  │ Step 5: 你验收 / review 安全审查 → 关窗               │    │
│  │ Step 6: AI **同步 SPEC**（标记本任务 ✅，更新 §1 总览+开工顺序）│    │
│  │ → 同步后告知「已同步」后再关窗                          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ③ 质量门禁（每条任务都必须过）                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ ▢ 后端改动 → pytest 通过数不低于基线                   │    │
│  │ ▢ 前端改动 → npm run build 绿                        │    │
│  │ ▢ 不改公共 API 契约                                  │    │
│  │ ▢ 不改 DB migration                                 │    │
│  │ ▢ 不改业务行为                                       │    │
│  │ ▢ 不改 AGENTS.md/PRD/TECH（除非接口变——但本轮不应）   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ④ 安全审查（后端任务必做）                                      │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ ▢ 公共方法/类加了 docstring                            │    │
│  │ ▢ 没有新增的安全性反模式（如用户输入直接拼 SQL）         │    │
│  │ ▢ import 链没有循环依赖                                │    │
│  │ ▢ 没有添加新的 as any / as unknown as T 类型绕过        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ⑤ 回退策略                                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ 如果实施中发现问题（pytest 红 / build 失败 /           │    │
│  │ 功能异常 / 意外副作用）：                               │    │
│  │ 1. AI 立即停止修改                                     │    │
│  │ 2. 报告问题原因 + 影响范围                              │    │
│  │ 3. 你用 `git checkout .` 或 `git stash` 回退          │    │
│  │ 4. 你决定是修问题还是放弃本任务                          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ⑥ 完工关单                                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ ▢ 本 SPEC §4 强门禁全过                               │    │
│  │ ▢ AI 已同步 SPEC（§1 总览 + §2 任务状态 + 开工顺序）  │    │
│  │ ▢ 你确认同步无误                                       │    │
│  │ ▢ 你关闭当前对话                                       │    │
│  │ ▢ 新开对话 -> 说「开工 task ${下一个代号}」             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## §4 · 每条任务验收强门禁（模板——每窗必须打印此表并逐项检查）

```
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — {任务代号}           │
│            ┃   ┃                                    │
│            ┗━━━┛                                    │
│                                                     │
│  📍 对话标记：{日期} · {任务代号} · I 窗             │
│                                                     │
│  ▢ 仅改 SPEC 约定的文件                              │
│  ▢ pytest 基线通过数不低于 {基线数字}                │
│  ▢ 后端改动 → `pytest {相关文件} -q` 全绿           │
│  ▢ 前端改动 → `npm run build` 绿                    │
│  ▢ 不改业务行为（AI 自证：比较改动前后同一 API 调用）│
│  ▢ 不改 DB schema / migration                       │
│  ▢ 不改 AGENTS.md / PRD / TECH（除非确有需要）       │
│  ▢ 不改公共 API 签名（请求/响应字段不变）             │
│  ▢ 任务 A → 人工抽测 2-3 题检索（R5-3）             │
│  ▢ **同步 SPEC**（标记本任务 ✅，更新 §1 + 开工顺序）│
│                                                     │
│  回退方案：git checkout -- {改动文件列表}            │
│                                                     │
│  ── 验收人签名：___________  日期：___________  ──  │
└─────────────────────────────────────────────────────┘
```

---

## §5 · 子 plan 文档格式

每条原子任务动工前，AI 必须在 `docs/tasks/code-refactor-{代号}-plan.md` 输出 plan，格式如下：

```markdown
# code-refactor-{代号} · Plan

> **父 SPEC**：`docs/tasks/code-refactor-spec.md`  
> **风险**：低/中/高  
> **预计改动**：{N 个文件，约 M 行增删}
> **基线**：pytest {N} passed · npm run build ✅

## §0 做什么 / 不做什么

## §1 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| ... | modify/delete/create | ... |

## §2 变更步骤（按序执行）

1. ...（每个步骤对应一条 complete_step 签名）
2. ...

## §3 边界 & 异常

## §4 验收门禁（本窗专用）

▢ {本窗独有的验收标准}
▢ 本节完成时删除子 plan 文件

## §5 回退指令

git checkout ...
```

---

## §6 · 基线记录

| 基线项 | 值 | 日期 |
|--------|----|------|
| `pytest tests/` 通过数 | 待记录（开工前跑） | — |
| `npm run build` 状态 | 待记录（开工前跑） | — |
| 当前 git HEAD | 待记录（开工前 `git rev-parse HEAD`） | — |

---

*— SPEC 总纲完 · 等待用户确认后开始逐条执行 —*

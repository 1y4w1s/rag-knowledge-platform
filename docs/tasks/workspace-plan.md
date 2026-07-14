# workspace · Plan

> **状态**：✅ **L 阶段 W1 定稿**（2026-07-05）· **Research ✅** · **W1-1 ✅** · **W1-2 ✅** · **W1-3 ✅** · **W1-4 ✅** · **W1-5 ✅** · **W1-6 ✅** · **W2 ✅** · **W3 ✅** · **W4 ✅** · **W5+-1 ✅** · **W5+-2 ✅** · **W5+-3 ✅** · **W5+-4 ✅** · **W5+-5 ✅** · **W5+-6 ✅** · **W5+-7 ✅** · **W5+-8 ✅** · **Plan-D8 ✅** · **下一：15min 计时全稿 或 Plan-11/2.15 可选**  
> **Research**：`docs/tasks/workspace-research.md`  
> **PRD**：`workspace-prd-ws1.md` ✅ · `workspace-prd-ws2.md`（V 冻结 shell v2 ✅）  
> **边界**：Implement 顺序 **W1 内核 → W2 侧栏 → W3 列表 → W4 概览**；**本 plan 不含** 注册三步 UI（W5+）、邀请码、RAG Plan-RAG

### 波次路线图（骨架 · 待 Research 关门前细化）

| 波次 | 任务 | PRD 对照 | 状态 | 依赖 |
|------|------|----------|------|------|
| **W1** | **内核**：`workspace` query · scope SQL · WorkspaceContext · generation · localStorage · Guards | WS-2-1 §1.2/§1.6 · WS-2-2 §2.1 · WS-2-3 §3.1 | ✅ W1-6 | Research ✅ |
| **W2** | 侧栏 segmented + Popover + `formatOrgLabel` + **› chevron** 全称入口 + 导航可见性 | WS-2-1 §1.1～§1.4 | ✅ 2026-07-05 | W1 |
| **W3** | 资料库列表 scope + 写权限 + `?q=` 与 workspace 联验 | WS-2-2 | ✅ 2026-07-05 | W1 |
| **W4** | Dashboard stats scope + member badge + D-1～D-4 桥接 | WS-2-3 | ✅ 2026-07-05 | W1 · dashboard-polish ✅ |
| **W5+** | 注册三步 · 邀请码 · Owner 转让 · WS-2-4～9 | WS-1-2 · WS-2 余页 | 🟡 W5+-1 ✅ | W1～W4 |

---

## W1 · 内核（✅ Plan 定稿 · 2026-07-05 · H8～H10 ✅ 用户确认）

> **一句话**：同一账号能在「我的空间 / 团队空间」间切换，后端按 `?workspace=` 筛库，前端不会把两个空间的数字/列表搞混。

### W1 假设收口（H8～H10 · Plan 签）

| # | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|---|----------|----------------------|------|------|
| H8 | 切换时**只记序号、丢弃旧响应**（不加 AbortController） | 实现快：连点切换时旧请求还在跑但页面**不会闪错数字**；缺点是多占一点带宽 | 仅 generation | ✅ 用户确认 2026-07-05 |
| H9 | API 层**自己读 localStorage** 拼 `?workspace=` | 改 `fetchKnowledgeBases` 等函数内部自动带参数，页面不用每次手写；Context 只管写 storage | storage 单源 | ✅ 用户确认 2026-07-05 |
| H10 | **403 在 api 文件里触发回落** | 一 403 就清 workspace 键 + toast + 重拉 personal；Dashboard 不用写第二套错误处理；api 层需能调到 Context 的 reset | api 内回落 | ✅ 用户确认 2026-07-05 |

**推荐**：三条均按 Research 默认签 ✅——W1 求稳求快，W3 再评估 AbortController。

---

### W1 不做什么（整波边界）

| 不做 | 归哪 |
|------|------|
| 侧栏 segmented / Popover / › chevron / `formatOrgLabel` UI | **W2**（预览 shell v2 已冻结） |
| 资料库列表页 scope 联验 · 写权限 UI 全面接 workspace | **W3** |
| Dashboard member badge · D-1～D-4 桥接 | **W4** |
| 注册三步 · 邀请码 · Owner 转让 · `/me` 组织展示名 | **W5+** |
| 改 `preview-*.html` / `preview-shell-v2.css` | V 已冻结 |
| chat/documents API 加 workspace Query | 靠 `kb_id` + deps；ResourceGuard 补 L1 |
| Plan-RAG 跨库搜 | W1 后再评估 |
| `account_type` flip 删除 | W5 注册重构 tech debt（H6） |

---

### Implement 顺序与 I 窗建议

```
W1-1（后端 scope + deps + pytest T1～T7）
  → W1-2（list/stats/create 接 scope · 同 pytest 绿）
  → W1-3（Context + api append workspace · M1）
  → W1-4（generation 丢弃 · M3）
  → W1-5（LS 键 + login/logout + align · M4/M5）
  → W1-6（Guards + routes · M6～M9）
  → W1 收尾：M10 build · cockpit 同步
```

**H1 硬约束**：W1-1～W1-2 与 W1-3 **同一部署批次**或连续 I 窗——旧前端无 workspace 会全站 403。

---

### W1-1 · 后端 `resolve_workspace` + Query + 修 deps ✅ 2026-07-05

**一句话**：服务器新增「工作区解析器」——收到 `?workspace=personal` 或 `?workspace=团队ID` 后，知道该查哪套资料库；并修 enterprise 用户读**自己个人库**的权限漏洞。

| 块 | 内容 |
|----|------|
| **新建** | `backend/app/services/workspace/scope.py`（≤150 行）· `WorkspaceScope` dataclass · `resolve_workspace(user, workspace: str)` |
| **修改** | `backend/app/api/knowledge_bases.py` — `list_kbs` / `create_kb` 增 `workspace: str = Query(...)` |
| | `backend/app/api/dashboard.py` — `read_dashboard_stats` 增 `workspace` Query |
| | `backend/app/core/deps.py` — `_assert_kb_ownership`：若 `kb.owner_user_id == me.id` → 允许（修 T7） |
| **测试** | 新建 `backend/tests/test_workspace_scope.py`（≤400 行）或扩 `test_dashboard.py` + `test_knowledge_bases.py` |

**本任务不做**

- 不改 `crud.py` / `stats.py` / `names.py` 业务逻辑（留 W1-2）
- 不改前端
- 不加 chat/documents workspace Query

**resolve_workspace 规则（Implement 照抄）**

| workspace 值 | 结果 |
|--------------|------|
| 缺参 / 空串 | **403**（H1） |
| 非法 UUID | **400** |
| `personal` | SQL：`owner_user_id == me`（不看 account_type） |
| `{org_id}` | 查 membership；无记录 → **403**「无权访问该工作区」；有 → `owner_org_id == org_id` |

**验收**

| ID | 场景 | 预期 |
|----|------|------|
| T5 | 任意 · **缺** workspace | 403 |
| T6 | 伪造他人 org_id | 403 |
| T7 | enterprise · GET **自己的** personal kb_id | 200（deps 修后） |

**你怎么验**：`pytest backend/tests/test_workspace_scope.py -k "missing or forged or personal_kb"` 绿 · OpenAPI 见 `workspace` Query 出现在 list/stats/create。

**大白话**：W1-1 只搭后端「筛库规则」和修一个权限洞——企业账号切到「我的空间」时，后端要能认出自己的个人库；还没改列表/统计怎么筛（那是 W1-2）。

---

### W1-2 · `list_kbs` + `get_dashboard_stats` + `create_kb` 接 scope ✅ 2026-07-05

**一句话**：列表、概览统计、建库三个接口真正用 W1-1 的 scope 筛数据——个人空间只看个人库，团队空间只看团队库，成员不能建库。

| 块 | 内容 |
|----|------|
| **修改** | `backend/app/services/knowledge_base/crud.py` — `list` / `create` / `_assert_can_create_kb` 接 `WorkspaceScope` |
| | `backend/app/services/knowledge_base/names.py` — 重名校验改 scope |
| | `backend/app/services/dashboard/stats.py` — `_kb_scope_clause` 改 `WorkspaceScope`；`member_count` 仅 team workspace |
| | `backend/app/api/knowledge_bases.py` — 路由调 service 时传入 resolved scope |
| | `backend/app/api/dashboard.py` — 同上 |

**本任务不做**

- 不改前端
- 不改 Guard
- stats `scope` 字段名保持 `personal` / `organization`（H7）

**create_kb 写归属**

```
workspace=personal  → owner_user_id=me; owner_org_id=null
workspace={org_id}  → owner_org_id=org_id; owner_user_id=null; member → 403
```

**验收（pytest 全矩阵）**

| ID | 场景 | 预期 |
|----|------|------|
| T1 | personal 用户 · `?workspace=personal` | 200 · 仅 personal 库 |
| T2 | enterprise admin · `?workspace=personal` | 200 · 仅自己的 personal 库（可为 0） |
| T3 | enterprise admin · `?workspace={org_id}` | 200 · 仅 team 库 · stats `scope=organization` |
| T4 | enterprise member · POST kb · team workspace | 403 |
| T5 | 缺 workspace | 403 |
| T6 | 伪造 org_id | 403 |
| T7 | enterprise GET 自己的 personal kb | 200 |

**你怎么验**：`pytest backend/tests/test_workspace_scope.py`（或 dashboard+kb tests）**T1～T7 全绿** · `docker compose build api` 后 curl 双 workspace 数字不同。

**大白话**：W1-2 让「查列表、看概览数字、新建库」都听 workspace 指挥——团队管理员在个人空间能看到自己的个人库（可能为空），在团队空间只看到团队库。

---

### W1-3 · `WorkspaceContext` + api append `?workspace=` ✅ 2026-07-05

**一句话**：浏览器里新增「当前在看哪个空间」的记忆；每次拉列表/概览时 URL 自动带上 `?workspace=`。

| 块 | 内容 |
|----|------|
| **新建** | `frontend/src/lib/workspace-storage.ts`（≤150 行）— 键 `zhian-workspace` · get/set |
| | `frontend/src/lib/workspace-context.tsx`（≤200 行）— Provider · `useWorkspace()` · `setWorkspace` · `resetToPersonal` 骨架 |
| **修改** | `frontend/src/main.tsx` — `AuthProvider` → **`WorkspaceProvider`** → Router |
| | `frontend/src/lib/dashboard-api.ts` — append `?workspace=`（H9：读 storage 同步函数） |
| | `frontend/src/lib/knowledge-base-api.ts` — list/stats/create 同上 |
| | `frontend/src/pages/DashboardPage.tsx` — 依赖 `workspace` 重拉 stats |
| | `frontend/src/lib/org-permissions.ts` — `canWriteKnowledgeBase(user, workspace)` |

**本任务不做**

- 不加 generation 丢弃（W1-4）
- 不做 align / login 清键（W1-5）
- 不改侧栏 UI（W2）
- 403 回落完整接线可 stub，W1-4/5 补

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| M1 | 登录 admin · DevTools Network | `GET …/dashboard/stats?workspace=personal` |
| M10 | `npm run build` | 绿（本任务末或 W1 末） |

**你怎么验**：`demo_admin` 登录 → 概览页 Network 见 `?workspace=personal` · 无 workspace 的旧调用应已消失。

**大白话**：W1-3 给网站装上「工作区记忆」——刷新后仍知道你在看个人还是团队，并且每次问服务器要数据都会说清楚「我要哪个空间的」。

---

### W1-4 · `workspaceGeneration` 丢弃过期响应

**一句话**：快速切换空间时，晚到的旧统计不会把数字闪错——只渲染和当前切换次数匹配的那次响应。

| 块 | 内容 |
|----|------|
| **修改** | `workspace-context.tsx` — `setWorkspace` 时 `generation++` · `navigate('/dashboard', { replace: true })` |
| | `dashboard-api.ts` — 请求带 `expectedGen` · 响应回调比对 generation |
| | `DashboardPage.tsx` — 切换时重拉 · 丢弃过期 setState |
| | `knowledge-base-api.ts` — list 同理（若页面有并发 list） |

**本任务不做**

- H8 默认：**不加 AbortController**（仅 generation 丢弃）
- 侧栏 segmented UI（W2）；W1 可用 DevTools 改 storage 或临时按钮测 M3

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| M3 | 快速连点切换（W2 前可用临时 hook / 改 LS + 刷新模拟） | Dashboard 数字**不闪**成另一空间 |

**你怎么验**：企业 admin · 个人↔团队快速切换 · 观察统计卡无「闪一下错数再回来」。

**大白话**：W1-4 防「串台闪烁」——像换电视频道，旧频道的画面晚到也不会盖在新频道上。

---

### W1-5 · localStorage 键 + login/logout + `/me` align

**一句话**：浏览器记住哪个空间、哪个库最近用过；换账号/脏数据时自动清掉并回到个人空间。

| 块 | 内容 |
|----|------|
| **扩展** | `workspace-storage.ts` — `recentKbKey(workspace)` · `migrateLegacyRecentKbKey()` · `clearWorkspaceAndRecentKeys()` |
| **修改** | `workspace-context.tsx` — `alignWorkspaceWithMe(user)` · mount + visibility visible（H12） |
| | `auth-context.tsx` — login/logout 调 clear（E10） |
| | `use-sidebar-chat-kb-id.ts` — 分键读写 · list fallback 带 workspace |
| | KB 详情/对话入口 — `persistRecentKbId(kbId, workspace)`（Dashboard D-1 等） |
| **删除** | 迁移后移除 legacy `zhian-recent-kb-id`（H11） |

**本任务不做**

- 不做 Guard（W1-6）
- 403 api 回落完整逻辑若 W1-3 stub，本任务与 H10 一并接 `resetToPersonal`
- 不做 `/me` 组织展示名（H4 · W2）

**align 规则（E3）**

| 条件 | 动作 |
|------|------|
| LS 假 UUID / 与 `/me.org_id` 不符 / personal-only 用户存 team 键 | `resetToPersonal()` + toast「工作区已重置」（H13 每次 toast） |

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| M4 | Application 改 `zhian-workspace` 为假 UUID · 刷新 | toast · personal stats |
| M5 | logout · 登录另一账号 | 无上一账号 workspace / recent 键 |

**你怎么验**：DevTools Application 面板改键 · 双账号轮换 · Tab 聚焦对齐（E8 可选第二 Tab 测）。

**大白话**：W1-5 管「浏览器小本本」——记你在哪个空间、最近打开哪个库；本子脏了或换人就擦掉重写。

---

### W1-6 · `WorkspaceGuard` + `ResourceGuard` · members 去 OrgAdminGuard ✅ 2026-07-05

**一句话**：硬闯 URL 时前端拦住——成员能进花名册只读、管理员在个人空间进不了团队设置、Bookmark 别空间的库会被踢回概览。

| 块 | 内容 |
|----|------|
| **新建** | `frontend/src/components/guards/WorkspaceGuard.tsx`（≤120 行） |
| | `frontend/src/components/guards/ResourceGuard.tsx`（≤120 行） |
| **修改** | `frontend/src/routes/index.tsx` — members → **WorkspaceGuard only**（H15）；settings → Workspace + OrgAdmin |
| | kb 详情/对话/doc 路由 — 外包 **ResourceGuard** |
| **保留** | `OrgAdminGuard.tsx` — 仅 settings |

**ResourceGuard 算法（H16）**

1. 读 `workspace` + 路由 `kb_id`
2. mount 时 `GET /knowledge-bases/{id}`（不带 workspace Query）
3. personal：`kb.owner_user_id === me`；team：`kb.owner_org_id === workspace`
4. 失败 → toast T3「该资源不在当前工作区」· `replace /dashboard`（H14）

**Toast 四档**

| 档 | 文案 | 触发 |
|----|------|------|
| T1 | 无权限访问该页面 | Member → settings |
| T2 | 请先切换到团队工作区 | Admin + personal → org 页 |
| T3 | 该资源不在当前工作区 | 别空间 kb URL |
| T4 | 工作区已重置 | E3 / 403 workspace |

**本任务不做**

- 侧栏菜单可见性（W2）
- Guard pytest（纯前端 L1）
- chat/documents 加 workspace Query

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| M6 | Member · team workspace · `/organization/members` | 200 只读花名册 |
| M7 | Member · `/organization/settings` | replace dashboard · toast T1 · **无** settings GET |
| M8 | Admin · personal · `/organization/members` | toast T2 · replace dashboard |
| M9 | personal · 地址栏 team 的 kb_id 详情 | toast T3 · dashboard |
| M2 | （W2 segmented 后）切 team · `/dashboard` | `?workspace={org_id}` · 数字一致 |
| M10 | `npm run build` | 绿 |

**你怎么验**：`demo_member` / `demo_admin` · 地址栏硬闯 · DevTools Network 确认 L2（M7 无 settings 请求）。

**大白话**：W1-6 是「前台保安」——改地址栏也进不了不该进的页；普通成员能看队友名单但不能改团队设置。

---

### W1 完工总验收

**pytest（W1-1 + W1-2）**

| ID | 场景 | 预期 |
|----|------|------|
| T1 | personal · `?workspace=personal` | 200 · 仅 personal 库 |
| T2 | enterprise admin · personal workspace | 200 · 仅自己的 personal 库 |
| T3 | enterprise admin · team workspace | 200 · team 库 · scope=organization |
| T4 | member POST kb · team | 403 |
| T5 | 缺 workspace | 403 |
| T6 | 伪造 org_id | 403 |
| T7 | enterprise GET 自己的 personal kb | 200 |

**跑法**：`pytest backend/tests/test_workspace_scope.py` · `docker compose build api`

**人工（M1～M10）**

| # | 操作 | 预期 | 依赖任务 |
|---|------|------|----------|
| M1 | admin 登录 · Network | stats 带 `?workspace=personal` | W1-3 |
| M2 | 切 team · `/dashboard` | `?workspace={org_id}` · 数字一致 | W2 UI + W1-3 |
| M3 | 快速切换 | 数字不闪 | W1-4 |
| M4 | 假 UUID 刷新 | toast 回落 | W1-5 |
| M5 | 换账号 login | 无泄漏键 | W1-5 |
| M6 | Member · team · members URL | 只读花名册 | W1-6 |
| M7 | Member · settings URL | 拦 + 无 GET | W1-6 |
| M8 | Admin · personal · members URL | T2 | W1-6 |
| M9 | personal · team kb URL | T3 | W1-6 |
| M10 | `npm run build` | 绿 | 全波 |

**文档同步（W1 I 窗末）**

- [x] `workspace-plan.md` W1-6 标 ✅
- [x] `cockpit.html`「进行中」→ W2 侧栏

**风险提醒**

| 风险 | 缓解 |
|------|------|
| H1 前后端不同步 | W1-1～2 与 W1-3 同批或连续 I 窗 |
| deps 未修 | W1-1 必含 T7 |
| members 仍 OrgAdminGuard | W1-6 必改 routes |
| Docker 未 rebuild | 改 backend 后 `docker compose build api` |

---

### W1 门禁三题（Implement 前须能答）

1. **触发点**：用户点侧栏切换（W2）或启动读 LS → 前端 `setWorkspace` → API `GET …?workspace=` → 后端 `resolve_workspace` → SQL scope。
2. **数据流**：`setWorkspace` → 写 `zhian-workspace` → generation++ → replace `/dashboard` → `fetchDashboardStats` 带 workspace → 后端 membership 校验 → `_kb_scope_clause` 聚合 → 前端比对 generation 后渲染。
3. **怎么验**：pytest T1～T7 绿 + M1 Network 见 query + M6～M9 硬闯 URL toast 对 + M10 build 绿。

---

## W2～W5 · 待 Research 关门后展开

### W2 · 侧栏 segmented + Popover + 导航可见性 ✅ 2026-07-05

**一句话**：侧栏能点「我的空间 ↔ 团队」切换；长组织名有短标签 + › 看全称；管理菜单只在团队空间出现。

| 块 | 内容 |
|----|------|
| **新建** | `format-org-label.ts` · `use-organization-name.ts` · `WorkspaceSwitcher.tsx` · `OrgNamePopover.tsx` |
| **修改** | `AppSidebar.tsx` · `index.css`（shell v2 token + ws-seg） |

**本任务不做**：Guard 逻辑 · 预览 HTML · W3 列表 scope

**验收**：M2 切 team · Network `?workspace={org_id}` · S1～S4 导航可见性 · `npm run build` 绿

---

### W3 · 资料库列表 scope + 写权限 + `?q=` 联验 ✅ 2026-07-05

**一句话**：资料库列表页按当前工作区拉数据；团队普通成员不能新建/改/删；切换空间时搜索词不串台。

| 块 | 内容 |
|----|------|
| **修改** | `KnowledgeBasesPage.tsx` — `canWriteKnowledgeBase(user, workspace)` · `isTeamMemberReadOnly` · workspace 变更清 `?q=` · 删库清 recent 分键 |
| | `org-permissions.ts` — `isTeamMemberReadOnly` |
| | `workspace-storage.ts` — `clearRecentKbId`（E8） |

**本任务不做**：详情页写权限（后续 wave）· Dashboard W4 scope · 预览 HTML

**验收**：personal/team 列表不同 · member 团队空间无新建/删库 · `?q=` 不串台 · `npm run build` 绿

---

### W4 · Dashboard stats scope + member badge + D-1～D-4 桥接 ✅ 2026-07-05

**一句话**：概览页数字跟当前工作区对齐；团队空间标题旁可点「N 名成员 ›」进花名册；去掉 Zone A 废话 badge；D-1～D-4 的 recent 库 / Banner dismiss 按 workspace 分键。

| 块 | 内容 |
|----|------|
| **修改** | `DashboardZoneA.tsx` — 删「团队空间 / 我的空间」pill · 团队 workspace 标题行 `{N} 名成员 ›` → `/organization/members` |
| | `DashboardStatusBanner.tsx` — 就绪 dismiss localStorage 按 `workspace` 分键 |
| | `DashboardPage.tsx` — 传 `isOrgAdmin` · Banner 传 `workspace` |
| | `index.css` — `.team-badge` link-button 样式（对齐 preview-shell-v2） |

**本任务不做**：长名 Info Banner（WS-1-2 §2.5）· 顶栏 T2 · 注册三步（W5+）

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| M2 | admin 切 personal ↔ team · 留 `/dashboard` | Network `?workspace=` 变 · 资料库数与列表一致 |
| S3 | Member · team · badge | 「N 名成员 ›」→ 只读花名册 · Tooltip「查看团队成员」 |
| S2 | Admin · team · badge | 同外观 · Tooltip「查看成员管理」 |
| D-1 | 有库 · 上传 CTA | 进当前 workspace 的 `recent_kb_id` 详情 |
| D-4 | 快捷提问 | 进当前 workspace 最近库对话 `?q=` |
| D-2 | 切 workspace | 就绪 dismiss 不串台（分键） |

**你怎么验**：`demo_admin` / `demo_member` · 切空间看概览「资料库」数 = 列表页行数 · 点 badge 进 `/organization/members` · `npm run build` 绿

---

## W5+ · 注册 / 邀请（2026-07-05 起）

### W5+-1 · 注册三步 UI shell ✅ 2026-07-05

**一句话**：注册页从单页改成 PRD 三步向导（用法 → 团队角色 → 登录信息）；组织名软校验；提交仍走现有 API（个人 + 团队·创建者）。

| 块 | 内容 |
|----|------|
| **新建** | `RegisterStepsIndicator.tsx` · `RegisterUsageStep.tsx` · `RegisterTeamRoleStep.tsx` · `RegisterCredentialsStep.tsx` · `RegisterChoiceCard.tsx` · `register-form-types.ts` |
| **修改** | `RegisterForm.tsx`（向导编排）· `auth-form-validation.ts`（组织名软/硬校验）· `index.css`（步骤条 + 软提示 token） |

**本任务不做**

- 邀请码后端 redeem · 成员完整注册（W5+-2）
- 注册成功 toast（WS-1-3）· 长名 Info Banner（WS-1-2 §2.5）
- `account_type` flip 删除 · Owner `is_owner` 字段

**验收**

| ID | 操作 | 预期 |
|----|------|------|
| S1 | 选个人 → 继续 | 跳过第 2 步，直达登录信息（2 步条） |
| S2 | 选团队 → 创建者 → 填「知岸科技」 | 第 3 步 chip 含团队名 · 注册成功 · 默认 team workspace |
| S3 | 创建者 · 45 字组织名 | 黄色软提示 · 可继续 |
| S4 | 创建者 · 90 字 · 点继续/创建 | 确认框 · 确认后成功 |
| S5 | 成员 · 填邀请码 · 创建账号 | 提示「邀请码注册将在下一步接入」（W5+-2） |
| M10 | `npm run build` | 绿 |

**你怎么验**：`/login` 注册 Tab · 走 S1～S5 · Network 见 personal/enterprise 注册 POST · 团队创建者登录后侧栏在团队空间。

**大白话**：注册页变成和预览一样的三步——先选个人还是团队，团队再选创建还是成员；创建者填「团队显示名称」有长短提示；真正提交注册目前只接「个人」和「团队创建者」，成员邀请码下一任务接后端。

---

### W5+-2 · 邀请码 redeem + 第 2 步预校验 ✅ 2026-07-05

**一句话**：成员凭邀请码注册；第 2 步点「继续」先验码（错则留本步）；提交时再验一次并建号；码可多人用；无效/过期整单失败（B1）。

#### 用户拍板（2026-07-05 ✅）

| # | 选项 | 选这个的后果（白话） | 状态 |
|---|------|----------------------|------|
| I1 | 邀请码 **可多人用** | 同一码可给多个同事注册；**没有**「码已被使用」提示；管理员停用/过期才失效 | ✅ 用户确认 |
| I2 | 第 2 步点「继续」**先调预校验 API** | 错码在第 2 步就红字拦住，进不了第 3 步；对码时返回团队名，第 3 步 chip 能显示「成员 · 知岸科技」 | ✅ 用户确认 |
| I3 | 提交注册 **再验一次**（B1） | 防止预校验后码被删/过期；仍错则 **不建账号**，留第 3 步红条 | 默认 ✅（B1） |

**不做**：一次性码 · 「已被使用」单独文案 · 错码回落个人账号 · 预校验跳过直接进第 3 步

#### 页面行为（Implement 照此）

| 时机 | 用户看到什么 |
|------|--------------|
| 第 2 步 · 码空/太短 | 字段红字，无法继续（现有） |
| 第 2 步 · 点继续 · 码无效/过期 | 邀请码字段红字 + 顶部红条：「邀请码无效或已过期，请核对或联系管理员」；**停留第 2 步** |
| 第 2 步 · 预校验通过 | 进入第 3 步；chip 含 **团队展示名**（来自预校验响应） |
| 第 3 步 · 提交 · 码仍有效 | 注册成功 → 默认 **团队 workspace** |
| 第 3 步 · 提交 · 码已失效 | 红条同上 · **不建账号** · 已填用户名/邮箱/密码保留 · 可回第 2 步改码 |
| 第 3 步 · 邮箱已占用 | 「该邮箱已注册」→ 引导去登录（与邀请码无关） |

#### 后端（骨架）

| 块 | 内容 |
|----|------|
| **库** | `organization_invite_codes`（`code` · `org_id` · `expires_at` nullable · `revoked_at` nullable · `created_by`）— **无** `max_uses` / 用完计数（I1） |
| **新建** | `POST /api/v1/auth/invites/validate` — 匿名 · body `{ code }` → `{ org_id, org_name }` 或 422 |
| **修改** | `POST /auth/register` — member 路径：`invite_code` 必填 · 事务内再验 + 写 membership · **不**消耗码 |
| **Admin 发码** | 最小：`POST /organization/invites`（admin only）供 demo/pytest；完整 UI 可跟 WS-2-8 同窗或 W5+-3 |

**validate 规则**

| 条件 | HTTP |
|------|------|
| trim 后空 / 格式不对 | 422 |
| 库中无此码 | 422「邀请码无效或已过期」 |
| `revoked_at` 非空 | 422 同上（**不**区分文案，I1） |
| `expires_at` < now | 422 同上 |
| 有效 | 200 + `org_id` + `org_name`（展示名） |

#### 前端

| 块 | 内容 |
|----|------|
| **新建** | `auth-invite-api.ts` — `validateInviteCode(code)` |
| **修改** | `RegisterForm` — 第 2 步 continue 调预校验 · 存 `resolvedOrgName` · 成员第 3 步启用创建 · 提交带 `invite_code` |
| **修改** | `auth-api.ts` — register 增 `invite_code?` |

#### 验收

| ID | 操作 | 预期 |
|----|------|------|
| I-V1 | 成员 · 错码 · 第 2 步继续 | 422 · 留第 2 步 · 不进第 3 步 |
| I-V2 | 成员 · 对码 · 继续 | 第 3 步 chip 含团队名 |
| I-V3 | 预校验通过后提交 | 201 · `/me` 有 org · 默认 team workspace |
| I-V4 | 预校验后对码 revoke · 再提交 | 422 · **无** user 行 |
| I-V5 | 同一码两人注册 | 均成功（I1） |
| I-V6 | pytest validate + register member | 绿 |
| M10 | `npm run build` | 绿 |

**你怎么验**：admin 发码（API/seed）→ 注册成员路径 · Network 见两次 validate（继续 + register 内）· 错码不过第 2 步。

**大白话**：码像「公司大门的通用通行证」，可以多个人用；第 2 步门口先刷一次卡，不对不让进填账号那页；最后点创建再刷一次，两次都过才建号进团队。

---

### W5+-3 · 发码 UI ✅ 2026-07-05

**一句话**：管理员在成员管理页一键生成邀请码，展示并复制，新成员走 W5+-2 注册路径加入。

#### 前端

| 块 | 内容 |
|----|------|
| **新建** | `InviteCodePanel.tsx` — 生成 · 展示码 · 复制 · 有效期文案 |
| **修改** | `organization-api.ts` — `createOrganizationInvite()` · `formatInviteExpiry()` |
| **修改** | `MembersPage.tsx` — `isOrgAdmin` 时渲染邀请码区块（成员页上方、花名册上方） |

#### 验收

| ID | 操作 | 预期 |
|----|------|------|
| I-G1 | Admin · 成员管理 · 生成邀请码 | 201 · 见 `ZHIAN-XXXX` · 可复制 |
| I-G2 | 新 Tab · 注册 · 团队·成员 · 粘贴码 | W5+-2 路径走通 · 201 |
| I-G3 | Member 进成员页 | **无**邀请码 UI（admin only） |
| M10 | `npm run build` | 绿 |

**你怎么验**：`demo_admin` 登录 → 切团队工作区 → 侧栏「成员管理」→ 生成邀请码 → 复制 → 无痕窗注册成员粘贴码 → 创建成功。

**大白话**：管理员在成员页点一下就能拿到「公司大门通行证」，复制发给同事；同事注册时填这个码就能进团队。

**这回不做**：Owner 转让 · 撤销码 UI · 组织设置页重复发码 · WS-2-8 成员只读花名册 · WS-2-4～9。

---

### W5+-4 · Owner 内核 ✅ 2026-07-05

**一句话**：团队创建者标记为「所有者」；列表展示；不可被移除；`/me` 带 `is_owner`。

| 块 | 内容 |
|----|------|
| **迁移** | `010` — `organization_members.is_owner` · 每 org 最早 admin 回填 |
| **后端** | 注册创建者 `is_owner=true` · 移除 Owner → 403 · 成员响应含 `is_owner` |
| **前端** | 花名册角色列显示 **所有者** · `StoredUser.is_owner` |

**下一**：Owner 转让 UI · WS-2-7 账号填码

---

### W5+-5 · WS-2-8 改角色 ✅ 2026-07-05

**一句话**：Owner 在成员管理页提拔/降级成员；Admin 只能移除 Member，看不到改角色按钮。

#### 用户拍板（2026-07-05 ✅）

| # | 选项 | 选这个的后果（白话） | 状态 |
|---|------|----------------------|------|
| H-R1 | 被降级 Admin **不自动**刷新浏览器登录信息 | 对方刷新或重登后侧栏才变；点管理页会被 API/Guard 403 拦住，不能真改东西 | ✅ 用户确认 |

**不做**：Owner 转让 · WS-2-7 · 撤销码 UI · Admin 互相改权 · auth 轮询刷新

#### 后端

| 块 | 内容 |
|----|------|
| **新建** | `deps.py` — `require_owner()` |
| **新建** | `members.py` — `update_member_role(...)` |
| **新建** | `OrganizationMemberRoleUpdate { role: admin \| member }` |
| **修改** | `api/organization.py` — `PATCH /members/{user_id}` |

**规则**：仅 Owner · 不能改 Owner 行 · 不能改自己 · 已是目标 role → 409

#### 前端

| 块 | 内容 |
|----|------|
| **修改** | `organization-api.ts` — `updateOrganizationMemberRole` |
| **新建** | `MemberRoleActions.tsx`（≤80 行） |
| **修改** | `MembersTable.tsx` · `MembersPage.tsx` — 传 `isOwner` |

#### 验收

| ID | 场景 | 预期 |
|----|------|------|
| O1 | Owner PATCH Member → admin | 200 · 对方 org_role=admin |
| O2 | Admin PATCH | 403 |
| O4 | Owner PATCH Admin(非Owner) → member | 200 |
| O5 | 列表 Owner 行 | 「所有者」 |
| O6 | Member PATCH | 403 |
| O7 | Owner PATCH Owner 行 | 403 |
| M10 | `npm run build` | 绿 |

**大白话**：只有创建者能提拔/降级副管；副管只能加人、踢普通成员，不能改任何人角色。

---

### W5+-6 · Owner 转让 ✅ 2026-07-05

**一句话**：创建者在成员管理页把「所有者」身份转给队友；自己降为管理员，对方升为所有者+管理员。

#### 用户拍板（2026-07-05 ✅）

| # | 选项 | 选这个的后果（白话） | 状态 |
|---|------|----------------------|------|
| H-T1 | 转让对象：**任意现有成员**（Admin 或 Member） | 下拉列出除自己外全部队友；转给普通成员时**自动升为管理员+所有者**；若只允许副管，须先手动提拔，多一步 | ✅ 默认 |
| H-T2 | 转让后旧 Owner：**保留 Admin、去掉 is_owner** | 你还在团队里当副管，侧栏仍有管理菜单，但不能再改角色/转让；若降为 Member 则管理菜单立刻消失 | ✅ 默认 |
| H-T3 | JWT 刷新 | 同 H-R1：**不自动**刷新对方浏览器；转让后你本页会调 `/me` 更新自己的 `is_owner` | ✅ 默认 |

**不做**：Owner 自退/离团 UI · WS-2-7 账号页 · 转让后踢旧 Owner · 二次确认邮箱

#### 后端

| 块 | 内容 |
|----|------|
| **新建** | `members.py` — `transfer_organization_ownership(...)` |
| **新建** | `OrganizationOwnershipTransferRequest/Response` |
| **修改** | `api/organization.py` — `POST /transfer-ownership` · `require_owner` |

**规则**：仅 Owner · 不能转给自己 · 目标须为同 org 成员且非 Owner · 事务内：旧 Owner `is_owner=false` 保持 admin；新 Owner `is_owner=true` + `role=admin`

#### 前端

| 块 | 内容 |
|----|------|
| **新建** | `TransferOwnershipDialog.tsx` — 下拉选成员 · 确认 |
| **修改** | `MembersTable.tsx` — Owner 行「转让所有权」 |
| **修改** | `MembersPage.tsx` · `organization-api.ts` |

#### 验收

| ID | 场景 | 预期 |
|----|------|------|
| O8 | Owner POST 转给 Member | 200 · 新 Owner `is_owner=true` · 旧 Owner `is_owner=false` 仍 admin |
| O9 | Owner 转给 Admin | 200 |
| O10 | Admin POST 转让 | 403 |
| O11 | 转给自己 | 403 |
| O12 | 转给非成员 | 404 |
| M10 | `npm run build` | 绿 |

**你怎么验**：`demo_admin`（Owner）→ 成员管理 → 所有者行点「转让所有权」→ 选 `demo_member` → 确认 → 花名册标签对调 · `/me` 旧 Owner 无 is_owner · pytest O8～O12 绿。

**大白话**：创建者可以把「老板章」交给队友——交出去后你还是副管，对方变成新老板；浏览器里你的「所有者」标签会立刻更新，对方要刷新或重登才看到。

---

### W5+-7 · WS-2-7 账号填码 ✅ 2026-07-05

**一句话**：个人用户登录后在账号设置页填邀请码加入团队；成功后默认切到团队工作区。

#### 后端

| 块 | 内容 |
|----|------|
| **新建** | `POST /settings/account/join-team` — body `{ invite_code }` → `{ message, account }` |
| **修改** | `services/account/settings.py` — `join_team_with_invite`（复用 `resolve_valid_invite` + 对齐 `add_organization_member`） |

**规则**：已有 membership → 409 · 无效码 → 422 · personal 用户 flip `account_type=enterprise` + 写 member 关系 · **不**消耗码（I1）

#### 前端

| 块 | 内容 |
|----|------|
| **新建** | `JoinTeamForm.tsx` — 仅 `!org_id` 时展示 |
| **修改** | `AccountSettingsPage.tsx` · `settings-api.ts` |

**成功**：刷新 `/me` · `setWorkspace(org_id)` · toast「已加入团队 {名}」· replace `/dashboard`

#### 验收

| ID | 场景 | 预期 |
|----|------|------|
| J1 | personal · 有效码 | 200 · `/me` 有 org · 侧栏可切团队 |
| J2 | 错码 | 422 · 字段红字 |
| J3 | 已在团队 | 409 · 无填码区块 |
| M10 | `npm run build` | 绿 |

**这回不做**：离开团队 UI · 成员页转让 · 撤销码

---

### W5+-8 · WS-2-7 离开团队 ✅ 2026-07-05

**一句话**：已在团队的用户在账号设置页自退；Owner 须先转让；成功后回到个人 workspace。

#### 后端

| 块 | 内容 |
|----|------|
| **新建** | `POST /settings/account/leave-team` → `{ message, account }` |
| **修改** | `services/account/settings.py` — `leave_team`（删 membership · flip `account_type=personal`） |

**规则**：无 membership → 409 · Owner `is_owner` → 403「离开前请先转让团队所有权」· 个人库不动

#### 前端

| 块 | 内容 |
|----|------|
| **新建** | `LeaveTeamForm.tsx` — Member/Admin 确认离开 · Owner 提示去成员管理转让 |
| **修改** | `AccountSettingsPage.tsx` · `settings-api.ts` |

**成功**：刷新 `/me` · `setWorkspace(personal)` · toast「已离开团队 {名}」· replace `/dashboard`

#### 验收

| ID | 场景 | 预期 |
|----|------|------|
| L1 | Member POST leave-team | 200 · `/me` 无 org · account_type personal |
| L2 | Owner POST | 403 |
| L3 | personal 用户 POST | 409 |
| M10 | `npm run build` | 绿 |

**这回不做**：填码加入 · 转让逻辑 · 撤销码

---

## 与 dashboard-polish / 002-plan 关系

| 文档 | 关系 |
|------|------|
| `dashboard-polish-plan.md` | D-1～D-4 **UI 已 ✅**；W4 只接 workspace scope，不重做 Banner/CTA |
| `002-plan.md` | 5.3/5.4 **已 ✅**；成员页在 W1 后改 `WorkspaceGuard` |
| `rag-optimization-plan.md` | R1 跨库搜 **依赖 W1** 后再评估 |

# 组织与部门 · PRD-ORG-1（企业级 · 分节确认）

> **状态**：✅ P 关 ORG-1-1～1-6（2026-07-07）· **I 关 ORG-5.3 ✅** · **V 关 ORG-5.4 ✅**（2026-07-07）  
> **预览**：[`preview-org-departments.html`](../preview-org-departments.html) · ORG-1-2/1-3 关键 S + 乱操作试玩 · grant · 共用 `preview-shell-v2.css`  
> **依据**：`org-departments-research.md`（§1 ✅ · H 企业级完整版 ✅）  
> **与 WS 关系**：**不替换** `workspace-prd-ws1/2`；在「团队空间」内**新增部门上下文**  
> **Supersede**：`002-plan.md`「KB 级 ACL Wave 2」→ 本 PRD 以 **部门归属 + grant** 实现

---

## 索引

| 节 | 内容 | 状态 |
|----|------|------|
| **ORG-1-1** | 核心定义 + 库可见性 | ✅ 2026-07-07 |
| **ORG-1-2** | 侧栏部门选择器 + 切换 | ✅ 2026-07-07 |
| **ORG-1-3** | 组织与部门管理页（Admin） | ✅ 2026-07-07 |
| **ORG-1-4** | 资料库归属与跨部门 grant | ✅ 2026-07-07 |
| **ORG-1-5** | 全链路 scope（列表/概览/搜/对话） | ✅ 2026-07-07 |
| **ORG-1-6** | 角色权限矩阵 | ✅ 2026-07-07 |

---

## ORG-1-1 核心定义 + 库可见性 ✅ 已确认（2026-07-07）

**这节定什么**：公司、部门、当前部门上下文、资料库三种归属——和 WS「我的空间/团队空间」怎么叠在一起。

### 核心概念

| 概念 | 定义 |
|------|------|
| **公司（organization）** | 一个 `organizations` 行；对应侧栏 segmented **「知岸科技」**；仍是一公司一 org |
| **部门（org_unit）** | 公司下的树节点；`parent_id` 可嵌套（事业部→部门→小组）；**无限层** |
| **我的空间** | 与 WS-1 相同；个人库；**不受**部门树影响 |
| **团队空间** | 与 WS-2 相同；`workspace=org_id` |
| **当前部门** | 团队空间内的**第二维上下文**；API：`department_id={uuid}` 或 Admin 的 `all` |
| **主部门** | 用户默认所属部门；忘带 `department_id` 时 **fallback**（H4B） |
| **公司公共库** | `org_unit_id = null` 的团队库；全公司 Member **可读** |
| **部门库** | `org_unit_id = 某节点`；默认仅该部门子树成员可见 |
| **跨部门 grant** | `kb_unit_grants`：把某库的读/写开放给其它部门或全公司（ORG-5 实现） |

### 库可见性（Member 在「研发部」上下文）

| 库 | 可见？ |
|----|--------|
| 研发部及其**子部门**库 | ✅ |
| 公司公共库 | ✅ |
| 被 grant 给研发部（或全公司）的其它部门库 | ✅（按 grant 权限） |
| 市场部 confidential 库（无 grant） | ❌ 列表不出现；硬闯 ID → 403 |
| 个人空间库 | ❌（在团队空间上下文不混排，WS-2 不变） |

**部门 Admin**：在**所管部门子树**内具备 write；**不**自动获得兄弟部门 Admin 权。

**公司 Owner / 公司 Admin**：可选 `department_id=all` 看全公司汇总；可管任意部门树节点。

### 正常流程（S）

| # | 谁 | 做什么 | 看见什么 |
|---|-----|--------|----------|
| S1 | 公司 Admin | 组织与部门页新建「研发部」「市场部」 | 树中出现两节点 |
| S2 | 公司 Admin | 任命张三为研发部 Admin | 张三在公司空间可选研发部；可建研发部库 |
| S3 | 研发 Member 李四 | 公司空间 · 当前部门=研发部 · 打开资料库 | 仅研发子树库 + 公司公共库 |
| S4 | 人事 Admin | 建「员工手册」公司公共库 | 全公司 Member 在任意部门上下文可读 |
| S5 | 人事 Admin | 对「保密薪酬库」不做 grant | 非人事部门 Member 不可见 |
| S6 | 人事 Admin | grant「员工手册」全公司只读 | 已在 S4；研发 Member 对话可引用 |
| S7 | 公司 Admin | 当前部门切「全公司」· 概览 | 统计为全公司汇总（非 Member 默认项） |

### 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 研发 Member 地址栏输入市场部库 `/knowledge-bases/{id}` | **403**；toast「无权访问该资料库」；跳回资料库列表 | 浏览器硬闯 |
| E2 公司空间 API 不带 `department_id` | **默认主部门** scope；非 Admin **不出现** `all` | Network 看 stats 数字与主部门一致 |
| E3 Member 伪造 `department_id=市场部` | **403** 或回落主部门（Implement 定一种，**禁止**看到市场库） | 改 query 刷新 |
| E4 切部门后仍停在旧部门库详情 URL | **403 或重定向**到 `/dashboard`；清 stale 列表缓存 | 研发部详情页切到市场部 |
| E5 对话/chat 带未授权 `kb_id` | SSE 不开始或首帧 error；**无 citation 泄密** | curl / 页面提问 |
| E6 跨库搜 `mode=content` 搜兄弟部门正文 | 结果**不含**未授权库文档 | Dashboard 找文档 |
| E7 被移出部门后 Bookmark 旧链接 | 启动 `/me` + membership 对齐；无权限 → 403 + 切主部门/概览 | 成员管理移除后刷新 |
| E8 Admin 用 `department_id=all` 后 member 账号登录 | Member **无**「全公司」选项；stats 不含兄弟部门机密库 | 两账号对比 |
| E9 父部门 Admin 能否管子部门库 | **能**（子树继承管理权）；兄弟部门 **不能** | 树形 A/B 两枝各建 Admin |
| E10 grant 撤销后旧对话点引用 | citation resolve →「源文档无权限」或「已不可见」（与 EW-D3 一致） | 撤 grant 后点历史消息 |

### 与现有 WS 的边界

| 项 | 定稿 |
|----|------|
| segmented 我的空间/公司 | **不改** WS-2-1 行为 |
| 注册 / 邀请码 / Owner 转让 | **不改** WS-1；新人默认进 **某一主部门**（ORG-2 定：创建者进根或「未分配」池） |
| 一人多团队（多 org） | **仍不做**；MVP 仍是一人一个 company |

---

**§1 确认后**：~~下一节 ORG-1-2~~ → 见下。

---

## ORG-1-2 侧栏部门选择器 + 切换 ✅ 已确认（2026-07-07）

**这节定什么**：公司空间内「当前部门」控件长什么样、谁能切、切换后页面怎么动；与 WS-2 segmented **叠加**，不替换。

### 2.1 位置与形态

| 项 | 定稿 |
|----|------|
| 位置 | 侧栏 **WS-2 segmented 正下方**、主导航 **上方** |
| 显示条件 | **仅**当前工作区 = 团队空间时渲染；「我的空间」**不显示** |
| 形态 | 单行按钮：**「当前部门 ▾ {短名}」**；点击 → **Popover 树**（无限层；当前节点高亮） |
| 短名 | 复用 `formatOrgLabel` 思路；树节点全称在 Popover 内换行展示 |
| 移动端 | ≤768px drawer 内同位置；树 Popover 全宽可滚动 |

### 2.2 选项列表（Popover 内）

| 选项 | 谁看见 | 说明 |
|------|--------|------|
| **{主部门名}** | 所有公司成员 | 默认选中；Member **至少**此项 |
| **{兼任部门…}** | 在多个 `org_unit_members` 的用户 | 与主部门并列；选后 scope 变 |
| **全公司** | Owner · 公司 Admin **仅** | `department_id=all`；汇总 scope |
| 兄弟部门（无兼任） | ❌ **不显示** | 防误切；硬闯 API 仍 403 |

### 2.3 切换行为（与 WS-2-1 对齐）

| 步 | 系统做什么 | 你怎么看见 |
|----|------------|------------|
| 1 | 用户 Popover 选新部门 | 按钮短名更新 |
| 2 | 写 `localStorage` `zhian-department-id`（团队空间分键） | — |
| 3 | `departmentGeneration++`；abort 在途 stats/列表请求 | Network 旧请求 canceled |
| 4 | `navigate('/dashboard', { replace: true })` | 离开跨部门详情 URL |
| 5 | 侧栏导航项不变（仍按 WS-2）；拉新 scope 数据 | 概览数字变 |
| 6 | 丢弃 generation 过期响应 | 无闪回旧部门数字 |

**切回「我的空间」**（segmented）：清 `zhian-department-id` 或忽略；不带 `department_id` query。

**切进团队空间**：若无存盘部门 → 用 **主部门**；Admin 上次若选「全公司」可恢复（分键存 `all`）。

### 2.4 正常流程（S）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 研发 Member 登录 · 进团队空间 | 选择器显示「研发部」；不可见「全公司」「市场部」 |
| S2 | 点选择器 · 见树 | 仅本人有权限的节点可点；其余灰显或不出现在树中 |
| S3 | 兼任人事+研发 · 切人事 | 跳概览；资料库列表仅人事子树 + 公共库 |
| S4 | 公司 Admin · 选「全公司」 | 概览为全公司汇总；资料库列表含各部门（可读库） |
| S5 | Admin 切「我的空间」再回团队 | 恢复上次部门或主部门（存盘策略） |

### 2.5 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 localStorage 篡改 `department_id=伪造 UUID` | 下次请求 **403** 或回落主部门 + toast「部门已重置」 | DevTools 改键刷新 |
| E2 选部门后浏览器后退到旧部门库详情 | ResourceGuard：**403** → 跳 `/dashboard` 或列表 | 切换后点后退 |
| E3 Member 通过 DOM 强行点「全公司」 | 选项 **不渲染**；API 带 `all` → **403** | 改 query 验 API |
| E4 部门被删/用户被移出时仍存旧 id | Tab focus `/me` 对齐 membership；无效 id 清键 + 回落 | 管理页移除成员后刷新 |
| E5 快速连点两个部门 | 以 **最后一次** 为准；generation 丢弃中间响应 | 连点 Popover |
| E6 我的空间下误留 department 键 | personal workspace **忽略** department；API 不带参 | 切空间看 Network |
| E7 Popover 打开时切 segmented 到个人 | 关闭 Popover；清 department 上下文 | 交互试玩 |
| E8 组织树仅一个根节点 | 选择器仍显示；Popover 单节点 | 新建公司仅 Owner |

### 2.6 不做

- ❌ 用顶栏下拉替代侧栏（与 WS-2 顶栏去重原则冲突）
- ❌ 部门选择器出现在「我的空间」
- ❌ 为省事先做平铺下拉（无树）— 与 H1 无限层矛盾

---

**ORG-1-2 确认后**：~~下一节 ORG-1-3~~ → 见下。

---

## ORG-1-3 组织与部门管理页（Admin）✅ 已确认（2026-07-07）

**这节定什么**：公司 Admin / Owner **在哪建部门树、挂成员、任命部门 Admin**；与现有「成员管理 / 团队设置」怎么分工。

### 3.1 与现有九页的关系

| 页面 | 路由 | 定稿职责（ORG 后） |
|------|------|-------------------|
| **团队设置** | `/organization/settings` | **不变**：公司展示名、Owner 转让入口 |
| **成员管理** | `/organization/members` | **公司级**花名册：邀请码、加邮箱、**公司** Admin/Member、Owner 标签、移除成员 |
| **组织与部门**（新） | `/organization/departments` | **部门树** + 部门成员 + 部门 Admin 任命 + 主部门 |

侧栏（团队空间 · Owner/公司 Admin）：在「成员管理」「团队设置」**之上或之下**增加 **「组织与部门」**。

Member / 部门 Admin：**无**此导航入口；硬闯 URL → 403 → 跳概览。

### 3.2 页面布局

| 区域 | 内容 |
|------|------|
| **左栏 ~40%** | 部门树（可折叠）；根 = 公司名；节点：名称 + 子节点数 badge |
| **右栏** | 选中节点的详情：**成员表** · **新建子部门** · **重命名** · **删除**（空节点才可删） |
| **顶栏操作** | 「新建一级部门」（挂在根下） |

**部门 Admin**（非公司 Admin）：Implement ORG-2 可选 **只读树 + 仅管本节点子树成员**；ORG-1 定稿 **公司 Admin 全树写**；部门 Admin 写范围在 ORG-1-6 矩阵再锁死。

### 3.3 部门 CRUD

| 操作 | 谁 | 规则 |
|------|-----|------|
| 新建子部门 | 公司 Owner/Admin | 名称 1～64 字；`parent_id` = 选中节点；同级不重名 |
| 重命名 | 公司 Owner/Admin | 即时保存；审计 `org_unit.rename` |
| 删除 | 公司 Owner/Admin | **仅当**无子部门、无挂载资料库、无成员时；否则 **409** + 说明原因 |
| 移动节点 | P1 可选 | MVP 可先 **不做**拖拽移树；要调整 = 删建 + 人工迁库（后台） |

### 3.4 部门成员

| 操作 | 说明 |
|------|------|
| **从公司花名册添加** | 下拉选已是 `organization_members` 的用户；写入 `org_unit_members` |
| **部门角色** | `unit_admin` / `unit_member`（与 ORG-1-6 对齐） |
| **设主部门** | 用户在公司内 **恰好一个** `is_primary=true`；影响 ORG-1-2 默认 scope |
| **兼任** | 同一用户可挂多节点；侧栏 Popover 出现多选项 |
| **移出部门** | 删 `org_unit_members` 行；若为主部门且仍有其它部门 → 自动改主；若唯一部门 → 回落 **「未分配」** 池（仅 Admin 可见列表） |

**邀请码新成员**（现有流程）：注册加入公司后默认进 **「未分配」**；Admin 在组织与部门页 **指派主部门** 后才出现在 Member 侧栏选择器。

**创建团队 Owner**：注册完成时自动为 **根节点 unit_admin**（或挂「未分配」+ 提示指派 — Implement 在 plan 二选一，默认 **Owner = 全树公司 Admin，主部门 = 第一个一级部门或根**）。

### 3.5 正常流程（S）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 公司 Admin 打开组织与部门 | 左树仅根或 seed 节点；右栏空态引导「新建一级部门」 |
| S2 | 新建「研发中心」→ 其下新建「后端组」 | 树两级；选择后端组见右栏成员表空 |
| S3 | 从花名册添加李四 · 角色部门 Member · 主部门 | 李四侧栏可选研发中心/后端组（子树可见性 ORG-1-1） |
| S4 | 任命张三为「研发中心」unit_admin | 张三可建研发中心子树内资料库；**不能**改市场部树 |
| S5 | 删除空叶子「后端组」 | 204；树更新 |
| S6 | 试删有资料库的「研发中心」 | **409**「该部门下仍有资料库」 |
| S7 | 成员管理页移除某用户公司身份 | 其所有 `org_unit_members` **级联清除** |

### 3.6 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 Member 硬闯 `/organization/departments` | **403**；toast；跳 `/dashboard` | 地址栏 |
| E2 部门 Admin 硬闯 | **403**（MVP 仅公司 Admin 写树） | 部门 Admin 账号 |
| E3 删除有子节点的部门 | **409**「请先删除或移动子部门」 | 点删除 |
| E4 同级重名部门 | **409** 字段提示 | 建两个「研发部」同父 |
| E5 把用户主部门设为未加入的节点 | **400** | API 乱 POST |
| E6 用户零部门（未分配）进团队空间 | 侧栏选择器 **disabled** + Banner「请联系管理员分配部门」；**不能**建库/对话 | 新 invite 未指派 |
| E7 连点「新建子部门」 | 防抖；以成功响应为准 | 连点 |
| E8 重命名后旧 department localStorage | 若 id 未变则仍有效；删节点则 ORG-1-2 E4 对齐 | 改名/删节点 |
| E9 公司 Admin 把自己主部门删到未分配 | **允许**但 Banner 提示；Admin 仍可用 `all` scope | 边界账号 |
| E10 超长部门名 65 字 | **400** 阻止 | 表单 |

### 3.7 不做

- ❌ 在本页做资料库 CRUD（仍在资料库列表；库创建时选 **归属部门** — ORG-1-4）
- ❌ 钉钉/AD 导入组织树
- ❌ 解散公司（仍 Wave 2）

---

**ORG-1-3 确认后**：~~下一节 ORG-1-4~~ → 见下。

---

## ORG-1-4 资料库归属与跨部门 grant ✅ 已确认（2026-07-07）

**这节定什么**：建库时挂哪个部门、公司公共库怎么建、**grant** 怎么把库开放给别的部门；与列表/对话可见性（ORG-1-1）对齐。

### 4.1 资料库三种归属

| 类型 | `org_unit_id` | 谁可创建 | 默认谁可见 |
|------|---------------|----------|------------|
| **部门库** | 某 `org_unit` UUID | 该公司 **unit_admin**（该节点或祖先）· 公司 Owner/Admin | 该节点 **子树** 成员 + 公司 Admin |
| **公司公共库** | `null` | **仅**公司 Owner/Admin | 全公司 `organization_members` |
| **个人库** | —（`owner_user_id`） | 个人空间 | 仅本人（WS 不变） |

**列表 scope**：团队空间 + 当前 `department_id` 下，只列 **可见** 的部门库 + 公共库 + grant 库（ORG-1-1 表）。

### 4.2 建库 UI（资料库列表 · 新建 Dialog）

| 字段 | 规则 |
|------|------|
| 名称 / 描述 | 与现有一致 |
| **归属** | 下拉：**当前部门**（默认）· **公司公共**（仅公司 Admin+ 可选）· **指定子部门**（Admin 可选树节点；部门 Admin 仅本节点及子树） |
| Member | **无**新建入口（与 PRD 一致） |

创建 API：`POST /knowledge-bases?workspace=&department_id=` + body 含 `org_unit_id`（公共库显式 `null`）。

**已有库迁移**（Implement ORG-1）：现 `owner_org_id` 团队库默认挂 **公司公共** 或 **「未分配」虚拟节点** — plan 写 migration 策略。

### 4.3 跨部门 grant（`kb_unit_grants`）

| 字段（概念） | 说明 |
|--------------|------|
| `kb_id` | 被共享的库 |
| `grantee_type` | `org_unit` · `company`（全公司） |
| `grantee_id` | 部门 UUID；全公司时 null |
| `permission` | MVP：**read**；P1 可选 **write**（部门 Admin 授权写） |

**管理入口**：资料库详情 · **设置/共享** 面板（Admin / 该库归属部门的 unit_admin）。

| 操作 | 谁 |
|------|-----|
| 添加 grant「全公司只读」 | 库归属部门的 unit_admin+ 或公司 Admin |
| 添加 grant「市场部只读」 | 同上 |
| 撤销 grant | 同上 |
| Member | **无** grant 管理入口 |

**可见性合并**：用户可见库 = 本部门子树库 ∪ 公共库 ∪ grant 目标含「本人当前部门或祖先或 company」的库。

### 4.4 正常流程（S）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 研发 unit_admin 建库 · 归属「研发中心」 | 研发 Member 列表可见；市场 Member **不可见** |
| S2 | 公司 Admin 建库 · 选「公司公共」 | 全公司 Member 任意部门上下文可见 |
| S3 | 人事 Admin 对「员工手册」加 grant 全公司 read | 研发 Member 对话可检索该库 |
| S4 | 人事 Admin 撤销 grant | 研发 Member 列表与对话**不再**命中该库 |
| S5 | 研发 Admin 试 grant 市场部的库 | **403**（只能 grant **自己有权 admin 的库**） |
| S6 | 编辑库 · 改归属部门 | 公司 Admin 或原/新部门 unit_admin；**有 grant 时 toast 提示**关联部门可见性会变 |
| S7 | 删部门前仍有库 | ORG-1-3 S6：**409**；须先迁库或删库 |

### 4.5 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 Member 建库 / 选公共 | **无 UI**；API → **403** | member 账号 |
| E2 硬闯 POST 库 · `org_unit_id=兄弟部门` | **403** | curl |
| E3 grant 自己不可见的库 | **403** | 研发 Admin grant 人事库 |
| E4 重复 grant 同一目标 | **409** 或幂等 200（Implement 定一种） | 连点添加 |
| E5 库迁到另一部门后旧 grant | grant **仍有效**（按 kb_id）；可见性按新归属+grant 重算 | 改归属后跨部门验 |
| E6 公共库再 grant 全公司 | **409** 冗余或忽略 | 公共库 + grant company |
| E7 对话检索 grant 库 · 撤 grant 后 | 进行中会话：下一条不可用；历史 citation ORG-1-1 E10 | 撤 grant 后提问 |
| E8 部门 Admin 建库选「公司公共」 | **403** 或下拉无此项 | 部门 Admin 表单 |
| E9 `org_unit_id` 指向已删部门 | 建库 **400**；已有库 migration 须先清理 | API |
| E10 个人空间误带 `org_unit_id` | personal workspace **忽略** org_unit | Network |

### 4.6 不做

- ❌ 库级 ACL 到**个人**（仅部门 + company grant）
- ❌ 外部分享链接 / 匿名读
- ❌ 在本节做 grant 的批量 Excel 导入

---

**ORG-1-4 确认后**：~~下一节 ORG-1-5~~ → 见下。

---

## ORG-1-5 全链路 scope（列表/概览/搜/对话/审计）✅ 已确认（2026-07-07）

**这节定什么**：`department_id` + 可见库集合 **同一条规则** 贯穿所有读路径；避免「列表看不见、对话却能问到」的假企业级。

### 5.1 统一规则（OrgScope · 后端单源）

**输入**：`user` · `workspace` · `department_id`（含 `all` / 主部门 fallback）

**输出**：

- `visible_kb_ids`：当前上下文可读的资料库 ID 集合
- `writable_kb_ids`：可 upload/删库/删文档的集合（部门 unit_admin 子树 + 公司 Admin + grant write 若有）
- `sql_filter`：列表/聚合复用

**合并公式**（与 ORG-1-1/1-4 一致）：

```
可见库 = 当前部门子树库 ∪ 公司公共库 ∪ grant 命中库
```

**Implement**：`services/org/scope.py`（或扩 `workspace/scope.py`）；**禁止**各 service 手写 if。

### 5.2 须接 OrgScope 的链路

| # | 入口 | 行为 |
|---|------|------|
| 1 | `GET /knowledge-bases` | 只返回 `visible_kb_ids` |
| 2 | `GET /dashboard/stats` | 文档/切片/失败率/3E-6 运营指标 **按 visible 聚合** |
| 3 | `GET /search/documents`（EW-E1 · R1-2） | 文件名/正文搜 **仅 visible** |
| 4 | `POST .../chat` SSE | 检索 `WHERE kb_id IN visible`；**硬校验**路径 `kb_id` ∈ visible |
| 5 | `GET .../messages` · citation resolve | 历史消息： citation 指向不可见库 → 「无权限/不可见」非 500 |
| 6 | `GET .../documents` 分页 | 库已在 visible 内才 200 |
| 7 | `require_kb_access` | 在现有 org 校验之上 **+ unit/grant** |
| 8 | `audit_logs` 查询（P1 页） | 公司 Admin 可按 `org_unit_id` 筛；部门 Admin 仅子树 |

**不改 scope 的**：`/auth/*` · `/settings/account` · personal workspace 个人库（仍 `owner_user_id`）。

### 5.3 前端 fetch 层

| 规则 | 说明 |
|------|------|
| 团队空间 | 所有 list/stats/search API **带** `workspace` + `department_id`（存盘值） |
| 个人空间 | **不带** `department_id` |
| `department_id=all` | 仅 Admin UI 发出 |
| generation | 与 WS `workspaceGeneration` **叠加** `departmentGeneration`（ORG-1-2） |

### 5.4 正常流程（S）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 研发 Member · 部门=研发 · 资料库列表 | 无市场库 |
| S2 | 同账号 · Dashboard 统计 | 文档数与 S1 列表一致 |
| S3 | Dashboard 跨库搜「年假」 | 仅命中 visible 库文档 |
| S4 | 研发库对话 · 问手册内容 | 若手册 grant 全公司 → 有引用；未 grant 市场库内容 → 不出现 |
| S5 | 公司 Admin · `all` · 概览 | 数字 ≥ 任一单部门 |
| S6 | grant 撤销后 · 同会话再问 | 不再引用被撤库 |
| S7 | 切部门 · Network | 所有上述 API query 中 `department_id` 同步变 |

### 5.5 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 `POST chat` · body/path `kb_id=市场库` · 研发 context | **403** 或 SSE error 帧；**无 chunk 泄密** | curl + 页面 |
| E2 检索 pipeline 漏 filter | **pytest 门禁**：兄弟部门 fixture 文档 **不得**出现在 retrieval 结果 | 自动化 |
| E3 stats 与 list 数字不一致 | 视为 **P0 bug**；同 OrgScope 单测覆盖 | 对比 API |
| E4 Admin `all` 后 Member 会话 | Member **不会**继承 Admin 的 localStorage | 两浏览器 |
| E5 缓存旧部门列表 | 切部门 abort + 清空 list state | 快切部门 |
| E6 对话 history 含不可见 citation | resolve 返回不可见文案（ORG-1-1 E10） | 撤 grant / 移部门 |
| E7 跨库搜 `mode=content` SQL 绕过 | tsvector 查询 **必须** join visible_kb 子查询 | pytest C* 扩展 |
| E8 internal/re-embed CLI | 默认 **不过** OrgScope（运维）；文档注明禁止误跑跨 org | DEPLOY 注 |
| E9 pytest 基线 | ORG-1 合并后 **全量 pytest 绿** + 新增 isolation 矩阵 | CI |

### 5.6 与 3E-6 关系

Plan-3E-6 运营指标（入库成功率、7 日 retry、磁盘失败计数）在 **ORG-3 完成侧栏 scope 后**须改为 **OrgScope 聚合**；Implement 3E-6 时若 ORG 未落地可先 org 维度假全公司，**ORG-3 后补一条迁移任务**（research 已记）。

### 5.7 不做

- ❌ 仅改前端 hide 兄弟部门库、后端不拦
- ❌ 对话「超级管理员偷看」后门
- ❌ 本波做 audit 完整 UI（只定 API filter 规则）

---

**ORG-1-5 确认后**：~~ORG-1-6~~ → 见下。

---

## ORG-1-6 角色权限矩阵 ✅ 已确认（2026-07-07）

**这节定什么**：公司级 + 部门级角色对各页面/API 的允许/禁止；Implement 与 pytest 对照表。

### 6.1 角色一览

| 角色 | 来源 | 范围 |
|------|------|------|
| **Owner** | `organization_members.is_owner` | 全公司 |
| **公司 Admin** | `org_role=admin` 非 Owner | 全公司 |
| **公司 Member** | `org_role=member` | 公司身份；写能力看部门 |
| **部门 Admin** | `org_unit_members.role=unit_admin` | **所挂节点及子树** |
| **部门 Member** | `org_unit_members.role=unit_member` | **所挂节点及子树**（读+对话） |
| **未分配** | 无 `org_unit_members` | 仅公司身份；**不能**用团队业务功能 |

同一人可同时：公司 Member + 多部门 unit 角色。判权取 **并集**（公司 Admin 覆盖部门写；部门 Admin 不自动获得公司 Admin）。

### 6.2 页面 / 导航

| 路由 | Owner | 公司 Admin | 公司 Member | 部门 Admin | 部门 Member | 未分配 |
|------|-------|------------|-------------|------------|-------------|--------|
| `/dashboard` 团队 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Banner |
| `/knowledge-bases` | ✅ | ✅ | ✅ 可见库 | ✅ 可见库 | ✅ 可见库 | ❌ 空+Banner |
| 建库 Dialog | ✅ | ✅ | ❌ | ✅ 子树 | ❌ | ❌ |
| 公司公共库 | ✅ 建 | ✅ 建 | 读 | 读 | 读 | ❌ |
| `/organization/departments` | ✅ | ✅ | ❌ | ❌ MVP | ❌ | ❌ |
| `/organization/members` | ✅ 管理 | ✅ 管理 | 只读花名册 | 只读 | 只读 | 只读 |
| `/organization/settings` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 部门选择器 · 全公司 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| grant 管理 | ✅ | ✅ | ❌ | ✅ 本库归属子树 | ❌ | ❌ |

### 6.3 资料库 / 文档 API（团队库）

图例：✅ 允许 · ❌ 403 · — 不适用

| 操作 | Owner/公司 Admin | 部门 Admin（子树库） | 部门 Member | 未分配 |
|------|------------------|----------------------|-------------|--------|
| 读库/预览/对话 | ✅ visible | ✅ visible | ✅ visible | ❌ |
| 建库（部门） | ✅ | ✅ 子树 | ❌ | ❌ |
| 建库（公共） | ✅ | ❌ | ❌ | ❌ |
| 上传/删文档 | ✅ visible 写集 | ✅ 子树写集 | ❌ | ❌ |
| 删库 | ✅ | ✅ 子树 | ❌ | ❌ |
| retry 失败文档 | ✅ | ✅ 子树 | ❌ | ❌ |
| PATCH 库名 | ✅ | ✅ 子树 | ❌ | ❌ |

**visible / 写集**：由 OrgScope 计算（ORG-1-5）；**非**全 org。

### 6.4 组织与部门 API

| 操作 | Owner | 公司 Admin | 部门 Admin | 其他 |
|------|-------|------------|------------|------|
| CRUD 部门树 | ✅ | ✅ | ❌ MVP | ❌ |
| 挂成员到部门 | ✅ | ✅ | ❌ MVP | ❌ |
| 任命 unit_admin | ✅ | ✅ | ❌ MVP | ❌ |
| 邀请码/公司成员 | ✅ | ✅ | ❌ | ❌ |
| Owner 转让 | ✅ | ❌ | — | — |

> **P1 可选**：部门 Admin 管理**本节点**成员（非 CRUD 树）— 确认后写入 plan backlog，MVP 不做的在 Implement 不暴露。

### 6.5 与 WS 旧角色映射

| 今天 | ORG 后 |
|------|--------|
| `org_admin` 能建任意团队库 | 公司 Admin：公共库 + 任意部门；**仍不能**代替 Owner 转让 |
| `org_member` 只读+对话 | 须 **有部门** + visible 库；子树内只读+对话 |
| 侧栏「成员管理」仅 admin | **不变**（公司级） |

### 6.6 乱操作 / 边界（E）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 部门 Member 调 POST 上传 | **403** | pytest + 浏览器 |
| E2 兄弟部门 unit_admin 删对方库 | **403** | 两 Admin 账号 |
| E3 公司 Member 无部门 | 团队 API **403** 或空列表+Banner | 未分配账号 |
| E4 降职：去掉 unit_admin | 下次请求 **403** 写操作 | 改角色后刷新 |
| E5 JWT 旧 org_role 与 DB 不一致 | `/me` align（现有 R2 策略） | Tab focus |
| E6 公司 Admin 非部门成员 | 仍可见 **all** scope + 全树管理 | Admin 账号 |
| E7 personal 账号 | **不**出现部门/团队写 API | personal workspace |

### 6.7 P 窗完成定义

- [x] 用户确认 ORG-1-6（2026-07-07）
- [x] PRD 索引 ORG-1-1～1-6 全 ✅
- [x] 下一：**L 关 ✅** · **I 关 ORG-5.3 ✅** · **V 关 ORG-5.4 ✅**（2026-07-07）

---

**ORG-1-6 确认后**：P 关 ✅ → 可开 **L 窗** 或并行 **3E-6 plan**。

# 工作区模型 · PRD-WS-2（9 页验收 · 分节确认）

> ⚠️ **浏览器预览请开同目录 [`workspace-prd-ws2.html`](./workspace-prd-ws2.html)**（和 `preview-register-workspace.html` 一样用 HTML）。  
> **WS-2-1 可交互预览**：[`preview-sidebar-ws2-1.html`](../preview-sidebar-ws2-1.html) ✅  
> **WS-2-2 可交互预览**：[`preview-kb-list-ws2-2.html`](../preview-kb-list-ws2-2.html) ✅  
> **WS-2-3 可交互预览**：[`preview-dashboard-ws2-3.html`](../preview-dashboard-ws2-3.html) ✅ **预览已同步**（策略 C3a/C3b + **› chevron** + T1 + [`preview-shell-v2.css`](../preview-shell-v2.css)）  
> **不要**对本文 `.md` 点「Open Preview」——会报 `file://` 安全错误。本 `.md` 仅给 Cursor / AI 编辑用。

> **签章（2026-07-05）**：**WS-2-1 §1.1.2/§1.4** · **WS-2-2** · **WS-2-3** · **WS-2-9** · 联动 **WS-1-2** ✅ — **预览 HTML + shell v2 ✅** · **排版修订（2026-07-05）**：全称入口 **Implement 用 › chevron**（行为同 Popover · `aria-label` 查看团队全称）· **Research §1～§3 ✅**

> **排版修订说明**：§1.1.2 原文「全称」文字钮 → **用户确认改为 ›**（照片/国际 SaaS 感）；seg 切换 / Popover 内容 / S8 Member 无设置链 **不变**；验收用语「点 › 开 Popover」。

> **依据**：`workspace-prd-ws1.md` ✅  
> **Implement 顺序**：W1 内核 → 本文件 §WS-2-1、WS-2-2 优先 → 其余页面

---

## WS-2-1 全局壳 · 侧栏工作区切换器 ✅ 已确认（2026-07-05 · 含 §1.1.2 策略 C + §1.4 顶栏去重）

**这节定什么**：登录后用户如何在「我的空间」与「团队空间」之间切换；哪些导航项随空间变化。

### 1.1 组件位置

| 项 | 定稿 |
|----|------|
| 位置 | 侧栏 **Brand 下方、主导航上方** |
| 形态 | 两段式切换（类似 segmented control），**不是**下拉隐藏 |
| 选项 | 始终：**我的空间**；有团队关系时：**{组织名称}**（超长省略） |
| 无团队 | 只显示「我的空间」，**不显示**灰色不可点团队项 |

#### 1.1.1 组织名过长（侧栏约 220px）

| 场景 | 定稿 |
|------|------|
| 侧栏 segmented · **团队段** | **单行**；≤18 字（约）**完整显示**；更长 → **策略 C**（去套话 + **突出核心段中间**，见 **§1.1.2**）；**禁止**仅保留前缀或纯首/尾拼接 |
| 侧栏 segmented · **「我的空间」段** | **优先完整显示**（固定 4 字，不省略）；团队段让出剩余宽度 |
| 悬停团队段 | **Tooltip** 显示组织全称（补充；**不替代** §1.1.2 Popover） |
| **点击**团队段 | **Popover**（§1.1.2）：全称换行 + **复制** + Admin **「组织设置」**链 |
| 顶栏小字（§1.4） | 侧栏 seg 可见时：**不**重复组织名；见 §1.4 **顶栏根治** |
| 组织名 **主展示位** | **侧栏 segmented 团队段**（+ §1.1.2 Popover）；Dashboard badge **不含**组织名（WS-2-3 **§3.1.1**） |
| 看全称去哪 | **点击 seg Popover**；**组织设置**（WS-2-9）完整换行展示 |
| 存储上限 | 后端 **255 字**（`organizations.name` = 展示名，WS-1-2 **§2.4**）；壳层 **不**渲染全长 inline |

**不做**：为长名改下拉切换器；侧栏内换行两行 segmented（会顶乱导航）。

#### 1.1.2 组织名展示 · 策略 C（去套话 + 品牌锚点 · ✅ 2026-07-05）

**这节定什么**：侧栏 `formatOrgLabel(name, mode=sidebar)` 怎么把长名切成可读短标签；**正常政企名**与**乱填/恶搞名**同一套函数，不崩、不 XSS。

**策略优先级**：① 用户短展示名（≤18 字原样）→ ② **策略 C 算法** → ③ Popover / 组织设置看 **存库全称**（255 字）。

##### 算法 C · 三步（Implement 单函数 + 单元测试 · 与预览/implement 同源）

| 步 | 做什么 | 白话 |
|----|--------|------|
| **C1 规范化** | `trim`；连续空白压成单空格 | 去首尾空格 |
| **C2 去套话** | 从 **核心段** `core` 剥常见前后缀（**反复**剥到不变） | 去掉「中华人民共和国」「中国」等前缀；「有限责任公司」「股份有限公司」「有限公司」等后缀 |
| **C3 壳层短标签** | **C3a 品牌锚点窗**（优先）或 **C3b 几何中心窗**（回退） | 侧栏 seg 只显示 `label`；Popover 始终存库全称 |

**C3 短标签规则**

| `core` 长度 | 侧栏显示 `label` |
|-------------|------------------|
| `core` 为空（剥套话剥光了） | **回退**用 C1 后原串 `raw`，走 C3a/C3b |
| ≤18 字 | **完整 `core`** |
| >18 字 | **`…` + 14 字窗口 + `…`**（Unicode **码点**；窗口中心见 C3a/C3b） |

**C3a 品牌锚点窗（优先）**

| 项 | 定稿 |
|----|------|
| 锚点探测 | 在 `core` 中找**首个**匹配 `/(集团\|股份\|公司\|中心\|研究院\|工作室\|分公司)/` 的索引 `cut` |
| 条件 | 若 `cut > 2`：`anchor = floor( codePoints(core[0:cut]).length / 2 )` |
| 窗口 | 码点 `[anchor-7, anchor+7)` → `label = "…" + slice + "…"` |

**C3b 几何中心窗（回退）**

| 项 | 定稿 |
|----|------|
| 何时 | C3a 无匹配（`cut ≤ 2` 或未命中） |
| 算法 | `mid = floor(len(codePoints(core)) / 2)`；取 `[mid-7, mid+7)` |

**套话表（MVP · 可扩展常量 · 最长优先）**

| 类型 | 示例 |
|------|------|
| 前缀 | `中华人民共和国`、`中国` |
| 后缀 | `有限责任公司`、`股份有限公司`、`有限公司` |

**为何不用「首 6 + 尾 6」**：显示名应突出 **品牌/业务**（多在 core 前半）；法定尾缀看 Popover 全文。

##### Popover · 全称入口（✅ 与 seg 切换分离）

| 项 | 定稿 |
|----|------|
| **切换工作区** | 点击 seg **文字区** → 行为不变（§1.2） |
| **看全称** | 团队段 **右侧独立控件**：**› chevron**（≥44px 命中区）；点击开/关 Popover · `aria-label="查看团队全称"` |
| **禁止** | 「已选团队时再点 seg 文字」才出 Popover |
| Popover 内容 | 存库全称（`word-break: break-all`）；**复制**；Admin →「组织设置」 |
| Member | 无设置链；**仍须**能开 Popover + 复制 |
| Tooltip | hover seg 可见全称（补充）；不替代 Popover |
| 无障碍 | 全称钮 `aria-expanded`；**Esc** 关闭 Popover |
| 选中态 seg | 仍显示策略 C 的 `label` |

##### 乱填 / 非正常用户（策略 C 必须过）

| # | 输入样例 | 系统怎么处理 | 你怎么验 |
|---|----------|--------------|----------|
| T1 | 255 字法定名，中间含 **「知岸科技」** | 剥套话后 `label` **须含「知岸科技」**（或核心段中间窗含该子串） | 与 **S7** 联验 |
| T2 | 仅套话：`中华人民共和国有限责任公司` | `core` 空 → 回退 `raw`；`…` 中间窗；Popover 全文 | 侧栏不空白 |
| T3 | 重复字：`啊啊啊…`×255 | 中间 14 字窗；不崩、不换行撑高 seg | Popover 全文 255 字 |
| T4 | 纯英文/数字/符号：`aaaa…` / `test_org_!!!` | 无套话可剥 → 对 `core=raw` 做中间窗 | 侧栏单行 ellipsis |
| T5 | emoji / 组合字符 | 按 **码点** 或 grapheme 切窗（Implement 用 `Intl.Segmenter` 或等价） | 不截断 surrogate 乱码 |
| T6 | 零宽字符 / 大量空格 | C1 压空白；存库仍 trim 后原值 | Popover 与库一致 |
| T7 | HTML/脚本样字符串 | **纯文本**展示；不 `innerHTML` 用户名字 | 无脚本执行 |
| T8 | 剥套话后仍 ≤18 的短恶搞名 | **完整显示** core（允许「不正常但可读」） | 不强行再加 `…` |

##### 交互边界

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| 连点「全称」钮 | Popover toggle；**不**切换工作区 | 与 **E5** debounce 不冲突 |
| 点 seg 文字切 team | 仅切换 workspace；**不**顺带开关 Popover | S2/S5 |
| Popover 开时切「我的空间」 | Popover 关闭 | 无残留浮层 |
| 复制失败 | toast「请手动选择复制」 | T7 联验 |

### 1.2 切换行为

| 行为 | 定稿 |
|------|------|
| 切换后 | 跳转到 **概览 `/dashboard`**（避免停在跨空间详情页） |
| **切换成功 toast** | **不发**（推荐）；segmented + 侧栏 + 概览数据变化即反馈。可选：「已切换到：{空间名}」——**禁止**出现 `replace`、路径、PRD 节号 |
| 持久化 | `localStorage` 记住上次工作区；刷新后恢复 |
| 默认 | 注册/登录后默认见 WS-1；无记录时：**有团队且刚注册为团队路径 → 团队**；否则 **我的空间** |
| API | 前端请求带 `workspace=personal` 或 `workspace={org_id}`（W1 后端） |

### 1.3 侧栏导航可见性

| 导航项 | 我的空间 | 团队空间 |
|--------|----------|----------|
| 概览 | ✅ | ✅ |
| 资料库 | ✅ | ✅ |
| 对话 | ✅（仅最近 **个人库**） | ✅（仅最近 **团队库**） |
| 成员管理 | ❌ 隐藏 | ✅ 仅 **admin** |
| 组织设置 | ❌ 隐藏 | ✅ 仅 **admin** |
| 账号设置 | ✅ | ✅ |

**权限**：不再用 `account_type === enterprise`；改为 **当前工作区 = 团队 && org_role === admin**（Owner 必为 admin，见 WS-1-6）。

### 1.4 顶栏 / 面包屑（根治 · ✅ 2026-07-05）

| 项 | 定稿 |
|----|------|
| 个人空间 | 顶栏 **可不显示**小字；若显示 → `当前：我的空间` |
| 团队空间 · 侧栏 seg **可见** | **禁止**单独显示 `当前：团队空间`（信息量为零）；**禁止**重复 `当前：{组织名}` |
| 团队空间 · 顶栏 **可选** | **方案 T1（推荐）**：**隐藏**顶栏 ctx 小字，仅保留页面标题「概览」等 |
| 团队空间 · 顶栏 **备选** | **方案 T2**：muted 链 `{N} 名成员 ›` → `/organization/members`（与 Zone A badge **二选一**，Implement **只选一种**） |
| 面包屑 | 暂不强制改（W1 不阻塞） |

**去重原则（全站壳层）**

| 信息 | 主载体 | 禁止 |
|------|--------|------|
| 组织展示名 | 侧栏 seg + §1.1.2 Popover | 顶栏长名复读；Dashboard badge 前缀 |
| 成员数 | Zone A badge **或** 顶栏 T2（二选一） | badge + 顶栏 **同时**显示相同「N 名成员」 |
| 工作区语境 | 侧栏 seg 选中态 | Zone A「当前工作区 · 团队空间」废话行（WS-2-3 **§3.2.1**） |

### 1.5 验收（W1 · 侧栏）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 仅个人用户登录 | 切换器只有「我的空间」 |
| S2 | 创建者/成员登录 | 可切换「我的空间 ↔ 团队」 |
| S3 | 在团队空间 | 侧栏出现成员管理/组织设置（admin） |
| S4 | 切回我的空间 | 成员管理/组织设置 **消失** |
| S5 | 切换工作区 | 进入概览；Dashboard 数据随空间变 |
| S6 | 组织名 ≥20 字（正常政企名） | 侧栏 **策略 C**（去套话 + 中间窗）；Popover 全文 | 「我的空间」仍完整 |
| S7 | 255 字极限名 · 中间含「知岸科技」 | 侧栏 `label` **含「知岸科技」**；**不是**纯「中华人民共和国…」 | Popover 255 字 + 复制 |
| S7b | 乱填名 T2～T4（见 §1.1.2） | 不崩、单行、Popover 与库一致 | 单元测试 `formatOrgLabel` |
| S8 | Member 点 **「全称」** 开 Popover | 见全称 + 复制；**无**「组织设置」链 | Admin 见设置链 |

### 1.6 乱操作与兜底（E 系列 · 企业级 fail-closed）

#### 1.6.0 三层纵深（对齐企业 SaaS，非「藏菜单就行」）

| 层 | 定稿 | 大白话 |
|----|------|--------|
| **L1 路由** | 无权限 **不挂载**目标页组件；`Navigate` **`replace`** → 安全页 + toast | 用户看不到管理页 DOM，也不闪一下 |
| **L2 前端 API** | 被拦路由 **不发**该页敏感请求；in-flight 请求带 `workspace` 序号，**过期响应丢弃** | 硬闯 URL 时 Network 里不应出现 members 列表 |
| **L3 后端** | 凡带 `workspace` / 资源 ID 的接口 **二次校验归属**；无权限 **403 JSON**（空敏感字段） | 就算改前端也拿不到数据 |

**拦截后禁止**：渲染目标页任何业务块；展示「假占位成员列表」；用上一页缓存凑管理数据。

**路由 vs API 分工（定死，不混用）**

| 场景 | 定稿 |
|------|------|
| 浏览器改 URL / 前端路由 | **`replace` → `/dashboard`**（或资源列表）+ toast；**不用** HTTP 403 页 |
| XHR / fetch | **403** + `{ detail: "…" }`；全局 interceptor → 回落 personal + 清 workspace 缓存（E3） |

**Toast 文案（三档）**：`无权限访问该页面` / `请先切换到团队工作区` / `该资源不在当前工作区` / `工作区已重置`

#### 1.6.1 守卫分工（Implement · W1）

| 守卫 | 校验 | 包住 |
|------|------|------|
| `WorkspaceGuard` | 管理类路由须 **当前工作区 = 团队** | `/organization/*` |
| `OrgAdminGuard` | `org_role === admin`（Owner 必过） | 同上 |
| `ResourceGuard` | `kb_id` / `doc_id` **∈ 当前 workspace** | 库详情、对话、预览（E6、E9） |

侧栏可见性 **≠** 安全边界；**以守卫 + API 为准**（WS-1-6）。

#### 1.6.2 E 系列验收

| # | 乱操作 | 系统怎么处理 | 禁止出现 |
|---|--------|--------------|----------|
| E1 | **Member** 地址栏打开 `/organization/members` 或 **`/organization/settings`** | L1：`replace` `/dashboard` + toast「无权限」；L2：**不请求** members/settings API | 成员邮箱、角色、邀请码 UI |
| E2 | **Owner/Admin** 在 **我的空间** 硬闯上述管理 URL | L1：须 **工作区=团队 且 admin**；否则 `replace` + toast「请先切换到团队工作区」 | 因身份 admin 跳过工作区校验 |
| E3 | `localStorage` **无效 / 失效 / 篡改** `org_id`；或 **`/me` 无 membership** | 启动 / focus：**与 `/me` 对齐** → 清 workspace 键 + 回落 personal + toast「工作区已重置」 | 静默继续用脏 team 上下文 |
| E4 | 库详情 / 对话 / 预览页 **切换工作区** | `replace` **`/dashboard`**（§1.2）；abort 未完成的详情 API | 跨空间详情停留 |
| E5 | **快速连点** segmented | debounce；以 **最后一次** 为准；同态不重复 `replace` | 多次闪跳 |
| E6 | 地址栏打开 **不属于当前 workspace** 的 `kb_id` / `doc_id`（Bookmark 硬闯） | L1：`ResourceGuard` → 列表或 `/dashboard` + toast「该资源不在当前工作区」；L3：**403** | 另一空间的库名、文档内容 |
| E7 | 切换工作区时 **旧 workspace API 仍在飞** | 请求带 `workspaceGeneration`；响应 **丢弃**过期代际 | Dashboard 数字闪错 |
| E8 | **多 Tab**：A Tab 离开团队，B Tab 仍显示团队壳 | `visibilitychange` / 定时 **`/me` 对齐**；失效走 E3 | B Tab  indefinitely 用失效 team |
| E9 | 浏览器 **后退** 到跨空间详情 / 管理页 | 路由 mount **再跑 ResourceGuard / AdminGuard**；失败同 E1/E6 | 后退绕过拦截 |
| E10 | **换账号登录**；logout | 登录成功 / logout：**清** `workspace` + **`recent-kb-id`**（按 workspace 分键见 W1） | 新用户继承旧 workspace |

**回落页数据范围**：仅展示 **当前工作区 + 当前角色** API 返回的字段。Member 在团队概览 **可见** `member_count` badge（只读数字，WS-2-3）；**不可**见管理操作与邀请码。

**后端统一**：`workspace={org_id}` 或资源不属于调用者 → **403**；前端 interceptor 与 E3 同路径回落。

---

## WS-2-2 资料库列表页 ✅ 已确认（2026-07-05）

**这节定什么**：`/knowledge-bases` 在**当前工作区**下展示哪些库、谁能新建/编辑/删除；与 WS-2-1 切换器、WS-1-6 角色如何对齐。

### 2.1 路由与数据范围

| 项 | 定稿 |
|----|------|
| 路由 | `/knowledge-bases`（侧栏「资料库」） |
| 列表 API | `GET /knowledge-bases?workspace=personal` 或 `workspace={org_id}`（W1） |
| 我的空间 | **仅** `owner_user_id = 我` 的个人库 |
| 团队空间 | **仅** `owner_org_id = 当前组织` 的团队库 |
| 禁止 | 同一列表混排个人库 + 团队库；缺 `workspace` 时不默认「全账号库」 |

**切换工作区**（沿用 WS-2-1 §1.2）：在列表页切换 segmented → **`replace` `/dashboard`**，不留在列表（避免 `?q=` 与旧空间列表串台）。

### 2.2 页面元素（当前工作区 + WS-1-6）

| 元素 | 我的空间 | 团队 · Owner/Admin | 团队 · Member |
|------|----------|-------------------|---------------|
| 标题区 | 「资料库」+ 副文案（见 §2.6） | 同左 | 同左 |
| **+ 新建资料库** | ✅ | ✅ | ❌ **不渲染** |
| 只读提示条 | — | — | 有库时 **MemberReadOnlyHint** |
| 搜索框 | 有库时显示 | 同左 | 同左（只读也可搜） |
| 卡片 · 进入 | ✅ | ✅ | ✅ |
| 卡片 · 编辑 / 删除 | ✅ | ✅ | ❌ **不渲染** |
| 卡片 meta | N 篇 · 更新时间 · 状态点 | 同左 | 同左 |
| 空态 | 可写：onboarding 三步 + 新建 CTA | 同左 | **「组织内还没有资料库」** + 联系管理员；**无**新建 CTA |

**写权限（Implement）**：`canWriteKb = (workspace===personal) \|\| (workspace===team && org_role===admin)`；Owner 与 Admin 同权（WS-1-6）。**不再**用 `account_type === enterprise` 决定团队库写权限。

### 2.3 搜索与 URL（L1 · 仅找库）

| 项 | 定稿 |
|----|------|
| 层级 | **L1 找库**（发现层三层见 [`rag-optimization-plan.md`](./rag-optimization-plan.md) §1） |
| Query | `?q=` 客户端过滤**资料库名称 / 描述**（沿用 `kb-list-utils`） |
| 作用域 | **仅**当前工作区已拉取的列表；不跨空间；**不搜文档文件名 / 正文** |
| 切换工作区 | 先跳 `/dashboard`（§2.1）；再进「资料库」时 **不带**上一空间 `?q=` |
| 无匹配 | `KbListSearchEmptyPanel` + 「清除搜索」 |
| L2 找库内文档 | **资料库详情**页搜文件名（Plan 1.7 ✅ · WS-2-4） |
| L3 跨库 / 正文 | **Plan-RAG R1**（原 Plan-10）；不在 WS-2-2 Implement |

### 2.4 验收（W1 · 列表）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 我的空间 · 有个人库 | 仅个人库卡片；有「+ 新建」 |
| S2 | 团队空间 · Owner | 仅团队库；有新建/编辑/删除 |
| S3 | 团队空间 · Member | 仅团队库；**无**新建/编辑/删除；有只读提示 |
| S4 | 个人 + 团队各有库 | 切换工作区 → 概览 → 再进列表，**库名与数量随空间变** |
| S5 | 有库 · `?q=制度` | 仅匹配**当前空间**库名/描述 |
| S6 | 团队 Member · 0 库 | 成员空态文案；无新建按钮 |
| S7 | 删库成功 | 卡片消失；清当前 workspace 的 `recent-kb-id`（W1 分键） |

### 2.5 乱操作与兜底（E 系列 · 列表页）

**纵深**：沿用 WS-2-1 §1.6.0 L1～L3；下表为**列表页特有**。

| # | 乱操作 | 系统怎么处理 | 你怎么验 |
|---|--------|--------------|----------|
| E1 | 在**列表页**切换工作区 segmented | `replace` **`/dashboard`**（WS-2-1 §1.2）；abort 列表 in-flight | 不留在 `/knowledge-bases`；旧空间列表不写入 UI |
| E2 | **Member** DevTools `POST /knowledge-bases?workspace=org_id` | L3：**403** + toast；列表不变 | DOM 无新卡片 |
| E3 | **Member** 强行触发 DELETE（DOM 被改） | L3：**403**；按钮结束 loading | 库仍在列表 |
| E4 | 脏 `localStorage` org_id 打开列表 | `/me` 对齐 → WS-2-1 **E3** 回落 personal + toast | 不展示他组织库名 |
| E5 | 列表加载中**切换工作区** | `workspaceGeneration++`；**丢弃**旧 GET（WS-2-1 E7） | 无「个人页闪团队库」 |
| E6 | `/knowledge-bases?q=<超长/特殊字符>` | 截断展示；过滤仍客户端；无匹配 → 搜索空态 | 无 XSS |
| E7 | **连点**删库确认 | 同一 `kb_id` 仅 **1 次** DELETE in-flight | 后端不双重删 404 |
| E8 | 删库后侧栏「对话」仍指旧 `recent-kb` | 清**当前 workspace** 的 recent 键；对话回落首库或 WS-2-6 空态 | 无 404 对话 |
| E9 | **后退**到切换前的 `/knowledge-bases` | mount 用**当前** workspace 重拉；不沿用 history 缓存列表 | 后退无他空间库 |
| E10 | **换账号 / logout** 后开列表 | 清 workspace + 分空间 recent（WS-2-1 E10） | 不见上一账号库 |

**交叉引用**：硬闯**详情** `kb_id` 属另一 workspace → **WS-2-1 E6**（ResourceGuard）。列表页只负责 **scope 正确的 GET**，不做 ResourceGuard。

### 2.6 文案 · 搜索边界 · RAG 优化（专业口径）

| 项 | 定稿 |
|----|------|
| **副文案** | **「整理文档集合，供 AI 带引用回答」**（Implement 替换现「…RAG 索引」） |
| **用户不直接管** | 向量 / 索引 / embedding — 上传、删文档、失败重试 = 间接维护索引 |
| **列表搜索** | 仅 **L1 库名/描述**；找文档 → 进库（L2）或 Plan-RAG **R1**（L3） |
| **持续优化** | 切片 / hybrid / rerank / golden → [`rag-optimization-plan.md`](./rag-optimization-plan.md) **R0～R5** |

**本节不做**：跨库搜文档 · 搜 PDF 正文 · 独立「索引管理页」· Rerank / 切片调参（属 Plan-RAG，非 W1 列表 scope）。

**可交互预览**：[`preview-kb-list-ws2-2.html`](../preview-kb-list-ws2-2.html)

---

## WS-2-3 概览 Dashboard ✅ 已确认（2026-07-05 · C1 + 根治增补）

**这节定什么**：登录后首页 **`/dashboard`** 在**当前工作区**下展示哪些统计、CTA、Banner；团队空间采用 **「协作透明、管理封闭」**——**所有**团队成员可见 `member_count` 与只读花名册；**管理操作**（增删改角色、邀请码、组织设置）仍 **admin only**；与 WS-2-1 切换回落、WS-2-2 列表 scope 对齐。

**已落地桥接**（Implement 时接 workspace，不重做 UI）：[`dashboard-polish-plan.md`](./dashboard-polish-plan.md) **D-1/D-2/D-3/D-4/D-7** ✅。

**花名册字段**：**Option A ✅**（2026-07-05 用户确认）— Member 只读页与 Admin 表格 **同列**：邮箱 · 昵称 · 角色 · 加入时间；无操作列、无邀请码区块。

> **↔ WS-2-1 §1.3 侧栏脚注**：Implement 时 WS-2-1 导航表须同步——团队空间下 Member 见 **「团队成员」**（非「成员管理」），Admin 见 **「成员管理」**；同路由 `/organization/members`，双 UI 模式。组织设置仍 admin only。本节为侧栏文案定稿来源。

### 3.1 路由与数据范围

| 项 | 定稿 |
|----|------|
| 路由 | `/dashboard`（侧栏「概览」；**WS-2-1 切换工作区后的默认落点**） |
| 统计 API | `GET /dashboard/stats?workspace=personal` 或 `workspace={org_id}`（W1） |
| 我的空间 | **仅**个人库及其文档 / chunk / 近 7 日对话（`owner_user_id = 我`） |
| 团队空间 | **仅**当前组织团队库及下属数据（`owner_org_id = 当前组织`） |
| 禁止 | 同一 Dashboard 混排个人 + 团队数字；缺 `workspace` 时不默认「全账号聚合」 |
| `scope` 字段 | 响应用 `personal` \| `organization` 标识当前 workspace（与现 schema 一致） |

**协作透明（team workspace · Member + Admin）**

| 字段 / 能力 | 谁返回 / 谁可用 | 谁渲染 / UI |
|-------------|-----------------|-------------|
| `member_count` | **`workspace=team`** 且用户 **∈ 当前 org**（Member + Admin） | Zone A 内联 badge **「{N} 名成员」**（**不含**组织名）→ 链 `/organization/members` |
| 花名册列表 | `GET /organization/members` **200**（Member + Admin） | 同路由；Member **只读**表格（A ✅：邮箱 · 昵称 · 角色 · 加入时间） |
| `org_name` | 前端用 `/me` 或 stats 扩展（Implement 二选一）；**仅 team workspace** | **侧栏 segmented 团队段** + Tooltip；**不**写入 Dashboard badge（去重，见 **§3.1.1**） |

#### 3.1.1 组织名 vs 成员 badge · 去重（C1 ✅）

| 位置 | 定稿 |
|------|------|
| **侧栏 segmented · 团队段** | **主展示位**：中间省略 + Popover（WS-2-1 **§1.1.2**） |
| **Dashboard Zone A · badge** | **仅** `{member_count} 名成员` + **›**（链式 affordance，§3.1.2） |
| badge Tooltip | Admin：`查看成员管理`；Member：`查看团队成员` |
| **顶栏** | WS-2-1 **§1.4 根治**（T1 隐藏 **或** T2 成员链；**不与** badge 重复） |
| **组织设置** | Admin 改 **展示名** 1～255（WS-2-9） |

**理由**：badge 宽度有限；255 字极限名时 badge 须 **始终可读成员数**（**S10** / **S11**）。

#### 3.1.2 成员 badge · 可发现性（根治 · 🟡）

| 项 | 定稿 |
|----|------|
| 文案 | `{N} 名成员` + 后缀 **›**（或 chevron icon） |
| 视觉 | **link-button** 形态（hover 下划线 / border 加深）；**禁止**静态灰 pill 无 affordance |
| 点击 | → `/organization/members`（Member 只读 / Admin 管理，同路由双模式） |
| Admin vs Member | **同 badge 外观**；Tooltip / 侧栏 nav 文案区分能力（管理封闭不变） |
| 键盘 | `Enter` / `Space` 可激活；`aria-label`：`{N} 名成员，查看团队` |

#### 3.1.3 全站组织名展示 · 统一规则（根治）

| 页面 / 区域 | 组织名 | 成员数 |
|-------------|--------|--------|
| 侧栏 seg | ✅ 中间省略 + Popover | — |
| Dashboard Zone A badge | ❌ | ✅ `{N} 名成员 ›` |
| Dashboard 顶栏 | ❌（§1.4 T1/T2） | T2 可选 |
| **成员管理 / 团队成员页**（WS-2-8） | 页标题 **「团队成员」/「成员管理」**；副标题 **仅** `{N} 人` 或 **无副标题** — **禁止** `{orgName} · N 人` |
| 组织设置（WS-2-9） | ✅ **完整展示名**换行 | 可选展示 member_count |

**管理封闭（admin only · Owner 含在内，WS-1-6）**

| 能力 | Member | Admin |
|------|--------|-------|
| 侧栏入口文案 | **「团队成员」** | **「成员管理」** |
| 邀请码 / 生成邀请 | ❌ 不展示 | ✅ |
| 添加 / 移除成员 | ❌；`POST`/`DELETE` → **403** | ✅ |
| 改角色 | ❌；`PATCH` → **403** | ✅（Owner 规则见 WS-1-6） |
| 组织设置 `/organization/settings` | ❌ L1 `replace` dashboard + toast | ✅ |
| Dashboard prefetch members | ❌ 概览 **不**预拉列表；点 badge / 侧栏再请求 | 同左 |

**写权限（CTA / Banner）**：`canWriteKb` 同 WS-2-2 §2.2（`personal \|\| (team && admin)`）；**不再**用 `account_type === enterprise` 决定 CTA。

### 3.2 页面区块（Zone A → Banner → 统计卡）

#### 3.2.1 Zone A · 去废话（根治）

| 项 | 定稿 |
|----|------|
| 标题 | 有库：「欢迎回来」；零库：onboarding 文案 |
| **删除** | 团队空间下 **不再**显示「当前工作区 · 团队空间」（与 seg 重复） |
| 个人空间 | 可选一行 mut：「个人资料库与对话」— **非必须** |
| 团队 meta | 标题行右侧：**badge** `{N} 名成员 ›`（§3.1.2） |
| 长名引导 Banner | Admin + 注册名 >80 字 → WS-1-2 **§2.5** Info Banner（在 Zone A **上方**） |

#### 3.2.2 统计卡 · 可点击（根治 · 非模板 Dashboard）

| 卡 | 点击目标 | 备注 |
|----|----------|------|
| 资料库 | `/knowledge-bases` | 当前 workspace scope |
| 已上传文件 | 最近库 `recent_kb_id` 详情 **或** 列表（Implement 优先 recent） | 零库 → 列表 |
| 已可提问文件 | 同上 + `?status=completed`（若详情支持） | 与 D-2 对齐 |
| 近 7 日提问 | 最近库对话 `/knowledge-bases/{id}/chat` | 零库 → 对话空态 |

| 项 | 定稿 |
|----|------|
| hover | 边框加深 + `cursor: pointer`（与 stat hover 一致） |
| 零库 | 卡仍展示 **0**；点击仍进列表 / 空态（不 disabled） |

#### 3.2.3 快捷提问 · 叙事

| 项 | 定稿 |
|----|------|
| 区块标签 | 输入框上方 mut 小字：**「向最近资料库提问」**（Implement 可省略若占高） |
| 占位符 | 有库：「例如：新人第一年年假有几天？」；零库 disabled + 「上传文档后即可提问…」 |
| 优先级 | **低于** Zone A 黑 CTA「上传文档」；发送钮 **outline**（非品牌橙实心） |

| 区块 | 我的空间 | 团队 · Owner/Admin | 团队 · Member |
|------|----------|-------------------|---------------|
| **Zone A · 欢迎** | §3.2.1 | 同左 | 同左 |
| **Zone A · CTA** | 「上传文档」「创建资料库」 | 同左 | **仅**「查看资料库」 |
| **Zone A · 团队 meta** | — | badge **「{member_count} 名成员 ›」** → **成员管理** | **同 badge** → **团队成员**（只读花名册） |
| **侧栏 · 成员入口** | — | 「成员管理」 | 「**团队成员**」 |
| **快捷提问** | §3.2.3 · 有库 + `recent_kb_id` → 对话 `?q=`（D-4） | 同左 | 同左 |
| **状态 Banner** | processing / failed / 就绪 dismiss（D-2） | 同左 | failed 副文案 **「联系管理员」**（D-2 · Plan-11/2C） |
| **统计卡 ×4** | §3.2.2 · workspace 内 · **可点击** | 同左 | 同左；**无**第 5 张「成员」卡 |
| **RAG 指标区** | 有库时展示 chunk 等（占位 metrics 沿用现站） | 同左 | 同左 |
| **recent_kb_id** | 当前 workspace 可见库内「最近活跃」库（DB-API ✅） | 同左 | 同左；零库 → CTA fallback 列表（D-1） |

**搜索边界**：Dashboard **不做** L1 库名搜索（属 WS-2-2）；**不做** L3 跨库搜（Plan-RAG **R1**，见 [`rag-optimization-plan.md`](./rag-optimization-plan.md) §1）。

### 3.3 与 WS-2-1 / WS-2-2 的衔接

| 场景 | 定稿 |
|------|------|
| 任意页切换工作区 | **`replace` `/dashboard`**（WS-2-1 §1.2）；概览 **重拉** stats；正常切换 **无 toast** |
| 切换后数字 | 须与 WS-2-2 列表 scope 一致（同 workspace 的库数 / 文档数） |
| Member 硬闯 **组织设置** | 仍走 WS-2-1 **E1** → dashboard + toast；**不**拦 `/organization/members`（只读合法） |
| Admin 硬闯管理 URL 但工作区=个人 | WS-2-1 **E2** → toast「请先切换到团队工作区」 |
| `recent_kb_id` | 按 **workspace 分上下文** 计算；删库清分键（WS-2-2 **E8**） |

### 3.4 验收（W1 · Dashboard）

| # | 操作 | 预期 |
|---|------|------|
| S1 | 我的空间 · 有个人库 | 4 张卡均为个人数据；无团队 meta；有上传/创建 CTA |
| S2 | 团队 · Owner/Admin | 4 张卡为组织数据；Zone A 见 **「N 名成员」badge**（无组织名前缀）；侧栏「成员管理」；badge / 侧栏进 `/organization/members` **管理模式** |
| S3 | 团队 · Member | 4 张卡为组织库/文档数据；**有**「N 名成员」badge；侧栏「**团队成员**」；点进只读花名册（A ✅ 四列）；CTA 仅「查看资料库」 |
| S4 | 个人与团队各有库 · 切换 segmented | 停留 `/dashboard`；数字与库名 scope **随空间变**（可先验切换器再验卡） |
| S5 | 有库 · 点「上传文档」 | 进**当前 workspace** 的 `recent_kb_id` 详情（D-1） |
| S6 | 快捷提问回车 | 进当前 workspace 最近库对话且 URL 带 `?q=`（D-4） |
| S7 | 团队 Member · 0 库 | 零库 onboarding / 空统计；**无**「创建资料库」 |
| S8 | 有 processing 或 failed | Banner 出现；点链进最近库 `?status=`（D-2/D-3；空库 + status 仍走 KB Plan-11/2.1） |
| S9 | Member 在花名册页 | 见邮箱 · 昵称 · 角色 · 加入时间；**无**移除 / 改角色 / 邀请码 UI |
| S10 | 团队 · 组织名 **255 字**（中间含品牌子串） | 侧栏 **策略 C** 含该子串；Popover 全称；badge「128 名成员 ›」 |
| S11 | 点击 badge | 进 `/organization/members`；Member 只读 / Admin 管理 |
| S12 | 点击统计卡「资料库」 | 进 `/knowledge-bases`（当前 workspace） |
| S13 | Admin · 注册名 >80 字 · 首次 Dashboard | 见 WS-1-2 **§2.5** Info Banner + 「去组织设置」 |
| S14 | Zone A | **无**「当前工作区 · 团队空间」废话行 |

### 3.5 乱操作与兜底（E 系列 · Dashboard 特有）

**纵深**：沿用 WS-2-1 §1.6.0 L1～L3；下表为**概览页特有**。

| # | 乱操作 | 系统怎么处理 | 你怎么验 |
|---|--------|--------------|----------|
| E1 | 在 **Dashboard** 切换工作区 segmented | 停留 `/dashboard`；**abort** 旧 stats GET；`workspaceGeneration++`（WS-2-1 **E7**）；**无 toast** | Network 仅新 workspace 一条 stats；数字不闪错 |
| E2 | **Member** DevTools 改 stats JSON 伪造更大 `member_count` | L2：以 **服务端原值** 渲染 badge；不持久化客户端篡改 | 刷新后恢复真值 |
| E3 | 脏 `localStorage` org_id 打开 Dashboard | `/me` 对齐 → WS-2-1 **E3** 回落 personal + toast | 不见他组织统计 |
| E4 | stats 请求 **缺 workspace** 或 workspace∉membership | L3：**403** 或 fail-closed 回落 personal（与 W1 统一）；interceptor 同 E3 | 不展示跨 org 数字 |
| E5 | Dashboard 加载中 **连点**切换 segmented | debounce；以最后一次为准（WS-2-1 **E5**） | 无多次 abort 竞态闪数 |
| E6 | **Member** `POST`/`DELETE`/`PATCH` members 或硬闯 **组织设置** | L3：**403** JSON；L1：settings → `replace` dashboard + toast | Network 无成功写操作；花名册 **GET** 仍 200 |
| E7 | 个人空间 stats 与团队 **Bookmark 旧 Tab** | focus `/me` 对齐（WS-2-1 **E8**） | 旧 Tab 不长期显示失效 team 数 |
| E8 | **后退**到切换前的 Dashboard | mount 用**当前** workspace 重拉 stats | 后退无他空间缓存数 |
| E9 | 零库 · Banner/卡外链 `?status=failed` | 进最近库详情仍 **DocumentFilterEmptyPanel**（Plan-11/2.1）；不叠 onboarding | 与 D-2 验收一致 |
| E10 | **换账号 / logout** 后开 Dashboard | 清 workspace + recent 分键（WS-2-1 **E10**） | 不见上一账号统计 |
| X2' | 255 字组织名 · 大 `member_count` | badge「N 名成员 ›」；侧栏 **策略 C** + Popover | **S7/S10/S7b** |
| X1 | 超长组织名（非 255 极限） | 侧栏中间省略；badge **不受影响** | badge 始终可见 |
| X3 | 点 seg 文字 vs 点「全称」 | seg **只**切换 workspace；「全称」**只**开 Popover | 与 §1.1.2 联验 |

**交叉引用**：硬闯 **kb/doc** URL → **WS-2-1 E6**；列表 scope → **WS-2-2 §2.1**；角色 → **WS-1-6**；花名册详情 → **WS-2-8**；侧栏文案 → **WS-2-1 §1.3**（脚注见本节开头）。

**可交互预览**：[`preview-dashboard-ws2-3.html`](../preview-dashboard-ws2-3.html)

---

## WS-2-4 ～ WS-2-8（提纲）

- WS-2-4 资料库详情  
- WS-2-5 文档预览  
- WS-2-6 对话  
- WS-2-7 账号设置（填码加入 / 离开团队）  
- WS-2-8 成员管理（邀请码 · **Owner 改角色** · 见 WS-1-6）  
  - **副标题 ✅**：**禁止** `{orgName} · {N} 人`；仅 `{N} 人` 或无副标题；组织名见侧栏 **「全称」** Popover / 组织设置  

---

## WS-2-9 组织设置 ✅ 已确认（2026-07-05 · 根治）

**这节定什么**：Admin 如何改团队展示名；长名用户如何自救；与注册 / 壳层展示闭环。

| 项 | 定稿 |
|----|------|
| 路由 | `/organization/settings`（admin only；Member → WS-2-1 **E1**） |
| 权限 | `org_role === admin`（Owner 含在内） |

### 9.1 团队展示名（MVP）

| 项 | 定稿 |
|----|------|
| 字段 | **团队显示名称**（绑定 `organizations.name`） |
| 展示 | 表单内 **完整换行**显示当前值（不 ellipsis） |
| 编辑 | 单行 input；**1～255** trim；保存 PATCH |
| Helper | 此名称显示在侧栏切换器；**建议 20 字以内** |
| 保存后 | 侧栏 seg **立即**更新；清 WS-1-2 **§2.5** long-name Banner dismiss 条件重算（≤40 字则 Banner 永不再现） |

### 9.2 法定名称（Phase 2 · 不做 MVP）

| 项 | Phase 2 |
|----|---------|
| 字段 | `legal_name` 可选 255 |
| UI | 只读 / 可编辑第二行；**不**进侧栏 seg |
| 注册 | 创建者可填两行 |

### 9.3 验收

| # | 操作 | 预期 |
|---|------|------|
| O9-1 | Admin 改展示名为「知岸科技」 | 侧栏完整显示；Popover 同值 |
| O9-2 | Admin 改展示名为 255 字 | 保存成功；侧栏 **策略 C** + Popover 全文 |
| O9-3 | 从 WS-1-2 §2.5 Banner 点「去组织设置」 | 进本页；改短后 Banner 不再出现 |
| O9-4 | Member 硬闯 URL | WS-2-1 **E1** |

### 9.4 乱操作

| # | 乱操作 | 系统怎么处理 | 你怎么验 |
|---|--------|--------------|----------|
| E9-1 | PATCH 空名 / 256 字 | **400**；表单 inline 错误 | 侧栏不变 |
| E9-2 | 连点保存 | debounce；一次 PATCH | 无重复写 |
| E9-3 | 改名的同时另一 Tab 在 Dashboard | focus `/me` 或 org 缓存失效 → 侧栏同步新名 | 无长期旧名 |

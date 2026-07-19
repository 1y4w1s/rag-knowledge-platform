# 睿阁前端设计评审 · 2026-07-15

> **基线**：dev server `localhost:5173` · 1280×900 viewport · Chrome 147
> **账号**：`demo_admin`（Owner 视角）/ `demo_member`（只读成员视角） · 亮/暗双主题
> **范围**：5 个核心页（Dashboard / KnowledgeBases / Org-Departments / Org-Members / Account-Settings）
> **截图**：`docs/frontend-rework/screenshots/` 共 20 张

---

## 一、已落地的修复（本对话前段已改，截图已验证生效）

| 改动 | 文件 | 截图证据 |
|---|---|---|
| 顶栏 scope chip `个人版`→`个人` / `团队·管理`→`管理员` / `团队·成员`→`成员` | `AppTopbar.tsx` | `admin_light_01-dashboard.png` 右上方 chip 已是「视角 · 个人」+ pill 「个人｜管理｜成员」 |
| pill 按钮同步简化 | `AppTopbar.tsx` | 同上 |
| Owner 排除「尚未分配部门」横幅 | `org-permissions.ts:19-22` | 截图未见横幅（demo_admin `is_owner: true`） |
| 暗色破口：`border-zinc-200` → `border-line2`（4 文件） | `input.tsx` / `CreateKnowledgeBaseDialog.tsx` / `EditKnowledgeBaseDialog.tsx` | `admin_dark_02-kb-list.png` 卡片描边正常，无浅灰残留 |
| `.empty-hero` 暗色渐变覆盖 | `index.css:273-280` | — |
| `SectionTitle` 提取共享 + KnowledgeBasesPage 容器/标题/aria-label 改造 | `components/common/SectionTitle.tsx` + `KnowledgeBasesPage.tsx` | `admin_light_02-kb-list.png` 资料库页已是 1180px 容器 + SectionTitle + 新建按钮在 trailing |

---

## 二、🔴 P0 必修（影响企业观感或产生歧义）

### P0-1 · `/organization/*` 与 `/settings/*` 工作区 scope 缺位
- **证据**：`admin_light_03-org-departments.png` / `04-org-members.png` / `admin_dark_03-org-departments.png`
- **症状**：demo_admin 在 `personal` workspace 直访 `/organization/departments` 等组织页：toast 提示「请先切换到团队工作区」，但页面**底图仍是 Dashboard 内容**（KPI 卡片 / 入库态势全部显示）
- **根因**：OrgDepartmentsPage / OrgMembersPage 等**没有 `if (workspace === 'personal') return <RequireTeamWorkspace />` 守卫**，组件渲染时直接 fetch → 失败 → fallback 显示 AppShell 的 Outlet 默认（Dashboard？）
- **P0 影响**：用户疑惑「我到底在哪个页面」+ 无端触发 fetch 错误（截图日志有 502/403）+ 视觉与路由不一致
- **建议**：在 4 个团队相关页（OrgDepartments / OrgMembers / OrgSettings / AccountSettings 的离开团队块）顶部包一个 `<RequireTeamWorkspace>` 组件，命中 personal 视角时显示空态「请先切换到团队工作区」+ CTA「切到团队」按钮，不再走 fetch

### P0-2 · 资料库页「面包屑 + SectionTitle」双标题
- **证据**：`admin_light_02-kb-list.png` / `member_light_02-kb-list.png` / `admin_light_05-account-settings.png`
- **症状**：顶栏下方「/ 资料库」（面包屑）和下方 SectionTitle「资料库 KNOWLEDGE BASES」**同时显示同样的中文标题**，且有英文副标
- **P0 影响**：双标题让"资料库"三个字被读两遍，违反 DESIGN.md §2「每节带 SectionTitle + aria-label」（不是双标题）+ 用户初见疑惑
- **建议**：方案 A：AppShellLayout 在 `KnowledgeBasesPage` / `AccountSettingsPage` 等已有 SectionTitle 的页面**隐藏面包屑**（AppShellLayout.tsx:62 已有 `pathname !== '/dashboard'` 守卫，可扩展黑名单）；方案 B：面包屑只显示路径第一段（`/资料库` → 空），靠 SectionTitle 承担主标题
- **建议方案 A 更稳**：在 AppShellLayout 加 `const HIDE_BREADCRUMB = ['/knowledge-bases', '/settings/account', ...]`

### P0-3 · 入库态势条零态塌缩
- **证据**：`member_dark_01-dashboard.png`（4 段全是 0）
- **症状**：`queued 0 / processing 0 / completed 0 / failed 0` 仍四等分显示 + 全部「0」标签。视觉上像「管道完好但没数据」，但实际语义是「空库，无任何文档」——应走空态
- **P0 影响**：member / 新用户首登看到的"假繁忙"管道，与"100% 入库成功率"大数字自相矛盾（成功 0 次的库说 100% 成功是误导）
- **建议**：
  - 当 `total = 0`：折叠 pipeline 条为单行 dashed 占位 + 文案「暂无入库活动，去资料库上传第一份文档吧」+ CTA
  - 同步隐藏"100% / 0.7s / 264"三个大数字（"100%" 改为 `—`）

---

## 三、🟡 P1 应修（设计一致性 / 细节）

### P1-1 · `/settings/account` 仍用 h2，未走 SectionTitle
- **证据**：`admin_light_05-account-settings.png`
- **症状**：「账号设置」h2 + tracking-[0.02em]（DESIGN §7 红线：中文禁字距）
- **建议**：改用 `<SectionTitle label="账号设置" en="ACCOUNT" />`，去掉 tracking

### P1-2 · 0 篇文档卡片的「今天更新」语义不严
- **证据**：`member_light_02-kb-list.png` 「111 / 0 篇文档 · 今天更新」
- **症状**：0 篇文档却有"今天更新"时间戳，文档不存在则更新时间无意义
- **建议**：卡片在 `document_count === 0` 时改为「空库 · 创建于 YYYY-MM-DD」

### P1-3 · 顶栏 chip 前缀「视角 ·」冗余
- **证据**：所有 20 张截图
- **症状**：chip 内容「个人 / 管理员 / 成员」已是身份描述，前缀「视角 ·」属文字噪音
- **建议**：去掉 chip 里的「视角 ·」字样，直接显示身份

### P1-4 · Dashboard 暗色下 `100%` 绿/红/黄饱和度
- **证据**：`admin_dark_01-dashboard.png` 「100% 入库成功率」偏浅绿
- **症状**：暗色背景下 #83a58e（ok 暗色 token）读起来偏弱，与 #cb6b3d 品牌色对比略乱
- **建议**：将 `--ok` 暗色值从 `#83a58e` 调到 `#9bc4a8`（更柔和），或将"100%"大数字加 1px 文字阴影

### P1-5 · 资料库卡片操作按钮层级混乱
- **证据**：`admin_light_02-kb-list.png` 卡片
- **症状**：「进入」实心 terracotta、「编辑/删除」白底文字——三种按钮风格不同层级
- **建议**：「进入」为主行动保留实心，「编辑/删除」合并为同一行的 ghost 按钮组 + hover 显示

---

## 四、🟢 P2 可延后

- **P2-1** 演示水印（侧边栏左下角"演示"）：开发态标识，prod 关闭
- **P2-2** 反馈按钮未在对话流中露出：本次范围未跑对话页
- **P2-3** 502 错误日志：截图时偶发，可能是 backend 上传 pipeline 502，需独立查（不影响视觉）
- **P2-4** member 视角 `/dashboard` 的 KPI「0/0/0」应做空态：现在还显示数字，empty 引导不够

---

## 五、未评审范围（本轮未实拍）

| 页 | 原因 | 下一轮必看 |
|---|---|---|
| `/knowledge-bases/:id`（KB 详情：文档列表/可见性/回收站） | 路由含 id，需先 list 抓 id | 重要：可见性/回收站/反馈按钮三个新接口都在这 |
| `/knowledge-bases/:id/chat`（对话） | 同上 | 重要：SSE 流、引用、反馈 UI |
| `/ask`（跨库搜） | — | 重要：搜索结果高亮 |
| `/login` | 截图未覆盖 | — |
| `/audit` | 截图未覆盖 | 重要：审计筛选增强 |

---

## 六、建议下一个对话

1. **先攻 P0-1 workspace scope guard**——这是 4 个团队页共有的根因，一个 `<RequireTeamWorkspace>` 组件能消 12 张图的问题
2. **再攻 P0-2 双标题**——改 AppShellLayout 一行
3. **再补拍 KB 详情 + 对话 + 跨库搜**——才能审"新接口是否落地"

> 整体评分：⭐⭐⭐☆☆（3/5） · Dashboard 风格已落地，团队 / 设置 / 列表页 60% 到位，**新接口（反馈/可见性/回收站/API Key）在前端是否落地尚未审计**。

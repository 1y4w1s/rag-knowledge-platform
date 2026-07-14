# 知岸 · 导航与路由外壳审计（App Shell & Routing Audit）

> **依据（真实代码）**：`AppShellLayout.tsx` / `AppSidebar.tsx` / `AppTopbar.tsx` / `sidebar-nav.tsx` / `routes/index.tsx` / `index.css`。
> **配套**：`design-system.md`（token/组件）、`redesign-scorecard.md`（评分）。
> **范围**：全站外壳（侧栏+顶栏+内容区）的一致性、激活态、透明层级、内容内距 breakout、移动抽屉。

---

## 1. 当前结构（Structure）

```
AppShellLayout  (.app-shell, h-screen, overflow-hidden, 顶部 --wash 径向光)
├─ drawer-backdrop           (z=120, 移动端)
├─ AppSidebar  (.app-sidebar, w=220px, bg=var(--surf-shell)=rgba(255,255,255,.78))
│   ├─ brand-row            知岸 (BrandMark + wordmark)
│   ├─ WorkspaceSwitcher     工作区切换
│   ├─ DepartmentPicker      部门选择
│   ├─ nav-label 导航
│   ├─ nav (flex-1)          概览 / 资料库 / 对话 / [组织与部门·成员管理·团队设置·操作审计] / 账号设置
│   └─ 账号设置 + UserAvatarMenu
└─ (col)
    ├─ AppTopbar  (.app-topbar, h=52px, bg=white/55, backdrop-blur, px-6)
    │   ├─ nav-toggle (移动)
    │   ├─ breadcrumb (override ?? handle.breadcrumb)
    │   ├─ trailing   (如「引用溯源」pill)
    │   └─ UserAvatarMenu
    └─ main  (.overflow-auto, p-6)  → <Outlet/> 各页面
```

**路由树**：`/login`（无壳）｜ `/`（→/dashboard）｜ ProtectedRoute → AppShellLayout 包裹 11 条 `shellPage` 路由（概览/对话/资料库/资料库详情/文档预览/资料库对话/账号设置/成员/部门/团队设置/审计）。

---

## 2. 审计发现（Findings）

| 编号 | 严重度 | 问题 | 根因 | 改造建议 |
|---|---|---|---|---|
| S1 | 🟠 P1 | **外壳透明度不统一**：侧栏 `rgba(255,255,255,.78)`，顶栏 `bg-white/55`（55%）。同属「壳」却一实一透，视觉权重割裂 | 两处各自硬编码不同透明度 | 统一为单一 `--c-shell`（建议 `.72`），侧栏/顶栏共用 |
| S2 | 🔴 P0 | **内容区 breakout 不一致**：`ChatPage` 用 `-m-6` + `h-[calc(100vh-3.25rem)]` 突破 `<main p-6>`，其余页尊重内距。导致 chat 下 `--wash` 被裁、与外壳节奏错位 | 聊天要"占满高度"而硬推翻内距 | 引入统一 `full-bleed` 工具（仅抹平左右/上下内距，保留 `--wash`），删除散落 `-m-6` |
| S3 | 🟡 设计 | **激活态用品牌赤陶**：侧栏激活 `nav-active-text=#CB6B3D`。与「品牌专留操作」原则表面冲突 | 激活≠状态，但未明文 | 在设计系统 §4.6 锁定：激活态**允许**品牌浅底+品牌字；状态色另算，不借品牌。已和解 |
| S4 | 🟡 一致性 | **「对话」导航指向 `/ask`，聊天实址 `/knowledge-bases/:id/chat`**：靠 `isChatNavActive` 兼容，但 AskPage 与 ChatPage 是否视觉同源待核 | 两个对话入口 | 评分环节核对 AskPage 与 ChatPage 同域一致（见 scorecard A-ask） |
| S5 | 🟡 卫生 | **侧栏顶部 Workspace/Department 与「导航」标签无分隔**：视觉连续，层级不清晰 | 缺分组描边 | 在 DepartmentPicker 下加 `--c-line` 分隔，复用 nav-label 节奏 |
| S6 | 🟡 a11y | **移动抽屉 z-index**：sidebar `open` 类需高于 `drawer-backdrop`(z=120)；当前 `--sidebar-drawer-z:120` 与 backdrop 同值，可能压不住 | z 值重合 | drawer-z 提到 `130`，确保侧栏浮于 backdrop 之上 |
| S7 | 🟢 通过 | 顶栏 breadcrumb 用 `text-muted` + `[&_b]:text-foreground`，加粗部分未用品牌——符合品牌专留规则 | — | 维持 |
| S8 | 🟢 通过 | `<main>` 语义正确、移动 `nav-toggle` 有 aria-expanded/controls | — | 维持 |

---

## 3. 统一外壳规范（Unified Shell Spec）

1. **透明壳**：侧栏与顶栏同用 `--c-shell: rgba(255,255,255,.72)` + 同款 `backdrop-blur-sm`；背后 `--wash` 光晕贯通（不被 breakout 裁切）。
2. **内容内距**：`<main>` 固定 `p-6`（24px）。需占满的页面（Chat）改用 `full-bleed` 工具类（仅去内距、保留 `--wash` 与外壳），**禁止散落 `-m-6`**。
3. **导航激活**：`--c-brand-soft` 浅底 + `--c-brand` 字 + `font-semibold` + 左 3px 赤陶短竖（与 BrandMark 同源）。其余项 `--c-ink-3`，hover `--c-surface-2`。
4. **分组**：侧栏分三段——品牌区 / 工作区区（Workspace+Department，下加 `--c-line` 分隔）/ 导航区（`导航` 小标签）/ 底部账号区。
5. **移动抽屉**：`--sidebar-drawer-z:130` > backdrop `120`；`Escape` 关闭（chat 已有，外壳层待补）。
6. **顶栏高度**：固定 52px，与 chat `calc(100vh-52px)` 对齐（用变量 `--topbar-h` 取代硬编码 `3.25rem`）。

---

## 4. 待办（同步回代码）

- 🔲 S1：把 `AppTopbar` 的 `bg-white/55` 改为 `bg-[var(--surf-shell)]`（或统一新 `--c-shell`）。
- 🔲 S2：新增 `full-bleed` 工具类，`ChatPage` 去掉 `-m-6`，改用外壳级占满。
- 🔲 S5：WorkspaceSwitcher/DepartmentPicker 下加分隔线。
- 🔲 S6：`--sidebar-drawer-z` 130。
- 🔲 S3：在 `index.css` 注释明确激活态用品牌为"允许"，避免后续误改。

> 下一页（ChatPage）预览已按本规范 §3 的「统一外壳 + full-bleed 思路」落地，供评审对照。

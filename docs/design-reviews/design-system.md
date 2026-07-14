# 知岸 · 统一设计系统（Canonical Design System）

> **定位**：本文件是「知岸」RAG 平台全站视觉与组件的**唯一事实来源（single source of truth）**。
> 它调和两套既有 token——
> ① 预览稿 `docs/*.html` 的 `:root` 变量（`--page` / `--terracotta` …）；
> ② 真实代码 `frontend/src/index.css` 的 Tailwind 主题变量（`--action` / `--nav-active-*` …）。
> 二者语义一致、仅命名不同；本文件给出**规范命名**，并在末尾提供映射表，供「预览 ↔ 代码」同步。
>
> **配套文档**：`app-shell-audit.md`（导航/外壳）、`knowledge-base-detail-design-review.md`（详情页台账）、`redesign-scorecard.md`（评分）。
> **硬规则**（沿用）：原版功能零增零减；背景统一中等暖白；状态语义统一（绿/琥珀/红）；品牌赤陶专留操作；评审稿不撒谎；响应式。

---

## 1. 设计原则（3 条）

1. **人文暖白为底，赤陶点睛**：中性暖白（`#FAFAF8`）承载信息密度，赤陶橙（`#CB6B3D`）只用于主操作与激活态，绝不被状态/背景借用。
2. **状态语义既定不可破**：完成=绿、进行中=琥珀、失败=红。任何页面不得改写。
3. **壳轻、内容重**：侧栏/顶栏用半透明外壳（`rgba(255,255,255,.78)`）后退；卡片/气泡用纯白上浮，承担视觉焦点。

---

## 2. 色彩 Token（Color）

| 规范名 | 值 | 用途 | 预览变量 | 代码变量 / Tailwind |
|---|---|---|---|---|
| `--c-page` | `#FAFAF8` | 页面底色 | `--page` | `--bg` / `bg-background` |
| `--c-surface` | `#FFFFFF` | 卡片/气泡/表面 | `--surface` | `--surf` / `bg-surface` |
| `--c-surface-2` | `#FBFAF8` | 次级表面（降级面板、输入框底） | `--surface-2` | `rgb(245 242 237/.65)` |
| `--c-shell` | `rgba(255,255,255,.72)` | 侧栏/顶栏半透明外壳（统一，禁止分裂） | （无，新增） | `--surf-shell` |
| `--c-ink` | `#1A1A1C` | 一级文字 | `--ink` | `--text` |
| `--c-ink-2` | `#54504B` | 二级文字（暖灰，贴合暖白） | `--ink-2` | `--mut-warm` |
| `--c-ink-3` | `#7A716A` | 三级/弱化文字（AA 4.6:1 ✓，暖灰） | `--ink-3` | `--mut` |
| `--c-line` | `#ECE7DF` | 描边一级 | `--line` | `--line` |
| `--c-line-2` | `#E4DDD2` | 描边二级（输入框/分区） | `--line-2` | `--line2` |
| `--c-brand` | `#CB6B3D` | 品牌 / 主操作 / 激活态 | `--terracotta` | `--action` |
| `--c-brand-hover` | `#B85A2E` | 主操作 hover | `--terracotta-hover` | `--action-hover` |
| `--c-brand-soft` | `#FFF1EA` | 品牌浅底（激活导航、主按钮浅底） | `--terracotta-soft` | `--nav-active-bg` / `--auth-selected` |
| `--c-ok` | `#5BA86E` | 状态·完成/可问答 | `--success` / `--ok-ink` | （代码现为 `#4A5D47` 需同步） |
| `--c-ok-bg` | `rgba(91,168,110,.16)` | 完成浅底 | `--ok-soft`（建议） | `--status-ok-bg` |
| `--c-ok-ink` | `#27693d` | 完成文字（深绿，AA） | `--ok-ink` | `--status-ok-text` |
| `--c-amber` | `#E8943A` | 状态·进行中/索引中 | `--amber` | （代码无，需新增） |
| `--c-amber-bg` | `rgba(232,148,58,.16)` | 进行中浅底 | `--amber-soft` | （需新增） |
| `--c-amber-ink` | `#9A5A12` | 进行中文字（AA） | `--amber-ink` | （需新增） |
| `--c-fail` | `#C24A3A` | 状态·失败/有失败（色相） | `--fail` | `--status-err-text` |
| `--c-fail-ink` | `#b23a2c` | 失败文字（深红，AA，alert 与徽章共用） | `--err-ink` | `--status-err-text` |
| `--c-fail-bg` | `rgba(194,74,58,.12)` | 失败浅底 | `--err-soft`（建议） | `--status-err-bg` |
| `--c-fail-border` | `#E8B4A0` | 失败描边/警示框 | — | `--status-err-border` |
| `--c-role` | `#5B6B8C` | 角色/身份徽章（所有者·管理员·部门角色）——非状态语义，专用中性 slate，禁止与状态色（绿/琥珀/红）或品牌赤陶混用 | （新增） | （需新增） |
| `--c-role-bg` | `rgba(91,107,140,.14)` | 角色浅底 | （新增） | （需新增） |
| `--c-role-ink` | `#3E4A63` | 角色文字（AA，深 slate） | （新增） | （需新增） |

> ⚠️ **代码同步提示**：`index.css` 现状态色偏灰绿（`--status-ok-text:#4A5D47`），与锁定规则「亮绿 `#5BA86E`」不一致。同步回代码时，`--status-ok-bg/-text` 应改为 `--c-ok-bg / --c-ok-ink` 取值，并新增琥珀对。

---

## 3. 字体 / 间距 / 圆角 / 阴影 / 动效

| 类别 | 规范 | 值 |
|---|---|---|
| 字体-正文 | `--font-sans` | 系统无衬线（`-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`） |
| 字体-标题 | `--font-serif` | 品牌衬线（`Georgia, "Songti SC", serif`）——仅登录/品牌字标用；Windows 细宋体为已知限制（H5） |
| 字号阶梯 | — | 12 / 13 / 14 / 16 / 20 / 28 px（≈ 0.75→1.75rem） |
| 间距尺度 | — | 4 / 8 / 12 / 16 / 20 / 24 / 32 px（1/2/3/4/5/6/8） |
| 圆角 | `--r` | 12px（卡片）；8px（控件）；999px（pill/头像） |
| 阴影 | `--shadow-sm / --shadow-md` | `0 1px 2px rgba(0,0,0,.04)` / `0 4px 24px rgba(0,0,0,.06)` |
| 背景 | `--wash` | 顶部椭圆径向暖光 `radial-gradient(ellipse 100% 55% at 50% 0%, rgba(245,240,235,.65), transparent 68%)` + 4% 颗粒（multiply）+ 26s 漂移；`prefers-reduced-motion` 关漂移 |
| 动效 | — | 微交互 120–160ms ease；背景漂移 `will-change:transform`；骨架脉冲尊重 reduced-motion |

---

## 4. 组件规范（Component Specs）

### 4.1 按钮 Button
| 变体 | 外观 | 用途 |
|---|---|---|
| `primary` | 实心赤陶 `#CB6B3D`，白字，hover `#B85A2E` | 主操作（新建对话、发送） |
| `outline` | 白底 + `--c-line-2` 描边，hover 浅暖底 | 次级操作（资料库详情、重试） |
| `ghost` | 透明，hover 浅暖底 | 图标/低密度操作 |
| `danger` | 红字/红描边，hover 红浅底 | 删除/归档（绝不用赤陶） |

规则：`<button>` 必须显式 `type`；焦点 `:focus-visible` 赤陶环 `ring-2`。

### 4.2 状态徽章 StatusBadge
胶囊（pill）造型，`bg=*-bg` + `color=*-ink`：
- `ok`：绿 `#5BA86E` 系 · `wait`：琥珀 `#E8943A` 系 · `err`：红 `#C24A3A` 系。
- 处理中可加 `pulse` 呼吸点（尊重 reduced-motion）。

### 4.3 输入框 Input
白底 + `--c-line-2` 描边 + 圆角 8px；focus 赤陶 `ring-2`；placeholder `--c-ink-3`；禁用降透明度。原生 `select` 一律替换为**自定义下拉**（role=listbox，键盘可达），见详情页台账 F1/F2。

### 4.4 数据表 Table
`border-collapse:separate; border-spacing:0` + 外层 `overflow:hidden` + 圆角 12px；`<th scope="col">`；表头 `--c-ink-2`（AA）；行 hover 浅暖底。

### 4.5 对话气泡 Chat Bubble
| 角色 | 对齐 | 外观 |
|---|---|---|
| 用户 | 右 | `--c-brand-soft` 浅底，`--c-ink` 字，圆角 14px，最大宽 78% |
| 助手 | 左 | 纯白卡片 `--c-surface` + `--c-line` 描边 + 柔影，圆角 14px |
- 流式光标：`chat-stream-cursor` 闪烁竖线；「正在检索…」检索态文字 `--c-ink-3`。
- 引用 chip：小号 pill，激活态赤陶描边；点击展开片段（`CitationPreview`）。
- 日期分隔：居中 `--c-ink-3` 小字 pill。
- 审批卡（编辑模式）：白卡 + 采纳(primary)/取消(outline) 按钮。

### 4.6 侧栏导航项 SidebarNavItem
- 默认：透明，`--c-ink-3` 字，hover `--c-surface-2` 底 + `--c-ink`。
- 激活：`--c-brand-soft` 浅底 + `--c-brand` 字 + `font-semibold` + 左 3px 赤陶短竖（BrandMark 同源）。

### 4.7 模式切换 AgentModeSwitcher
分段控件（segmented）：三个按钮 `快速/精准/编辑`，`role=group` + `aria-pressed`；激活 = 赤陶底白字；其余 hover 浅暖底。

### 4.8 引用溯源 Pill（顶栏 trailing）
中性暖 chip：`bg=#EFEBE6` + `text=#524A44`（**非**品牌色），圆角 pill。遵守「品牌专留操作」。

### 4.9 空态 / 加载态
- 空态：虚线壳卡片（`chat-state-empty`），标题 + 描述 + 可选 action，对齐 `kb-result-empty`。
- 加载：骨架/Spinner（`Loader2 animate-spin`），脉冲动画尊重 reduced-motion。

---

### 4.10 角色徽章 RoleBadge
- **用途**：标识**身份/权限**（所有者、管理员、成员、部门角色），**非流程状态**，绝不可借用状态色。
- **配色**：专用中性 slate `--c-role` 系（`bg=--c-role-bg` + `color=--c-role-ink`）；**禁止**使用状态色（绿/琥珀/红）或品牌赤陶。
- **造型**：与 StatusBadge 同 pill（圆角 999px，字号 12px，字重 600）。
- **反模式**：❌ 用琥珀/绿/红表示角色（破坏状态语义唯一性）。

## 5. 预览变量 ↔ 代码变量 映射表（同步用）

| 规范名 | 预览 `:root` | 代码 `index.css` | Tailwind 类 |
|---|---|---|---|
| 页面底 | `--page` | `--bg` | `bg-background` |
| 表面 | `--surface` | `--surf` | `bg-surface` |
| 外壳半透 | — | `--surf-shell` | — |
| 一级字 | `--ink` | `--text` | `text-foreground` |
| 三级字 | `--ink-3` | `--mut` | `text-muted` |
| 描边1 | `--line` | `--line` | `border-border` |
| 描边2 | `--line-2` | `--line2` | — |
| 品牌 | `--terracotta` | `--action` | `text-accent` / `bg-action` |
| 品牌hover | `--terracotta-hover` | `--action-hover` | — |
| 品牌浅底 | `--terracotta-soft` | `--nav-active-bg` | `bg-[var(--nav-active-bg)]` |
| 完成 | `--ok-ink` / `--success` | `--status-ok-text`（待改） | — |
| 进行中 | `--amber` | （缺） | — |
| 失败 | `--err-ink` / `--fail` | `--status-err-text` | — |
| 角色 | `--role` | （缺） | — |
| 角色浅底 | `--role-soft` | （缺） | — |
| 角色文字 | `--role-ink` | （缺） | — |
| 圆角 | `--r` | `--r` | `rounded-[var(--r)]` |
| 阴影 | `--shadow` | `--shadow-sm/-md` | `shadow-sm/-md` |

> **同步策略**：真实代码已在用 Tailwind 主题变量，故「规范命名」直接复用代码变量名（`--action` 等）即可；预览稿只需把 `--terracotta` 别名指向 `--action`，避免双套源头漂移。

---

## 6. 反模式（Forbidden Patterns）

- ❌ 状态色借用品牌赤陶（如「处理中」用赤陶）。
- ❌ 侧栏/顶栏用不透明纯白（破坏「壳轻」层级）。
- ❌ 原生 `<select>` / `<input type=radio>` 裸露（破坏设计系统）。
- ❌ 表格 `border-collapse:collapse` 导致圆角失效。
- ❌ 背景加粒子 / 加强光束 / 超过中等强度。
- ❌ 衬线中文标题在 Windows 走 SimSun 仍偏细（已知限制，暂接受）。

# 知岸 · 资料库详情页（KnowledgeBaseDetailPage）设计评审发现与改造台账

> **适用范围**：`frontend/src/pages/KnowledgeBaseDetailPage.tsx` 及其 11 个子组件
> （`KnowledgeBaseDetailHeader` / `DocumentSection` / `DocumentTable` / `DocumentStatusBadge` /
> `DocumentRowActions` / `DocumentListToolbar` / `DocumentStatusFilterBar` / `DocumentListPagination` /
> `DocumentUploadButton` / `KnowledgeBaseGrantsPanel` / `KnowledgeBaseDetailSkeleton`）。
> **预览文件**：`docs/knowledge-base-detail-warm-white-preview.html` / `docs/knowledge-bases-warm-white-preview.html`
> **维护规则**：每次评审后更新本表，作为"同步回代码"前的唯一事实来源。功能事实以原组件为准。
> **范围说明**：Round 1 及之前聚焦资料库**详情页**；**Round 2（2026-07-12）扩展覆盖资料库列表页 `KnowledgeBasesPage`**，将列表页对齐到详情页已锁定的设计系统（状态语义 / Token / 控件 / a11y）。

---

## 一、全站改造硬规则（已锁定，不可破）

1. **原版功能一个不留、一个不增，只做外观优化。** 改造任何页面前先读原组件，枚举其全部功能点 + 全部状态（happy / loading / empty / error / 权限变体），预览必须覆盖这些状态。
2. **背景统一为全站「中等」暖白渐变**（径向光晕 + 颗粒 + 26s 缓慢漂移，尊重 `prefers-reduced-motion`），不加粒子、不加额外渐变、不加强光束。
   - ⚠️ 注：「仅改背景、卡片原版」规则**仅锁定于登录页**；其余页面卡片的纯功能性缺陷可按"外观/结构修正"修。
3. **状态语义全站统一**：完成 = 绿 `#5BA86E`、进行中 = 琥珀 `#E8943A`、失败 = 红 `#C24A3A`；品牌赤陶 `#CB6B3D` **专留给操作**（主按钮），不被状态借用。
4. **评审稿不撒谎**：预览里的所有控件都必须"活"（或明确标注为静态）；不允许出现点了没反应的死按钮。
5. **响应式**：窄屏收光晕、关漂移、无粒子；表格/工具栏允许横向滚动。

---

## 二、设计系统 Token（当前已定）

| Token | 值 | 用途 |
|---|---|---|
| `--page` | `#FAFAF8` | 页面底色 |
| `--surface` | `#FFFFFF` | 卡片/表面 |
| `--surface-2` | `#FBFAF8` | 次级表面（降级面板） |
| `--terracotta` | `#CB6B3D` | 品牌强调 / 主操作 |
| `--terracotta-hover` | `#B85A2E` | 强调 hover |
| `--terracotta-soft` | `#FFF1EA` | 强调浅底 |
| `--ink` / `--ink-2` / `--ink-3` | `#1A1A1C` / `#54504B` / `#7A716A` | 文字三级（--ink-3 已过 AA 4.5:1） |
| `--line` / `--line-2` | `#ECE7DF` / `#E4DDD2` | 描边两级 |
| `--success` / `--amber` / `--fail` | `#5BA86E` / `#E8943A` / `#C24A3A` | 状态三色 |
| `--amber-soft` / `--amber-ink` | `rgba(232,148,58,.16)` / `#9a5a12` | 进行中浅底/字 |
| `--r` | `12px` | 圆角 |
| `--shadow` | 双层柔影 | 卡片投影 |

---

## 三、历次评审发现总表

编号前缀：**F**=功能/缺陷，**D**=设计层，**A**=可访问性/结构，**H**=卫生。

| 编号 | 严重度 | 类别 | 问题描述 | 根因 | 改造动作 | 状态 |
|---|---|---|---|---|---|---|
| F1 | 🔴 P0 | 缺陷 | 自定义下拉被 `.grants{overflow:hidden}` 裁切，菜单下半截看不见 | 圆角裁切与绝对定位弹层冲突 | 去掉 `overflow:hidden`，头部单独圆角 | ✅ 已修复 |
| F2 | 🔴 P0 | 缺陷 | 下拉嵌在 `<label>` 内，点下拉会误 toggle 单选 | label 点击冒泡到 radio | `.select` 移出 label，作兄弟节点 | ✅ 已修复 |
| F3 | 🟠 P1 | a11y | 骨架屏 `pulse` 动画不尊重 `prefers-reduced-motion` | 漏加守卫 | 补 `@media reduce` 守卫 | ✅ 已修复 |
| F4 | 🟠 P1 | a11y | 表头 `<th>` 文字对比度 ≈3.8:1 不达标 AA | 浅底压浅米 | `--ink-3`→`--ink-2` 提至 ~7.3:1 | ✅ 已修复 |
| F5 | 🟠 P1 | 正确性 | `添加共享` 按钮在 `<form>` 内缺 `type`，默认 submit | 漏写 type | 加 `type="button"` | ✅ 已修复 |
| F6 | 🟠 P1 | 一致性 | 失败-只读文件名是深色加粗（像链接却不可点） | 与处理中行"不可点"外观不统一 | 补 `muted` 类 | ✅ 已修复 |
| F7 | 🟠 P1 | 交互 | 分页「跳转」按钮是死按钮 | 未绑 handler | 接 JS（后升级为 pager 控制器） | ✅ 已修复 |
| D1 | 🟠 设计 | 视觉权重 | 共享面板与文档表同权重，抢戏、切断主轴 | 同 border+shadow | 降级：浅边框+off-white+紧凑内距 | ✅ 已修复 |
| D2 | 🟠 设计 | 色彩语义 | 「处理中」用品牌赤陶，与主按钮撞色 | 状态借用了品牌色 | 改琥珀 `#E8943A` | ✅ 已修复 |
| D3 | 🟠 设计 | 布局 | 工具栏未给筛选态留位，筛选条无家可归 | 布局没预留 | 筛选条入工具栏（→ 引入 D4） | ✅ 已修复 |
| D4 | 🔴 设计 | 逻辑矛盾 | **筛选条默认显示"正在筛选：处理中"，但表格是混合状态** | 把 specimen 搬进主路径当默认 | 默认隐藏，由「高级筛选」唤出 | 🔲 本轮修 |
| D5 | 🔴 设计 | 视觉 | 表格是方角，`border-collapse:collapse` 使 `border-radius` 失效 | collapse 模式不圆角 | 改 `separate`+`border-spacing:0` | 🔲 本轮修 |
| D6 | 🟠 设计 | 字体 | 衬线标题 `Georgia,"Songti SC"` 中文落宋体，Windows 屏显发虚 | 无中文字形回退到细宋体 | 调整字体栈（仍偏细，见 H5） | 🔲 本轮修 |
| D7 | 🟠 设计 | 注释 | 徽章注释写"处理中=赤陶"，实为琥珀 | 改动未同步注释 | 改正注释 | 🔲 本轮修 |
| A1 | 🟠 a11y | 结构 | `<div class="grant-list">` 直接包 `<li>`，无效 HTML | 误用 div | 改 `<ul>` | 🔲 本轮修 |
| A2 | 🟠 交互 | 死控件 | 排序 pill 点了不切箭头/不切换 active | 未绑 handler | 接 JS：单 active + 箭头翻转 | 🔲 本轮修 |
| A3 | 🟠 交互 | 死控件 | 「高级筛选」按钮无反应 | 未绑 handler | 接 JS：唤出筛选条 | 🔲 本轮修 |
| A4 | 🟡 a11y | 可访问名 | 搜索框只有 placeholder，屏幕阅读器读不出用途 | 缺 aria-label | 加 `aria-label="搜索文件名"` | 🔲 本轮修 |
| A5 | 🟡 a11y | 标签关联 | 「跳至」`<label>` 无 `for` | 漏写 for | 加 `for` + input `id` | 🔲 本轮修 |
| A6 | 🟡 a11y | 状态跟随 | 分页「上一页/下一页」禁用态写死，不随当前页 | 未联动 | pager 控制器统一 disable | 🔲 本轮修 |
| A7 | 🟡 a11y | 地标 | 整页是 `<div class="page">`，缺 `<main>` | 误用 div | 改 `<main>` | 🔲 本轮修 |
| A8 | 🟡 a11y | 焦点环 | `.fname` 链接无 `:focus-visible` 赤陶环 | focus 规则未覆盖 | 并入 focus 规则 | 🔲 本轮修 |
| H1 | 🟡 卫生 | 换行 | 超长**英文**文件名无 `overflow-wrap:anywhere` | 漏写 | 加 `overflow-wrap:anywhere` | 🔲 本轮修 |
| H2 | 🟡 卫生 | 死样式 | `.btn-blocked` 定义从未使用 | 遗留 | 删除 | 🔲 本轮修 |
| H3 | 🟡 卫生 | 颜色统一 | 失败红两处（`--fail` 与徽章 `#b23a2c`）不统一 | 写死 | 抽 `--err-ink` 变量 | 🔲 本轮修 |
| H4 | 🟡 卫生 | 键盘导航 | 自定义下拉无键盘上下键选择 | 仅点击 | **已知限制**（代码中 Radix 已处理，预览范围不补） | ⏸ 已知限制 |
| H5 | 🟡 卫生 | 字体 | 中文衬线在 Windows 仍是 SimSun，偏细 | 系统字体所限 | 已知限制；如需更稳可改无衬线加粗 | ⏸ 已知限制 |
| R1-1 | 🟠 P1 | 可维护性 | 红/绿颜色散落 4 处字面量（#C24A3A/#b23a2c/#9a4a2e/#27693d），改主题色要改多处 | token 定义了但组件内未落地 | 抽 `--ok-ink`/`--err-ink` 统一；删除 `--err-text` 字面量，alert 改引用 `--err-ink` | ✅ 本轮修 |
| R1-2 | 🟠 P1 | UX | 共享面板默认展开，文档表被压到首屏下 | 预览为展示功能选了展开态 | 主路径默认收起（`display:none`+“展开”文案），toggle 仍可用 | ✅ 本轮修 |
| R1-3 | 🟡 P2 | 性能 | 背景动画层未提升，长会话轻量掉帧 | 缺 `will-change` | `body::after` 加 `will-change:transform` 提升合成层 | ✅ 本轮修 |
| R1-4 | 🟡 P2 | 可访问性 | 数据表 `<th>` 缺 `scope="col"` | 漏写 | 7 个表头加 `scope="col"` | ✅ 本轮修 |
| R1-5 | 🟡 P2 | 可访问性 | 自定义下拉非完整键盘可达 listbox | 预览仅点击 | 维持已知限制（代码层 Radix 已处理） | ⏸ 已知限制 |
| R2-1 | 🔴 P0 | 一致性 | 列表页「索引中/处理中」徽章用品牌赤陶 `--terracotta`，违反硬规则#3（进行中=琥珀） | 列表页建于锁定 amber 规则之前，未同步 | 列表页状态色改为 `--amber-ink`/`--amber-soft`；详情页为基准 | ✅ 本轮修 |
| R2-2 | 🟠 P1 | 一致性 | 列表页排序仍为原生 `<select>`，详情页已换自定义 | 列表页控件未统一 | 列表页排序换自定义 `.select`（同款 CSS/JS） | ✅ 本轮修 |
| R2-3 | 🟠 P1 | 交互 | 列表页分页按钮无 JS，点了没反应（死控件） | 未绑 handler | 接 pager 控制器（prev/next/页码联动+禁用态） | ✅ 本轮修 |
| R2-4 | 🟡 P2 | 可维护性 | Token 漂移：列表 `--ink-3`(#8A8079) / `--radius` / 缺 `will-change` / alert 写死红 / 徽章亮绿亮红 / 标题字体栈顺序 | 两页 token 各自一套 | 统一 `--ink-3`/`--r`/`--ok-ink`/`--err-ink`/`--amber-*`/`--err-*` + `will-change` + `--serif` | ✅ 本轮修 |
| R2-5 | 🟡 P2 | a11y | 列表页搜索框缺 `aria-label`、根节点 `<div>` 非 `<main>` | 漏写/误用 | 加 `aria-label`、根节点改 `<main>` | ✅ 本轮修 |
| R2-6 | 🟡 P2 | 一致性 | 列表页空态 `solid` 边框 / 详情页 `dashed` | 两页不一致 | 列表页空态改 `dashed` 对齐详情页 | ✅ 本轮修 |
| R2-7 | 🟠 P1 | 交互 | 详情页「高级筛选」静态显示"处理中"，点了才显示，未真正可选状态（撒谎） | 把 specimen 当默认 | 高级筛选展开"完成/处理中/失败"选项；选中联动筛选条；清除复位 | ✅ 本轮修 |

---

## 四、本轮改造记录（2026-07-12）

**目标**：清掉 D4 / D5 / D6 / D7 / A1–A8 / H1–H3（D1–D3、F1–F7 已在之前轮次修复）。

- **D4 + A3 联动**：筛选条默认 `hidden`，「高级筛选」按钮唤出、点「清除筛选」隐藏 → 默认态与表格（全量混合）一致，不再自相矛盾。
- **D5**：表格 `border-collapse:separate;border-spacing:0` + 保留 `overflow:hidden` + 外层 `.table-wrap` 圆角兜底 → 真正圆角。
- **A6**：分页重构为 pager 控制器，上一页/下一页/页码/跳转统一导航，首页禁用"上一页"、末页禁用"下一页"。
- **A2**：排序 pill 单 active + 箭头方向翻转（↓/↑、A→Z/Z→A）。
- **A1**：`grant-list` div→ul，样式零影响。
- **A4/A5/A7/A8/H1/H2/H3/D6/D7**：照表落实。

**未动**：功能、状态 specimens、原生控件替换、背景系统。

---

## 五、待办 / 已知限制

- ⏸ **H4** 自定义下拉键盘导航：预览仅点击；真实代码由 Radix `Select` 提供，无需在预览补。
- ⏸ **H5** 中文衬线 Windows 偏细：如需更强可读性，后续可把品牌标题整体改无衬线加粗（需评估与登录页一致性）。
- 📌 下一页候选：对话页 `ChatPage`（消息气泡、输入框、模型选择等更多控件待统一）。

---

## 六、迭代优化循环记录（Review → Summarize → Improve → Re-review）

> 按用户要求建立的持续迭代机制：每轮先评审当前痛点、分类汇总、逐条改造、再复评，并记录改进前后变化。本台账即循环的唯一追踪载体。

### Round 1（2026-07-12，针对已完成 18 项修复的版本）

**评审维度**：性能 / 可维护性 / 可访问性 / 用户体验。
**发现**：R1-1 颜色字面量蔓延、R1-2 共享面板默认展开、R1-3 背景层未提升、R1-4 表头缺 scope、R1-5 下拉键盘可达（已知限制）。

**改进前后对照**：

| 项 | 改造前 | 改造后 |
|---|---|---|
| 红色字面量 | `#C24A3A`(删除) / `#b23a2c`(徽章) / `#9a4a2e`(alert) 三处独立 | `--fail`(删除按钮) + `--err-ink`(徽章+alert 共用) 两处 token，alert 改引用 `--err-ink` |
| 绿色字面量 | `#27693d` 写死在徽章 | 抽 `--ok-ink` token，单一来源 |
| 背景动画 | `body::after` 无 `will-change`，长会话可能重 compositing 颗粒层 | 加 `will-change:transform`，动画层独立提升 |
| 共享面板 | 主路径默认展开，文档表首屏不可见 | 默认收起（`display:none` + “展开”），toggle 仍可用，文档表成为首屏主内容 |
| 数据表 | `<th>` 无 `scope` | 7 个表头均加 `scope="col"` |
| 功能/状态 | — | 全部保留，specimens 未动 |

**复评结论**：R1-1~R1-4 已消除；R1-5 维持已知限制（代码层 Radix 覆盖）。本轮使设计系统 token 真正落地、长会话性能更稳、表格语义完整、监控台首屏优先级正确。下一轮可从两个方向继续：① 视觉层深抠（卡片信息密度、空状态插画、跨页一致性审计）；② 真实代码层可维护性/性能（见下方待办）。

### 真实代码层待办（同步回代码时处理，预览范围之外）

- 🔲 **`DocumentStatusBadge` 颜色映射**：原组件 `DOT_CLASS` 仍用 褐/赤陶/深赤陶 字面量（本轮视觉已统一为绿/琥珀/红）。同步时须将该映射改为引用设计 token（绿/琥珀/红），否则代码层会与预览脱节。
- 🔲 **设计 token 落地机制**：当前预览靠 `:root` 变量，真实代码用 Tailwind + Radix。同步时应把 `--ok-ink/--err-ink/--amber-ink` 等抽成 Tailwind theme 扩展或 CSS 变量，避免组件内再写死色值。
- 🔲 **大列表性能**：`DocumentTable` 当前 38 篇 / 6 篇分页，规模小无虞；若未来单库文档上千，需评估虚拟滚动（windowing）以防长列表重渲染卡顿。
- 🔲 **组件重渲染边界**：`KnowledgeBaseDetailPage` 任一状态变化是否引发整表重渲染，可在同步时确认用 `React.memo` / 选择器收窄订阅范围。

---

### Round 2（2026-07-12，资料库两页对齐 + 详情页筛选活化）

**评审维度**：跨页一致性（硬规则#3 状态语义 / Token 命名 / 控件形态）、交互诚实性（死控件 / 撒谎）、a11y 地标。
**发现**：R2-1 状态色违规（列表仍赤陶）、R2-2 原生 select、R2-3 死分页、R2-4 Token 漂移、R2-5 a11y、R2-6 空态边框、R2-7 详情筛选撒谎。

**改进前后对照**：

| 项 | 改造前 | 改造后 |
|---|---|---|
| 列表「处理中」徽章 | `color:var(--terracotta)` 品牌赤陶（违反规则#3） | `color:var(--amber-ink);background:var(--amber-soft)` 琥珀，与详情页一致 |
| 列表状态徽章文字 | 亮绿 `--success` / 亮红 `--fail` | 深绿 `--ok-ink` / 深红 `--err-ink`，与详情页同一 token |
| 列表排序控件 | 原生 `<select>` | 自定义 `.select`（与详情页同款，aria listbox） |
| 列表分页 | 死按钮，无 handler | pager 控制器：prev/next/页码联动，首尾禁用态 |
| 列表 alert | 写死 `rgba(194,74,58,.08/.25/.4)` | 引用 `--err-bg`/`--err-border`/`--err-ink` token |
| 列表 `--ink-3` | `#8A8079` | `#7A716A`（= 详情页） |
| 列表半径 token | `--radius`（详情用 `--r`） | 统一为 `--r` |
| 列表标题字体 | `Georgia,"Songti SC",…` | `--serif:"Songti SC","STSong","SimSun",Georgia,serif`（= 详情页） |
| 列表背景动画 | `body::after` 无 `will-change` | 补 `will-change:transform`（= 详情页 R1-3） |
| 列表 a11y | 搜索框无 `aria-label`、`<div class="page">` | `aria-label="搜索资料库"` + `<main class="page">` |
| 列表空态 | `border:1px solid` | `border:1px dashed`（= 详情页） |
| 详情高级筛选 | 静态"处理中"，点击才显示，无可选项 | 点击展开「完成/处理中/失败」选项，选中联动筛选条文案，清除筛选复位 |

**复评结论**：R2-1~R2-7 全部消除，资料库**两页**现已共享同一设计系统（状态语义 / Token / 自定义控件 / a11y 地标 / 空态）。详情页为规范基准，列表页已对齐。本轮未新增已知 P0/P1 缺陷。

**下一步候选（待用户定方向）**：
- ① 同步回代码（详情页 → 列表页；重点 `DocumentStatusBadge` 颜色映射改为 token、`KnowledgeBasesPage` 状态色 + 控件替换）；
- ② 继续迭代其余页面（AskPage / ChatPage / 设置类等）——上一轮误把 ChatPage 提前做了，用户已要求先收尾知识库，故 ChatPage 仍按"知识库收尾后"处理。

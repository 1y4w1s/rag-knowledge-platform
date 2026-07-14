# 知岸 UI 设计规范（DESIGN.md）

> **版本**：v0.1  
> **状态**：✅ **Wave 4.0 设计规范全部确认** · ✅ **Wave 4.1 前端壳已落地**（2026-07-03）  
> **下一步**：Wave 5.4 成员/组织（Wave 5.3 ✅ 账号设置改密已落地）
> **依据**：`docs/PRD.md` §5、`docs/tasks/003-feasibility.md` §4、`docs/tasks/002-plan.md` Wave 4  
> **技术栈**：React + Vite + **shadcn/ui** + Tailwind CSS  
> **最后更新**：2026-07-03（登录页赤陶橙配色落地）

---

## 确认进度

| 节 | 主题 | 状态 |
|----|------|------|
| DESIGN-1 | 定位与原则 | ✅ **L5 暖白 · 知岸品牌**（2026-07-03） |
| DESIGN-2 | 配色与字体 | ✅ **暖白 + E6 暖褐 + F4 衬线**（2026-07-03） |
| DESIGN-3 | 全局布局壳 | ✅ **220px 侧栏 · 9 页统一壳**（2026-07-03） |
| DESIGN-4 | 登录 / 注册页 | ✅ **L5 MiMo Hero 结构**（2026-07-03） |
| DESIGN-5 | Dashboard 与知识库页 | ✅ **卡片网格 + 文档表**（2026-07-03） |
| DESIGN-6 | 对话页与引用区 | ✅ **统一壳 + chip 溯源 + 空/加载/错态**（2026-07-09 G2-3.3） |
| DESIGN-7 | 组件与 shadcn 约定 | ✅ **胶囊按钮 + F4 字体 token**（2026-07-03） |

> **全部节 ✅** — 可开工 **Wave 4.1**（侧栏 + 9 路由占位）。

**可视化预览**：用浏览器打开 [`docs/design-preview.html`](design-preview.html)

| 模式 | 说明 |
|------|------|
| **全站 9 页**（默认） | L5 暖白 + E6 暖褐 · PRD 全部主路由 |
| **字体对照** | F1 / F3 / F4 AURORA 衬线 / F5 霞鹜文楷 |

**9 页 Tab**：登录 → 概览 → 知识库 → 库详情 → 文档预览 → 对话 → 账号 → 成员 → 组织

---

## DESIGN-1 定位与原则 ✅

> **定稿（2026-07-03）**：**L5 MiMo 暖白** · 品牌 **知岸** · 引用溯源为差异化招牌

**这节定什么**：知岸长什么样、和别的项目怎么区分、答辩演示时给人什么印象。

### 产品气质

| 维度 | 选择 | 大白话 |
|------|------|--------|
| 整体风格 | **企业 SaaS · 暖白知识工作台** | 像正经后台 + MiMo 式留白；不像社交 App |
| 信息密度 | **中等偏高** | Dashboard、文档列表要一眼看到数字和状态；对话页留白多一些 |
| 差异化重点 | **引用溯源可读** | 引用卡片比聊天泡泡更重要；配色不能抢引用区注意力 |
| 与 Signal 关系 | **技术可借鉴，视觉必须独立** | 不同主色、不同侧栏宽度、不同登录页结构 |

### 三参考图组合（来自 003-feasibility）

| 参考 | 用在哪 | 不用在哪 |
|------|--------|----------|
| **AURORA**（白底 + 海军蓝） | 登录/注册结构、企业组织入口 | 全站背景 |
| **智联 CRM**（玻璃拟态 + 大图） | 登录页**可选**氛围背景 | 主应用内页（影响 PDF/引用阅读） |
| **蓝企鹅家政**（侧栏 SaaS + 卡片网格） | 登录后：侧栏、知识库列表、面包屑 | 登录页 |

### 定稿组合（L5 · 2026-07-03）

| 区域 | 定稿 | 参考 |
|------|------|------|
| **登录** | L5 MiMo Hero · 大 wordmark + hero-desc + segmented Tab | [MiMo Code](https://mimo.mi.com/) |
| **主应用** | **220px** 暖白侧栏 + 顶栏面包屑 + 半透明白卡片 | preview ②～⑨ |
| **对话** | 与同站同壳 · 消息下引用 chip + 可展开预览 | preview ⑥ |

> 早期草案（AURORA 海军蓝 / 240px 侧栏）已弃，Implement 以 **DESIGN-2 token + preview** 为准。

### 硬约束（PRD / plan 不可改）

- 9 主路由 + 全局侧栏，**不砍页**
- MVP 界面 **中文**（UI i18n → P1）
- 企业版：成员管理、组织设置 **仅 admin 可见**
- 组件库：**shadcn/ui**（与 TECH-6、002-plan 一致）

### 不做

- ❌ 全站玻璃拟态 / 重背景图（抢引用阅读）
- ❌ 暗色模式默认（P1 可加；MVP 浅色）
- ❌ 复制 Signal 配色与布局
- ❌ **单字「智」+ 色块方块 Logo**（模板感强，显 Low；见下 W1～W3 替代）

### 品牌与 Wordmark ✅ 已确认（2026-07-03）

> **更名**：产品中文名 **知岸**（原「智库」）；答辩全称 **基于 RAG 的知岸系统设计与实现**（PRD §1 已同步）。  
> **无英文副标**；代码目录仍为 `rag-knowledge-platform`。

**命名气质**：像语雀——两字、有意象（知识到岸有依据），不直译「知识库系统」，不张扬。

| 项 | 定稿 |
|----|------|
| **登录页** | **L5 MiMo Hero**（见 DESIGN-4 ✅） |
| **侧栏** | **W1**：纯 Wordmark「知岸」，**全站统一 220px**（含对话页） |
| **W3 标记** | 仅 favicon / 小图标场景；**对话页不再用图标轨** |
| **对话顶栏** | 与同站：`对话 / {知识库名}` 面包屑 + 工具条（切换库 · 新建对话 · 引用溯源） |

#### Wordmark 规格（W1 / W2 共用主标）

| 项 | 值 |
|----|-----|
| 字体 | **Noto Serif SC**（标题/wordmark）· **Noto Sans SC**（正文）· Inter 数字 |
| 字重 | 标题 600～700 · 正文 400～500 |
| 字距 | 标题 `0.02em` · 正文默认 |
| 颜色 | `#18181B` |
| 登录主标字号 | **`2.5rem`（40px）/ 700** · Noto Serif SC |
| 侧栏字号 | `0.9375rem`（15px）· Noto Serif SC / 600 |
| 登录说明 | 一段 **hero-desc**（见 DESIGN-4），不用双层 tagline |

#### W3 标记（favicon / 小图标）

- 竖条 `3×20px` + 圆点 `6px`，色 `#6E6560`；象征引用锚点/页码  
- **禁止**：单字色块、emoji、AI 大脑图标

#### 品牌出现频率

| 位置 | 规则 |
|------|------|
| 浏览器标题 | `知岸` 或 `知岸 · {知识库名}` |
| 登录 | 知岸 + hero-desc 说明段 |
| 侧栏 | Wordmark 一次 · **220px 全站含对话** |
| 对话区 | 面包屑 + 工具条；引用 chip 在消息下 |
| 输入占位 | 「提问…」/「向知识库提问…」，不用「向知岸提问…」 |

---

## DESIGN-2 配色与字体 ✅

> **定稿（2026-07-03）**：A 暖白 · E6 暖褐 · **F4 AURORA 衬线字体**

### DESIGN-2-① 背景与中性色 ✅（2026-07-03）

> **定稿：方案 A · L5 暖白**（MiMo 系米白底 + 暖灰边框，preview 全站 9 页已用此套）

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg` | `#FAFAF8` | 页面底（登录 + 主界面 + 对话） |
| `--wash` | radial `rgba(245,240,235,0.65→transparent)` | 顶区暖晕（登录 Hero + `.app-shell`） |
| `--surf` | `#FFFFFF` | 卡片、输入框 |
| `--surf-glass` | `rgba(255,255,255,0.72)` + blur | 侧栏、顶栏 |
| `--text` | `#18181B` | 正文、wordmark |
| `--mut` | `#71717A` | 次要文案 |
| `--mut-warm` | `#52525B` | hero-desc、说明段 |
| `--line` / `--line2` | `#EFEAE4` / `#E8E4DF` | 分隔线、边框 |
| `--ubg` | `#F5F2ED` | 用户消息泡 |
| `--nav-on` | `#F5F2ED` | 侧栏选中 |

**不做（相对 B/C/D）**：冷灰 `#F4F4F5` 全站底 · Kimi 纯白无边框 · 企业蓝灰底。

### DESIGN-2-② 强调色 ✅（2026-07-03）

> **定稿：E6 暖褐** — 褐灰引用 + 贴 `#F5F2ED` / `#E8E4DF` 主色；主钮仍黑 `#18181B`。

| Token | 色值 | 用途 |
|-------|------|------|
| `--pri` | `#18181B` | 主按钮、登录 Tab 选中 |
| `--acc` | `#6E6560` | 引用 chip 序号圆点、W3 标记、链接强调 |
| `--acc-text` | `#524A44` | 引用 chip 文案 |
| `--acc-bg` | `#EFEBE6` | 引用 chip 底、「引用溯源」pill |
| `--status-ok-bg` | `#E5EBE3` | 文档状态「完成」（与引用色分离） |
| `--status-ok-text` | `#4A5D47` | 完成状态文案 |

备选曾见 preview 字体对照 Tab；Implement 以 **E6 暖褐** 为准。

备选对照曾见 preview **字体对照** Tab；Implement 以 **F4** 为准。

### DESIGN-2-③ 字体 ✅（2026-07-03）

> **定稿：F4 AURORA 衬线** — 标题 **Noto Serif SC**（思源宋体）+ 正文 **Noto Sans SC**

| 用途 | 字体 | 规格 |
|------|------|------|
| **登录 Hero「知岸」** | Noto Serif SC | `2.5rem` / 700 · `letter-spacing: 0.02em` |
| **页面 h2 / 知识库卡片名** | Noto Serif SC | `1.05rem`～`0.9rem` / 600 |
| **侧栏 wordmark** | Noto Serif SC | `0.9375rem` / 600 |
| **正文、表单、表格、对话** | Noto Sans SC | `0.875rem` · line-height 1.55～1.75 |
| **英文/数字** | Inter（fallback） | 与 sans 栈同排 |
| **小字/标签** | Noto Sans SC | `0.75rem`～`0.8125rem` |

**不做**：全站宋体长文 · 对话气泡内大段 serif · 表格全文 serif（难读）。

### 组件风格 ✅

| 组件 | 规则 |
|------|------|
| 主按钮 | 黑底 `#18181B` · **胶囊** `border-radius: 9999px` |
| 次按钮 | 描边 `#E8E4DF` · 胶囊 |
| 输入框（对话） | 白底 · 暖边框 · **胶囊形容器** |
| 卡片/列表 | 半透明白 `rgba(255,255,255,0.85)` · 暖边框 · 轻阴影 |
| 引用 chip | **E6 暖褐** `--acc` / `--acc-bg` |
| 字体 | 标题 `font-serif` · 正文 `font-sans`（见 DESIGN-2-③） |

### 不做

- ❌ 应用内改深海军侧栏（与 L5 暖白冲突）  
- ❌ 冷灰 `#F4F4F5` 全站底（已弃）  
- ❌ 暗色模式 MVP  

---

## DESIGN-3 全局布局壳 ✅

> **定稿（2026-07-03）** — preview **全站 9 页** 已统一

| 项 | 定稿（预览） |
|----|-------------|
| **登录后壳** | 左 **220px** 侧栏（wordmark + 导航）+ 顶栏面包屑 + 暖白内容区 |
| **对话页** | **与概览/知识库同壳**（不再单独 56px 图标轨） |
| **对话工具条** | 引用溯源 · 切换知识库 · 新建对话 |
| **个人版** | 隐藏成员、组织设置 nav |
| **引用** | 消息下方 chip + 可展开预览 |

---

## DESIGN-4 登录 / 注册页 ✅

> **定稿（2026-07-03）**：**L5 MiMo Hero 结构** · **2026-07-03 晚** 配色升级为 **人文暖白 + 赤陶橙**（仅登录/注册页，应用内仍 L5 黑灰主色）

### 赤陶橙登录页规格（Implement 按此）

| 项 | 值 |
|----|-----|
| **背景** | `#FDFBF9` + 暖杏 radial 渐变（`.auth-page` · 非纯白） |
| **主卡片** | `#FFFCFA` · **560×640px** min · 暖色多层阴影 |
| **正文** | `#332B2B`（杜绝纯黑） |
| **次要文案** | `#7A6E6A` |
| **边框/分隔** | `#EDE4DC` |
| **主行动色** | `#CB6B3D`（按钮、聚焦环、步骤圆点、单选选中） |
| **Hover 主色** | `#B85A2E` |
| **账号类型选中底** | `#FFF1EA` · Hover `scale(1.01)` |
| **Tab 容器底** | `#F5EDE8` |
| **主标** | 「知岸」`2.25rem` / **700** / Noto Serif SC |
| **hero-desc** | 居中 · max-width ~420px · `--auth-muted` |
| **Tab** | 登录 / 注册 · **注册 2 步**（① 账号凭证 ② 选择与完成） |
| **步骤条** | **细线 + 赤陶橙圆点**（非粗进度条） |
| **密码框** | 内置显示/隐藏小眼睛（登录 + 注册） |
| **密码强度** | 注册步骤 1 · 弱红 `#E05252` / 中橙 `#E8943A` / 强绿 `#5BA86E` |
| **按钮** | 主按钮 `#CB6B3D` · 圆角 10px · 次按钮描边 `--auth-line` |

**CSS 作用域**：token 定义在 `.auth-page`（`index.css`），**不修改**全局 `--pri` / 应用内主按钮。

**预览文件**：[`docs/auth-warm-orange-preview.html`](auth-warm-orange-preview.html)（定稿对照）

### 不做

- ❌ 登录页单字色块 Logo  
- ❌ 英文副标  
- ❌ 全站改赤陶橙主色（仅 auth 页）

> **应用内**：与 L5 **同系暖白 + E6 暖褐引用**（见 DESIGN-2 ✅）；登录页单独赤陶橙行动色。

### 备选（preview 仍保留对照）

L1 标准卡片 · L2 MiMo 暖白 · L3 Kimi 极简 · L4 企业分栏 · **旧 L5 黑灰主按钮**（`design-preview.html` 登录 Tab）

---

## DESIGN-5 Dashboard 与知识库页 ✅

> **定稿（2026-07-03）** — preview **② 概览 · ③ 知识库 · ④ 库详情 · ⑤ 文档预览**  
> **概览 v4.3.2（2026-07-03）** — `docs/dashboard-warm-white-preview.html` · **Implement 以此为准**（v4.3.1 归档）

### ② 概览 · v4.3.1 信息架构

| 区域 | 职责 | 规则 |
|------|------|------|
| **顶栏** | breadcrumb + **搜索 input**（⌘K） | 内容区不重复 h2 |
| **Zone A** | 欢迎 + **主/次 CTA** + 芯片 + **快捷提问** | 主按钮赤陶橙；**资料库 `<select>`** 可切换；空态 input disabled |
| **Banner** | 条件状态条 | **文件名** + 白话摘要；整理中 **indeterminate** 进度；**独占**异常详情 |
| **Health** | 系统探活 | **仅企业版管理员**；白话「服务 / 资料索引 / 问答模型」 |
| **Zone B** | 四统计卡 + **环比** | delta 仅「较上周/较上月 +N」；**不用**状态解释当 delta |
| **Zone B′** | **最近动态** | **统计下方整行**；`activities.length === 0` **不渲染**；最多 5 条、`max-height` 内滚动 |
| **Zone C** | RAG 可观测 | 可折叠；用户文案「质量报告」；**不对用户露** golden_qa |
| **Zone D** | 资料库列表 | `showKb` 就绪态必 true；卡内 **独立按钮**（非嵌套假链）；**无**与 Banner 重复 note |

**术语**：侧栏与内容区统一 **「资料库」**（路由仍为 `/knowledge-bases`）。

**去重原则**：整理中/失败 → Banner 详述；动态只保留**其他**操作；KB 卡仅文件数 + 状态点。

**账号类型**：企业版 **成员数仅在 org-chip**；不增第五统计卡；侧栏 admin 项正常 opacity。

**Banner 暖色 token**（对齐 `#CB6B3D` / `#FFF1EA`，不用系统黄/绿/红）：

| 类型 | 背景 | 边框 | 文字 |
|------|------|------|------|
| 整理中 | `#FFF1EA` | `#E8C4B0` | `#8B4513` |
| 就绪 | `#F5F2ED` | `#D4CCC4` | `#524A44` |
| 失败 | `#FFF5F0` | `#E8B4A0` | `#9A4A2E` |

**就绪 Banner dismiss spec**：`localStorage` key `dashboard-ready-banner-dismissed`；全部就绪且无异时常显一次；用户点 × 后隐藏；若再出现 processing/failed 则重置显示逻辑。

**CTA → 路由表**（v4.3，Implement 对照 `frontend/src/routes/index.tsx`）：

| 入口 | 目标路由 | 状态 |
|------|----------|------|
| 顶栏搜索 / ⌘K | `/search?q=` 或命令面板 | 🟡 Wave 5+ |
| 快捷提问 Enter | `/knowledge-bases/:recentId/chat?q=` | 🟡 |
| 快捷芯片 · 上传/建库/对话 | `/knowledge-bases/:recentId` 等 | 🟡 Wave 4.4 |
| Banner · 查看进度 / 去处理 | `?status=processing` / `failed` | 🟡 |
| 动态项 · 查看/继续/去处理 | 预览 / 对话 / 库详情 | 🟡 |
| RAG · 评估报告 | drawer 或 `/admin/evaluation` | 🟡 Wave 5+ |
| 查看全部资料库 | `/knowledge-bases` | ✅ |

**API 扩展（🟡 Implement 时）**：`recent_kb_id`、`recent_activities[]`、`rag_evaluated_at`、`GET /dashboard/health`、`member_count` / `org_name`。

### ③～⑤ 资料库相关页

| 页 | 布局要点 |
|----|----------|
| **③ 资料库列表** | `page-hd` 标题 + 「+ 新建资料库」主按钮 · **kb-grid** 卡片（名称 / 文档数 / 进入·删除） |
| **④ 库详情** | 面包屑 `资料库 / {名}` · 上传 + 开始对话 · **data-table**（文件名 / 格式 / 状态 badge） |
| **⑤ 文档预览** | 面包屑到文件名 · 左侧 PDF/文本预览区 · 右侧元信息（页码、大小） |

| 状态 badge | 色 |
|------------|-----|
| 完成 | 暖褐 `#A68B6B` 点 / 列表内 badge |
| 处理中 | 赤陶橙 `#CB6B3D` |
| 失败 | 深赤陶 `#B85A2E` + 「重试」 |

---

## DESIGN-6 对话页与引用区 ✅

> **定稿（2026-07-03）** — preview **⑥ 对话** · **G2-3.3 空/加载/错态统一（2026-07-09）**

| 项 | 规格 |
|----|------|
| **壳** | 与全站同：220px 侧栏 + 顶栏 `对话 / {资料库名}` · 桌面 **260px 历史侧栏**（G2） |
| **工具条** | 引用溯源 pill · 切换资料库 · + 新建对话 |
| **消息** | 用户泡 `#F5F2ED` · AI 块白底 · max-width ~680px 居中 · **按日 pill + 相对时间**（G2-3.2） |
| **引用 chip** | 暖褐 `#6E6560` · 序号圆点 · 文档名 + 章节页码 |
| **引用预览** | chip 下方可展开块 · 「查看原文 →」链到预览页 |
| **输入** | 底部 sticky · 胶囊容器 + 圆形发送钮（G2-3.2 UX-1） |
| **空态** | `ChatEmptyPanel` · 虚线卡片壳（对齐 `KbResultEmptyPanel`）· 消息区 / 无库 / 侧栏「暂无会话」共用 |
| **加载** | `ChatLoadingPanel` · `Loader2` + 文案 · 首屏 `ChatPageShellSkeleton` · 历史 / 侧栏列表同组件 |
| **错态** | `AlertBanner` 暖色 token · 列表 / 历史 / 流式 / 无库检查均带 **重试**（可重试时）· 非系统红 |

**组件 SSOT**：`frontend/src/components/chat/ChatEmptyPanel.tsx` · `ChatLoadingPanel.tsx` · `ChatPageShellSkeleton.tsx` · `ThreadListPanel.tsx` · `AskPage.tsx` / `ChatPage.tsx`。

Wave 5 细调：SSE 流式打字、多轮 thread、chip 点击跳预览（布局已定，交互后补）。

---

## DESIGN-7 组件与 shadcn 约定 ✅

> **定稿（2026-07-03）** — shadcn/ui + Tailwind · token 对齐 DESIGN-2

| 预览类 / 场景 | shadcn 组件 | 定制 |
|---------------|-------------|------|
| 主/次按钮 `btn-sm-pri/out` | `Button` | `rounded-full` · pri=`bg-zinc-900` |
| 登录 segmented Tab | `Tabs` | 灰底滑块 · 圆角容器 |
| 表单输入 | `Input` + `Label` | 圆角 10px · 暖边框 · **Noto Sans SC** |
| 统计 / kb 卡片 | `Card` | `bg-white/85` · 暖边框 · 标题 `font-serif` |
| 文档列表 | `Table` | 行 hover · 状态用 `Badge` · 正文 sans |
| 侧栏 nav | 自研 `AppSidebar` | 220px · wordmark **Noto Serif SC** |
| 引用 chip | 自研 `CitationChip` | E6 暖褐 · 非 shadcn 默认 |
| 对话输入 | `Input` 包在 flex 容器 | 外层 `rounded-full` + shadow |
| 成员/组织表单 | `Card` + `Input` + `Button` | 与 preview ⑦⑧⑨ 一致 |

**Tailwind 扩展**：

```js
fontFamily: {
  sans: ['"Noto Sans SC"', 'Inter', 'PingFang SC', 'sans-serif'],
  serif: ['"Noto Serif SC"', 'Songti SC', 'serif'],
},
// + DESIGN-2 CSS 变量 --bg、--line2、--acc 等
```

**不做**：深海军侧栏主题 · shadcn 默认 zinc 冷灰全站 · 暗色 mode MVP · 全站 serif 正文。

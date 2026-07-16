# 睿阁 · 前端设计系统（DESIGN.md）

> **版本**：v1.0（概览页落地验证版）
> **状态**：✅ 概览页（Dashboard / Knowledge Cockpit）已落地，构建零错误
> **来源**：本规范提炼自**当前真实代码** —— `frontend/src/index.css` 的 token 定义 + `DashboardPage` 及 `components/dashboard/*`。是本仓库后续页面重做的**对齐基线**。
> **说明**：本文档**取代**早期 `docs/DESIGN.md` 中「知岸 / 暖白 + 220px 侧栏」旧规范；品牌、配色、壳结构均已演进为下方系统。登录 / 对话 / 知识库等页须在本系统上重做对齐（尚无独立落地规范）。

---

## 0. 设计定位

**「知识驾驶舱 / Knowledge Cockpit」** —— 暖陶土（terracotta）品牌色 + 衬线大数字，把 RAG 平台的「入库 → 可信 → 活跃 → 动态」做成一屏可扫读的运营仪表盘。亮色干净中性、暗色暖棕，双主题一致。

---

## 1. 设计 Token（明暗双主题，定义在 `index.css` 的 `:root`）

### 1.1 颜色

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--bg` | `#FAFAFA` | `#16120f` | 页面底 |
| `--surf` | `#F5F5F0` | `#1f1813` | 卡片底 |
| `--surf2` | `#f7f4f0` | `#261e17` | 卡片内嵌 / 悬浮底 / 进度槽 |
| `--text` | `#1a1512` | `#ECE6DF` | 正文 / 主数字 |
| `--mut` | `#6B6560` | `#9b8f86` | 次要文案、标签 |
| `--line` | `rgba(140,100,64,.20)` | `rgba(203,107,61,.14)` | 悬停加深描边 |
| `--line2` | `rgba(140,100,64,.14)` | `rgba(236,230,223,.10)` | 卡片边框 / 分隔线 |
| `--action` | `#cb6b3d` | `#e07a45` | 主行动色（terracotta） |
| `--brand-grad` | `135° #e8824e→#cf6a3a→#b14e26` | 同 | 品牌渐变（按钮 / 强调） |
| `--ok` | `#4c7c5e` | `#83a58e` | 成功 / 健康 |
| `--warn` | `#8a7218` | `#d8c074` | 处理中 / 待关注 |
| `--info` | `#3f72b0` | `#6f97c4` | 信息 |
| `--que` | `#5b6b7c` | `#8b97a6` | 排队 |
| `--bad` | `#a8453a` | `#c06a5e` | 失败 / 异常 |
| `--trend` | `rgba(184,90,45,.12)` | `rgba(212,118,74,.18)` | 活跃度浅格 |
| `--trend-peak` | `rgba(184,90,45,.40)` | `rgba(224,122,69,.58)` | 活跃度深格 |

### 1.2 字体

- **展示型数字 / 标题**：Noto Serif SC（思源宋体），`--serif`
- **正文 / 标签**：Noto Sans SC，`--sans`
- 数字一律 `tabular-nums`

### 1.3 圆角 / 阴影 / 过渡

- 卡片 `rounded-2xl`(16px)；小徽章 `rounded-[6px]`
- 投影：`--card-shadow`（柔和）+ 顶部高光 `--top-hi`（inset）；hover 抬升 `--card-shadow-lift`
- 过渡：`--transition`（.35s，覆盖 `background-color / border-color / color / box-shadow / transform`）

---

## 2. 页面布局结构

- **容器**：`max-w-[1180px]`，`px-7 pb-16 pt-7`，水平居中。
- **纵向分节**，每节 `<section aria-label>` + `SectionTitle`（左 4px brand 竖条 → 衬线中文标题 17px / 600 → 大写英文小标 11px → 右侧 1px hr）。
- **节序**：`KPI Ribbon → 入库态势 → 可信与性能 → 活跃度 → 最近对话与动态 → 数据口径 footer`。
- **栅格**：KPI `grid-cols-2 lg:grid-cols-4`（等宽）；双栏 `md:grid-cols-2`；非对称 `md:grid-cols-[1.4fr_1fr]`；统一 `gap-3 / gap-4`。
- **三态**：loading 骨架屏（pulse）/ error（AlertBanner + 重试）/ empty（EmptyStateV44 引导去知识库）。
- **Footer 数据口径**：maxHeight 动画展开 + `aria-expanded` / `aria-controls`。

---

## 3. 数据展示范式

| 模块 | 组件 | 展示手法 |
|------|------|----------|
| KPI | `VitalCard` | 衬线 32px **bold** 数字 + `CountUp` + 左侧语义色带(3px) + 4% tint(hover→8%)；整卡可 `Link` 跳转 |
| 入库态势 | `IngestionPanel` | 左右分栏 `1.7fr_1px_1fr`：四态管道条(flex 占比，**白字保对比度**) + 图例 + mini 指标；右=存储健康键值表(zeroOk✓) |
| 可信 | `RagProofCard` | 46px ok 色大数字 + gauge 进度条 + 评估日期 |
| 性能 | `PerfTable` | 键值表：延迟 / 样本数 / 引用覆盖率 / P95 |
| 活跃度 | `ActivityChart` | 7 日日历格 heatmap + hover/focus tooltip(完整日期+次数) + 量化图例(低→高) + 7 日合计 |
| 构成 | `CompositionBar` | 格式分布进度条 + 底部汇总 |
| 动态 | `FeedList` ×2 | 图标块 + 标题/meta + 相对时间；`recent` 项左侧 brand 高亮条；空态虚线图标 |

**通用约定**：数字一律 `--serif` + `tabular-nums` + bold/semibold；缺失值统一 `—`；右上角小徽章 `rounded-[6px] border px-2 py-[3px]` 标口径（如「实时四态」「按日分桶」）；趋势按日分桶、构成按格式聚合（真实后端聚合）。

---

## 4. 交互模式

- **主题切换**（顶栏太阳图标）：`localStorage > 系统偏好(prefers-color-scheme)`；用户未手动选时跟随系统；切换用 **View Transitions API** 平滑动画（不支持则降级）。
- **悬停反馈**：卡片 hover 上浮 `-translate-y-0.5` + 边框加深 + 阴影抬升；feed 行 hover 背景变 `--surf2`。
- **焦点可见**：全局 `:focus-visible { outline: 2px solid var(--brand) }`；活动格 `ring-2 action`。
- **跳转联动**：KPI 整卡跳对应页；活动格点击跳 `/ask?date=YYYY-MM-DD`（为按日筛选留接口）。
- **可访问性**：语义 `section` / `footer`、`aria-label`、tooltip `pointer-events-none`、`prefers-reduced-motion` 全局守卫（动画时长压到 ~0）。

---

## 5. 视觉风格方向

- **暖陶土品牌**（terracotta），主色 `#cf6a3a` / action `#cb6b3d`(暗 `#e07a45`)，渐变 `--brand-grad`；语义 ok/warn/info/que/bad 用于状态。
- **「数字衬线、文字无衬线」对比美学**：展示型数字用衬线，正文/标签用无衬线。
- **卡片**：`rounded-2xl`(16px) + 1px 描边(`--line2`) + 顶部高光(`--top-hi`) + 柔和投影(`--card-shadow`)。
- **明暗双主题**：亮色=干净中性浅灰、无纸纹、中性灰阴影；暗色=暖棕黑、暖棕投影 `rgba(12,8,6,.55)`。

---

## 6. 硬约束（红线，重做必须遵守）

1. 容器 `1180px` / `px-7`；每节带 `SectionTitle` + `aria-label`。
2. 颜色全走 token（`var(--*)`），禁止硬编码（token 定义处除外）；明暗双主题必须全覆盖。
3. WCAG AA：管道白字、mut 对比度达标；全局焦点环；`prefers-reduced-motion` 守卫。
4. 数字 `tabular-nums` + 衬线；缺失值 `—`；loading/error/empty 三态齐备。
5. 数据来自真实 API `GET /api/v1/dashboard/stats`，Tier-1 主轴**无需改后端**即可上线；中文文案优先。

---

## 7. 排版规则（中文 letter-spacing 红线）

- **中文正文与标签：禁止 letter-spacing**（含 Tailwind `tracking-wide` 等）。中文字形为全宽等身，加字距会破坏均匀节奏、显得松散，与「干净」定位冲突。
- **拉丁大写英文小标**（如 `SectionTitle` 的 `en` 副标）：**可保留** `tracking-[2px]`，用于提升大写拉丁可读性 —— 这是唯一允许的 letter-spacing 场景。
- **展示型数字**：使用 `tabular-nums`，**不加** letter-spacing（保持等宽节奏）。
- 字号底线：中文不小于 12px。

---

## 8. 已知预留位（非阻断，重做时按此处理）

- 活跃度目前仅近 7 日；更长区间需扩展 `ActivityChart` 并约定粒度。
- `CompositionBar` / `PerfTable` 的「引用覆盖率 / P95 / 体积」后端尚未返回，显示 `—`，按预留位保留。

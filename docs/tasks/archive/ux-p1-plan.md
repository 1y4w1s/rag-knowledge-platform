# UX-P1 · 全站 UI/UX 精品改造 Plan

> **状态**：⏸ **搁置**（2026-07-08 · 用户优先 Eval-Ops）· L 窗已过 · 答辩 2027-05 · **dashboard compare V ✅** · kb-list compare HTML 已产出（未 V 验收）  
> **依据**：浏览器验收 2026-07-08 · `DESIGN.md` · `preview-shell-v2.css` · `dashboard-content-v4.3.2-preview.html` · **`preview-ux-p1-dashboard-compare.html`（v4.3.2-lite）**  
> **目标**：**像 deliberate product，不像 AI 模板** — 功能 P0 + 全站视觉层级 + 设计系统单源 + 375/a11y  
> **原则**：每页 **Before/After 对比预览** 过关才 Implement · WIP=1 · 一次 I 窗一条原子任务

---

## §0 做 & 不做

| 做（精品范围） | 不做（仍 Out of scope） |
|----------------|-------------------------|
| 10 路由 + 全局壳 · UX-1～8 全修 | Plan-10 **跨库搜** UI 大改 |
| **概览 v4.3.2-lite**（见 compare + `dashboard-content-v4.3.2-preview.html`） | 支付 / 积分 / OCR |
| 全站 token 单源（CSS → Tailwind/shadcn） | 换品牌名 / 换主色系 |
| 空态 / 错态 / loading / Toast 规范统一 | 一次 Implement 改完全站 |
| 375 全页回归 · focus/对比度 a11y 基线 | endless 同窗抛光（**每页 V 冻结**） |
| 10 页 + 索引 **compare 预览** | 后端 API / 权限逻辑大改 |
| 微交互（150～300ms · `prefers-reduced-motion`） | — |
| **可选 Wave F**：暗色模式（答辩前 3 个月再评估） | — |

---

## §1 痛点总览（设计师审计 · 2026-07-08）

### 1.1 功能 / 交互（必须先修）

| 级 | 代号 | 痛点 |
|----|------|------|
| **P0** | UX-1～3,6,7 | 对话输入、面包屑、退出叠层、picker 刷新、Admin 切部门 |
| **P1** | UX-4,5,8 | member toast、侧栏退出、切部门确认 |

### 1.2 视觉 / 品牌（精品必做）

| 级 | 代号 | 痛点 | 精品 TO-BE |
|----|------|------|------------|
| **V-1** | 壳层漂移 | React ≠ preview-shell-v2 | Token 单源 + 组件规格表 |
| **V-2** | 概览过密 | 10 盒堆叠 | **v4.3.2-lite**：Zone A + 四卡 + RAG 折叠 + KB 小卡 |
| **V-3** | 对话阅读 | chip 挤、留白不足 | 引用区主视觉 · 消息 rhythm |
| **V-4** | 列表/表 | 模板空态、hover 不统一 | 每页定制空态 + 统一 card/table 语法 |
| **V-5** | 错态 | raw 英文/JSON | 全站 `AppError` 中文 + 图标 |
| **V-6** | 375 | 组织/Grant/预览边缘 | 每页 compare 含窄屏 Tab |
| **V-7** | a11y | focus 弱、icon-only | 对比度 + aria + 键盘路径 |

---

## §2 五波改造策略（精品 · 2027 答辩前可从容推进）

```
Wave A 地基(P0) → Wave B 核心体验+视觉 → Wave C 企业页 → Wave D 设计系统 → Wave E 抛光+a11y
                                                      ↘ Wave F 暗色(可选)
```

| Wave | 主题 | 预览产出 | Implement | 预估 |
|------|------|----------|-----------|------|
| **A** | 壳层 + P0 可用性 | shell + chat compare | A1～A6 | 1～2 周 |
| **B** | 答辩主路径 **体验+视觉** | dashboard/kb/detail/preview/chat compare | B1～B5 | 3～4 周 |
| **C** | 登录 + 组织 + 设置 | login/members/org ×2 compare | C1～C5 | 2 周 |
| **D** | **设计系统单源** | `design-tokens-ux-p1.md` + shell v3 css | D1～D4 | 1～2 周 |
| **E** | 微交互 · 空错态 · 375 · a11y | 索引页补 E 用例 · 375 截图 | E1～E5 | 1～2 周 |
| **F** | 暗色（可选） | `preview-ux-p1-dark-compare.html` | F1 | 答辩前评估 |

**每页 V 冻结线**：TO-BE 你验收 ✅ 后，该页仅收 P0 缺陷；「更好看」进下一 Wave 或 backlog。

---

## §3 对比预览规范

### 3.1 文件清单（11 个）

| 页面 | 文件 | 精品 TO-BE 要点 |
|------|------|-----------------|
| 索引 | `preview-ux-p1-index.html` | 进度表 · 链全部 compare |
| 壳层 | `preview-ux-p1-shell-compare.html` | 侧栏菜单 · toast · picker · 375 drawer |
| 概览 | `preview-ux-p1-dashboard-compare.html` | **v4.3.2-lite ✅ V** · 无 chip · RAG 默认折叠 · KB 整卡可点 |
| 资料库 | `preview-ux-p1-kb-list-compare.html` | info 条 · 空态插画线框 |
| 库详情 | `preview-ux-p1-kb-detail-compare.html` | sticky 表头 · Grant 摘要 |
| 预览 | `preview-ux-p1-doc-preview-compare.html` | z-index · 窄屏 stack |
| 对话 | `preview-ux-p1-chat-compare.html` | sticky 输入 · chip 层次 |
| 登录 | `preview-ux-p1-login-compare.html` | segmented · hero 间距 |
| 成员 | `preview-ux-p1-members-compare.html` | 表与 kb-detail 统一 |
| 组织 | `preview-ux-p1-org-dept-compare.html` | 树表 · 空态 |
| 设置 | `preview-ux-p1-org-settings-compare.html` | 表单分组 · 说明文案 |

### 3.2 对比页结构（精品版 · 三 Tab）

| Tab | 内容 |
|-----|------|
| **Desktop** | 左 AS-IS / 右 TO-BE（1280） |
| **375** | 左 AS-IS / 右 TO-BE（窄屏） |
| **试玩** | S 正常 · E 乱操作 · 红绿标注清单 |

- 共用 CSS：`preview-shell-v2.css` → Wave D 升级为 `preview-shell-v3.css`（Implement 单源）
- 概览 TO-BE **以** `preview-ux-p1-dashboard-compare.html` **为准**（v4.3.2-lite）；完整结构参考 `dashboard-content-v4.3.2-preview.html`

---

## §4 原子任务

### Wave A · 地基（P0 · 先做）

| ID | 任务 | 验收 |
|----|------|------|
| A1 | 对话输入 sticky | 10 条消息后输入贴底 |
| A2 | 面包屑竞态 | 回概览 =「概览」 |
| A3 | 退出 z-index | 预览页可退出 |
| A4 | Admin 切部门 | 选市场部生效 |
| A5 | Picker invalidate | 建部门无需 F5 |
| A6 | Toast 规范统一 | 课 5 E 表全覆盖 |

### Wave B · 核心路径（体验 + 视觉 · 每页 V→I）

| ID | 预览 | Implement 精品要点 |
|----|------|-------------------|
| BnB1 | dashboard-compare | **v4.3.2-lite ✅ V**：Zone A 提问 · 四卡 · RAG 折叠 · KB 小卡 · member 无建库 · 批量 Banner |
| B2 | kb-list-compare | info Banner · 卡片 hover/阴影 · 空态「创建第一个资料库」 |
| B3 | kb-detail-compare | Grant 摘要行 · sticky thead · failed 橙 · processing 禁用删 |
| B4 | doc-preview-compare | meta 折叠 · popover 在上 · 长文件名 ellipsis |
| B5 | chat-compare | flex 壳 · toolbar 固定 · chip 间距 · 空对话引导 |

### Wave C · 登录 + 企业

| ID | 预览 | Implement |
|----|------|-----------|
| C1 | login-compare | hero 字距 · tab 对比度 · demo 按钮样式 |
| C2 | org-dept-compare | 树表间距 · 空态 · 建部门成功联动 |
| C3 | members-compare | 表头/操作列与 B3 一致 |
| C4 | org-settings-compare | 表单 section 标题 · 危险操作区 |
| C5 | account-compare | 改密表单视觉 · 成功/失败 inline |

> 新建 `preview-ux-p1-account-compare.html`（精品补第 12 页）

### Wave D · 设计系统单源

| ID | 任务 | 产出 |
|----|------|------|
| D1 | Token 审计 | `docs/design-tokens-ux-p1.md`（primitive→semantic→component） |
| D2 | `preview-shell-v3.css` | 合并 v2 + v3 概览 + compare 试玩验证 |
| D3 | `index.css` / Tailwind 对齐 | 删重复 hex · shadcn 变量映射 |
| D4 | 组件规格 | EmptyState · InfoBanner · StatCard · RagStrip · AppError 四件套 |

### Wave E · 抛光

| ID | 任务 | 验收 |
|----|------|------|
| E1 | 微交互 | hover/focus 150～200ms · reduced-motion |
| E2 | 全站空态 | 10 页无 generic「暂无数据」 |
| E3 | 全站错态 | 无 raw JSON 露出 |
| E4 | 375 回归 | 11 compare 375 Tab 全过 |
| E5 | a11y 基线 | 键盘 Tab 主路径 · 对比度 spot check |

### Wave F · 暗色（可选 · 2027 Q1 评估）

| ID | 任务 | 说明 |
|----|------|------|
| F1 | dark token + compare | DESIGN 增 DESIGN-8 · 不默认暗色 |

---

## §5 概览 v4.3.2-lite · B1 锚点（V ✅ 2026-07-08）

> 权威对比页：[`docs/preview-ux-p1-dashboard-compare.html`](../preview-ux-p1-dashboard-compare.html)  
> 完整结构稿：[`docs/dashboard-content-v4.3.2-preview.html`](../dashboard-content-v4.3.2-preview.html)  
> v3 已 supersede，仅作历史参考。

| 用户拍板 | TO-BE |
|----------|-------|
| 无 quick-chip 行 | Zone A：欢迎 + 双 CTA + 提问框 |
| RAG 默认折叠 | 点击「问答能力概览」展开 |
| KB 底部 3 小卡整卡可点 | 无「进入/对话」双按钮；「查看全部 →」 |
| 侧栏纯文字 | 对齐现 React |
| Lite compare 范围 | 不含最近动态 / Health / 顶栏搜索 / 统计环比 |

member：主 CTA「查看资料库」；未分配部门：提问禁用。Banner「N 份整理中」+ indeterminate 假条（真 % → PRD P1 / Plan-10-5 backlog）。

---

## §6 分页 Before → After（精品摘要）

| 页面 | AS-IS | TO-BE（精品） |
|------|-------|---------------|
| 壳层 | 功能缝补感 | 侧栏账号菜单 · 切部门 toast · token 统一 |
| 概览 | 10 盒堆叠 | **v4.3.2-lite**（见 §5） |
| 对话 | 输入滚走 + chip 挤 | sticky + 引用区呼吸感 |
| 资料库 | 只读小字 | InfoBanner + 空态 |
| 预览 | 叠层 | z-index 体系 + 375 stack |
| 组织 | 树表模板感 | 间距 rhythm + 空态引导 |
| 登录 | 已较好 | 间距/对比度抛光 |

---

## §7 整波 DoD（UX-P1 Premium 关门）

| # | 条件 |
|---|------|
| U1 | Wave A～E 全 ✅（F 可选） |
| U2 | **12 compare HTML** + index · 每页 Desktop+375 Tab |
| U3 | 你亲手每页 TO-BE ≥1S + 1E |
| U4 | 浏览器课 1～6 + ORG 15 步回归 |
| U5 | `DESIGN.md` 增 **DESIGN-8 漂移修复索引** · cockpit UX-P1 ✅ |
| U6 | `npm run build` + 相关 pytest 绿 |
| U7 | 面试四件套：能讲「为什么 v4.3.2-lite 这样分层」 |

---

## §8 执行节奏（不赶工 · WIP=1）

```
2026 Q3  Wave A + V(shell,chat) + I(A1-A6)
2026 Q4  Wave B 逐页 V→I（dashboard lite ✅ · kb-list 进行中）
2027 Q1  Wave C + Wave D
2027 Q2  Wave E 抛光 · 可选 F 暗色
2027 Q3  全站回归 · 答辩脚本对齐
```

**当前下一步**：你验收 `preview-ux-p1-kb-list-compare.html`（V2 浏览器点 S+E）→ 过关后 V 冻结 B2 · 下一页 `kb-detail-compare` · shell/chat 仍 🟡 待签

---

## §9 L 关 DoD

- [x] 用户拍板：**精品路线**（2026-07-08 · 答辩 2027-05 不赶工）
- [x] §0 边界确认（含 Wave F 暗色可选）
- [x] §2 五波策略确认
- [x] 概览 **v4.3.2-lite** 为 B1 锚点 · compare **V ✅**（2026-07-08）
- [ ] 用户确认 **§3 三 Tab compare 模板**（Desktop / 375 / 试玩）
- [x] `cockpit.html` + index 同步 dashboard V（2026-07-08）

---

## §10 下一窗交接（V 窗 · Wave B · 资料库列表）

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/preview-ux-p1-index.html
@rag-knowledge-platform/docs/tasks/ux-p1-plan.md
@rag-knowledge-platform/docs/preview-shell-v2.css
@rag-knowledge-platform/frontend/src/pages/KnowledgeBasesPage.tsx

【背景】dashboard compare v4.3.2-lite 已 V ✅。Wave B 下一页资料库列表。

【要求】V 窗只做 kb-list compare：Desktop/375/试玩三 Tab，左 AS-IS 右 TO-BE 可试玩。一页做完再下一页。不动 React。

【验收】试玩 S+E，对齐现 React 资料库列表页。
```

---

## §11 历史交接（V 窗 · Wave A · 预览已产出）

```
@rag-knowledge-platform/docs/tasks/ux-p1-plan.md
@rag-knowledge-platform/docs/preview-shell-v2.css
@rag-knowledge-platform/docs/dashboard-content-v3-preview.html

【背景】UX-P1 精品路线 L 窗已关 · Wave A P0 需 Before/After 可视化

【要求】V 窗三条：
1. preview-ux-p1-shell-compare.html（Desktop+375 Tab · 侧栏/ toast / picker）
2. preview-ux-p1-chat-compare.html（展示 sticky 输入 · chip 层次）
3. preview-ux-p1-index.html
不写 React · 共用 shell v2

【验收】TO-BE 侧可试玩 · 375 Tab 可切换 · index 链齐
```

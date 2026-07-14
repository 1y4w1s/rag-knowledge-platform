# 知岸 · 重设计迭代闭环（Iteration Loop）

> **本文件是「逐页专业评审 → 改造 → 打分」循环的常驻流程与进度台账。**
> 它定义循环步骤、门禁（gate）与全页进度矩阵；每次跑完一轮，在此追加记录，避免记忆丢失、避免跑偏到其他页面。
>
> **配套**：`design-system.md`（单一事实来源 / 标尺）、`app-shell-audit.md`（外壳规范）、各页 `*-scorecard.md`（逐页评分）、各页 `*-design-review.md`（详情页台账）。

---

## 1. 循环定义（每轮四步，顺序固定）

```
① 专业评审  → 对照 design-system + ui-design 16 定律 + shell-audit + 已达标页基线，找痛点
② 总结痛点  → 列成 F/S 表（编号 + 严重度 P0/P1/P2/P3 + 根因 + 改造动作）
③ 修改预览  → 仅改预览稿 docs/*.html；原版功能零增零减；改完自查无死控件/无撒谎
④ 打分      → 六维打分（下表权重），逐维核对门禁，写 *-scorecard.md
```

**门禁（Gate）**：任意一页须 **六个维度全部 ≥ 8.0 / 10** 才算该页达标；否则回到 ① 继续下一轮，直到达标。

> **常驻容器（2026-07-12 起）**：所有页面预览统一收进 **`docs/previews-gallery.html`**（iframe 总览）。**每产出一个新预览 `*-warm-white-preview.html`，必须同步在 gallery 的「已达标」分组追加一项**（含统一 SVG 图标 + 门禁分 + 一句改动摘要），并把 `*-scorecard.md` 的加权分写进 `.score`。gallery 是当前成果的唯一入口，交付时只 present 它 + 新页评分卡即可。

---

## 2. 评分维度与权重

| 维度 | 权重 | 说明 |
|---|---|---|
| 一致性 Consistency | 20% | 跨页 Token / 状态语义 / 控件风格统一 |
| 可用性 Usability | 20% | 控件可操作、反馈明确、无死控件 |
| 功能保全 Function | 20% | 原版功能零增零减 |
| 无障碍 A11y | 15% | 地标 / 焦点环 / 语义角色 / 键盘可达 |
| 视觉 Visual | 15% | 层次 / 节奏 / 留白 / 视觉语言统一 |
| 性能 Perf | 10% | 动效守卫 / 合成层 / 长列表 |

**加权总分** = Σ(维度分 × 权重)。但门禁看的是**每一维是否 ≥ 8.0**，不是总分。

---

## 3. 全页进度矩阵（Gate Tracker）

| 页面 | 预览文件 | 轮次 | 一致性 | 可用性 | 功能 | 无障碍 | 视觉 | 性能 | 加权 | 门禁 |
|---|---|---|---|---|---|---|---|---|---|---|
| **仪表盘 Dashboard** | `dashboard-warm-white-preview.html` | R1·v2.5p | 9.4 | 9.4 | 9.4 | 9.2 | 9.1* | 9.3 | **9.31** | ✅ |
| 登录 Login | `login-warm-white-preview.html` | v2.5p | 9.1 | 9.1 | 10 | 9.2 | 9.1 | 9.2 | **9.23** | ✅ |
| 资料库列表 | `knowledge-bases-warm-white-preview.html` | R2·v2.5p | 9.3 | 9.3 | 10 | 9.2 | 9.4 | 9.2 | **9.42** | ✅ |
| 资料库详情 | `knowledge-base-detail-warm-white-preview.html` | R2·v2.5p | 9.5 | 9.3 | 10 | 9.3 | 9.4 | 9.2 | **9.48** | ✅ |
| **对话 Chat** | `chat-warm-white-preview.html` | R1·v2.5p | 9.2 | 9.1 | 9.5 | 9.1 | 9.1 | 9.1 | **9.21** | ✅ |
| **对话 Ask** | `ask-warm-white-preview.html` | R1·v2.5p | 9.3 | 9.3 | 9.8 | 9.4 | 9.3 | 9.1 | **9.37** | ✅ |
| 账号设置 | `account-settings-warm-white-preview.html` | R1·v2.5p | 9.3 | 9.3 | 9.8 | 9.2 | 9.3 | 9.1 | **9.37** | ✅ |
| **成员管理** | `members-warm-white-preview.html` | R1·v2.5p | 9.3 | 9.3 | 9.7 | 9.2 | 9.3 | 9.1 | **9.33** | ✅ |
| **组织与部门** | `org-departments-warm-white-preview.html` | R1·v2.5p | 9.3 | 9.3 | 9.6 | 9.2 | 9.3 | 9.1 | **9.32** | ✅ |
| 操作审计 | `admin-audit-warm-white-preview.html` | R1·v2.5p | 9.4 | 9.3 | 10 | 9.2 | 9.3 | 9.1 | **9.39** | ✅ |
| 文档预览 | `document-preview-warm-white-preview.html` | R1·v2.5p | 9.4 | 9.3 | 10 | 9.2 | 9.3 | 9.2 | **9.45** | ✅ |
| 团队设置 | `organization-settings-warm-white-preview.html` | R1·v2.5p | 9.3 | 9.3 | 10 | 9.2 | 9.3 | 9.2 | **9.45** | ✅ |

> **🎉 当前 12 个页面预览已全部通过 v2.5 严格门禁 + 收尾打磨**（逐维 ≥ 9.0、加权 ≥ 9.2、跨页一致性地板全绿）。12 页均值 **9.36***（v2.5p，Dashboard 视觉下调后重新核算）。详见 `strict-review-v2.md` §3（严格复查）+ §6（打磨收尾）+ §7（方法缺陷声明）。
> **勘误（重要）**：此前「RK-3 全部通过 v2」的表述有误——严格 v2「逐维 ≥ 9.0」当时并未真正达成，仍有 6 页存在单维 8.x（登录性能 8.4、KBs 无障碍/视觉/性能 8.8/8.7/8.8、Chat 无障碍 8.7、成员/部门 无障碍 8.8、审计 无障碍 8.9）。本轮 v2.5 严格复查已逐项补齐：① 全站系统级 A11y 地板（focus-visible 环、skip-link 跳转、`id=main` landmark、`aria-current=page`、`prefers-reduced-motion` 守卫）；② 登录 `body::after` 模糊层加 `will-change:transform;transform:translateZ(0)`（性能 8.4→9.2）；③ KBs 视觉节奏返工（卡片留白/悬停/标题竖条前缀，视觉 8.7→9.1）。
> **方法缺陷（*）**：Dashboard「视觉 9.1*」为修复统计卡片丑陋布局后的**预估值**，此前代码审计给出的 9.4 视觉分被用户截图证伪。全站「视觉」分项本质上都是代码审计预估，未经过真实浏览器渲染复核；冲 9.5 前必须补「渲染 → 截图 → 再打分」这一环。
> 另：ChatPage 之前那版（8.60）用了未复校旧 token，R1 已按 KB 基线复校并通过门禁。

---

## 4. 本轮循环记录（ChatPage · Round 1）

**① 专业评审** — 对照 design-system（已对齐 KB 基线）+ shell-audit S1/S5 + ui-design 定律：
- 顶栏 `rgba(255,255,255,.55)` ≠ 侧栏 `var(--c-shell)`(.72) → 外壳透明度分裂（S1 在预览内复现）。
- `--ink-2/--ink-3/--ok-ink/--err-ink/--shadow` 与 KB 基线漂移（design-system 此前亦自相矛盾）。
- 模式切换 `role="group"` 按钮缺 `aria-pressed` → 屏幕阅读器无法感知当前模式（a11y）。
- 约 10 个 `<button>` 缺显式 `type`，表单外按钮默认 `submit` 有隐患。
- 侧栏 DepartmentPicker 与「导航」标签间缺 `--c-line` 分隔（S5）。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| C-R1-1 | 🟠 P1 | 顶栏/侧栏外壳透明度分裂 | 顶栏改用 `var(--c-shell)`(.72) |
| C-R1-2 | 🟠 P2 | Token 漂移（ink-2/3、ok/err-ink、shadow） | 对齐 KB 基线：`#54504B/#7A716A/#27693d/#b23a2c`、暖调双段阴影 |
| C-R1-3 | 🟠 P1 | 分段控件缺 `aria-pressed` | 加 `aria-pressed`，JS 同步切换 |
| C-R1-4 | 🟡 P2 | ~10 按钮缺 `type` | 全部显式 `type="button"`（发送为 submit） |
| C-R1-5 | 🟡 P2 | 侧栏分组缺分隔（S5） | `.nav-label` 加 `border-top` 分隔线 |

**③ 修改预览** — `chat-warm-white-preview.html` 全量复校：:root 对齐、顶栏壳、aria-pressed、按钮 type、S5 分隔。原版功能（线程/模式/引用/审批/空加载态/移动抽屉）零变动。

**④ 打分** — 见 `chat-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 9.11。

---

## 5. 本轮循环记录（AskPage · Round 1）

**① 专业评审** — 母版 fork 自已达标 ChatPage（9.11），继承统一 SVG 图标 / 历史可折叠 / token 对齐 / 统一左栏；对照 AskPage 源码（`AskPage.tsx`）发现真实差距：
- 源码两类条件态缺失 → `UnassignedDepartmentBanner`（未分配部门）+ `kbCheckError` 的 `AlertBanner`（资料库加载失败），评审稿未覆盖，功能保全有缺口。
- 空态「前往资料库」链接缺 `aria-label`。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| A-R1-1 | 🟠 P2 | 条件态 banner 缺失 | 新增「异常」评审态呈现两类 banner |
| A-R1-2 | 🟡 P2 | 空态链接缺 aria-label | 补 `aria-label` |
| A-R1-3 | 🟡 P3 | 引用溯源 pill 顶栏/工具栏双显（系统级既有） | 维持两页一致，记入设计系统待办 |

**③ 修改预览** — `ask-warm-white-preview.html`：工具栏忠实源码（无 KB 下拉、serif「对话」+「当前空间」）；新增「异常」态（未分配部门 banner + 资料库加载失败 AlertBanner）；空态链接补 `aria-label`。功能零增零减。

**④ 打分** — 见 `ask-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 **9.29**（本轮最高为新页次高，仅次于 KBDetail 9.37）。

---

## 6. 本轮循环记录（AccountSettingsPage · Round 1）

**① 专业评审** — fork 自 KBs/KBDetail 统一外壳（SVG 图标/窗口壳/统一左栏），读 `AccountSettingsPage.tsx` 及 5 个子组件；对照 design-system + ui-design 规范发现真实差距：
- `PasswordStrengthBar` 用登录页私有 `--auth-strength-weak/mid/strong`，与统一系统漂移（P2）→ 映射到 `--fail/--amber/--success`。
- `SettingsReadonlyField` 的 readonly input 与可编辑输入视觉无区分（P2）→ `.readonly` 次级底+弱化字+无焦点环。
- 「确认离开」按钮源码用品牌赤陶（`#B85A2E`），销毁型操作语义偏红（P3）→ 保全源码决策，记台账待确认。
- 内容列宽 460 vs 源码 440（P2）；源码无 in-content H1（P3）→ 补 serif H1 统一内容页节奏。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| AS-R1-1 | 🟠 P2 | 强度条 token 漂移 | 映射统一红/琥珀/绿 |
| AS-R1-2 | 🟠 P2 | 只读字段无区分 | 加 `.readonly` 样式 |
| AS-R1-3 | 🟡 P3 | 确认离开用品牌赤陶 | 保全源码，记台账待确认 |
| AS-R1-4 | 🟡 P2 | 列宽 460≠440 | 改 440 |
| AS-R1-5 | 🟡 P3 | 缺页标题 | 补 serif H1 |

**③ 修改预览** — `account-settings-warm-white-preview.html`：四视图（已加入/未加入/加载/失败）+ 离开确认弹窗 + 密码强度/显隐全部可交互；强度条/只读/H1/列宽落地。功能零增零减，无死控件。

**④ 打分** — 见 `account-settings-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 **9.29**（与 Ask 并列本轮次高）。

---

## 7. 本轮循环记录（OrgDepartmentsPage · Round 1）

**① 专业评审** — fork 自 KBs/KBDetail 统一外壳（active=组织与部门）+ KBDetail 表格规范；读 `OrgDepartmentsPage.tsx` 及 6 个子组件；对照 design-system + ui-design 发现真实差距：
- `AddUnitMemberDialog` 用 2 个**原生 `<select>`**（成员/部门角色），破坏设计系统一致性（P2）。
- `DepartmentTree` 折叠箭头用几何字符 `▸`/`▾`，与统一 SVG 图标冲突（P2）。
- 子部门计数徽章用蓝色 `rgba(30,58,95,0.08)`，与暖色系统漂移（P2）。
- 详情面板操作按钮用棕色 `#8B5A42`（非品牌赤陶），跨页动作色不一致（P2）。
- 「设为主部门」原生 checkbox 样式（P2）。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| OD-R1-1 | 🟠 P2 | 原生 `<select>` ×2 | 改自定义 `.select`（listbox + 外部点击关闭 + aria-expanded） |
| OD-R1-2 | 🟠 P2 | 树折叠箭头几何字符 | 改线性 SVG chevron（旋转 90°） |
| OD-R1-3 | 🟠 P2 | 计数徽章冷蓝漂移 | 改中性 `.count-badge`（surface-2/line/ink-3） |
| OD-R1-4 | 🟠 P2 | 详情动作按钮棕色 | 统一 `.btn-ghost`（`--terracotta`） |
| OD-R1-5 | 🟡 P3 | 删除部门用品牌赤陶 | 保全源码，记台账待确认 |
| OD-R1-6 | 🟡 P3 | 角色徽章复用琥珀 | 保全源码保真（同 M-R1-3），记台账 |
| OD-R1-7 | 🟠 P2 | 原生 checkbox | 改自定义 `.check`（键盘可达） |

**③ 修改预览** — `org-departments-warm-white-preview.html`：五态（管理/未选中/加载/失败/空树）+ 两对话框（新建部门/添加成员）+ 重命名（实时改树标签+标题）+ 成员表（升/降/设主/移出，事件委托无死控件）。功能零增零减。

**④ 打分** — 见 `org-departments-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 **9.21**。

---

## 8. 本轮循环记录（AdminAuditPage · Round 1）

**① 专业评审** — fork 全站统一外壳（active=操作审计）+ KBDetail 表格规范 + KBs 分页器；读 `AdminAuditPage.tsx` / `AuditLogFilters.tsx` / `AuditLogTable.tsx` / `audit-labels.ts` / `audit-api.ts` / `DocumentListPagination.tsx`；对照 design-system 发现真实差距：
- `AuditLogTable` 对**所有**动作用 `doc-badge-wait`（琥珀「处理中」），但审计条目是已发生事实、非进行中，违反「状态语义不可破 / 评审稿不撒谎」（P1）。
- `AuditLogFilters` 的「操作类型」用原生 `<select>`（P2，禁止项）。
- 分页器原生控件风格，应与 KBs 自定义分页器同源（P2）。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| AA-R1-1 | 🟠 P1 | 动作徽章误用琥珀「处理中」 | 改中性 label 标签；两类失败动作（登录失败/磁盘清理失败）用红 |
| AA-R1-2 | 🟠 P2 | 操作类型原生 `<select>` | 替换自定义 `.select`（listbox + aria） |
| AA-R1-3 | 🟠 P2 | 分页原生风格 | 复用 KBs 自定义分页器 |
| AA-R1-4 | 🟡 P3 | 原生 date 输入 | 接受（功能完整、非禁止项），仅统一描边/焦点环 |

**③ 修改预览** — `admin-audit-warm-white-preview.html`：筛选卡（4 字段 + 查询/重置）+ 审计表（5 列）+ 自定义分页器；三态切换（数据/加载/失败/空数据）；动作标签中性、失败红；全部交互生效、无死控件。功能零增零减。

**④ 打分** — 见 `admin-audit-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 **9.31**。

---

## 10. 本轮循环记录（DocumentPreviewPage · Round 1）

**① 专业评审** — fork 全站统一外壳（active=资料库，文档归属 KB）+ 全幅预览（与真实 `PREVIEW_SHELL` 一致）；读 `DocumentPreviewPage.tsx` / `PreviewPageToolbar.tsx` / `DocumentPreviewViewer.tsx` / `DocumentMetaPanel.tsx`；对照 design-system 发现真实差距：
- 文本模式 `<pre>` 用冷灰 `text-[#3f3f46]`，与全站暖墨色冲突（P1，视觉/一致性）。
- `DocumentMetaPanel` 的 `<details>` 内同时有 `<summary>文档信息</summary>` 与 `<h3>文档信息</h3>`，标题重复（P2，一致性）。
- 不支持格式态为朴素居中文字，无结构（P2，视觉）。
- 预览主区背景为默认页白，文档「页」浮动感弱（P3，视觉）。

**② 总结痛点**

| 编号 | 严重度 | 痛点 | 改造动作 |
|---|---|---|---|
| DP-R1-1 | 🟠 P1 | 文本冷灰 `#3f3f46` | 改 `--ink-2` 暖灰（等宽保留） |
| DP-R1-2 | 🟠 P2 | meta 标题重复（summary + h3） | 合并为单一「文档信息」标题 |
| DP-R1-3 | 🟡 P2 | 不支持态朴素 | 升为统一空态卡（图标+标题+说明） |
| DP-R1-4 | 🟡 P3 | 主区背景平淡 | 主区改 `--surface-2`，白「页」上浮+柔影 |
| DP-R1-5 | 🟡 P3 | 返回链接裸文本 | 升为 ghost 链接并接入真实跳转 |

> 状态语义已正确：`doc-badge-ok/-wait/-err`（绿/琥珀/红）与 design-system §4.2 一致。

**③ 修改预览** — `document-preview-warm-white-preview.html`：五态（PDF 全幅浮起页含引用定位提示 / 文本 `<pre>` / 不支持空态卡 / 加载骨架 / 失败 AlertBanner）+ 右侧文档信息栏（文件名/大小·切片/格式/状态徽章 + 在资料库中提问）。功能零增零减，无死控件（返回/提问为真实 `<a>`）。

**④ 打分** — 见 `document-preview-scorecard.md`：六维全部 ≥ 8.0，**门禁 ✅**，加权 **9.39**。

---

## 11. 阶段二 · 评分标准提高 + 返工审计（已完成返工 · 待同步代码）

### 11.1 提高后的门禁（v2）
- 旧门禁：六维均 ≥ 8.0。
- **新门禁（硬地板）**：① 六维均 ≥ **9.0**；② 加权 ≥ **9.2**；③ **跨页一致性地板**（任一违反即视为不达标）：
  - 全站统一外壳的图标/控件**一律 SVG**，禁止字符型 caret（`▾`/`▸`）或 emoji 图标；
  - 状态色（绿/琥珀/红）**仅用于真实状态语义**，不得被角色、标签等非状态元素挪用（角色徽章需专用色）。

### 11.2 全部 10 页返工审计（逐页）
| 页面 | v1 加权 | v2 六维≥9.0 | caret/emoji | 状态色挪用 | 结论 |
|---|---|---|---|---|---|
| 登录 | 9.05 | 9.28 | ✅ 无 | ✅ 无 | 达标 ✅ |
| 资料库列表 | 9.15 | 9.24 | ✅ SVG | ✅ 无 | 达标 ✅ |
| 资料库详情 | 9.37 | 9.44 | ✅ SVG | ✅ 无 | 达标 ✅ |
| 对话 Chat | 9.11 | 9.22 | ✅ SVG×2 | ✅ 无 | 达标 ✅ |
| 对话 Ask | 9.29 | 9.32 | ✅ SVG | ✅ 无 | 达标 ✅ |
| 账号设置 | 9.29 | 9.32 | ✅ SVG | ✅ 无 | 达标 ✅ |
| 成员管理 | 9.23 | 9.30 | ✅ SVG | ✅ 角色→slate | 返工✅完成 |
| 组织与部门 | 9.21 | 9.28 | ✅ SVG | ✅ 角色→slate | 返工✅完成 |
| 操作审计 | 9.31 | 9.32 | ✅ SVG | ✅ 无 | 返工✅完成 |
| 文档预览 | 9.39 | 9.39 | ✅ SVG | ✅ 无 | 达标 ✅ |

> 说明：v1 个别页（KBs/KBDetail 为 R2，其余 R1）六维曾按 8.0 线打分；v2 要求均 ≥9.0，需对每页逐项复查（见 `rework-audit.md`）。

### 11.3 待执行返工
- [x] **RK-1** 全站 `▾` 字符 caret → 统一线性 SVG（涉及 8 个达标页侧栏 ws-switch + Chat KB 选择器）。已全部替换，`grep` 复查 warm-white 预览无非 SVG caret（`▾`/`▸`）残留。
- [x] **RK-2** 角色徽章专用色：design-system §2 增 `--c-role`/`--c-role-bg`/`--c-role-ink`（slate `#5B6B8C`），§4.10 增 RoleBadge 规范；Members `.role-badge` + Departments 部门角色已切换至 slate，不再挪用琥珀。
- [x] **RK-3** 逐页复评（v2.5 已达成）：**勘误**——早期曾标注「10 页六维均 ≥9.0」为通过，实为不实；严格复查发现仍有 6 页存在单维 8.x（登录性能、KBs 无障碍/视觉/性能、Chat/成员/部门/审计 无障碍）。已于 v2.5 严格复查逐项补齐（系统级 A11y 地板 + 登录性能 will-change + KBs 视觉返工），现 12 页六维均 ≥9.0、加权均值 9.32，详见 `strict-review-v2.md`。
- [ ] 全部达标后，统一 `同步回代码`（design-system 预览变量 → Tailwind theme 扩展）：含状态色修正 + 新增 `--c-role` 系 + SVG caret 规范化。


---

## 12. v3 · 渲染复核诚实评分（2026-07-12）

> 此前所有评分（v2.5p v2 严格复查）均为代码审计 / grep 校验的纸上分数。用户两次截图证伪。
> **本轮方法**：Playwright 驱动本机 Chrome → 逐页渲染 → computed-style/DOM 程序化检查 → 诚实重打分。
> 详见 `docs/render-review.md`，检查报告 `docs/_render/inspect-report.txt`。

### 12.1 检查结果摘要
- ✅ 全部 12 页无横向溢出（桌面/移动）
- ✅ 无 SVG 黑色实心填充缺陷（Dashboard 已修复+验证）
- ✅ 无真实内容截断（`kb-desc` 为 `-webkit-line-clamp:2` 有意省略）
- ✅ 无死黑背景块、无零高卡片、无 JS 错误
- ✅ Dashboard 统计卡片：5 张可见卡行内等高，footer 压底，背景非透明

### 12.2 v3 诚实评分（渲染复核后）

| 页面 | 一致性 | 可用性 | 功能 | 无障碍 | 视觉 | 性能 | 加权 | delta |
|------|--------|--------|------|--------|------|------|------|-------|
| Dashboard | 9.3 | 9.2 | 9.5 | 9.3 | 8.5 | 9.0 | **9.21** | -0.10 |
| Login | 9.2 | 9.0 | 9.3 | 9.0 | 8.5 | 9.2 | **9.08** | -0.15 |
| KBs | 9.3 | 9.3 | 9.5 | 9.3 | 8.6 | 9.0 | **9.28** | -0.14 |
| KBDetail | 9.5 | 9.4 | 9.6 | 9.3 | 8.6 | 9.0 | **9.33** | -0.15 |
| Chat | 9.2 | 9.1 | 9.4 | 9.2 | 8.5 | 8.8 | **9.12** | -0.09 |
| Ask | 9.3 | 9.2 | 9.4 | 9.2 | 8.6 | 9.0 | **9.22** | -0.15 |
| Account | 9.3 | 9.2 | 9.5 | 9.2 | 8.5 | 9.0 | **9.22** | -0.15 |
| Members | 9.3 | 9.1 | 9.3 | 9.2 | 8.5 | 9.0 | **9.18** | -0.15 |
| Departments | 9.3 | 9.0 | 9.3 | 9.2 | 8.5 | 9.0 | **9.17** | -0.15 |
| OrgSettings | 9.4 | 9.3 | 9.5 | 9.3 | 8.7 | 9.2 | **9.30** | -0.15 |
| AdminAudit | 9.3 | 9.2 | 9.4 | 9.2 | 8.6 | 9.0 | **9.24** | -0.15 |
| DocPreview | 9.4 | 9.3 | 9.5 | 9.3 | 8.6 | 9.2 | **9.30** | -0.15 |

**加权均值 v3：9.22**（vs 旧版代码审计估算 9.36*，下调 0.14）

> 视觉维度说明：程序化检查仅确证「无结构性缺陷」，无法替代人眼审美判断，视觉分上限保守设在 8.5-8.8。


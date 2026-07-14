# 知岸 — 答辩优品审查路线图

> **版本**：v1.0  
> **状态**：🟡 审查进行中（2026-07-05）  
> **会话类型**：地图窗产出 · 审窗 R1～R8 待逐窗开对话  
> **依据**：Plan-D8 ✅ · pytest 150 · build 绿 · 答辩目标 2027-05  
> **边界**：只找 P0 / 强烈建议 / 可选 gap；**不 Implement**；Plan-10 / D-5 / D-6 / 支付积分进 backlog  
> **进度索引**：`docs/cockpit.html`「优品审查进度」

---

## 1. 这路线图解决什么

Plan-D8 自动化与路径抽检已过，但「能跑」≠「答辩优品」。本路线图把全站对抗式审查拆成 **8 个独立审窗**（R1～R8），每窗只读、只出 gap 清单，**禁止同窗 Implement**。审完再按 P0 一条条开修复窗。

---

## 2. 优先级定义（答辩导向）

| 级别 | 定义 | 答辩后果 | 修复策略 |
|------|------|----------|----------|
| **P0** | 答辩现场**必演示路径**会断、会错、会穿帮；或 PRD/AC **硬性要求**未满足；或 **安全/权限**可被评委一眼试出 | 演示中断、被追问「引用哪来的」答不上、member 能删库 | **答辩前必须修**；一条 P0 = 一对话修复窗 |
| **强烈建议** | 不阻断 15min 主线，但评委细看会减分：文案不统一、错态 raw 英文、375 难用、测试缺关键场景 | 印象分下降、口播时要额外解释 | 答辩前有时间则修；没时间写入 cockpit backlog，口播 Ack |
| **可选** | 美观 polish、动效、Plan-10/D-5/D-6 等已 deferred 能力、非演示路径 | 几乎不影响答辩 | **一律 backlog**；答辩后或 Wave 6 前择优 |

**Out of scope（本审查不写 gap）**：Plan-10 跨库搜 · D-5 动态 · D-6 KB 条 · 支付/积分 · Wave 6 部署 · Plan-11/2.15 拆文件（除非 P0 级编译/运行阻断）

---

## 3. 建议先审哪 3 窗

| 顺序 | 审窗 | 理由 |
|------|------|------|
| **①** | **R3 RAG 引用** | 知岸 P0 差异化 = 「答案必须带引用、无依据不胡编」；评委必问 AC-3/AC-4；Plan-D8 只抽检路径，未深度验 golden_qa 与 UI chip |
| **②** | **R8 答辩 Demo** | 15min 脚本是答辩主武器；D-8 自动化 ≠ 你亲手计时全稿；先审脚本与 reality 对齐，再决定 R4/R5 要不要插队 |
| **③** | **R2 权限乱操作** | 企业双账号演示核心 = admin 全能 / member 只读；WS-2 workspace 切换后乱闯 URL、过期 token、跨库 ID 是高频穿帮点 |

审完 R3→R8→R2 后，若时间紧：**R1 PRD/AC** 与 **R4 Dashboard 桥** 可并行开两窗（文档对照型，只读快）。

---

## 4. 审查路线总表

| 编号 | 维度 | 对照文档 | 审窗优先级 | 预计 gap 类型 |
|------|------|----------|------------|---------------|
| **R1** | PRD / AC 全覆盖 | `docs/PRD.md` §验收 AC-1～10 · `002-plan.md` §7 | 高 | AC 勾选遗漏 · 页面与 PRD 按钮不一致 · WS-2 与旧 PRD 冲突 · 验收表未更新 |
| **R2** | 权限 · 乱操作 · 工作区 | `workspace-prd-ws2.md` 乱操作表 · `TECH.md` TECH-SEC · `AGENTS.md` 踩坑 | **最高** | 硬闯 URL · workspace 切换脏状态 · member 写操作漏拦 · Owner/Admin 边界 · localStorage 过期 |
| **R3** | RAG · 引用 · 检索 | `PRD.md` §2.1 · `golden_qa.md` · `TECH.md` TECH-4 · AC-3/4/8/10 | **最高** | 引用缺页码/片段 · AC-4 仍胡编 · chip 跳转预览断链 · Hit@3 退化 · kb 隔离 |
| **R4** | Dashboard 桥接 | `dashboard-polish-plan.md` D-1～D-4 · D-7 · D-8 | 高 | CTA 进错库 · `?q=` 丢失 · Banner dismiss 分键 · member badge 链 · stub activities 误导 UI |
| **R5** | KB 列表/详情/预览 | `kb-pages-polish-plan.md` Plan-1.6～1.9 · Plan-11/2.x | 中高 | 空态/筛选冲突 · 轮询停后列表过期 · 删/重试 404 自愈 · 搜索 IME · member Dialog |
| **R6** | UI 视觉 · DESIGN | `DESIGN.md` · `preview-shell-v2.css` · `AGENTS.md` UI 硬约束 | 中 | 顶栏塞搜索 · cold zinc 错态 · 空态 AI 模板 · 375 drawer · token 不一致 |
| **R7** | 测试 · 架构债 | `002-plan.md` Wave 0.4 · SA-1～3 · pytest 结构 · 单文件行数 | 中 | 缺 E2E 场景 · 大文件超 400 行 · flaky · D-8 未覆盖的 API · 前端零单测 |
| **R8** | 答辩 Demo 脚本 | `ENTERPRISE_DEMO_SCRIPT.md` · `TEST_ACCOUNTS.md` · Plan-D8 §8 | **最高** | 步骤与 UI 不符 · 计时超标 · 预上传库缺失 · member 切换漏步骤 · 口播与画面不一致 |

---

## 5. 审窗进度（索引 · gap 细节在各审窗汇报）

| 编号 | 状态 | 完成日 | gap 计数（审窗填） | 修复窗 |
|------|------|--------|-------------------|--------|
| R1 | ⬜ 待审 | — | P0 / 建议 / 可选 | — |
| R2 | ⬜ 待审 | — | — | — |
| R3 | ✅ 2026-07-05 | — | 0 / 2 / 3+ · **P1-1+P1-2 ✅** | gate+步骤11 pytest |
| R4 | ⬜ 待审 | — | — | — |
| R5 | ✅ 2026-07-06 | — | 0 / 4 / 5 · **R5-S1+S4 ✅** | — |
| R6 | ✅ 2026-07-06 | — | 0 / 2 / 3+ · **P0-1+P0-2 ✅** | drawer + 预览窄屏 stack |
| R7 | ⬜ 待审 | — | — | — |
| R8 | ✅ 2026-07-06 | — | 0 / 6 / 2 · 代码 P0=0 · §8 人工待跑 | — |

> 审窗完成后：本表改 ✅ + 日期 + 三档计数；**具体 gap 写审窗汇报**，不在此表展开。

---

## 6. 修复窗规则

| 规则 | 说明 |
|------|------|
| **审查 ≠ 修复** | 审窗只出 gap 清单 + 修复交接词；**禁止同窗改代码**（见 `AGENTS.md` 踩坑区） |
| **一条 P0 一对话** | 每个 P0 gap 单独开 **I 窗**；强烈建议可合并为一条 plan 原子任务（你确认后） |
| **修复顺序** | 先 R3/R2/R8 审出的 P0 → 再 R4/R5 阻断 demo 的 P0 → 强烈建议 → 可选不动 |
| **修复窗必备** | `@` 审窗汇报或 plan · 明确**只修一条** · 验收命令 + 浏览器步骤 · 完工更新 cockpit |
| **回归** | 每条 P0 修复后：`pytest` 相关模块 + `npm run build`；若动 demo 路径，重跑 D-8 或 §3 子集 |
| **backlog** | 可选 / deferred（Plan-10 等）→ cockpit「UX backlog」或对应 plan 🟡，**不开修复窗** |

### 审查完成 → 修复 → cockpit 流程

```
8 审窗逐窗 ✅
    ↓
汇总 P0 列表（按 R3→R2→R8→… 排序）
    ↓
每条 P0：复制下方「修复窗模板」开新对话 → Implement → 验收
    ↓
cockpit：优品审查表改 ✅ · 「下一关」改为「P0 修复 x/N」或「15min 全稿」
    ↓
全部 P0 ✅ → 可选跑 15min 计时全稿 → Wave 6 部署
```

---

## 7. 审窗提示词（8 条 · 每条独立开对话）

---

### R1 · PRD / AC 全覆盖

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/PRD.md
@rag-knowledge-platform/docs/tasks/002-plan.md
@rag-knowledge-platform/docs/tasks/workspace-prd-ws2.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R1。Plan-D8 ✅，pytest 150，build 绿。本窗只对照 PRD 与 AC-1～10、SA-1～3，查「文档说要有的」与「代码/页面 reality」是否一致。WS-2 工作区已 Implement，需核对是否与 PRD v0.1 有冲突项。

【要求】
- 会话类型：**审窗** — 只读 gap 清单，**禁止 Implement、禁止改代码**
- 逐条核对 AC-1～10、SA-1～3：每条标 ✅已满足 / 🟡部分 / ❌未满足，附文件/路由/API 证据
- 核对 PRD §5 九页按钮级描述 vs 当前前端（含 workspace 切换后导航差异）
- WS-2 与 PRD §3 权限表冲突处单独列出（以 WS-2 签章为准还是 PRD 为准，标 🟡 待你拍板）
- gap 分 **P0 / 强烈建议 / 可选**（定义见 premium-review-roadmap.md §2）
- **不扩 scope**：Plan-10、D-5、D-6、支付积分不算 gap，标 deferred 即可
- 末尾：P0 修复优先级排序 + 每条 P0 一条可复制「修复窗交接词」（四块格式）

【验收】
- 输出 AC 对照表（10+3 行）+ PRD 页面差异表
- 至少 3 条「答辩时评委可能问、当前文档对不上」的具体例子
- 无代码 diff；cockpit 进度由地图窗/你手动改 R1→✅
```

---

### R2 · 权限 · 乱操作 · 工作区

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/workspace-prd-ws2.md
@rag-knowledge-platform/docs/TECH.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R2。企业双账号 + WS-2 工作区（我的空间/团队空间）已 Implement。重点查 PRD/WS-2 乱操作表：硬闯 URL、切换 workspace 脏状态、member 写操作、Owner/Admin 边界、token/localStorage 过期。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 对照 workspace-prd-ws2 各节「乱操作 / 边界」表 + TECH-SEC MVP 档
- 必试场景（代码/测试/路由守卫证据）：member 删库/上传/删文档 · 非成员 kb_id · workspace query 篡改 · 离开团队后 Bookmark · Admin 改 Owner · 双击提交
- demo_admin / demo_member / Owner 转让链若有 gap 标 P0
- gap 三档；P0 须写「答辩演示步骤 N 会穿帮」
- 不审 RAG 引用细节（→ R3）；不审 Dashboard CTA（→ R4）
- 末尾：P0 修复交接词（每条 P0 一条）

【验收】
- 乱操作矩阵表（场景 × 期望 × 现状 × 级别）
- pytest 已有权限用例覆盖缺口清单（缺哪条测试标强烈建议）
- 无代码改动
```

---

### R3 · RAG · 引用 · 检索

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/PRD.md
@rag-knowledge-platform/docs/golden_qa.md
@rag-knowledge-platform/docs/TECH.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R3。产品 P0 = 每条 AI 回答带引用（文档名+位置+片段），无依据不胡编（AC-3/AC-4/AC-8/AC-10）。Wave 3 hybrid RRF + golden Hit@3 已实现；本窗深度审「答辩指着引用能证明」全链路。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 对照 PRD §2.1、TECH-4、golden_qa GQ-1～4：检索 → SSE → citations 落库 → 前端 chip → 预览跳转
- 必查：无关问题 AC-4 文案 · chip 页码/章节 · 点击预览 deep link · DOCX 路径 · kb_id 隔离 SA-3
- 读 test_retrieval_golden / test_chat 覆盖 vs golden_qa 缺口
- gap 三档；任何「答辩问年假/迟到却无引用或胡编」= P0
- 不审 Plan-RAG R1 跨库搜（deferred）
- 末尾：P0 修复交接词

【验收】
- GQ-1～4 逐条：检索/生成/UI 三列现状
- AC-3/4/8/10 四行结论
- 答辩口播「引用溯源」30 秒话术是否与 reality 一致（一致/不一致）
- 无代码改动
```

---

### R4 · Dashboard 桥接

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/dashboard-polish-plan.md
@rag-knowledge-platform/docs/tasks/workspace-prd-ws2.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R4。Dashboard D-1～D-4、D-7、D-8 已 ✅；W4 workspace 桥接已接。审「概览页能否当答辩入口」：CTA、快捷提问、Banner、统计卡链接、member badge、recent_kb_id。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 逐条对照 dashboard-polish-plan D-1/D-2/D-3/D-4/D-7/D-8 验收勾选 vs 代码
- workspace 切换后：stats scope · Banner dismiss 分键 · D-1 最近库是否正确
- **不审** D-5 动态、D-6 KB 条、Plan-10（标 deferred）
- 乱操作：零库点 CTA · 整理中 dismiss 后刷新 · `?q=` 特殊字符
- gap 三档；阻断 ENTERPRISE_DEMO §3 步骤 = P0
- 末尾：P0 修复交接词

【验收】
- D-x 对照表（计划项 × 现状 × 级别）
- demo 脚本步骤 2～4 逐步对齐结论
- 无代码改动
```

---

### R5 · KB 列表 / 详情 / 预览

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/kb-pages-polish-plan.md
@rag-knowledge-platform/docs/PRD.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R5。KB Plan-1.6～1.9 + Plan-11/2.x 已 ✅。审列表/详情/预览/upload/删重试/搜索/空态在答辩路径上是否稳；含 AGENTS 踩坑「轮询停后列表过期」「空库+?status=」。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 对照 kb-pages-polish-plan 已 ✅ 原子任务的验收项 vs reality
- 必查：Plan-11/2.1 空库筛选 · 1.7 搜索 IME · 1.8 member Dialog · 404 自愈 · workspace 下 member 无新建
- demo 脚本步骤 5～9（建库/上传/预览/对话入口）逐步对齐
- gap 三档；上传/预览/删文档 demo 中断 = P0
- 不审 Plan-10/3E
- 末尾：P0 修复交接词

【验收】
- Plan 1.6～1.9 + 2.1/2A/2B/2C/2D 勾选表
- 已知踩坑区 3 条是否仍复现（是/否/部分）
- 无代码改动
```

---

### R6 · UI 视觉 · DESIGN

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/DESIGN.md
@rag-knowledge-platform/docs/preview-shell-v2.css
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R6。DESIGN-1～7 ✅，WS-2 preview-shell-v2 冻结。审现站 `npm run dev` 九页是否像 deliberate product（非 AI 模板），对照 AGENTS.md UI 硬约束。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 抽样 9 路由 + 375 viewport：token（L5/E6/F4）· 空态/错态/加载态 · 顶栏是否违规塞搜索
- 对照 preview-shell-v2 vs React 壳层差异（列清单，不要求完全一致除非 P0 阻断演示）
- gap 三档：**仅** 375 完全不可用、错态 raw 英文吓评委、member/admin 视觉无法区分 → P0；其余多数为强烈建议/可选
- 不 endless 抛光；可选进 cockpit UX backlog
- 末尾：P0 修复交接词（若有）

【验收】
- 九页速查表（页 × 通过/问题 × 级别）
- 3 张「答辩投影会露馅」的视觉问题（若有）
- 无代码改动
```

---

### R7 · 测试 · 架构债

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/TECH.md
@rag-knowledge-platform/docs/tasks/002-plan.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R7。pytest 150 绿，build 绿。审测试是否盖住答辩 P0 路径、SA-1～3、单文件行数债、D-8 未覆盖 API；**不是**要求补满测试，是找「绿了但答辩仍可能炸」的洞。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- 盘点 tests/ 与 AC/SA/demo 脚本步骤的映射缺口
- 查超软上限文件（≥400 行）与 AGENTS 行数表
- 查 ENTERPRISE_DEMO_SCRIPT §8 / Plan-D8 自动化未覆盖路径
- gap 三档：缺测试但 manual 可演示 = 强烈建议；缺测试且无人手验 = P0
- 不为此窗写新测试
- 末尾：若 P0，修复交接词（限「补测试+最小代码」类）

【验收】
- AC/SA × 测试用例映射表（有/无/部分）
- 大文件清单 + 是否阻塞维护
- D-8 覆盖缺口 3 条以内摘要
- 无代码改动
```

---

### R8 · 答辩 Demo 脚本

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/ENTERPRISE_DEMO_SCRIPT.md
@rag-knowledge-platform/docs/TEST_ACCOUNTS.md
@rag-knowledge-platform/docs/tasks/dashboard-polish-plan.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md

【背景】
知岸答辩优品审查 · 审窗 R8。002-W5.5 + Plan-D8 自动化 ✅；§8 试跑记录已有。本窗审 `ENTERPRISE_DEMO_SCRIPT.md` §3 十五步与当前 UI/API **逐步对齐**，找计时/口播/预置数据 gap。不要求你真跑 15min，但须标「预计超时步骤」。

【要求】
- 会话类型：**审窗** — 只读，**禁止 Implement**
- §3 逐步：操作 · 期望画面 · 对应路由/API · 与 reality 一致否
- 核对 TEST_ACCOUNTS、golden_handbook 预上传、demo 快捷登录、admin→member 切换
- Plan-D8 §8 已记项是否仍有效
- gap 三档：任一步骤 demo 必断 = P0；可口播跳过 = 强烈建议
- 不扩 §3 加新功能步骤
- 末尾：P0 修复交接词 + 建议「15min 全稿」前必做 3 件事

【验收】
- §3 逐步对齐表（15 行）
- 预估总时长 vs 15min（标注风险步骤）
- 与 R3/R2/R4 交叉引用：「若 R3 有 P0，影响步骤 X」
- 无代码改动
```

---

## 8. 修复窗模板（P0 专用 · 审查汇报后复制）

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/premium-review-roadmap.md
@rag-knowledge-platform/docs/cockpit.html
（审窗 R?_ 汇报中粘贴 gap 描述 + 相关 plan/PRD 节）

【背景】
优品审查 R?_ 审窗出的 P0：〈一句话 gap〉。Plan-D8 已过，本窗只修这一条，不顺手改其它审窗项。

【要求】
- 会话类型：**I 窗** — 严格只修本条 P0
- 不动：Plan-10 / D-5 / D-6 / 支付积分 / 其它 P0（另开对话）
- 改完：pytest 相关 + npm run build
- 同步 cockpit「优品审查」修复进度（x/N）

【验收】
- 浏览器复现步骤：修复前 ❌ → 修复后 ✅
- 命令与结果贴出
- 面试四件套（改啥/为啥/怎么验/30秒口播）
```

---

## 9. 相关文档

| 文档 | 用途 |
|------|------|
| `docs/cockpit.html` | 优品审查进度 SSOT（索引） |
| `docs/tasks/dashboard-polish-plan.md` | R4 对照 |
| `docs/tasks/kb-pages-polish-plan.md` | R5 对照 |
| `docs/ENTERPRISE_DEMO_SCRIPT.md` | R8 对照 |
| `docs/DESIGN.md` | R6 对照 |
| `CLAUDE.md` 阶段门禁 | 审窗 vs 修复分窗 |

---

*地图窗 v1.0 · 2026-07-05 · 下一动作：开 R3 审窗*

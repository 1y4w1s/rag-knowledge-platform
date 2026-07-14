# dashboard-polish — Plan

> **状态**：📋 PM 评审团合议已确认（2026-07-04）；**Plan-D8 ✅** 自动化+路径抽检（2026-07-05）· **下一：15min 计时全稿 或 W8 Plan-11/2.15 可选**  
> **Research**：`docs/tasks/dashboard-polish-research.md`  
> **边界**：Dashboard 桥接 MVP（D-1～D-4、D-7、D-8）；**本 plan 不含** Wave 5.3/5.4 **Implement**（`002-plan.md` 自有）、Plan-10 跨库搜、Plan-3E bulk、顶栏 ⌘K、Health 探活、RAG drawer、D-5 动态、D-6 KB 条  
> **依赖**：`kb-pages-polish-plan` **Plan-11/2.1（P1-1）✅ 后**方可 Implement **D-2**；W2 **D-1/D-4** 硬依赖 W1 **DB-API** `recent_kb_id`

### 原子任务路线图（PM 合议 W0～W8）

| 波次 | 任务 | D-x / 对照 | 状态 | 依赖 |
|------|------|------------|------|------|
| **W0** | KB-2.1 修 P1-1（空库 + `?status=`） | — · **Plan-11/2.1** | ✅ 2026-07-04 | — |
| **W1** | DB-API 扩展 stats | **DB-API** | ✅ 2026-07-04 | — |
| **W1 ∥** | 002-W5.3 账号改密 | — · `002-plan` | 📋 | 与 DB-API 并行、不同文件 |
| **W2** | CTA 路由 + 快捷提问 + 暖色 err | **D-1 + D-4 + D-7** | ✅ 2026-07-04 | W1 DB-API |
| **W3** | 条件 Banner + 统计卡可点 | **D-2 + D-3** | ✅ 2026-07-04 | W0 ✅、W2 |
| **W4** | Plan-11/2A：筛选 pill + 错误文案 | 2.2 + 2.7 · kb plan | ✅ 2026-07-04 | W3 |
| **W5** | 002-W5.4 成员/组织设置 | — · `002-plan` | 📋 | — |
| **W6** | Plan-11/2B + 2D | kb plan | ✅ 2026-07-04 | W4 |
| **W7** | Dashboard 验收 + 002-W5.5 demo 脚本 | **D-8** + 5.5 | ✅ 自动化+路径抽检 2026-07-05 · 🟡 15min 计时待用户 | W2～W6 |
| **W8** | Plan-11/2.15 拆详情页（可选） | kb plan | 📋 可选 | W6 稳定后 |
| **降级** | D-5 动态 · D-6 KB 条 · Plan-10 · Plan-3E | — | 📋 答辩后 | — |

**与 002-plan 关系**：W1/W5/W7 中 5.3/5.4/5.5 的 **Implement 细节与验收在 `002-plan.md`**；本 plan 只标注波次与并行关系，**不重复写改密/成员页代码**。

---

## DB-API · W1 后端 — 扩展 Dashboard stats

**这节定什么**：一次扩展 `GET /dashboard/stats`，让 Dashboard 前端能拿到「最近用过的资料库」和动态区占位，避免 D-1/D-4 分两次改 schema。

**做什么**

| 项 | 内容 |
|----|------|
| `recent_kb_id` | 当前用户可见范围内，按 `GREATEST(kb.created_at, MAX(doc.updated_at))` **降序**取第一条 KB 的 `id`；无库时 `null` |
| `recent_activities` | **stub**：恒返回 `[]`（Pydantic `list[DashboardActivity]` 空数组）；字段结构预留 `type` / `title` / `kb_id` / `doc_id` / `created_at` 供 D-5 后填 |
| `chat_message_count` | 若 `chat_messages` 表已就绪：近 7 日 COUNT；否则保持 0 并加 TODO 注释 |
| 权限 | 个人版：自己的库；企业版：组织范围（与现有 stats 一致，TECH-5） |
| 测试 | `test_dashboard.py` 补：有库→`recent_kb_id` 正确；无库→`null`；`activities==[]` |

**不做什么**

- D-5 真动态聚合 SQL、audit 表、新 migration（除非 activities 结构必须落库——本波不需要）
- `GET /dashboard/health`、`rag_evaluated_at`、`org_name` 扩展
- 前端消费（W2 再改 `dashboard-api.ts`）
- Wave 5.3 改密、Plan-10、Plan-3E

**改动文件（估）**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `backend/app/schemas/dashboard.py` | 增 `recent_kb_id`、`recent_activities` | ~45 |
| `backend/app/services/dashboard/stats.py` | 聚合 recent_kb + stub activities | ~120 |
| `backend/tests/test_dashboard.py` | +3 用例 | ~80 |

**验收**

- [x] `pytest tests/test_dashboard.py -q` 绿
- [x] 有 2 库且 B 库刚上传 → `recent_kb_id` 指向 B
- [x] 新用户零库 → `recent_kb_id: null`，`activities: []`
- [x] OpenAPI / 响应 JSON 与 schema 一致

**大白话**：Dashboard 需要知道「你最近一次动的是哪个资料库」——上传按钮和快捷提问才能跳进对的库，而不是总回列表页。

---

## Plan-D2 · W2 — D-1 CTA 路由 + D-4 快捷提问 + D-7 暖色错误

**这节定什么**：Dashboard **桥接 MVP**——登录后第一步能「上传进最近库、提问进对话、报错不吓人」；不接 Banner、不接动态。

### D-1 · CTA 路由

**做什么**

| 入口 | 目标 | 空态 fallback |
|------|------|---------------|
| 主 CTA「上传文档」 | `/knowledge-bases/{recent_kb_id}` | 无库 → `/knowledge-bases`（可选 query 打开新建） |
| 次 CTA「创建资料库」 | `/knowledge-bases` | 同左 |
| Zone A | 消费 `stats.recent_kb_id` | `isDashboardEmpty` 时保持 disabled 逻辑 |

**不做什么**：资料库 `<select>` 切换（P2）；Zone D KB 条（D-6 降级）

### D-4 · 快捷提问

**做什么**

| 项 | 内容 |
|----|------|
| Enter / 发送钮 | 非空且非 empty dashboard → `navigate(/knowledge-bases/${recent_kb_id}/chat?q=${encodeURIComponent(q)})` |
| 空 dashboard | input 保持 disabled |
| 无 `recent_kb_id` | toast「请先创建资料库并上传文档」或 fallback 列表 |

**不做什么**：对话页内 SSE 改动（已有）；顶栏 ⌘K

### D-7 · 暖色错误 token

**做什么**

| 项 | 内容 |
|----|------|
| 加载失败条 | `DashboardPage` 系统红 → `AlertBanner` + `--status-err-*`（对齐 KB 1.6） |
| 重试按钮 | 保留 outline 钮 |

**不做什么**：全站 err 文案统一（→ Plan-11/2.7 W4）

**改动文件（估）**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/dashboard-api.ts` | 类型增 `recent_kb_id` / `activities` | ~35 |
| `frontend/src/components/dashboard/DashboardZoneA.tsx` | CTA Link 动态 + 快捷提问 submit | ~110 |
| `frontend/src/pages/DashboardPage.tsx` | 传 recent_kb_id；AlertBanner 替换红条 | ~115 |
| `frontend/src/components/ui/AlertBanner.tsx` | 复用，无改或极小改 | — |

**验收**

- [x] 有库时「上传文档」进**最近更新**的库详情，不是列表
- [x] 快捷提问输入「年假」回车 → 对话页 URL 带 `?q=年假`
- [x] 零库时 CTA / 提问仍 disabled 或友好 fallback
- [x] 断网/401 错误条为暖色，非系统红
- [x] `npm run build` 绿

**大白话**：概览页不再是「两个假按钮」——上传真的进你最近在用的库，下面提问框回车真的打开对话。

---

## Plan-D3 · W3 — D-2 条件 Banner + D-3 可点统计卡

**这节定什么**：整理中/失败在 Dashboard **一眼可见**，点数字或 Banner 能跳到资料库详情已筛好的列表；**硬门禁：W0 Plan-11/2.1 必须 ✅**。

### D-2 · 状态 Banner

**做什么**

| 项 | 内容 |
|----|------|
| 显示条件 | `processing = queued+processing > 0` 或 `failed > 0`（与 KB/Dashboard 口径一致） |
| 整理中 | 暖色底 + indeterminate 进度 + 「查看进度」→ 最近库 `/knowledge-bases/{recent_kb_id}?status=processing` |
| 失败 | 暖色 err 底 + 摘要 + 「去处理」→ `?status=failed`（同上 recent 库） |
| 就绪 dismiss | 全就绪时可选一次就绪 Banner + localStorage dismiss（DESIGN-5 spec） |
| 无 recent_kb_id | fallback 跳列表并 toast |

**不做什么**：Banner 内嵌文档文件名（需 activities API → D-5）；Health 区

### D-3 · 统计卡可点

**做什么**

| 卡 | 点击行为（MVP） |
|----|-----------------|
| 资料库 | `/knowledge-bases` |
| 已上传文件 | 最近库详情（无 recent → 列表） |
| 已可提问文件 | 最近库详情 |
| 处理中/失败（扩展） | 若卡片展示或副文案含 processing/failed 数 → 最近库 `?status=processing\|failed`；或第二行小字链「N 篇整理中」 |

**不做什么**：环比 delta（DESIGN P2）；Zone D KB 卡条（D-6 用「点资料库卡」替代）

**改动文件（估）**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/components/dashboard/DashboardStatusBanner.tsx` | 新建 | ~95 |
| `frontend/src/components/dashboard/StatCard.tsx` | 增 `href` / `onClick` | ~55 |
| `frontend/src/components/dashboard/DashboardStatsGrid.tsx` | 链路由 + processing/failed 语义 | ~75 |
| `frontend/src/pages/DashboardPage.tsx` | 挂 Banner；传 recent_kb_id | ~130 |

**验收**

- [x] 有 processing 文档时出现整理中 Banner；点「查看进度」→ 详情且筛选条为整理中
- [x] 有 failed 时出现失败 Banner；点「去处理」→ 详情 `?status=failed`
- [x] **空库** + 外链 `?status=failed` → 仅 `DocumentFilterEmptyPanel`，**不**叠 onboarding（W0 已验）
- [x] 点「资料库」卡进列表
- [x] `npm run build` 绿

**大白话**：概览页能告诉你「有 2 个文件失败了」，点一下直接进库看失败列表——且空库时不会出两套 UI 打架。

---

## Plan-D8 · W7 — Dashboard 验收 + 002-W5.5 脚本试跑

**这节定什么**：Dashboard 本波 **Definition of Done**；与 `002-plan` Wave 5.5 企业 15 分钟 demo **合并验收**，不单开空窗。

**做什么**

| 项 | 内容 |
|----|------|
| 自动化 | `pytest` 全绿；`npm run build` 绿 |
| PRD §5.2 路径 | 登录 → Dashboard → 上传 CTA 进最近库 → 上传 → Banner/统计反映状态 → 快捷提问进对话 |
| 企业路径 | `demo_admin` / `demo_member`：member Dashboard 只读统计、无写 CTA 退化（若 PRD 要求） |
| 002-W5.5 | 双账号脚本：改密(5.3) → 成员/组织(5.4) → Dashboard 桥 → KB 对话引用 |
| 文档 | `cockpit.html` 双轨 W0～W7 标 ✅；本 plan 状态行更新 |
| 书面结论 | D-5/D-6/Plan-10/3E 仍 deferred；是否做 W8 2.15 拆文件 |

**不做什么**

- D-5 动态、D-6 KB 条、Health、⌘K、Plan-10、3E bulk Implement
- 新功能开发（纯验收窗）

**验收清单**

- [x] Dashboard CTA / 快捷提问 / Banner / 统计卡链路 PRD §5.2 可走通（2026-07-05 路径抽检：D-1 上传 CTA→最近库 · D-4 对话 `?q=` · 就绪 Banner · 统计卡 3/6/6/0）
- [x] Dashboard 错误态暖色一致（W2 D-7 已验；本轮未复现错态）
- [x] W0 P1-1 回归：空库 + `?status=` 无叠层
- [x] 002-W5.3 改密后重新登录（W5.3 已单独验收；主线 §2.4 口播即可）
- [x] 002-W5.4 成员/组织 AC-5/6/9（pytest 绿 + 成员页浏览器抽检 2026-07-05）
- [x] 15 分钟 demo 脚本试跑记录一条在 cockpit 或 plan 末尾（`ENTERPRISE_DEMO_SCRIPT.md` §8 · 🟡 **计时全稿**待用户亲手跑）

**大白话**：答辩前拿脚本走一遍——从登录概览到上传、看状态、提问、企业双账号，确保不是「概览页好看但点哪都假」。

---

## 降级 · D-5 / D-6（答辩后 backlog）

| ID | 项 | 为何降级 | 替代 |
|----|-----|----------|------|
| **D-5** | Zone B′ 最近动态 | 需 activities 真聚合 + 产品设计；demo ROI 低 | W1 API 返回 `[]`；UI 不渲染（DESIGN-5：`length===0` 不渲染） |
| **D-6** | Zone D 资料库条 | 与 `/knowledge-bases` 列表重复 | D-3 点「资料库」统计卡进列表 |
| — | Health 探活 | 企业 admin P2 | Wave 6+ |
| — | RAG 质量报告 drawer | 依赖 golden_qa 产品化 | 现有 RAG 占位区保留 |
| — | 顶栏 ⌘K / Plan-10 | kb plan 1.9 已 defer | §Plan-10 |
| — | Plan-3E bulk | 企业级加固 | 答辩前最多 3E-7 一条 |

---

## 依赖与并行说明

```
W0 KB-2.1 (kb plan) ──must──▶ W3 D-2
W1 DB-API ──must──▶ W2 D-1/D-4
W2 ──▶ W3 D-2/D-3
W3 + W0 ──▶ W4 Plan-11/2A
```

| 并行 OK | 禁止并行 |
|---------|----------|
| W1 DB-API ∥ 002-W5.3（不同目录） | 同对话改 `KnowledgeBaseDetailPage` 2.1 与 2.15 |
| W0 KB-2.1 ∥ W1（不同对话） | W3 D-2 在 W0 未验收时开工 |

**Explicit 不含**：本 plan **不 Implement** Wave 5.3/5.4 页面与 auth 改密逻辑、Plan-10 跨库 API、Plan-3E、⌘K 全局搜——见各 plan 边界。

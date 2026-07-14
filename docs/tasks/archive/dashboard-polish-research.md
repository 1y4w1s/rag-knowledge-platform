# dashboard-polish — Research

> **状态**：🟡 调研 stub（2026-07-04）· PM 评审团合议已确认实施顺序  
> **依据**：`DESIGN-5` v4.3.2、`PRD §5.2`、`docs/dashboard-content-v4.3.2-preview.html`、现有 `DashboardPage.tsx` / `GET /dashboard/stats`  
> **PM 评审**：见对话 [Dashboard×KB 顺序评审](0145a033-a306-4509-9913-5b39f07ac710) · 合议结论已写入 `dashboard-polish-plan.md` W0～W8  
> **边界**：本波不含 Wave 5.3/5.4 **Implement**（002-plan 自有）、Plan-10 跨库搜、Plan-3E bulk、顶栏 ⌘K、Health 探活、RAG drawer

---

## 1. 现状摘要（已实现）

| 域 | 已有 | 文件 |
|----|------|------|
| 统计 API | `knowledge_base_count`、`document_count`、`documents_by_status`、`total_chunk_count`、`member_count` | `backend/app/services/dashboard/stats.py` |
| 概览页壳 | Zone A 欢迎 + 双 CTA + 快捷提问 UI（disabled 空态） | `DashboardZoneA.tsx` |
| 四统计卡 | 资料库 / 已上传 / 已可提问 / 近 7 日提问 | `DashboardStatsGrid.tsx` |
| RAG 区 | 占位 metrics（非真 golden_qa） | `DashboardRagMetrics.tsx` / `mock-dashboard.ts` |
| 加载/错误 | skeleton + **系统红** err 条 | `DashboardPage.tsx` |
| KB 详情 `?status=` | 筛选条 + `DocumentFilterEmptyPanel`（1.6 ✅） | `KnowledgeBaseDetailPage.tsx` |
| KB P1-1 | 空库 + `?status=` 时 onboarding 与筛选空态**叠层** 🟡 | 同上 · Plan-11/2.1 |

---

## 2. Gap 对照（DESIGN-5 / PRD vs 代码）

### 2.1 Zone A · CTA 与快捷提问

| 要求（DESIGN-5 CTA 表） | 现状 | Gap |
|-------------------------|------|-----|
| 「上传文档」→ **最近库**详情 | 链到 `/knowledge-bases` 列表 | ❌ **D-1** |
| 「创建资料库」→ 列表或新建弹窗 | 链到列表，无弹窗 deep link | ❌ D-1 |
| 快捷提问 Enter → `/knowledge-bases/:recentId/chat?q=` | input 无 onSubmit / 路由 | ❌ **D-4** |
| 资料库 `<select>` 切换 recent | 无 select | 🟡 MVP 可省略，用 recent_kb_id 默认 |

### 2.2 Banner · 状态条

| 要求 | 现状 | Gap |
|------|------|-----|
| 整理中 / 失败 / 就绪 Banner | 无 Banner 组件 | ❌ **D-2** |
| 「去处理」→ 库详情 `?status=processing\|failed` | 1.6 详情已支持 query；Dashboard 未链出 | ❌ D-2 |
| 暖色 token + dismiss 就绪条 | token 在 KB 页已有；Dashboard 无 | ❌ D-2 + **D-7** |
| **前置** | P1-1：空库 + `?status=` UI bug | 🟡 **W0 KB-2.1 必须先修** |

### 2.3 Zone B · 统计卡

| 要求 | 现状 | Gap |
|------|------|-----|
| 四卡 + 可选环比 delta | 只展示数字，不可点 | ❌ **D-3** |
| 点「处理中/失败」语义跳转 | 无 | ❌ D-3 → 最近库 `?status=` 或列表 |

### 2.4 Zone B′ · 最近动态

| 要求 | 现状 | Gap |
|------|------|-----|
| `recent_activities[]` 最多 5 条 | API **无**字段 | ❌ **降级 D-5** |
| `length === 0` 不渲染 | 整区未实现 | 📋 答辩后 |

### 2.5 Zone D · 资料库条

| 要求 | 现状 | Gap |
|------|------|-----|
| Dashboard 底部 KB 卡条 | 未实现 | ❌ **降级 D-6**（与列表页重复） |
| 替代 | 点「资料库数」卡跳 `/knowledge-bases` | D-3 MVP 可覆盖 |

### 2.6 后端 API

| 字段/接口 | DESIGN-5 | 现状 | 建议 |
|-----------|----------|------|------|
| `recent_kb_id` | 🟡 Implement | **无** | W1 **DB-API**：按 `updated_at` 聚合取最近库 |
| `recent_activities[]` | 🟡 | **无** | W1 stub 返回 `[]`；D-5 后再填 |
| `chat_message_count` | 近 7 日提问 | 字段有，可能仍 0 | W1 接真表 COUNT（若 chat 表已有） |
| `GET /dashboard/health` | 企业 admin | **无** | 降级，不进本波 |
| `rag_evaluated_at` | RAG drawer | **无** | 降级 |

---

## 3. 与 kb-pages-polish 的衔接

| 链路 | KB 侧 | Dashboard 侧 | 依赖 |
|------|-------|--------------|------|
| Banner「去处理」 | 详情读 `?status=`（1.6） | D-2 外链带 query | **W0 2.1 修 P1-1** |
| 筛选 pill 视觉 | Plan-11/2.2 | D-2 Banner 同 token | W4 统一 |
| 错误文案 | Plan-11/2.7 | D-7 暖色 err | W2/W4 |
| 空态三步 | 1.6 ✅ | CTA 空态 disabled | D-1 fallback 列表 |

**硬门禁**：`kb-pages-polish-plan` **Plan-11/2.1 ✅** 之前，**禁止 Implement D-2**。

---

## 4. 与 002-plan 的分工

| 任务 | 归属 plan | 本 research |
|------|-----------|-------------|
| Wave 5.3 改密 | `002-plan.md` | 仅记录 W1 **并行**，不写 Implement |
| Wave 5.4 成员/组织 | `002-plan.md` | W5 |
| Wave 5.5 demo 脚本 | `002-plan.md` | W7 与 D-8 合并验收 |
| Dashboard 桥接 | **本 plan** W2～W3 | ✅ |

---

## 5. 最大风险

1. **D-2 先于 P1-1** — Banner 引到空库双 UI，答辩露馅 → W0 硬门禁。  
2. **`recent_kb_id` 无库** — D-1 上传 CTA 须 fallback 列表 + 新建弹窗。  
3. **scope creep** — Health / ⌘K / Plan-10 / 3E 易混入 → plan 头部 Explicit 边界。  
4. **双轨进度** — 5.3 被 Dashboard 挤掉 → cockpit 须 **002 主线 + Dashboard 增强** 双轨显示。

---

## 6. 建议波次（→ plan 路线图）

| 波次 | 内容 | 类型 |
|------|------|------|
| W0 | KB-2.1（Plan-11/2.1） | KB · 非本 plan Implement，但是 D-2 前置 |
| W1 | DB-API ∥ 002-W5.3 | 后端 + 002 并行 |
| W2 | D-1 + D-4 + D-7 | Dashboard 桥 MVP |
| W3 | D-2 + D-3 | Banner + 可点统计卡 |
| W4～W6 | Plan-11 2A/2B/2D + 002-W5.4 | 见 kb plan |
| W7 | D-8 + 002-W5.5 | 验收 |
| 降级 | D-5、D-6 | 答辩后 |

---

## 7. 测试基线

- `backend/tests/test_dashboard.py` — 现有 stats 权限/聚合用例  
- W1 后补：`recent_kb_id` 有库/无库/多库；`activities` 恒为 `[]`  
- 前端无单测；验收靠 `npm run build` + PRD §5.2 人工路径 + `demo_admin` / `demo_member`

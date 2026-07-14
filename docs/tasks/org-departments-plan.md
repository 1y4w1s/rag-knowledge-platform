# 组织与部门 · Implement Plan（L 窗）

> **状态**：✅ I 关 ORG-5.3 + V 关 ORG-5.4（2026-07-07）· 组织域 Implement + 预览关单  
> **依据**：`org-departments-prd.md` ORG-1-1～1-6 ✅ · `org-departments-research.md` H 企业级完整版 ✅  
> **并行**：`plan-3e-6-plan.md`（可观测）独立 I 窗；**ORG-3 后** 3E-6 须补 department scope 聚合（Plan-3E-6b）

---

## 0. 不做什么

- ❌ 多 unrelated 公司（一 login 多 org）
- ❌ 钉钉/AD 组织树同步
- ❌ 部门级计费 / 积分
- ❌ 库级 ACL 到个人
- ❌ MVP 部门 Admin 自管组织树 CRUD（P1 backlog）
- ❌ 拖拽移树（删建代替）
- ❌ 答辩/demo 专用捷径（须走 OrgScope）

---

## 1. 迁移与默认（Plan-0 · Implement 前）

| # | 任务 | 文件/动作 | 验收 |
|---|------|-----------|------|
| **0.1** | Alembic：`org_units` · `org_unit_members` · `knowledge_bases.org_unit_id` nullable · `kb_unit_grants` · closure/path 列 | `alembic/versions/016_org_units.py` | migrate head 绿 ✅ 2026-07-07 |
| **0.2** | 数据迁移：每 org 建 **根 unit**；现有 `owner_org_id` 库 → **`org_unit_id=null`（公司公共）** 或 plan 确认挂根 | migration data step | 现有 demo 库仍可读 ✅ 2026-07-07 |
| **0.3** | 新 invite 成员：`organization_members` 无 unit → **未分配**；Owner 注册 → 公司 Admin + 主部门=根或首个一级（**默认：根**） | seed + register 路径 | pytest 绿 ✅ 2026-07-07 |
| **0.4** | `resolve_org_context` → 支持主部门 + 兼任列表（`/me` 扩展） | `auth/org_context.py` · schema | `/me` 返回 `primary_unit_id` · `unit_ids[]` ✅ 2026-07-07 |

---

## 2. ORG-1 · 后端 OrgScope + 读隔离

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| **1.1** | `OrgScope` 服务：visible_kb_ids · writable_kb_ids · sql filter | `services/org/scope.py` 或扩 `workspace/scope.py` | 单元测试矩阵 ≥12 ✅ 2026-07-07 |
| **1.2** | `require_kb_access` + `_assert_kb_ownership` 接 unit/grant | `core/deps.py` | 兄弟部门 kb → 403 ✅ 2026-07-07 |
| **1.3** | `GET /knowledge-bases` scope | `knowledge_base/crud.py` · api | pytest 绿 ✅ 2026-07-07 |
| **1.4** | `GET /dashboard/stats` scope | `dashboard/stats.py` | stats ⊆ list ✅ 2026-07-07 |
| **1.5** | `GET /search/documents` scope | search service | C* pytest 扩展 ✅ 2026-07-07 |
| **1.6** | `POST chat` + retrieval enforce visible | `services/rag/*` · `api/chat.py` | 无泄密 pytest ✅ 2026-07-07 |
| **1.7** | messages / citation resolve 不可见 copy | 现有 EW-D3 扩展 | 撤 grant 用例 ✅ 2026-07-07 |
| **1.8** | query：`department_id` + fallback 主部门 + `all` Admin | api deps | E2/E3 PRD ✅ 2026-07-07 |
| **1.9** | CI：isolation 矩阵 job | `.github/workflows/ci.yml` | 绿 ✅ 2026-07-07 |

**ORG-1 DoD**：pytest 全绿 + 手工：研发 Member curl 市场 kb_id → 403。

---

## 3. ORG-2 · 组织与部门管理（Admin API + 页）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| **2.1** | CRUD API `org_units` | `api/org_units.py` · service | S1～S6 PRD ✅ 2026-07-07 |
| **2.2** | unit members API（add/remove/set primary/role） | `api/org_unit_members.py` | 主部门唯一 ✅ 2026-07-07 |
| **2.3** | 页面 `/organization/departments` 树+右栏 | `pages/OrgDepartmentsPage.tsx` 等 | Admin 浏览器建树 ✅ 2026-07-07 |
| **2.4** | 侧栏入口 + OrgAdminGuard | `AppSidebar.tsx` | Member 无入口 ✅ 2026-07-07 |
| **2.5** | 未分配 Banner + 业务 disabled | `DashboardPage` 等 | E6 PRD ✅ 2026-07-07 |
| **2.6** | audit：`org_unit.*` actions | audit events pytest | 绿 ✅ 2026-07-07 |

---

## 4. ORG-3 · 侧栏部门选择器 + 前端 scope

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| **3.1** | `DepartmentContext` + localStorage + generation | `lib/department-context.tsx` | ORG-1-2 S1～S5 ✅ 2026-07-07 |
| **3.2** | Popover 树组件 | `components/sidebar/DepartmentPicker.tsx` | 移动端 drawer ✅ 2026-07-07 |
| **3.3** | fetch 层统一 `department_id` | `dashboard-api` · `knowledge-base-api` · search | Network 齐 ✅ 2026-07-07 |
| **3.4** | 切部门 replace `/dashboard` | 与 workspace 联动 | E2 不乱详情 ✅ 2026-07-07 |
| **3.5** | **Plan-3E-6b**：Dashboard 运营指标接 OrgScope | `stats.py` + 前端 OpsMetrics | 3E-6 文档同步 ✅ 2026-07-07 |

---

## 5. ORG-4 · 资料库归属 + grant

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| **4.1** | 建库 Dialog 归属字段 | KB create UI + API | S1/S2 ✅ 2026-07-07 |
| **4.2** | `kb_unit_grants` CRUD API | `api/kb_grants.py` | S3/S4 ✅ 2026-07-07 |
| **4.3** | 库详情「共享」面板 | `KnowledgeBaseGrantsPanel.tsx` | grant/撤销 ✅ 2026-07-07 |
| **4.4** | OrgScope 合并 grant | `org/scope.py` | S3 对话命中 ✅ 2026-07-07 |
| **4.5** | pytest grant + 边界 E1～E8 | `test_org_grants.py` | 绿 ✅ 2026-07-07 |

---

## 6. ORG-5 · 硬验收 + 文档

| # | 任务 | 验收 |
|---|------|------|
| **5.1** | 全链路手工脚本（研发/市场/人事/grant） | 步骤表 15 步内 ✅ 2026-07-07 · [`ORG_DEPARTMENTS_ACCEPTANCE.md`](../ORG_DEPARTMENTS_ACCEPTANCE.md) |
| **5.2** | `TECH.md` TECH-5 矩阵更新 | 与 ORG-1-6 一致 ✅ 2026-07-07 |
| **5.3** | `cockpit.html` 组织域进度 | 与 plan 一致 ✅ 2026-07-07 |
| **5.4** | V 窗：`preview-org-departments.html` | P0 交互试玩 ✅ 2026-07-07 · ORG-1-2/1-3 S+E · grant · shell v2 |

---

## 7. 实施顺序（WIP=1）

```
Plan-0 → ORG-1.1～1.2（Scope 核心）→ ORG-1.3～1.8（链路）→ ORG-2 → ORG-3 → ORG-4 → ORG-5
```

**一次 I 窗只做 plan 一条**（例：仅 1.1+1.2 或仅 2.3）。

---

## 8. 大白话（Implement 前须听懂）

| 做完 ORG-1 | 浏览器里 |
|------------|----------|
| 后端 | 研发账号 **API 层** 就拿不到市场库数据，不是页面藏行 |
| 做完 ORG-2 | Admin 能画部门树、把人挂进研发部 |
| 做完 ORG-3 | 侧栏能切部门，概览数字跟着变 |
| 做完 ORG-4 | 人事能把「员工手册」共享给全公司 |
| 做完 ORG-5 | 文档/驾驶舱和 PRD 对齐，你能走一遍验收表 |

---

## 9. L 关 DoD

- [x] 用户确认本 plan（逐 Wave Implement 至 ORG-5.3 · 2026-07-07）
- [x] Implement 前 **门禁三题**能答（触发点 / 数据流 / 怎么验）
- [x] 与 `plan-3e-6-plan.md` 并行边界已读

**门禁三题（参考答案）**

1. **触发点**：侧栏选部门 · Admin 建树 · 建库选归属 · grant 面板  
2. **数据流**：请求带 `department_id` → OrgScope 算 visible_kb → SQL/SSE filter → 403 fail-closed  
3. **怎么验**：两部门两账号 + grant 用例 + pytest isolation job 绿

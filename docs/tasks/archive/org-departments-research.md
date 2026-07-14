# 组织部门树（一公司 · 多部门）— Research

> **状态**：✅ R 关（§1 + H 企业级完整版 · 2026-07-07）· P/L/I 关至 ORG-5.3 ✅  
> **触发**：产品目标定为「一个公司多个部门」；不以改动量砍 scope，以**最终页面效果**为准。  
> **会话类型**：R 窗 · **禁止 Implement**（PRD 新节确认前不写业务代码）  
> **并行**：Plan-3E-6 可观测与本文**不冲突**（3E-6 可继续 L/I）；部门树为 **Wave 7 / 组织域** 独立流水线。

---

## §1 目标终态 · 用户在浏览器里看见什么（✅ 用户确认 2026-07-07）

**这节定什么**：做完「公司 + 部门树」后，**页面长什么样**——不是表结构，是你打开产品能点的路径。

### 1.1 一句话

登录 **知岸科技** 的员工：侧栏仍是「我的空间 ↔ 公司」，但在**公司空间内**多一层 **「当前部门」**（可切「全公司 / 研发部 / 市场部 / …」）；资料库、概览统计、跨库搜索、对话**默认只在该部门可见范围内**；公司 Owner/Admin 可管组织树、给部门设管理员；部门 Admin 只管本部门库与成员；普通成员**看不到**未授权部门的 confidential 库。

### 1.2 侧栏与切换（终态 UX）

```
┌─ 知岸 ─────────────────┐
│ [ 我的空间 | 知岸科技 ] │  ← 现有 WS-2 segmented，不变
│ 当前部门 ▾  研发部      │  ← **新增**（仅在公司空间显示）
│ ─────────────────────  │
│ 概览                   │
│ 资料库                 │
│ …                      │
│ 组织与部门  （Admin）   │  ← **新增** 管树 + 部门成员
└────────────────────────┘
```

| 控件 | 谁看见 | 点了发生什么 |
|------|--------|--------------|
| segmented 我的空间/公司 | 所有人 | 与现 WS-2 一致；切公司 → `/dashboard` |
| **部门选择器** | 公司空间内所有人 | 切部门 → `/dashboard`；列表/统计/搜索 scope 变 |
| 「全公司」选项 | Owner · 公司 Admin | 看**有权限的**全部部门汇总（不是 member 默认项） |
| 「组织与部门」 | Owner · 公司 Admin | 组织树 CRUD、拖拽排序（P1 可先做列表+新建子部门） |

**Member 默认**：进公司空间 → 部门选择器锁在**所属部门**（不可选其他部门，除非兼任多部门）。

### 1.3 资料库与隔离（终态规则）

| 库类型 | 谁建 | 谁可见 | 举例 |
|--------|------|--------|------|
| **部门库** | 部门 Admin+ | 该部门成员 + 上级 Admin | 「研发部 · 接口规范」 |
| **公司公共库** | 公司 Admin+ | 全公司 Member | 「员工手册」「IT 政策」 |
| **个人库** | 本人 | 仅本人 | 现有 personal workspace |

**对话 / 检索**：在部门 scope 下提问，**只能**命中当前可见库；硬闯其他部门 `kb_id` → 403 + 前端回落。

### 1.4 角色（终态 · 比 today 多一层）

| 角色 | 范围 | 能做什么 |
|------|------|----------|
| **Owner** | 全公司 | 组织树、公司 Admin 任命、转让 Owner |
| **公司 Admin** | 全公司 | 建公司公共库、管任意部门、看全公司概览 |
| **部门 Admin** | 一个或多个部门 | 本部门建库/上传/删文档、加本部门成员 |
| **部门 Member** | 所属部门 | 读本部门库 + 公司公共库；对话；**不能**看兄弟部门库 |

> today 的 org `admin/member` 是**全公司扁平**角色；终态要 **拆成公司级 + 部门级** 两套（见 §3 H2）。

### 1.5 概览页差异（终态）

| scope | 统计卡数字 |
|-------|------------|
| 我的空间 | 不变 |
| 公司 · 全公司（Admin） | 全公司库/文档/失败数汇总 |
| 公司 · 研发部 | **仅研发部**库与文档；RAG/运营指标同 scope |

### 1.6 明确不做（本模块边界内）

- ❌ 多公司集团（一个登录横跨多个 unrelated org）— 仍是一公司一 `organization`
- ❌ 与钉钉/AD 自动同步组织树 — Wave 后期 / SSO 再议
- ❌ 部门级计费 — PRD §14

---

## §2 现状 gap（Research 事实 · Implement 前必读）

| 今天 | 终态需要 | 差距 |
|------|----------|------|
| `organizations` 扁平 | 部门树 `org_units` | **无表** |
| `knowledge_bases.owner_org_id` | + `org_unit_id` nullable（null=公司公共） | **无字段** |
| `organization_members` 全公司角色 | + `org_unit_members` 部门角色 | **无表** |
| `workspace=personal\|org_id` | + `department_id` query 或 path | **无参数** |
| `require_kb_access` 只验 org | 验 org + unit membership | **逻辑要改** |
| `resolve_org_context` 取一条 membership | 主部门 + 兼任列表 | **语义不足** |
| 侧栏 segmented 两段 | + 部门选择器 | **无 UI** |
| 跨库搜 EW-E1 | filter by visible units | **要改** |

**代码锚点**：`scope.py` · `deps.py` `_assert_kb_ownership` · `stats.py` · `AppSidebar` · `organization/members` 页。

---

## §3 架构假设（✅ 用户确认「企业级完整版」2026-07-07）

| 假设 | 定稿 |
|------|------|
| **H1** | 无限层 `org_units` + closure/物化路径 |
| **H2** | 公司 `organization_members` + 部门 `org_unit_members`（可兼任） |
| **H3** | API：`?workspace=&department_id=`；对内 **OrgScope 统一引擎** |
| **H4** | 缺参 → 主部门；Admin 显式 `all`；跨 unit kb **403** |
| **H5** | `kb_unit_grants` 跨部门共享（ORG-5） |

---

## §4 建议实施波次（不砍效果 · 仅排顺序）

> 完整 PRD 节 + plan 在 §1/H1～H4 确认后写；此处只列**终态能力**拆分。

| Wave | 交付（用户可验收） | 依赖 |
|------|-------------------|------|
| **ORG-1** | 表 + 后端 scope：`org_units`、KB 挂 unit、读隔离 pytest | — |
| **ORG-2** | 组织与部门管理页（Admin 建树、设部门 Admin） | ORG-1 |
| **ORG-3** | 侧栏部门选择器 + Dashboard/KB 列表 scope | ORG-1 |
| **ORG-4** | 跨库搜 / chat / citations 全链路 unit filter | ORG-1 |
| **ORG-5** | 兼任多部门 · 公司公共库 · **kb_unit_grants** · 全公司 Admin 概览 | ORG-2 |
| **ORG-6** | 预览 HTML + PRD 签章 + 乱操作表 | ORG-3 |

**与 3E-6**：可并行；Dashboard 运营指标在 ORG-3 后须 **按 department scope 重聚合**（plan 里写一条迁移任务即可）。

---

## §5 R 关 DoD

- [x] **§1 目标终态** 用户确认（2026-07-07）
- [x] **H1～H5 企业级完整版** 用户确认（2026-07-07）
- [x] §2 gap 能 3 句话口述（见 research §2）
- [x] **P 关** `org-departments-prd.md` ORG-1-1～1-6 ✅（2026-07-07）
- [x] **L 关** `org-departments-plan.md` ✅ · **I 关 ORG-5.3 ✅**（2026-07-07）

---

## §6 相关文档

- 现有工作区：`workspace-prd-ws2.md` · `workspace-research.md`
- 权限 today：`TECH.md` TECH-5 · `deps.py`
- 曾 defer：`002-plan.md` KB 级 ACL（Wave 2）→ 本模块** supersede** 为「部门 + 库归属」

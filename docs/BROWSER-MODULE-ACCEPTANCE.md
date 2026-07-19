# 知岸 · 浏览器模块验收清单

> **流程**：[`../../docs/process/BROWSER-ACCEPTANCE.md`](../../docs/process/BROWSER-ACCEPTANCE.md)  
> **定位**：**计划最后一关 BA-FINAL**（[`enterprise-master-plan.md` §9](tasks/enterprise-master-plan.md)）· 代码线 UX/功能做完后再 **WIP=1 全表勾**  
> **原则**：**一模块一条线验完再勾** · pytest/build 绿 ≠ 本表过关 · 勾 ✅ 时写日期  
> **环境**：Docker **`http://localhost/`** · 账号见 [`TEST_ACCOUNTS.md`](TEST_ACCOUNTS.md)

**图例**：⬜ 未验 · 🟡 部分验/有 UX gap · ✅ 你确认浏览器过关

---

## 0. 开测前（每轮扫一次）

- [ ] 三容器 up：`zhiku-api` · `zhiku-postgres` · `zhiku-web`
- [ ] `http://localhost:8000/health` → `database: ok`
- [ ] 浏览器打开 **`http://localhost/`**（不是 5173，除非你在 dev 模式）
- [ ] 侧栏选 **知岸演示公司**（团队空间）

---

## 模块表（按侧栏顺序）

| ID | 模块 | 路由 | 账号 | 最少验什么（S） | 乱操作（E） | 状态 |
|----|------|------|------|-----------------|-------------|------|
| **M1** | 登录 · 工作区 | `/login` → 侧栏 | admin | 登录进概览 · 切「我的空间↔团队」 | 错密 → 提示 · 非企业用户无团队 | ✅ 2026-07-09 |
| **M2** | 概览 | `/dashboard` | admin | 三格数字 · 运营指标 · 找文档 | 零库 Banner · 点统计卡跳转 | ✅ 2026-07-08 |
| **M3** | 资料库列表 | `/knowledge-bases` | admin | **分页** 24/页 · 搜索 · **切部门留本页** | `?page=999` 回落 · 空搜索 | ✅ 2026-07-09 |
| **M4** | 库详情 | `/knowledge-bases/:id` | admin | 文档表 · 筛选 · 上传 · 分页 | 空库+`?status=` 不叠 onboarding | ✅ |
| **M5** | 文档预览 | `…/documents/:docId` | admin | PDF/文本能看 · 引用进预览 | 整理中不可预览 · **源文档已删** 文案 | ✅ 2026-07-09 · md+pdf · chip→预览 |
| **M6** | 对话 · 引用 | `…/chat` | admin | 问 P1/P2 · **引用 chip** · 展开片段 | 无依据拒答 · 删 doc 后 chip 灰 | ✅ 2026-07-08 |
| **M7** | member 只读 | M3/M4/M6 | **member** | 无新建/删库 · 只读 hint | 硬闯管理 URL · **toast 一致（UX-4）** | ✅ 2026-07-09 · +新建灰/点 toast（hide 可选 gap） |
| **M8** | 组织 · 部门 | `/org/departments` | admin | 建树 · 改名 · 删空节点 | 建部门后 **picker 刷新（UX-6）** | ✅ 2026-07-09 |
| **M9** | 成员 · 团队设置 | `/members` · `/org/settings` | admin | 花名册 · 邀请码 · member 只读 | member 进 settings → 拦 | ✅ 2026-07-09 · 5173 |
| **M10** | 操作审计 | `/admin/audit` | admin / member | admin：分页 · 筛选 · member：**侧栏不可见** | 硬闯 `/admin/audit` | ✅ 2026-07-09 · member 无 toast 跳概览（可接受） |
| **M11** | 账号设置 | `/account` | admin | 改密 · 登出再登 | — | ✅ 2026-07-09 |
| **M12** | 组织隔离 · grant | 跨模块 | member | **ORG 15 步** 或 M11 **抽 A/B/C** | 市场库硬闯 · grant 撤销 | ✅ 15/15 2026-07-08 |

---

## 分模块操作卡（复制到验收时用）

### M3 · 资料库列表（当前建议优先补验）

| 步 | 操作 | 预期 |
|----|------|------|
| 1 | `demo_admin` · 团队空间 · 资料库 | 底部「第 1–24 条，共 N 个资料库」· Network `limit=24` |
| 2 | 点下一页 / 跳页 | URL `?page=2` · 卡片变 |
| 3 | 当前部门切「市场部」 | **仍在资料库页** · toast · 约 2 库 |
| 4 | 搜「模拟」 | 结果变 · 清除搜索恢复 |
| E1 | 地址栏 `?page=999` | 回到最后一页，非空态卡死 |

### M10 · 操作审计

| 步 | 操作 | 预期 |
|----|------|------|
| 1 | admin · 侧栏「操作审计」 | 表格 · 分页 |
| 2 | 筛 action / 时间 | 列表变 |
| 3 | `demo_member` 登录 | **无**审计菜单 · 硬闯 URL 被拦 |

### M7 · member 只读（UX-4 回归）

| 步 | 操作 | 预期 |
|----|------|------|
| 1 | `demo_member` · 资料库 | 无「+ 新建」· 有只读提示 |
| 2 | 硬闯 `/admin/audit` | toast / 跳走 |
| 3 | 列表/概览乱点写操作 | **中文 toast**（与详情一致） |

---

## 与现有脚本的关系

| 文档 | 何时用 |
|------|--------|
| 本文 **M1～M12** | **日常**：每原子任务 I 关 · 里程碑扫模块 |
| [`ORG_DEPARTMENTS_ACCEPTANCE.md`](ORG_DEPARTMENTS_ACCEPTANCE.md) | 清库后 / 大版本 · **全 15 步** |
| [`eval-M11-release-checklist.md`](tasks/eval-M11-release-checklist.md) §3 | **发版后** · health + demo + ORG 抽 3 步 |
| [`ENTERPRISE_DEMO_SCRIPT.md`](ENTERPRISE_DEMO_SCRIPT.md) | 答辩/demo 串联 · 非日常模块表 |

---

## 建议验收顺序（WIP=1 · 一次一模块）

```
M3 列表分页 → M10 审计 → M7 member → M8 组织 picker → M11 账号 → 其余补勾
```

每完成一模块：改上表 **状态** + `cockpit.html` §浏览器模块验收 + 对话回 **「Mx ✅」**。

---

## 面试 30 秒（模块验收版）

> 我们不只看 pytest——每个模块我有浏览器清单，例如资料库列表要亲手翻页、切部门看 toast，member 要试硬闯 URL。自动化保证逻辑，浏览器保证「用户真的能用」。

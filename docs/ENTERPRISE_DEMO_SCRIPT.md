# 知岸 — 企业双账号 15 分钟答辩 Demo 脚本

> **任务**：002-W5.5（`002-plan.md` Wave 5.5）· **R5-4** golden 对齐（`rag-optimization-plan.md`）  
> **版本**：v1.1  
> **状态**：✅ golden P1～P3 + AC-4 对齐（2026-07-07 · R5-4）  
> **用途**：毕业设计答辩现场操作稿；与 `docs/TEST_ACCOUNTS.md` 账号一致  
> **关联验收**：`dashboard-polish-plan.md` Plan-D8 · 对话题与引用期望 ↔ [`golden_qa.md`](golden_qa.md) · 浏览器抽检 ↔ [`RAG_PRODUCTION_BASELINE.md`](RAG_PRODUCTION_BASELINE.md) §5

---

## 1. 这脚本演示什么（30 秒电梯词）

**知岸**是企业知识库 RAG 系统：管理员上传文档、管理组织；成员只读使用、可对话查资料。核心亮点是 **AI 回答必须带引用**（文档名 + 位置），无依据不胡编；成员 **看不到也点不到** 写操作。

答辩主线（与 `002-plan.md` §7 成功指标对齐）：

```
admin 登录 → Dashboard 概览 → 组织/成员 → 建库上传 → 预览 → 对话引用
→ 退出 → member 登录 → 权限只读 → member 对话
```

---

## 2. 答辩前准备（不计入 15 分钟）

### 2.1 环境

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
  docker compose exec api alembic current   # 期望：010 (head)
```

另开终端：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run dev
```

| 检查项 | 地址 / 命令 | 期望 |
|--------|-------------|------|
| 前端 | http://localhost:5173/login | 登录页正常 |
| Demo 快捷登录 | `frontend/.env.development` 含 `VITE_SHOW_DEMO_LOGIN=true`（`npm run dev` 默认有） | 登录按钮下方出现「开发者 · 一键 demo 登录」；生产 `npm run build` 不显示 |
| API | http://localhost:8000/health | `database: ok` |
| DeepSeek Key | `.env` 已配置 | 对话能流式返回 |

### 2.2 演示账号（与种子脚本一致）

| 角色 | 用户名 | 邮箱 | 密码 | 组织 |
|------|--------|------|------|------|
| **管理员** | `demo_admin` | `demo-admin@example.com` | `password123` | 知岸演示公司 |
| **成员** | `demo_member` | `demo-member@example.com` | `password123` | 同上 |

账号缺失时重建：见 `docs/TEST_ACCOUNTS.md` §「账号不存在时重建」。

### 2.3 演示文档（答辩演示库 · 必传两份）

「**答辩演示库**」须同时入库以下两份 fixture（与 [`golden_qa.md`](golden_qa.md) / R5-3b 浏览器抽检一致）：

| 文件 | 路径 | 用途 |
|------|------|------|
| **MD 手册** | `backend/tests/fixtures/golden_handbook.md` | P1 / P2 / AC-4 中文章节引用（GQ-1、GQ-8） |
| **PDF 手册** | `backend/tests/fixtures/golden_handbook.pdf`（见下生成） | **P3** 英文页码引用（GQ-4 · 第 2 页） |

PDF 与 golden 测试同源（reportlab 两页小册）。若 fixtures 目录尚无 pdf，答辩前生成一次：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -c "from pathlib import Path; from tests.test_retrieval_golden import _make_golden_pdf; p=Path('tests/fixtures/golden_handbook.pdf'); _make_golden_pdf(p); print('OK', p.resolve())"
```

> **缺 PDF 会怎样**：P3「annual leave 10 days which page」无法演示 **PDF 页码 chip**（R5-3b 实测 chip#2 为 `golden_handbook.pdf · p.2`）。

#### 对话验收题（与 golden P1～P3 + AC-4 一致）

| Demo | golden | 答辩问题 | 期望回答要点 | 期望引用（点 chip 核对） |
|------|--------|----------|--------------|-------------------------|
| **P1** | GQ-1 | 年假有多少天？ | **10 天** | `golden_handbook.md · 1.1 年假` · 摘录含 `年假10天` |
| **P2** | GQ-8 | 迟到超过 30 分钟不会按旷工算吧？ | **会**按旷工半天（否定问法未误导） | `1.2 迟到` · 摘录含 `旷工` |
| **P3** | GQ-4 | annual leave 10 days which page | 英文答 · **第 2 页** | `golden_handbook.pdf · Chapter 1 Attendance · p.2` · 摘录含 `annual leave 10 days`（Top-1 偶为 MD 节时 **点 chip#2**） |
| **AC-4** | — | 公司上市计划是什么？ | 「未找到相关依据」类话术 | **无 citation** · 不吐虚假引用 |

时间充裕可加问（R5-3b 已绿，非 15min 主线）：GQ-11「餐补福利表里每月多少钱？」→ 300 元 · `2.2 餐补`；GQ-12「带薪年休假可以休多少天？」→ 10 天 · `1.1 年假`。

> **省时技巧**：答辩前 1 天用 `demo_admin` 建好「**答辩演示库**」并上传 **md + pdf**，状态均为「完成」。现场可跳过建库，直接从 **§3 步骤 5** 进库；若文档已删，现场再走步骤 6 上传。

### 2.4 改密（002-W5.3）说明

**15 分钟主线不含真实改密**（改密会强制退出，打断节奏）。改密能力已在 W5.3 单独验收；答辩时可 **口播**「账号设置支持旧密换新密，改后须重新登录」，或答辩后附录 **§6 可选：改密演示**。

---

## 3. 15 分钟操作脚本（主流程）

> **计时起点**：向评委说「开始演示」并打开登录页。  
> **角色切换**：步骤 10 前必须 **顶栏退出登录**，再登 `demo_member`。

| 步骤 | 时长 | 累计 | 账号 | 操作 | 口述要点（可脱稿） | 预期画面 / AC |
|------|------|------|------|------|-------------------|---------------|
| **1** | 1:00 | 1:00 | — | 打开 http://localhost:5173/login | 「这是知岸登录页，企业版支持组织与角色权限。」 | 登录 Tab |
| **2** | 1:30 | 2:30 | admin | 用户名 `demo_admin` / 密码 `password123` → 登录 | 「管理员登录后进入 **概览 Dashboard**，不是直接进资料库列表。」 | `/dashboard` · PRD §5.2 |
| **3** | 1:30 | 4:00 | admin | 指统计卡片：资料库数、文档数、处理中/失败、近 7 日对话；指组织名与成员数 | 「Dashboard 是管理员工作台：一眼看到入库进度和对话活跃度。」 | 数字与 API 一致 |
| **4** | 0:45 | 4:45 | admin | 侧栏 → **组织设置** | 「管理员可修改组织名称；MVP 不做解散组织。」 | `/organization/settings` · AC 组织可读可改 |
| **5** | 0:45 | 5:30 | admin | 侧栏 → **成员管理** | 「`demo_member` 已在组织中；答辩展示 admin 能看成员列表与角色。」 | 列表含 demo-member · AC-5 |
| **6** | 2:30 | 8:00 | admin | 侧栏 → **知识库** → **新建资料库**「答辩演示库」（若已有则跳过新建）→ 进入详情 → **上传** `golden_handbook.md` **与** `golden_handbook.pdf`（见 §2.3） | 「两份手册：中文 MD + 英文 PDF；上传后解析→切片→向量化。」 | 两篇文档 badge → `completed` · **AC-2** |
| **7** | 0:30 | 8:30 | admin | 若仍在处理：指状态点 / 等轮询刷新（最多约 1 分钟）；或答辩前预上传 | 「后台用 BackgroundTasks + pgvector，2G 云也能跑。」 | 两篇均 `completed` |
| **8** | 0:45 | 9:15 | admin | 文档表点 **PDF** 文件名 → **预览页** | 「PDF/MD 可内嵌预览；P3 页码演示依赖 PDF 已入库。」 | `/documents/:docId` · Wave 5.1 |
| **9** | 1:00 | 10:15 | admin | **开始对话** → **P1**：「年假有多少天？」 | 「RAG：hybrid 检索 + 流式生成；**回答下方有引用 chip**。」 | 答 **10 天** · chip `1.1 年假` · 摘录含 `年假10天` · **AC-3** |
| **10** | 0:30 | 10:45 | admin | 点 P1 引用 chip → 预览 | 「引用可点到原文，证明答案来自文档。」 | 预览页 · 摘录与 §2.3 P1 一致 |
| **11** | 0:45 | 11:30 | admin | **P2**：「迟到超过 30 分钟不会按旷工算吧？」 | 「**否定问法**也不误导：明确会按旷工。」 | chip `1.2 迟到` · 摘录含 `旷工` · 对齐 GQ-8 |
| **12** | 0:45 | 12:15 | admin | **P3**：「annual leave 10 days which page」 | 「**中英分离** + **PDF 页码**；英文问英文答。」 | chip 含 `golden_handbook.pdf` · **p.2** · 摘录含 `annual leave 10 days` · 对齐 GQ-4 |
| **13** | 0:45 | 13:00 | admin | **AC-4**：「公司上市计划是什么？」（手册无此内容） | 「无依据时明确说明未找到，**不吐虚假引用**。」 | 无 citation · **AC-4** |
| **14** | 0:15 | 13:15 | admin | 顶栏 **退出登录** | 「接下来换成员账号，看权限差异。」 | 回 `/login` |
| **15** | 1:45 | 15:00 | member | `demo_member` / `password123` 登录 → Dashboard → 知识库 → 进「答辩演示库」 | 「成员看到 **同一组织** 的资料库，但 **不能建库/删库/编辑**。」 | 列表 **成员只读提示** · **AC-6 UX** |
| **16** | （穿插 15） | — | member | Dashboard：无「创建资料库」，CTA「查看资料库」；侧栏 **无** 成员管理/组织设置 | 「写操作对 member **隐藏**；上传/编辑为灰钮 + Toast。」 | Plan-11/2C |
| **17** | （穿插 15） | — | member | 详情：上传/编辑灰钮点一下 → Toast；文档操作列 **仅预览** | 「删文档/重试 **不显示**，不是灰色误导。」 | 仅预览 |
| **18** | （可选 +1:00） | 16:00 | member | 侧栏 → **团队成员** 或 badge 进花名册 | 「成员可看队友名单（只读），不能发码/添加/移除。」 | 只读四列 · 无管理 UI |
| **19** | （可选 +1:00） | — | member | **开始对话** → 再问 **P1**「年假有多少天？」 | 「成员 **只读**，但对话与引用与 admin 一致。」 | 引用正常 · **AC-5** |

**主流程 15:00 停在步骤 15 结束**（含 P1～P3 + AC-4 四轮对话）；步骤 18～19 时间紧可口播跳过，或计入缓冲。

---

## 4. 管理员 vs 成员 — 关键路径对照

| 能力 | `demo_admin` | `demo_member` |
|------|--------------|---------------|
| 登录后进 Dashboard | ✅ 完整统计 + 写 CTA | ✅ 只读统计，CTA「查看资料库」 |
| 侧栏：成员管理 / 组织设置 | ✅ 可见 | ❌ 不可见（见「团队成员」只读花名册） |
| 直输 `/organization/members` | ✅ 管理模式 | ✅ **只读花名册**（2026-07-05 PRD H15） |
| 资料库：新建 / 编辑 / 删除 | ✅ | ❌ 无按钮 |
| 资料库列表只读提示 | — | ✅ 有提示条 |
| 详情：上传 / 编辑资料库 | ✅ | ⚪ 灰钮 + Toast |
| 文档：预览 | ✅ | ✅ |
| 文档：删除 / 失败重试 | ✅ | ❌ 操作列不显示 |
| 对话 + 引用 | ✅ | ✅ |
| 账号设置（改密） | ✅ | ✅（本 demo 主线不演示） |

---

## 5. 002-W5.5 验收对照

| 验收项 | 来源 | 本脚本覆盖步骤 |
|--------|------|----------------|
| 双账号 15 分钟 demo | `002-plan.md` 5.5 | §3 全流程，计时表 |
| 上传 → Dashboard 有数 → 预览 → 引用 | `002-plan.md` §7 | 3、6～12 |
| golden P1～P3 对话 + 引用 | `golden_qa.md` GQ-1/4/8 · `RAG_PRODUCTION_BASELINE.md` §5 | 9～12 |
| member 权限拒绝 / 只读 UX | `002-plan.md` §7 · AC-6 | 15～18 |
| 改密(5.3) → 成员/组织(5.4) → Dashboard → KB 对话 | `dashboard-polish-plan.md` D-8 | 4～5（改密见 §2.4 / §6） |
| 与 `TEST_ACCOUNTS.md` 一致 | 任务约束 | §2.2 账号表 |
| admin/member 关键路径 | Plan-11/2C 验收 | §4 对照表 |

---

## 6. 可选附录

### 6.1 改密演示（+2 分钟，单独验收 W5.3）

1. `demo_admin` → 侧栏 **账号设置**
2. 填写旧密码 `password123`、新密码 `password1234` → 保存
3. 自动跳转登录页 → 用新密码登录 → **改回** `password123`（避免下次 demo 踩坑）

### 6.2 Dashboard 快捷路径（+1 分钟）

- 概览页点 **「上传文档」** → 应进入 **最近活跃资料库** 详情（D-1）
- 快捷提问框输入「年假」回车 → 进对话且 URL 带 `?q=`（D-4）

### 6.3 资料库页加分项（时间充裕）

- 详情页 **文件名搜索** 输入「手册」→ 表过滤
- 筛选 pill 点「失败」→ 空库时仅筛选空态（Plan-11/2.1）

---

## 7. 故障与降级

| 现象 | 处理 |
|------|------|
| 登录 401 | 清 Local Storage `zhian_access_token` / `zhian_user` 后重登 |
| 上传后一直 processing | 查 `docker compose logs api`；确认 `.env` 嵌入/LLM Key；答辩用 **预上传完成** 的库 |
| 对话无流式 / 报错 | 查 DeepSeek Key；错态应为 **暖色 AlertBanner**（非系统红） |
| 成员看不到资料库 | 重跑 `seed_enterprise_demo.py`；确认两账号同一组织 |
| 改密后 demo 账号进不去 | 用 §6.1 改回 `password123` 或重跑种子（仅重置 member/admin 用户时） |

---

## 8. D-8 试跑记录

### 8.1 ① 15 分钟计时说明（回归参考 · 不阻塞 Wave 6 关单）

| 项 | 说明 |
|----|------|
| **计什么** | 从向评委说「开始演示」并打开登录页起，按 **§3 步骤 1～15** 表内「累计」列跑完 **member 进同一答辩演示库**（含 P1～P3 + AC-4 四轮对话） |
| **不计什么** | **§2 答辩前准备**（docker / npm / 预上传 md+pdf）· **§6 可选附录**（改密、Dashboard 快捷路径）· 步骤 18～19 |
| **②③④ 状态** | **✅ 2026-07-07 用户亲手**：预上传 md+pdf · P1 引用 · member 切换 · AC-4 无依据拒答（见下行试跑表） |
| **① 你还须做** | **脱稿 + 口述** 跑一遍 **1～15**，用秒表/手机计时，在 **§8.2 表** 填一行「实际耗时 / 是否 ≤15:00」 |
| **通过标准** | 累计 ≤ **15:00** 且步骤 9～13 引用现象与 **§2.3** P1～P3、AC-4 一致；超时则压缩步骤 4～5 口述或步骤 8 预览，**勿删 P1～P3** |
| **与 R5-4 关系** | 本文 v1.1 已对齐 `golden_qa.md`；① 只验证「15 分钟内讲得完」，不改变 golden 期望 |

### 8.2 试跑记录表（答辩前填一行）

| 日期 | 试跑人 | 实际耗时 | 是否 15 分钟内 | 备注 |
|------|--------|----------|----------------|------|
| 2026-07-05 | AI 代码对照 | — | 待你亲手跑 | **Gap（已修）**：成员只读花名册 · 发码 · 所有者标签 · alembic head · focus 刷新 |
| 2026-07-05 | AI 自动化+路径抽检 | — | 🟡 ① 计时待跑 | **自动化 ✅** · **路径抽检 ✅** · ②③④ 当时待补 |
| 2026-07-07 | 用户亲手 | — | 🟡 ① 计时待跑 | **② 预上传 ✅**（md+pdf）· **P1 ✅** · **member ✅** · **AC-4 ✅** · api 重建修障 · **🟡 仅剩 ①** |
| 2026-07-07 | R5-4 文档对齐 | — | 🟡 ① 计时待跑 | **脚本 v1.1**：§2.3 必传 md+pdf · §3 步骤 9～12 = **P1～P3** + 步骤 13 **AC-4** · 与 `golden_qa` / `RAG_PRODUCTION_BASELINE` §5 一致 · **① 仍须亲手计时一行** |

> **D-8 试跑**：②③④ 已 ✅；**15 分钟计时 ①** 仍须你按 §8.1 跑完填 §8.2 最后一列耗时后再改 cockpit「① ✅」。

---

## 9. 相关文档

- 测试账号：`docs/TEST_ACCOUNTS.md`
- 验收集 / 答辩 P1～P3：`docs/golden_qa.md` · 浏览器抽检：`docs/RAG_PRODUCTION_BASELINE.md` §5
- 页面行为：`docs/PRD.md` §5.2～5.9
- 开发清单：`docs/tasks/002-plan.md` Wave 5.5
- Dashboard 合并验收：`docs/tasks/dashboard-polish-plan.md` Plan-D8

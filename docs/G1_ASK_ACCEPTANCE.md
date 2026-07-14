# 知岸 — 工作区对话 `/ask` · 手工验收表

> **任务**：G1-5.3（`docs/tasks/discovery-smart-chat-plan.md` Wave 5）  
> **版本**：v1.0  
> **状态**：✅ 脚本就绪（2026-07-09）  
> **用途**：浏览器跟着点，验收 **侧栏「对话」→ `/ask`** 跨库问答；与 `discovery-smart-chat-prd.md` **G-1-5** S/E 对齐  
> **账号**：与 [`TEST_ACCOUNTS.md`](TEST_ACCOUNTS.md) 一致（`demo_admin` · `demo_member`）

---

## 1. 这表验收什么（30 秒）

侧栏点 **「对话」** 进 **`/ask`**，不用先选资料库；系统在 **当前空间 + 当前部门可见的全部库** 里一起搜，流式回答；引用 chip **库名在前**；刷新页面 **历史还在**。库详情 **「开始对话」** 仍是 **单库** chat，chip **不带库名**。

**主线**：工作区对话 → 多库 chip → 概览跳转发问 → 库内单库对比 → 组织隔离与 grant。

---

## 2. 验收前准备（不计入勾选）

### 2.1 环境

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
docker compose exec api alembic current   # 期望：017 (head)
```

另开终端（dev 模式）：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run dev
```

| 检查项 | 地址 | 期望 |
|--------|------|------|
| 前端 | http://localhost:5173/login | 登录页正常 |
| API | http://localhost:8000/health | `database: ok` |
| DeepSeek Key | 项目 `.env` 已配置 | 对话能流式返回 |

### 2.2 演示账号

| 角色 | 用户名 | 密码 | 组织 |
|------|--------|------|------|
| **公司 Admin** | `demo_admin` | `password123` | 知岸演示公司 |
| **研发 Member** | `demo_member` | `password123` | 主部门研发部 |

### 2.3 数据前置（二选一）

**推荐 A**：已跑过 [`ORG_DEPARTMENTS_ACCEPTANCE.md`](ORG_DEPARTMENTS_ACCEPTANCE.md) **15 步** — 含「员工手册（人事）」+ grant 全公司 + `golden_handbook.md`。

**最小 B**（未跑 ORG 时）：

1. `demo_admin` · 团队 · 建库「答辩演示库」· 上传 `backend/tests/fixtures/golden_handbook.md`  
2. 侧栏 **对话** 能问「年假有多少天？」并出 chip  

### 2.4 pytest 基线（开工前 1 分钟 · A 层）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_ask_chat.py tests/test_retrieval_golden.py -q
```

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run build
```

期望：`test_ask_chat` + golden **12/12** 绿 · `npm run build` 绿。

---

## 3. 正常用例 S（主流程 · 可勾选）

> **用法**：做完一步勾一步；全部 ✅ = G1-5.3 S 关通过。

### S · 工作区对话主线

- [ ] **S1** · `demo_admin` · 团队空间 · 侧栏点 **「对话」** → 地址栏 `/ask` · 页头 **不强调单一库名**
- [ ] **S2** · 同页输入 **「年假有多少天？」** → **流式出字** · 下方 chip 格式 **库名 · 文档 · 章节** · 回答或引用含 **「10」**
- [ ] **S3** · 点任一 chip → 跳进 **该库** 文档预览（与库内对话一致）
- [ ] **S4** · **刷新** `/ask` → **历史消息仍在**（含 chip）
- [ ] **S5** · 侧栏 **概览** → 输入框提问回车 → 跳转 **`/ask?q=…`** 并 **自动发问**
- [ ] **S6** · 进任一库详情 → **开始对话** → 单库 chat 页 · chip **无库名前缀**（仅文档/章节）
- [ ] **S7** · `demo_member` 登录 · 团队 · **当前部门 = 研发部** · 侧栏 **对话** → 问员工手册内容 → **有引用** · **无**「薪酬保密库」chip
- [ ] **S8** · 侧栏切 **我的空间**（个人）· **对话** → 仅 **个人库** 内容可命中（团队独有库搜不到）

**S 全勾 = 8/8**

---

## 4. 乱操作 / 边界 E（可勾选）

> 可与 §3 穿插测；不必按序号。

- [ ] **E1** · 个人空间 · 侧栏对话问 **仅团队库才有** 的内容 → **拒答**（AC-4 风格）
- [ ] **E4** · 地址栏硬闯 `/knowledge-bases/{错库id}/chat` → **仍只搜该库** 或 403（与现网库内 chat 一致）
- [ ] **E5** · 工作区对话问 **完全无关** 问题 → **拒答** · 无胡编引用
- [ ] **E7** · 多库均有依据时（如 ORG 场景多库有文档）→ 回答下 **多条 chip** · **库名可不同**
- [ ] **E14** · 完成 S2 后 · `demo_admin` **撤销** 员工手册 grant · `demo_member` 刷新 `/ask` → 旧消息里该 chip **灰态 / 来源不可用**
- [ ] **E17** · **未分配** Member（`unit_ids=[]`）硬闯 `/ask` → **禁用提问** 或跳概览 · 见 **未分配 Banner**

**E 建议至少勾 E1 · E5 · E14 · E17 四条**

---

## 5. 自动化门槛 A（AI 已跑 · 你确认绿即可）

| # | 项 | 命令 | 期望 | 勾选 |
|---|-----|------|------|------|
| **A1** | 跨库 scope pytest | `pytest tests/test_ask_chat.py tests/test_retrieval_workspace.py -q` | 绿 | - [ ] |
| **A2** | golden 回归 | `pytest tests/test_retrieval_golden.py -q` | **12/12** | - [ ] |
| **A3** | 前端构建 | `cd frontend; npm run build` | 绿 | - [ ] |

---

## 6. PRD G-1-5 对照

| PRD | 本表 |
|-----|------|
| S1～S4 | §3 S1～S2 · S7～S8 |
| S5 | §3 S5 |
| S6 | §3 S6 |
| S7 | §3 S3 |
| E1 · E5 | §4 |
| E7 | §4 E7 |
| E14 | §4 E14 |
| E17 | §4 E17 |
| E4 | §4 E4 |
| A1～A3 | §5 |

---

## 7. G1-5.3 退出 DoD

| # | 条件 | 本表 |
|---|------|------|
| G5-3-1 | S 表 **可勾选** · 含 `/ask` 主路径 | §3 |
| G5-3-2 | E 表覆盖 PRD G-1-5 边界 | §4 |
| G5-3-3 | A 层命令与 plan §3 一致 | §5 |
| G5-3-4 | 试跑记录可填 | §8 |

---

## 8. 试跑记录（请你亲手跑完再填）

| 项 | 值 |
|----|-----|
| 日期 | |
| 执行人 | |
| 环境 | localhost Docker + `npm run dev` / `http://localhost/` |
| alembic | |
| ORG 15 步已跑 | ⬜ 是 · ⬜ 否（用最小 B） |
| S 通过数 | /8 |
| E 通过数 | /6（或注明「仅测 E1/E5/E14/E17」） |
| A 层 | ⬜ pytest 绿 · ⬜ build 绿 |
| 失败项 # | |
| 备注 | |

---

## 9. 关联文档

- PRD：`docs/tasks/discovery-smart-chat-prd.md` G-1-5  
- Plan：`docs/tasks/discovery-smart-chat-plan.md` G1-5.3  
- TECH：`docs/TECH.md` §3.5.2 · §5.7  
- 组织域前置：`docs/ORG_DEPARTMENTS_ACCEPTANCE.md`  
- 全模块 BA-FINAL：`docs/BROWSER-MODULE-ACCEPTANCE.md` M6/M12  
- 进度：`docs/previews-gallery.html` G-1 · G1-5.3
